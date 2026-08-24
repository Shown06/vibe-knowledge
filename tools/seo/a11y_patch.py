# -*- coding: utf-8 -*-
"""Lighthouse Accessibility の失格3項目を3言語ページで同時に潰す（冪等）。
 - color-contrast: inline <code> の #6b6b67 on #ede9e3 = 4.42 → #60605c = 5.22
 - heading-order:  h1 → h3 の飛びを、直後にh3が続く .section-label を h2 に昇格して解消
 - landmark-one-main: </nav> 〜 <footer> を <main> で包む
"""
import os, re

LP = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lp")
FILES = ["index.html", "ja/index.html", "zh/index.html"]
CODE_FG = "#60605c"   # on var(--code-bg)=#ede9e3 → contrast 5.22 (WCAG AA 4.5 以上)


def fix_contrast(h):
    n = 0
    for sel in (".feature code", ".privacy-list li code"):
        pat = re.compile(r"(" + re.escape(sel) + r" \{ font-family: monospace;)( color: [^;]+;)?")
        h, c = pat.subn(lambda m: m.group(1) + f" color: {CODE_FG};", h)
        n += c
    if n != 2:
        raise SystemExit(f"contrast rules not found (matched {n}/2)")
    return h


def fix_heading_order(h):
    # 直後の見出しが h3 の .section-label だけを h2 に昇格（h1→h3 の飛びを解消）
    out, pos, promoted = [], 0, 0
    for m in re.finditer(r'<p class="section-label">(.*?)</p>', h, re.S):
        nxt = re.search(r"<h([1-6])\b", h[m.end():])
        out.append(h[pos:m.start()])
        if nxt and nxt.group(1) == "3":
            out.append(f'<h2 class="section-label">{m.group(1)}</h2>')
            promoted += 1
        else:
            out.append(m.group(0))
        pos = m.end()
    out.append(h[pos:])
    h = "".join(out)
    already = len(re.findall(r'<h2 class="section-label">', h))
    if already < 2:
        raise SystemExit(f"section-label promotion failed (h2 labels={already})")
    return h


def fix_main_landmark(h):
    if "<main>" in h:
        return h
    i = h.index("</nav>") + len("</nav>")
    j = h.index("<footer>")
    return h[:i] + "\n\n<main>\n" + h[i:j].strip("\n") + "\n</main>\n\n" + h[j:]


for rel in FILES:
    p = os.path.join(LP, rel)
    h = open(p, encoding="utf-8").read()
    h = fix_main_landmark(fix_heading_order(fix_contrast(h)))
    open(p, "w", encoding="utf-8").write(h)
    heads = [t for t, _ in re.findall(r"<(h[1-6])[^>]*>(.*?)</\1>",
                                      re.sub(r"<noscript>.*?</noscript>", "", h, flags=re.S)[h.index("<body"):] if False else
                                      re.sub(r"<noscript>.*?</noscript>", "", h, flags=re.S).split("<body", 1)[1], re.S)]
    skips = [(a, b) for a, b in zip(heads, heads[1:]) if int(b[1]) - int(a[1]) > 1]
    print(f"{rel}: main={h.count('<main>')} h2labels={len(re.findall(r'<h2 class=.section-label.>', h))} "
          f"headings={heads} heading-skips={skips or 'none'}")
