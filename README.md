# AI 日报

每日追踪 **AI Coding** 与 **具身智能** 领域动态，自动生成静态站点并部署到 Cloudflare Pages。

线上地址：`https://ai-daily.pages.dev`

## 内容口径

- **每日 15 条精选**：AI Coding 8 条 + 具身智能 7 条，逐条标注信息来源与时效。
- **社区一手信源优先**：X / Reddit / Hacker News / Linux.do / V2EX / 知乎 / B站 / GitHub Releases / HuggingFace 等，先做多方交叉验证再写入正式条目。
  - 官方公告 → 已确认
  - ≥2 独立社区源，或 1 社区源 + 1 官媒 → 大概率属实
  - 社区单源未交叉 → 单列「社区快讯」，标注待验证 / 低置信度
- **DeepSeek 专项**：每期单列，明确标注「今日有 D」或「今日无 D」。
- **能力评分与价格表**（三口径交叉，每日现场抓取）：
  - [llm-stats.com](https://llm-stats.com/) — 实时价格 / 吞吐 / Price vs Performance
  - [livebench.ai](https://livebench.ai/) — 多维审计分 + 每成功任务成本
  - [artificialanalysis.ai](https://artificialanalysis.ai/) — Intelligence Index / Agentic Index
- **GitHub 当日趋势榜**：AI 专项 + 综合双榜。

## 目录结构

```
ai-daily/
├── public/                  # Cloudflare Pages 部署根目录
│   ├── index.html           # 索引首页（构建生成，勿手改）
│   ├── latest.html          # 跳转至最新一期
│   └── YYYY-MM-DD.html      # 每日日报页（自包含，内联 CSS）
├── md/
│   └── YYYY-MM-DD.md        # 日报 Markdown 源
├── scripts/
│   └── build.py             # 站点构建脚本
└── archive.json             # 归档元数据（构建生成）
```

## 构建

```bash
# 从仓库上一级目录读取 AI日报_YYYY-MM-DD.md/.html
python scripts/build.py

# 指定日报源目录
python scripts/build.py --src /path/to/reports
```

脚本会拷贝日报文件进 `public/` 与 `md/`，并重建 `public/index.html`、`public/latest.html`、`archive.json`。

## 发布

```bash
python scripts/build.py
git add -A
git commit -m "日报 YYYY-MM-DD"
git push
```

推送后 Cloudflare Pages 自动重新部署，约 30 秒上线。

## Cloudflare Pages 配置

| 项 | 值 |
|---|---|
| Framework preset | None |
| Build command | *(留空)* |
| Build output directory | `public` |
| Root directory | *(留空)* |
| 生产分支 | `main` |

## 免责声明

内容由自动化流程汇总生成，仅供参考，不构成投资或商业决策依据。所有条目均标注原始信源，转载请注明出处。社区信源条目已标注置信度，请自行判断。
