#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 日报 Markdown -> 深色卡片 HTML 转换器。

用法:
    python md2html.py <input.md> [output.html]

设计要点:
  - 复用既有深色卡片模板的 CSS 变量与组件类（.toc / .scroll / .pvp / .tag / .back-toc 等）
  - 支持: h1-h4、表格、无序/有序列表、引用块、<details>、水平线、粗体、行内代码
  - 目录表格中的章节号自动渲染为 .toc-jump 胶囊按钮
  - 置信度文案自动着色为 .t-conf / .t-prob / .t-pend 标签
  - 性价比条形图（含 ██ 方块的表格）自动转成 .pvp 条形组件
"""
import html
import re
import sys
from pathlib import Path

CSS = """
  :root{
    --bg:#0d1117; --panel:#161b22; --panel2:#1c2330; --border:#2a3340;
    --txt:#e6edf3; --muted:#9da7b3; --accent:#58a6ff; --green:#3fb950;
    --yellow:#e3b341; --red:#f85149; --purple:#bc8cff; --cyan:#39c5cf;
    --r-sm:8px; --r-md:12px; --r-lg:16px;
    --s-1:8px; --s-2:16px; --s-3:24px; --s-4:36px;
    --shadow-1:0 1px 2px rgba(0,0,0,.25);
    --shadow-2:0 6px 20px rgba(0,0,0,.35);
    --shadow-glow:0 6px 24px rgba(88,166,255,.18);
    --font-display:"Space Grotesk","Segoe UI","Microsoft YaHei",sans-serif;
    --font-body:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;
    --ease:cubic-bezier(.2,0,0,1);
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--txt);font-family:var(--font-body);line-height:1.7;
    padding:var(--s-3);max-width:1200px;margin:0 auto;font-size:15px}
  h1{font-family:var(--font-display);font-size:clamp(26px,3.2vw,34px);margin-bottom:var(--s-1);letter-spacing:.3px}
  h2{font-family:var(--font-display);font-size:clamp(19px,2.4vw,24px);margin:var(--s-4) 0 var(--s-2);
    padding-bottom:var(--s-1);border-bottom:1px solid var(--border);color:var(--accent);
    scroll-margin-top:var(--s-2);letter-spacing:.3px}
  h3{font-size:clamp(15px,1.8vw,17px);margin:var(--s-3) 0 var(--s-1);color:var(--cyan);letter-spacing:.2px}
  h4{font-size:14.5px;margin:var(--s-2) 0 var(--s-1);color:var(--txt);
    padding:6px 0 6px 10px;border-left:3px solid var(--purple)}
  p{margin:var(--s-1) 0;font-size:15px}
  blockquote{background:var(--panel);border-left:3px solid var(--accent);border-radius:0 var(--r-sm) var(--r-sm) 0;
             padding:12px 16px;margin:var(--s-2) 0;font-size:13.5px;color:#c3ccd6;box-shadow:var(--shadow-1)}
  blockquote p{margin:3px 0;font-size:13.5px}
  ul,ol{margin:var(--s-1) 0 var(--s-1) 24px;font-size:15px}
  li{margin:6px 0;line-height:1.65}
  table{width:100%;border-collapse:collapse;font-size:13px;margin:var(--s-2) 0}
  th,td{border:1px solid var(--border);padding:8px 10px;text-align:center;vertical-align:top}
  th{background:var(--panel2);color:var(--accent);font-weight:600;position:sticky;top:0;
     box-shadow:0 1px 0 var(--border)}
  tbody tr:nth-child(even){background:rgba(255,255,255,.022)}
  tbody tr:hover{background:rgba(88,166,255,.07)}
  td:nth-child(2){text-align:left}
  .scroll{overflow-x:auto;max-height:640px;overflow-y:auto;border:1px solid var(--border);
    border-radius:var(--r-md);box-shadow:var(--shadow-1)}
  .scroll table{margin:0;border:0}
  details{background:var(--panel);border:1px solid var(--border);border-radius:var(--r-md);
    padding:12px 16px;margin:var(--s-2) 0;box-shadow:var(--shadow-1)}
  summary{cursor:pointer;color:var(--accent);font-size:14px;font-weight:600;outline:none;
    transition:color .15s var(--ease)}
  summary:hover{color:var(--cyan)}
  details[open] summary{margin-bottom:var(--s-1)}
  code{background:var(--panel2);padding:2px 6px;border-radius:var(--r-sm);font-size:12.5px;color:var(--yellow)}
  a{color:var(--accent);text-decoration:none}
  a:hover{text-decoration:underline}
  hr{border:0;border-top:1px solid var(--border);margin:var(--s-3) 0}
  strong{color:#fff}
  .ds-banner{background:linear-gradient(90deg,rgba(57,197,207,.18),rgba(57,197,207,.04));
             border:1px solid var(--cyan);border-radius:12px;padding:14px 18px;margin:16px 0}
  .tag{display:inline-block;font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600;white-space:nowrap}
  .t-conf{background:rgba(63,185,80,.15);color:var(--green);border:1px solid var(--green)}
  .t-prob{background:rgba(227,179,65,.15);color:var(--yellow);border:1px solid var(--yellow)}
  .t-pend{background:rgba(248,81,73,.13);color:var(--red);border:1px solid var(--red)}
  .t-mute{background:rgba(157,167,179,.12);color:var(--muted);border:1px solid var(--border)}
  .pvp{background:var(--panel);border:1px solid var(--border);border-radius:var(--r-md);
    padding:var(--s-2) var(--s-3);margin:var(--s-2) 0;box-shadow:var(--shadow-1)}
  .pvp h3{margin-top:0}
  .bar-row{display:flex;align-items:center;gap:10px;margin:9px 0;font-size:13px}
  .bar-name{width:210px;flex-shrink:0;text-align:right;color:var(--muted);white-space:nowrap;
    overflow:hidden;text-overflow:ellipsis}
  .bar-name.ds{color:var(--cyan);font-weight:700}
  .bar-track{flex:1;background:var(--panel2);border-radius:var(--r-sm);overflow:hidden;height:20px;min-width:80px}
  .bar-fill{height:100%;border-radius:var(--r-sm);background:linear-gradient(90deg,#1f6feb,#58a6ff);
    transition:width .6s var(--ease)}
  .bar-fill.ds{background:linear-gradient(90deg,#1a7f86,#39c5cf)}
  .bar-val{width:86px;flex-shrink:0;color:var(--green);font-weight:700;text-align:right}
  .bar-score{width:118px;flex-shrink:0;color:var(--muted);font-size:11.5px}
  .toc{background:var(--panel);border:1px solid var(--border);border-radius:var(--r-md);
    padding:var(--s-2) var(--s-3);margin:var(--s-2) 0;box-shadow:var(--shadow-1)}
  .toc a{display:inline-block;margin:4px 10px 4px 0;font-size:13px}
  .toc-jump{display:inline-block;min-width:28px;text-align:center;padding:4px 10px;border-radius:var(--r-sm);
    background:linear-gradient(135deg,#1f6feb,#58a6ff);color:#fff !important;font-weight:700;
    box-shadow:0 2px 8px rgba(31,111,235,.3);transition:transform .12s var(--ease),filter .12s var(--ease)}
  .toc-jump:hover{text-decoration:none !important;transform:translateY(-2px);filter:brightness(1.08)}
  h2[id]{cursor:default;position:relative;transition:background .15s var(--ease)}
  h2[id]:hover{background:rgba(88,166,255,.07);border-radius:var(--r-sm);padding-left:8px}
  h2[id]::after{content:"\\1F517 此章节可从目录定位";position:absolute;left:100%;top:6px;margin-left:12px;
    font-size:11.5px;color:var(--accent);white-space:nowrap;opacity:0;transition:opacity .15s;pointer-events:none}
  h2[id]:hover::after{opacity:1}
  @media(max-width:780px){h2[id]::after{display:none}}
  .foot{color:var(--muted);font-size:12px;margin-top:var(--s-4);text-align:center;
    border-top:1px solid var(--border);padding-top:var(--s-2)}
  @keyframes fadeUp{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
  h2,h3,.pvp,.scroll,details,blockquote{animation:fadeUp .5s var(--ease) both}
  @media(prefers-reduced-motion:reduce){*{animation:none !important}}
  @media(max-width:780px){.bar-name{width:120px}.bar-val{width:70px}.bar-score{display:none}body{padding:var(--s-2)}}
  .back-toc{
    position:fixed;left:20px;bottom:20px;z-index:50;
    display:inline-flex;align-items:center;gap:6px;
    background:linear-gradient(135deg,#58a6ff,#39c5cf);
    color:#06121f;font-size:14px;font-weight:700;
    padding:11px 16px;border-radius:24px;cursor:pointer;
    box-shadow:0 4px 16px rgba(0,0,0,.45);border:none;
    transition:transform .15s ease, box-shadow .15s ease;
    -webkit-tap-highlight-color:transparent;
  }
  .back-toc:hover{transform:translateY(-2px);box-shadow:0 6px 22px rgba(88,166,255,.5)}
  .back-toc:active{transform:translateY(0)}
  @media(max-width:780px){.back-toc{left:12px;bottom:12px;font-size:13px;padding:9px 13px}}
"""

JS = """
document.querySelectorAll('a[href^="#"]').forEach(function(a){
  a.addEventListener('click', function(e){
    var el = document.querySelector(this.getAttribute('href'));
    if(el){ e.preventDefault(); el.scrollIntoView({behavior:'smooth', block:'start'}); }
  });
});
var btn = document.querySelector('.back-toc');
if(btn){ btn.addEventListener('click', function(){
  var t = document.getElementById('toc');
  if(t){ t.scrollIntoView({behavior:'smooth', block:'start'}); }
}); }
"""

CONF_MAP = [
    ("\u2705 \u5df2\u786e\u8ba4", "t-conf"),
    ("\U0001F7E1 \u5927\u6982\u7387\u5c5e\u5b9e", "t-prob"),
    ("\U0001F534 \u5f85\u9a8c\u8bc1", "t-pend"),
]


def slugify(text):
    """GitHub 风格锚点：去掉非字母数字/中文字符，空格转连字符，转小写。"""
    t = re.sub(r"<[^>]+>", "", text)
    t = re.sub(r"[\*`_\[\]\(\)#]", "", t)
    t = t.strip().lower()
    t = re.sub(r"[\s]+", "-", t)
    t = re.sub(r"[^\w\u4e00-\u9fff\-]", "", t)
    return t


def inline(text):
    """行内标记转换。"""
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', out)
    for token, cls in CONF_MAP:
        out = out.replace(token, '<span class="tag %s">%s</span>' % (cls, token))
    return out


def is_bar_table(rows):
    return any("\u2588" in c or "\u258c" in c or "\u258f" in c or "\u258e" in c
               for r in rows for c in r)


def render_bar_table(header, rows):
    """把带方块字符的性价比表渲染成条形图组件。"""
    parts = ['<div class="pvp">']
    for r in rows:
        if len(r) < 6:
            continue
        strip = lambda x: re.sub(r"[*`]", "", x).strip()
        name = strip(r[1])
        score, price, ratio, bar = strip(r[2]), strip(r[3]), strip(r[4]), r[5]
        m = re.search(r"([\d.]+)\s*%", bar)
        pct = float(m.group(1)) if m else 0.0
        ds = " ds" if re.search(r"deepseek|glm", name, re.I) else ""
        parts.append(
            '<div class="bar-row">'
            '<div class="bar-name%s">%s</div>'
            '<div class="bar-track"><div class="bar-fill%s" style="width:%.1f%%"></div></div>'
            '<div class="bar-val">%s</div>'
            '<div class="bar-score">%s / %s</div>'
            '</div>' % (ds, html.escape(name), ds, pct,
                        html.escape(ratio), html.escape(score), html.escape(price))
        )
    parts.append('</div>')
    return "\n".join(parts)


def render_table(header, rows, is_toc):
    thead = "".join("<th>%s</th>" % inline(c) for c in header)
    body = []
    for r in rows:
        tds = []
        for i, c in enumerate(r):
            if is_toc and i == 0:
                m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", c.strip())
                if m:
                    tds.append('<td><a class="toc-jump" href="%s">%s</a></td>'
                               % (m.group(2), m.group(1)))
                    continue
            tds.append("<td>%s</td>" % inline(c))
        body.append("<tr>%s</tr>" % "".join(tds))
    tbl = ('<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>'
           % (thead, "".join(body)))
    if len(rows) > 14:
        return '<div class="scroll">%s</div>' % tbl
    return tbl


def convert(md_text):
    lines = md_text.split("\n")
    out = []
    i = 0
    n = len(lines)
    in_details = False

    while i < n:
        line = lines[i]
        s = line.strip()

        # 原生 HTML 块（details/summary）直接透传
        if s.startswith("<details"):
            out.append(s)
            in_details = True
            i += 1
            continue
        if s.startswith("</details>"):
            out.append(s)
            in_details = False
            i += 1
            continue
        if s.startswith("<summary"):
            out.append(s)
            i += 1
            continue

        if not s:
            i += 1
            continue

        # 水平线
        if re.fullmatch(r"-{3,}", s):
            out.append("<hr>")
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            if level == 1:
                out.append("<h1>%s</h1>" % inline(text))
            elif level == 2:
                anchor = slugify(text)
                if text.startswith("\u76ee\u5f55"):
                    anchor = "toc"
                out.append('<h2 id="%s">%s</h2>' % (anchor, inline(text)))
            else:
                out.append("<h%d>%s</h%d>" % (level, inline(text), level))
            i += 1
            continue

        # 表格
        if s.startswith("|") and i + 1 < n and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            header = [c.strip() for c in s.strip("|").split("|")]
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            is_toc = header and header[0].startswith("\u7ae0\u8282")
            if is_bar_table(rows):
                out.append(render_bar_table(header, rows))
            else:
                wrap = '<div class="toc">%s</div>' if is_toc else "%s"
                out.append(wrap % render_table(header, rows, is_toc))
            continue

        # 引用块
        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            paras = [inline(b) for b in buf if b]
            out.append("<blockquote>%s</blockquote>"
                       % "".join("<p>%s</p>" % p for p in paras))
            continue

        # 列表
        if re.match(r"^([-*]|\d+\.)\s+", s):
            ordered = bool(re.match(r"^\d+\.\s+", s))
            tag = "ol" if ordered else "ul"
            items = []
            while i < n:
                cur = lines[i].strip()
                if not cur:
                    i += 1
                    if i < n and re.match(r"^([-*]|\d+\.)\s+", lines[i].strip()):
                        continue
                    break
                if re.match(r"^([-*]|\d+\.)\s+", cur):
                    items.append(re.sub(r"^([-*]|\d+\.)\s+", "", cur))
                elif items:
                    items[-1] += " " + cur
                else:
                    break
                i += 1
            out.append("<%s>%s</%s>" % (tag, "".join("<li>%s</li>" % inline(x) for x in items), tag))
            continue

        # 普通段落
        buf = [s]
        i += 1
        while i < n:
            nxt = lines[i].strip()
            if (not nxt or nxt.startswith(("#", "|", ">", "<", "-", "*"))
                    or re.match(r"^\d+\.\s+", nxt)):
                break
            buf.append(nxt)
            i += 1
        text = " ".join(buf)
        if text.startswith("*") and text.endswith("*") and text.count("*") == 2:
            out.append('<p class="foot">%s</p>' % inline(text.strip("*")))
        else:
            out.append("<p>%s</p>" % inline(text))

    return "\n".join(out)


def main():
    if len(sys.argv) < 2:
        print("usage: md2html.py <input.md> [output.html]")
        return 1
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".html")
    md = src.read_text(encoding="utf-8")

    title = "AI \u65e5\u62a5"
    m = re.search(r"^#\s+(.*)$", md, re.M)
    if m:
        title = re.sub(r"[#*]", "", m.group(1)).strip()

    body = convert(md)
    doc = (
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '<title>%s</title>\n<style>%s</style>\n</head>\n<body>\n%s\n'
        '<button class="back-toc" type="button">\u2191 \u56de\u5230\u76ee\u5f55</button>\n'
        '<script>%s</script>\n</body>\n</html>\n'
        % (html.escape(title), CSS, body, JS)
    )
    dst.write_text(doc, encoding="utf-8")
    print("OK -> %s (%d bytes)" % (dst, len(doc.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
