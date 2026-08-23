#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 日报站点构建脚本
--------------------------------------------------
从上级工作区目录读取 AI日报_YYYY-MM-DD.md / .html，
拷贝进 public/ 与 md/，并重建深色卡片风格索引首页 public/index.html。

用法：
    python scripts/build.py              # 从默认源目录（仓库上一级）构建
    python scripts/build.py --src <dir>  # 指定日报源目录
"""
import argparse
import datetime
import html
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "public")
MDDIR = os.path.join(ROOT, "md")

WD = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# ---------------------------------------------------------------- 元信息提取

TITLE_PATTERNS = [
    re.compile(r"^###\s+(\d{1,2})\.\s+(.+?)\s*$"),          # ### 1. xxx
    re.compile(r"^\*\*(\d{1,2})\.\s+(.+?)\*\*\s*$"),         # **1. xxx**
]

CLEAN = [
    (re.compile(r"\*\*(.+?)\*\*"), r"\1"),
    (re.compile(r"`(.+?)`"), r"\1"),
    (re.compile(r"\[(.+?)\]\(.+?\)"), r"\1"),
    (re.compile(r"【本版最重要新增】|【最重要】"), ""),
]


def clean_text(s):
    for pat, rep in CLEAN:
        s = pat.sub(rep, s)
    return s.strip(" 　—-·")


def extract_meta(md_path):
    """从日报 markdown 中提取索引所需的元信息。"""
    with open(md_path, encoding="utf-8") as fh:
        text = fh.read()

    meta = {"deepseek": None, "highlights": [], "counts": {}}

    # DeepSeek 有无：优先认「今日有 D」，其次「今日无D」
    if re.search(r"今日有\s?D", text):
        meta["deepseek"] = True
    elif re.search(r"今日无\s?D", text):
        meta["deepseek"] = False

    # 精选条目标题（取前 3 条）
    seen = set()
    for line in text.splitlines():
        for pat in TITLE_PATTERNS:
            m = pat.match(line.strip())
            if not m:
                continue
            idx, title = m.group(1), clean_text(m.group(2))
            if idx in seen or not title:
                continue
            seen.add(idx)
            meta["highlights"].append(title)
            break
        if len(meta["highlights"]) >= 3:
            break

    # 规模统计
    meta["counts"]["chars"] = len(text)
    meta["counts"]["items"] = len(re.findall(r"^(?:###\s+\d{1,2}\.|\*\*\d{1,2}\.\s)", text, re.M))
    meta["counts"]["tables"] = text.count("\n|---") + text.count("\n|--:") + text.count("\n|:--")
    meta["has_community"] = bool(re.search(r"社区(?:信源|快讯)", text))
    meta["has_pvp"] = "Price vs Performance" in text
    meta["has_github"] = bool(re.search(r"GitHub\s*(?:热门|趋势)", text))
    return meta


def collect(src):
    """扫描源目录，返回按日期倒序的日报列表。"""
    days = {}
    for name in os.listdir(src):
        m = re.match(r"^AI日报_(\d{4}-\d{2}-\d{2})\.(md|html)$", name)
        if not m:
            continue
        date, ext = m.group(1), m.group(2)
        days.setdefault(date, {})[ext] = os.path.join(src, name)

    out = []
    for date in sorted(days, reverse=True):
        pair = days[date]
        if "html" not in pair:
            print("  ! 跳过 %s：缺少 html" % date)
            continue
        rec = {"date": date, "html": pair["html"], "md": pair.get("md")}
        d = datetime.date.fromisoformat(date)
        rec["weekday"] = WD[d.weekday()]
        rec["meta"] = extract_meta(pair["md"]) if pair.get("md") else {
            "deepseek": None, "highlights": [], "counts": {}}
        rec["size_kb"] = round(os.path.getsize(pair["html"]) / 1024, 1)
        out.append(rec)
    return out


# ---------------------------------------------------------------- 首页渲染

CSS = """
:root{--bg:#0d1117;--panel:#161b22;--panel2:#1c2330;--border:#2a3340;
  --txt:#e6edf3;--muted:#9da7b3;--accent:#58a6ff;--green:#3fb950;
  --yellow:#e3b341;--red:#f85149;--purple:#bc8cff;--cyan:#39c5cf}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--txt);line-height:1.65;padding:32px 24px 48px;
  font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;max-width:1180px;margin:0 auto}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
header{border-bottom:1px solid var(--border);padding-bottom:20px;margin-bottom:26px}
h1{font-size:30px;letter-spacing:.5px}
.tagline{color:var(--muted);font-size:14px;margin-top:8px}
.stats{display:flex;gap:12px;flex-wrap:wrap;margin-top:18px}
.stat{background:var(--panel);border:1px solid var(--border);border-radius:10px;
  padding:10px 16px;min-width:104px}
.stat .n{font-size:22px;font-weight:700;color:var(--accent);line-height:1.2}
.stat .l{font-size:11.5px;color:var(--muted);margin-top:2px}
h2{font-size:19px;margin:34px 0 14px;color:var(--accent);
  border-bottom:1px solid var(--border);padding-bottom:8px}
.hero{background:linear-gradient(135deg,rgba(88,166,255,.12),rgba(57,197,207,.04));
  border:1px solid var(--accent);border-radius:14px;padding:20px 22px}
.hero .hd{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.hero .date{font-size:24px;font-weight:700}
.hero .wd{color:var(--muted);font-size:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:12px;
  padding:16px 18px;transition:border-color .16s,transform .16s}
.card:hover{border-color:var(--accent);transform:translateY(-2px)}
.card .hd{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.card .date{font-size:17px;font-weight:700}
.card .wd{color:var(--muted);font-size:12.5px}
ul.hl{list-style:none;margin:10px 0 0}
ul.hl li{font-size:12.8px;color:#c3ccd6;margin:6px 0;padding-left:16px;position:relative;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
ul.hl li:before{content:"▍";position:absolute;left:0;color:var(--accent);font-size:11px}
.tag{display:inline-block;font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600;
  border:1px solid transparent;white-space:nowrap}
.t-has{background:rgba(57,197,207,.15);color:var(--cyan);border-color:var(--cyan)}
.t-no{background:rgba(157,167,179,.12);color:var(--muted);border-color:var(--border)}
.t-feat{background:rgba(188,140,255,.13);color:var(--purple);border-color:var(--purple)}
.links{margin-top:14px;padding-top:12px;border-top:1px solid var(--border);
  display:flex;gap:14px;font-size:12.5px;align-items:center}
.links .kb{margin-left:auto;color:var(--muted);font-size:11.5px}
.note{background:var(--panel);border-left:3px solid var(--accent);border-radius:0 8px 8px 0;
  padding:12px 16px;margin:16px 0;font-size:13px;color:#c3ccd6}
.note p{margin:4px 0}
code{background:var(--panel2);padding:1px 5px;border-radius:4px;font-size:12px;color:var(--yellow)}
footer{color:var(--muted);font-size:12px;margin-top:44px;text-align:center;
  border-top:1px solid var(--border);padding-top:18px}
@media(max-width:640px){body{padding:20px 14px 36px}h1{font-size:24px}.grid{grid-template-columns:1fr}}
"""


def ds_tag(flag):
    if flag is True:
        return '<span class="tag t-has">今日有 D ✅</span>'
    if flag is False:
        return '<span class="tag t-no">今日无 D</span>'
    return ""


def feat_tags(meta):
    out = []
    if meta.get("has_community"):
        out.append('<span class="tag t-feat">社区信源</span>')
    if meta.get("has_pvp"):
        out.append('<span class="tag t-feat">性价比表</span>')
    return "".join(out)


def render_hl(meta):
    hl = meta.get("highlights") or []
    if not hl:
        return ""
    lis = "".join("<li>%s</li>" % html.escape(t) for t in hl)
    return '<ul class="hl">%s</ul>' % lis


def render_links(rec, hero=False):
    date = rec["date"]
    md = ('<a href="../md/%s.md">Markdown 源</a>' % date) if rec["md"] else ""
    label = "阅读今日日报 →" if hero else "阅读全文 →"
    return ('<div class="links"><a href="%s.html"><strong>%s</strong></a>%s'
            '<span class="kb">%s KB</span></div>' % (date, label, md, rec["size_kb"]))


def build_index(days, out_path):
    total_items = sum(d["meta"]["counts"].get("items", 0) for d in days)
    latest = days[0] if days else None
    span = "%s ~ %s" % (days[-1]["date"], days[0]["date"]) if days else "—"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    p = []
    p.append('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">')
    p.append('<meta name="viewport" content="width=device-width,initial-scale=1.0">')
    p.append('<title>AI 日报 · 每日 AI Coding 与具身智能动态</title>')
    p.append('<meta name="description" content="每日追踪 AI Coding 与具身智能领域动态，'
             '含社区一手信源验证、DeepSeek 专项、三口径模型能力评分与价格表。">')
    p.append('<style>%s</style>\n</head>\n<body>' % CSS)

    p.append('<header>')
    p.append('<h1>🤖 AI 日报</h1>')
    p.append('<p class="tagline">每日追踪 <strong>AI Coding</strong> 与 <strong>具身智能</strong>'
             ' · 社区一手信源交叉验证 · DeepSeek 专项 · 三口径能力评分与价格表</p>')
    p.append('<div class="stats">')
    p.append('<div class="stat"><div class="n">%d</div><div class="l">已发期数</div></div>' % len(days))
    p.append('<div class="stat"><div class="n">%d</div><div class="l">累计条目</div></div>' % total_items)
    p.append('<div class="stat"><div class="n">%s</div><div class="l">最新一期</div></div>'
             % (latest["date"][5:] if latest else "—"))
    p.append('<div class="stat"><div class="n">3</div><div class="l">评分数据源</div></div>')
    p.append('</div></header>')

    if latest:
        p.append('<h2>最新一期</h2>')
        p.append('<div class="hero"><div class="hd">')
        p.append('<span class="date">%s</span><span class="wd">%s</span>%s%s'
                 % (latest["date"], latest["weekday"], ds_tag(latest["meta"]["deepseek"]),
                    feat_tags(latest["meta"])))
        p.append('</div>')
        p.append(render_hl(latest["meta"]))
        p.append(render_links(latest, hero=True))
        p.append('</div>')

    if len(days) > 1:
        p.append('<h2>往期归档</h2>')
        p.append('<div class="grid">')
        for rec in days[1:]:
            p.append('<div class="card"><div class="hd">')
            p.append('<span class="date">%s</span><span class="wd">%s</span>%s'
                     % (rec["date"], rec["weekday"], ds_tag(rec["meta"]["deepseek"])))
            p.append('</div>')
            p.append(render_hl(rec["meta"]))
            p.append(render_links(rec))
            p.append('</div>')
        p.append('</div>')

    p.append('<h2>关于本站</h2>')
    p.append('<div class="note">')
    p.append('<p><strong>内容口径</strong>：每日 15 条精选（AI Coding 8 条 + 具身智能 7 条），'
             '每条标注信息来源与时效。社区单源未交叉验证的线索单列「社区快讯」，'
             '标注为待验证 / 低置信度，不计入已确认条目。</p>')
    p.append('<p><strong>评分数据源</strong>：<code>llm-stats.com</code>（实时价格 / 吞吐）、'
             '<code>livebench.ai</code>（多维审计分 + 每成功任务成本）、'
             '<code>artificialanalysis.ai</code>（Intelligence / Agentic Index），每日现场抓取。</p>')
    p.append('<p><strong>覆盖区间</strong>：%s　|　<strong>本页构建于</strong>：%s</p>' % (span, now))
    p.append('<p><strong>免责声明</strong>：内容由自动化流程汇总生成，仅供参考，'
             '不构成投资或商业决策依据。转载请注明原始信源。</p>')
    p.append('</div>')

    p.append('<footer>AI 日报 · 自动化生成并部署于 Cloudflare Pages'
             ' · 每日更新<br>构建时间 %s</footer>' % now)
    p.append('</body>\n</html>')

    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(p))


def build_latest_redirect(latest_date, out_path):
    doc = ('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">\n'
           '<meta http-equiv="refresh" content="0;url=./%s.html">\n'
           '<title>跳转至最新一期</title>\n</head>\n<body>\n'
           '<p>正在跳转至最新一期：<a href="./%s.html">%s</a></p>\n</body>\n</html>\n'
           % (latest_date, latest_date, latest_date))
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(doc)


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.dirname(ROOT),
                    help="日报源目录（默认为仓库上一级目录）")
    args = ap.parse_args()
    src = os.path.abspath(args.src)

    os.makedirs(PUBLIC, exist_ok=True)
    os.makedirs(MDDIR, exist_ok=True)

    print("源目录：%s" % src)
    days = collect(src)
    if not days:
        print("未找到任何 AI日报_YYYY-MM-DD.html，终止。")
        return 1

    for rec in days:
        shutil.copyfile(rec["html"], os.path.join(PUBLIC, rec["date"] + ".html"))
        if rec["md"]:
            shutil.copyfile(rec["md"], os.path.join(MDDIR, rec["date"] + ".md"))
        d = rec["meta"]["deepseek"]
        print("  + %s %s  条目 %-3s  D:%s" % (
            rec["date"], rec["weekday"], rec["meta"]["counts"].get("items", "?"),
            "有" if d else ("无" if d is False else "?")))

    build_index(days, os.path.join(PUBLIC, "index.html"))
    build_latest_redirect(days[0]["date"], os.path.join(PUBLIC, "latest.html"))

    with open(os.path.join(ROOT, "archive.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump([{"date": r["date"], "weekday": r["weekday"],
                    "deepseek": r["meta"]["deepseek"],
                    "items": r["meta"]["counts"].get("items"),
                    "highlights": r["meta"]["highlights"]} for r in days],
                  fh, ensure_ascii=False, indent=2)

    print("\n完成：%d 期，索引 public/index.html" % len(days))
    return 0


if __name__ == "__main__":
    sys.exit(main())
