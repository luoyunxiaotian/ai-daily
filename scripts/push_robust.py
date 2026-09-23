#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub 健壮推送脚本 —— 多路径自动回退

背景（2026-09-23 实测得出）：
  WorkBuddy 沙箱会注入 http_proxy/https_proxy=http://127.0.0.1:<port>，
  git 默认读取该环境变量。该代理不稳定，表现为：
    - "Failed to connect to github.com:443 after 21xxx ms"
    - "CONNECT tunnel failed, response 502"
  两条路都可能间歇性失败，因此需要多路径重试。

回退顺序：
  路径1  直连           —— 清空 *_proxy 环境变量
  路径2  沙箱代理       —— 沿用环境里已有的代理
  路径3  S302 反代      —— 启动 Steamcommunity_302 CLI，靠 hosts 劫持 + 本地 Caddy 转发；
                           git 必须清空 *_proxy 才会走 hosts（否则代理会绕过劫持）
  路径4  SSH            —— git@github.com

安全约束：
  - S302 退出后 hosts 劫持会残留（github.com -> 127.0.0.1），会导致后续断网。
    本脚本在 finally 中强制恢复 hosts 备份。
  - 不打印任何 token（输出统一脱敏）。

用法：
  python push_robust.py [--repo <path>] [--remote origin] [--branch main] [--tries N]
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

HOSTS = r"C:\Windows\System32\drivers\etc\hosts"
S302_DIR = r"D:\Tool\Steamcommunity_302"
S302_CLI = os.path.join(S302_DIR, "steamcommunity_302.cli.exe")

PROXY_KEYS = [
    "http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
    "all_proxy", "ALL_PROXY", "ftp_proxy", "FTP_PROXY",
]


def log(msg):
    print(msg, flush=True)


def sanitize(text, token=None):
    if token:
        text = text.replace(token, "***")
    return text


def run(cmd, env, cwd, timeout=180):
    """返回 (rc, combined_output)"""
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, timeout=timeout,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           shell=False)
        out = p.stdout.decode("utf-8", "replace")
        return p.returncode, out
    except subprocess.TimeoutExpired:
        return 124, "[TIMEOUT after %ss]" % timeout
    except Exception as e:  # noqa
        return 127, "[EXC] %r" % e


def base_env():
    return os.environ.copy()


def env_no_proxy():
    e = base_env()
    for k in PROXY_KEYS:
        e.pop(k, None)
    e["GIT_TERMINAL_PROMPT"] = "0"
    return e


def env_with_proxy():
    e = base_env()
    e["GIT_TERMINAL_PROMPT"] = "0"
    return e


def get_token():
    """从 git credential-manager 取 token，失败返回 None"""
    try:
        p = subprocess.run(["git", "credential-manager", "get"],
                           input=b"protocol=https\nhost=github.com\n\n",
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=60)
        out = p.stdout.decode("utf-8", "replace")
        for line in out.splitlines():
            if line.lower().startswith("password="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return None


def backup_hosts():
    bak = HOSTS + ".bak.pushrobust"
    try:
        shutil.copyfile(HOSTS, bak)
        return bak
    except Exception as e:
        log("  [warn] hosts 备份失败: %r" % e)
        return None


def restore_hosts(bak):
    if not bak or not os.path.exists(bak):
        return
    try:
        shutil.copyfile(bak, HOSTS)
        os.remove(bak)
        log("  [cleanup] hosts 已恢复，备份文件已删除")
    except Exception as e:
        log("  [warn] hosts 恢复失败: %r" % e)


def has_s302_residue():
    try:
        with open(HOSTS, "r", encoding="utf-8", errors="ignore") as f:
            return "#S302" in f.read()
    except Exception:
        return False


def try_paths(repo, remote, branch, tries, token):
    """依次尝试各路径，成功返回路径名"""
    push_url = "https://github.com/luoyunxiaotian/ai-daily.git"
    attempts = []

    # 路径1 / 路径2 交替重试
    for i in range(tries):
        attempts.append(("直连(绕过代理)", ["git", "push", remote, branch], env_no_proxy()))
        attempts.append(("沙箱代理", ["git", "push", remote, branch], env_with_proxy()))
        if token:
            url = "https://x-access-token:%s@github.com/luoyunxiaotian/ai-daily.git" % token
            e = env_no_proxy()
            attempts.append(("直连+token", ["git", "push", url, branch], e))

    # 路径4 SSH（仅当未完全失败时最后兜底）
    attempts.append(("SSH", ["git", "push", "git@github.com:luoyunxiaotian/ai-daily.git", branch],
                     env_no_proxy()))

    for name, cmd, env in attempts:
        # 先确认远端已有该分支的最新状态是否需要推
        rc, out = run(["git", "status", "-sb"], env_with_proxy(), repo, timeout=60)
        if rc == 0 and ("ahead" not in out):
            log("[skip] 本地无领先提交，无需推送")
            return "UP_TO_DATE"

        log("[try] %s ..." % name)
        rc, out = run(cmd, env, repo)
        out = sanitize(out, token)
        if rc == 0:
            log("  [OK] %s 推送成功" % name)
            if out.strip():
                log("  " + out.strip().replace("\n", "\n  ")[:800])
            return name
        else:
            log("  [fail] rc=%s :: %s" % (rc, out.strip().replace("\n", " | ")[:300]))

    return None


def try_s302(repo, remote, branch, token):
    """启动 S302 CLI 后走 hosts 劫持反代。注意：进程在本环境无法长期常驻，
    仅在同一次调用窗口内有效；结束后必须恢复 hosts。"""
    if not os.path.exists(S302_CLI):
        log("[S302] 未找到 CLI，跳过")
        return None
    if has_s302_residue():
        log("[S302] 检测到 hosts 已有劫持残留，跳过启动以免叠加")
        return None

    bak = backup_hosts()
    proc = None
    try:
        log("[S302] 启动 CLI ...")
        proc = subprocess.Popen([S302_CLI], cwd=S302_DIR,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(22)  # 等待 caddy 起来 + hosts 写入 + 证书安装

        if proc.poll() is not None:
            log("[S302] 主进程已退出（rc=%s），仍尝试（Caddy 子进程可能存活）" % proc.returncode)
        else:
            log("[S302] 主进程存活 pid=%s" % proc.pid)

        env = env_no_proxy()
        cmd = ["git", "push", remote, branch]
        log("[S302] 尝试推送（清空 *_proxy 以让 hosts 劫持生效）...")
        rc, out = run(cmd, env, repo, timeout=180)
        out = sanitize(out, token)
        if rc == 0:
            log("  [OK] S302 反代推送成功")
            return "S302"
        log("  [fail] rc=%s :: %s" % (rc, out.strip().replace("\n", " | ")[:300]))
        return None
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
        restore_hosts(bak)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--tries", type=int, default=2)
    args = ap.parse_args()

    log("=== 健壮推送 · repo=%s branch=%s ===" % (args.repo, args.branch))

    token = get_token()
    if token:
        log("凭据: 已获取 (长度 %d，输出已脱敏)" % len(token))
    else:
        log("凭据: 未获取到，依赖 credential helper")

    ok = try_paths(args.repo, args.remote, args.branch, args.tries, token)
    if ok:
        log("\n=== 推送完成，路径: %s ===" % ok)
        return 0

    log("\n=== 常规路径全部失败，尝试 S302 反代 ===")
    ok = try_s302(args.repo, args.remote, args.branch, token)
    if ok:
        log("\n=== 推送完成，路径: %s ===" % ok)
        return 0

    log("\n=== 全部路径失败 ===\n建议：本地提交已保留，待网络恢复后重跑本脚本，"
        "或在 GUI 中常驻运行 Steamcommunity_302.exe 后再试。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
