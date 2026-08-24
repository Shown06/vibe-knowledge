# -*- coding: utf-8 -*-
"""lp/{index,ja/index,zh/index}.html の SEO/AIO メタを決定論的に再構築する。
再実行しても同じ結果になる（冪等）。fail-closed: 想定パターンが見つからなければ例外で停止。
"""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_keywords import EN, JA, ZH, flat

BASE = "https://vibeknowledge.dev"
REPO = "https://github.com/Shown06/vibe-knowledge"
LP = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lp")

TITLES = {
    "en": "Vibe Knowledge — Turn Claude Code Sessions Into Flashcards Automatically (Free OSS)",
    "ja": "Vibe Knowledge（バイブナレッジ）— Claude Codeのセッションを自動でフラッシュカード化する無料OSS",
    "zh": "Vibe Knowledge — 把 Claude Code 编程会话自动变成闪卡的免费开源工具",
}
DESCS = {
    "en": "Turn every Claude Code session into plain-language flashcards automatically. Free MIT-licensed OSS, fully local, MCP server built in, installs in 30 seconds.",
    "ja": "Claude Codeでコーディングするたびに、学んだ概念を自動でフラッシュカード化。インストール30秒・クラウド不要・APIキー不要・完全無料のMITライセンスOSS。MCPサーバー対応でセッション内から自分の知識を検索でき、間隔反復クイズで定着させられます。",
    "zh": "每次用 Claude Code 写代码，Vibe Knowledge 都会自动把学到的概念整理成通俗易懂的闪卡。安装只需30秒、数据全部留在本地、无需联网账号、完全免费的 MIT 开源工具。内置 MCP 服务器与间隔重复复习，帮你把经验真正记住。",
}
OG_TITLES = {
    "en": "Vibe Knowledge — Your Claude Code sessions, turned into knowledge",
    "ja": "Vibe Knowledge — Claude Codeセッションを自動フラッシュカード化",
    "zh": "Vibe Knowledge — 把 Claude Code 会话自动变成你的知识",
}
OG_DESCS = {
    "en": "Every time you build with Claude Code, Vibe Knowledge silently turns what happened into flashcards. Free, open source, local-only, MCP-ready.",
    "ja": "Claude Codeでコーディングするたびに学んだ概念を自動でフラッシュカード化。インストール30秒・完全無料・ローカル完結・MCP対応OSS。",
    "zh": "每次用 Claude Code 写代码，都会自动生成闪卡。30秒安装、完全免费、数据本地保存、支持 MCP 的开源工具。",
}
OG_IMG_ALT = {
    "en": "Vibe Knowledge - open source tool that turns Claude Code sessions into flashcards",
    "ja": "Vibe Knowledge - Claude Codeセッションを自動フラッシュカード化するOSSツール",
    "zh": "Vibe Knowledge - 把 Claude Code 会话自动变成闪卡的开源工具",
}
LOCALES = {"en": "en_US", "ja": "ja_JP", "zh": "zh_CN"}
HTML_LANG = {"en": "en", "ja": "ja", "zh": "zh-CN"}
URLS = {"en": BASE + "/", "ja": BASE + "/ja/", "zh": BASE + "/zh/"}
KEYWORDS = {"en": flat(EN), "ja": flat(JA), "zh": flat(ZH)}
BREADCRUMB_LEAF = {"en": None, "ja": "日本語", "zh": "中文"}
SW_DESC = {
    "en": "Open-source tool that automatically converts Claude Code coding sessions into flashcards. 30-second install, no cloud, completely free. Works as an MCP server so you can search your own knowledge base from inside a session.",
    "ja": "Claude Codeでのコーディングセッションを自動でフラッシュカードに変換するオープンソースツール。インストール30秒、クラウド不要、完全無料。MCPサーバーとして利用することで、セッション内から自分の知識ベースを検索できる。",
    "zh": "把 Claude Code 编程会话自动转换成闪卡的开源工具。30秒安装、无需云端、完全免费。可作为 MCP 服务器使用，在会话中直接检索自己的知识库。",
}
FAQ_FILES = {"en": "/tmp/vk_faq_en.json", "ja": "/tmp/vk_faq_ja.json", "zh": "/tmp/vk_faq_zh.json"}


def ld(obj):
    return ('<script type="application/ld+json">\n'
            + json.dumps(obj, ensure_ascii=False, indent=2) + "\n</script>")


def jsonld_blocks(lang):
    url = URLS[lang]
    out = []
    out.append(ld({
        "@context": "https://schema.org", "@type": "WebSite",
        "@id": BASE + "/#website", "name": "Vibe Knowledge",
        "alternateName": ["バイブナレッジ", "vibe-knowledge", "VibeKnowledge"],
        "url": url, "inLanguage": HTML_LANG[lang],
        "description": DESCS[lang],
        "publisher": {"@id": BASE + "/#organization"},
    }))
    out.append(ld({
        "@context": "https://schema.org", "@type": "Organization",
        "@id": BASE + "/#organization", "name": "Vibe Knowledge",
        "url": BASE + "/", "logo": BASE + "/icon-512.png",
        "description": SW_DESC[lang],
        "sameAs": [REPO, "https://github.com/Shown06"],
        "foundingDate": "2026-06-11",
    }))
    out.append(ld({
        "@context": "https://schema.org", "@type": "Brand",
        "@id": BASE + "/#brand", "name": "Vibe Knowledge",
        "alternateName": ["バイブナレッジ", "VibeKnowledge"],
        "url": BASE + "/", "logo": BASE + "/icon-512.png",
        "slogan": {"en": "Your coding sessions. Turned into knowledge.",
                   "ja": "書いたコードが、そのまま知識になる。",
                   "zh": "写过的代码，直接变成你的知识。"}[lang],
    }))
    out.append(ld({
        "@context": "https://schema.org", "@type": "Person",
        "@id": BASE + "/#developer", "name": "Shown06",
        "url": "https://github.com/Shown06",
        "sameAs": ["https://github.com/Shown06"],
        "jobTitle": {"en": "Software Developer", "ja": "ソフトウェア開発者",
                     "zh": "软件开发者"}[lang],
    }))
    sw = {
        "@context": "https://schema.org", "@type": "SoftwareApplication",
        "@id": BASE + "/#software", "name": "Vibe Knowledge",
        "alternateName": "バイブナレッジ", "description": SW_DESC[lang], "url": url,
        "applicationCategory": "DeveloperApplication",
        "applicationSubCategory": "Learning & Education",
        "operatingSystem": "macOS, Linux, Windows (WSL)",
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD",
                   "availability": "https://schema.org/InStock",
                   "url": url},
        "license": "https://opensource.org/licenses/MIT",
        "codeRepository": REPO,
        "downloadUrl": "https://raw.githubusercontent.com/Shown06/vibe-knowledge/refs/tags/v1.1.0/install.sh",
        "installUrl": url, "softwareVersion": "1.1.0",
        "isAccessibleForFree": True,
        "author": {"@id": BASE + "/#developer"},
        "publisher": {"@id": BASE + "/#organization"},
        "brand": {"@id": BASE + "/#brand"},
        "inLanguage": ["en", "ja", "zh-CN"],
    }
    out.append(ld(sw))
    items = [{"@type": "ListItem", "position": 1, "name": "Vibe Knowledge", "item": BASE + "/"}]
    leaf = BREADCRUMB_LEAF[lang]
    if leaf:
        items.append({"@type": "ListItem", "position": 2, "name": leaf, "item": url})
    out.append(ld({"@context": "https://schema.org", "@type": "BreadcrumbList",
                   "@id": url + "#breadcrumb", "itemListElement": items}))
    faq = json.load(open(FAQ_FILES[lang], encoding="utf-8"))
    if len(faq) < 50:
        raise SystemExit("FAQ under 50 for " + lang)
    out.append(ld({
        "@context": "https://schema.org", "@type": "FAQPage",
        "@id": url + "#faq", "inLanguage": HTML_LANG[lang],
        "mainEntity": [{"@type": "Question", "name": x["q"],
                        "acceptedAnswer": {"@type": "Answer", "text": x["a"]}} for x in faq],
    }))
    return "\n\n".join(out)


def head_meta(lang):
    url = URLS[lang]
    kw = ",".join(KEYWORDS[lang])
    alts = [LOCALES[l] for l in ("en", "ja", "zh") if l != lang]
    return f'''<title>{TITLES[lang]}</title>
<meta name="description" content="{DESCS[lang]}">
<meta name="keywords" content="{kw}">
<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1">
<meta name="author" content="Shown06">
<meta name="theme-color" content="#c0392b">
<meta name="color-scheme" content="light">

<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" sizes="180x180" href="/touch-icon-180.png">
<link rel="manifest" href="/manifest.webmanifest">

<!-- OGP -->
<meta property="og:title" content="{OG_TITLES[lang]}">
<meta property="og:description" content="{OG_DESCS[lang]}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<meta property="og:site_name" content="Vibe Knowledge">
<meta property="og:locale" content="{LOCALES[lang]}">
''' + "".join(f'<meta property="og:locale:alternate" content="{a}">\n' for a in alts) + f'''<meta property="og:image" content="{BASE}/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:type" content="image/png">
<meta property="og:image:alt" content="{OG_IMG_ALT[lang]}">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{OG_TITLES[lang]}">
<meta name="twitter:description" content="{OG_DESCS[lang]}">
<meta name="twitter:image" content="{BASE}/og-image.png">
<meta name="twitter:image:alt" content="{OG_IMG_ALT[lang]}">

<link rel="canonical" href="{url}">

<!-- hreflang alternates -->
<link rel="alternate" hreflang="en" href="{BASE}/">
<link rel="alternate" hreflang="ja" href="{BASE}/ja/">
<link rel="alternate" hreflang="zh-CN" href="{BASE}/zh/">
<link rel="alternate" hreflang="x-default" href="{BASE}/">

''' + jsonld_blocks(lang)


def patch(path, lang):
    h = open(path, encoding="utf-8").read()
    orig = h
    h = re.sub(r'<html[^>]*lang="[^"]*"', f'<html lang="{HTML_LANG[lang]}"', h, count=1)
    if f'lang="{HTML_LANG[lang]}"' not in h[:200]:
        raise SystemExit("lang rewrite failed: " + path)

    # <title> .. 最後のJSON-LD</script> を丸ごと差し替え（既存headの他要素=charset/viewport/styleは温存）
    start = h.index("<title>")
    end = h.rindex("</script>", 0, h.index("</head>")) + len("</script>")
    h = h[:start] + head_meta(lang) + h[end:]

    # 冪等: 2回目以降は h == orig になりうる（正常）
    open(path, "w", encoding="utf-8").write(h)
    return len(KEYWORDS[lang])


if __name__ == "__main__":
    for rel, lang in (("index.html", "en"), ("ja/index.html", "ja"), ("zh/index.html", "zh")):
        assert 120 <= len(DESCS[lang]) <= 160, (lang, len(DESCS[lang]))
        assert len(KEYWORDS[lang]) >= 150, (lang, len(KEYWORDS[lang]))
        n = patch(os.path.join(LP, rel), lang)
        print(f"patched {rel} lang={lang} keywords={n} desc={len(DESCS[lang])}")
