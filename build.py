#!/usr/bin/env python3
"""Static site generator for www.dailybharat10.com.

Pulls the channel's public YouTube RSS feed (no API key), merges it into
data/videos.json (so pages outlive the feed's 15-item window), then writes
index.html, /news/<id>/ watch pages, /archive/, sitemap.xml, robots.txt.
Output is deterministic: a re-run with no new video changes no file, so the
scheduled workflow only commits when there is something new.
"""
import html
import json
import re
import sys
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
SITE = "https://www.dailybharat10.com"
CHANNEL_ID = "UC3oT8ClEaeXBjrUdBrxYTrw"
HANDLE = "@dailybharat10"
YT = "https://www.youtube.com/@dailybharat10"
SUBSCRIBE = YT + "?sub_confirmation=1"
FEED = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
NAME = "Daily Bharat News"
EMAIL = "dailybharat10@gmail.com"
DATA = ROOT / "data" / "videos.json"
IST = timezone(timedelta(hours=5, minutes=30))
WEEK = ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]
MONTH = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त",
         "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]

KINDS = {  # key: (label, css colour class, section heading)
    "bulletin": ("ताज़ा बुलेटिन", "k-saffron", "आज की ताज़ा खबर"),
    "hundred": ("100 ख़बरें", "k-blue", "बाकी करीब 100 ख़बरें, 10 मिनट में"),
    "story": ("पूरी कहानी", "k-violet", "पूरी कहानी: एक खबर, पूरी जानकारी"),
    "short": ("शॉर्ट", "k-pink", "फटाफट शॉर्ट्स"),
}

ICON = {
    "yt": '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.6 12 3.6 12 3.6s-7.5 0-9.4.5A3 3 0 0 0 .5 6.2C0 8.1 0 12 0 12s0 3.9.5 5.8a3 3 0 0 0 2.1 2.1c1.9.5 9.4.5 9.4.5s7.5 0 9.4-.5a3 3 0 0 0 2.1-2.1c.5-1.9.5-5.8.5-5.8s0-3.9-.5-5.8ZM9.6 15.6V8.4l6.2 3.6-6.2 3.6Z"/></svg>',
    "bell": '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 22a2.5 2.5 0 0 0 2.5-2.5h-5A2.5 2.5 0 0 0 12 22Zm7-6.5V11a7 7 0 0 0-5.5-6.8V3.5a1.5 1.5 0 0 0-3 0v.7A7 7 0 0 0 5 11v4.5L3 17.5V19h18v-1.5l-2-2Z"/></svg>',
    "play": '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M8 5.5v13a1 1 0 0 0 1.5.9l10.5-6.5a1 1 0 0 0 0-1.8L9.5 4.6A1 1 0 0 0 8 5.5Z"/></svg>',
    "clock": '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 5v5.4l4 2.4-.8 1.3-4.8-2.9V7H13Z"/></svg>',
    "lang": '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12.9 15.1 10.4 12.6a17.4 17.4 0 0 0 3.7-7.1H17V3.5h-7V1.5H8v2H1v2h11.2A15.7 15.7 0 0 1 9 10.7 15.3 15.3 0 0 1 6.7 7.5H4.7a17.5 17.5 0 0 0 3 4.6L3.6 16.2 5 17.6l5-5 3.1 3.1.8-.6ZM18.5 10h-2L12 22h2l1.1-3h4.8l1.1 3h2l-4.5-12Zm-2.6 7 1.6-4.3 1.6 4.3h-3.2Z"/></svg>',
    "shield": '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 1 3 5v6c0 5.5 3.8 10.7 9 12 5.2-1.3 9-6.5 9-12V5l-9-4Zm-1.3 15.3-3.5-3.5 1.4-1.4 2.1 2.1 5.1-5.1 1.4 1.4-6.5 6.5Z"/></svg>',
    "paper": '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M4 4h13a2 2 0 0 1 2 2v1h1a1 1 0 0 1 1 1v9a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V5a1 1 0 0 1 1-1Zm2 4v2h9V8H6Zm0 4v2h9v-2H6Zm0 4v2h6v-2H6Z"/></svg>',
    "arrow": '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="m13 5-1.4 1.4L16.2 11H4v2h12.2l-4.6 4.6L13 19l7-7-7-7Z"/></svg>',
    "menu": '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M3 6h18v2H3V6Zm0 5h18v2H3v-2Zm0 5h18v2H3v-2Z"/></svg>',
}


# ---------------------------------------------------------------- data ---
def fetch_feed():
    req = urllib.request.Request(FEED, headers={"User-Agent": "Mozilla/5.0 (dailybharat10.com site build)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        root = ET.fromstring(r.read())
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
          "m": "http://search.yahoo.com/mrss/"}
    out = []
    for e in root.findall("a:entry", ns):
        out.append({
            "id": e.find("yt:videoId", ns).text,
            "title": e.find("a:title", ns).text or "",
            "published": e.find("a:published", ns).text,
            "desc": e.find("m:group/m:description", ns).text or "",
        })
    return out


def classify(v):
    t, d = v["title"], v["desc"]
    if unicodedata.normalize("NFC", t).startswith("आज की ताज़ा खबर"):
        return "bulletin"
    if "ख़बरें" in unicodedata.normalize("NFC", t) and ("100" in t or "१००" in t):
        return "hundred"
    if "#shorts" in (t + d).lower():
        return "short"
    return "story"


def load_videos():
    vids = {}
    if DATA.exists():
        for v in json.loads(DATA.read_text(encoding="utf8")):
            vids[v["id"]] = v
    try:
        for v in fetch_feed():
            vids[v["id"]] = v
    except Exception as exc:  # network down: build from what we already have
        print("feed fetch failed, using stored data:", exc, file=sys.stderr)
    for v in vids.values():
        v["kind"] = classify(v)
    out = sorted(vids.values(), key=lambda v: v["published"], reverse=True)
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf8")
    return out


# ------------------------------------------------------------- helpers ---
def esc(s):
    return html.escape(s or "", quote=True)


def clean_title(t):
    t = re.sub(r"\s*#\S+", "", t).strip(" |")
    return re.sub(r"\s+", " ", t)


def dt_ist(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(IST)


def hi_date(iso):
    d = dt_ist(iso)
    return f"{WEEK[d.weekday()]}, {d.day} {MONTH[d.month - 1]} {d.year}"


def thumb(v, size="hq"):
    return f"https://i.ytimg.com/vi/{v['id']}/{size}default.jpg"


def watch_url(v):
    return f"{SITE}/news/{v['id']}/"


def parse_desc(desc):
    """Split a YouTube description into chapters / summary / bullets / credits."""
    chapters, bullets, paras, credits, cur = [], [], [], [], []
    in_credits = False
    for raw in desc.replace("\r", "").split("\n"):
        line = raw.strip()
        if not line:
            if cur:
                paras.append(" ".join(cur))
                cur = []
            in_credits = False
            continue
        m = re.match(r"^((?:\d{1,2}:)?\d{1,2}:\d{2})\s+(.+)$", line)
        if m:
            chapters.append((m.group(1), m.group(2)))
            continue
        if re.match(r"^(#\S+\s*)+$", line) or "Hit Subscribe" in line:
            continue
        if re.match(r"^\d{1,2} \w+ \d{4} \|", line) and ("Aaj Ki" in line or "Khabar" in line or "Hindi" in line):
            continue
        if line[0] in "🔥▶📹📌" or "youtu.be/" in line and "चित्र" not in line:
            continue
        if line.startswith("- "):
            bullets.append(line[2:].strip())
            continue
        if line.startswith(("इस वीडियो में", "चित्र साभार")):
            in_credits = True
        if in_credits:
            credits.append(line)
            continue
        cur.append(line)
    if cur:
        paras.append(" ".join(cur))
    return chapters, paras, bullets, credits


def ts_seconds(ts):
    parts = [int(x) for x in ts.split(":")]
    s = 0
    for p in parts:
        s = s * 60 + p
    return s


def autolink(text):
    return re.sub(r"(https?://[^\s<]+)", r'<a href="\1" rel="nofollow noopener" target="_blank">\1</a>', esc(text))


# -------------------------------------------------------------- layout ---
NAV = [("/", "होम"), ("/#bulletin", "ताज़ा बुलेटिन"), ("/#hundred", "100 ख़बरें"),
       ("/#stories", "पूरी कहानी"), ("/archive/", "सभी वीडियो"), ("/#about", "हमारे बारे में")]


def head(title, desc, path, image=None, extra="", og_type="website"):
    image = image or f"{SITE}/assets/img/og-default.png"
    url = SITE + path
    return f"""<!DOCTYPE html>
<html lang="hi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1">
<meta name="theme-color" content="#0a1233">
<meta property="og:site_name" content="{NAME}">
<meta property="og:type" content="{og_type}">
<meta property="og:locale" content="hi_IN">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{image}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<meta name="twitter:image" content="{image}">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" type="image/png" href="/assets/img/favicon-192.png" sizes="192x192">
<link rel="apple-touch-icon" href="/assets/img/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="preload" href="/assets/fonts/fonts.css" as="style">
<link rel="stylesheet" href="/assets/fonts/fonts.css">
<link rel="stylesheet" href="/assets/style.css">
{extra}
</head>
"""


def ld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "</script>"


ORG = {
    "@type": ["Organization", "NewsMediaOrganization"],
    "@id": SITE + "/#org",
    "name": NAME,
    "alternateName": ["Daily Bharat", "डेली भारत न्यूज़", HANDLE],
    "url": SITE + "/",
    "logo": {"@type": "ImageObject", "url": SITE + "/assets/img/icon-512.png", "width": 512, "height": 512},
    "sameAs": [YT, f"https://www.youtube.com/channel/{CHANNEL_ID}"],
    "email": EMAIL,
    "inLanguage": "hi",
    "ethicsPolicy": SITE + "/#about",
}


def header(active_path=""):
    links = "".join(f'<a href="{h}">{esc(t)}</a>' for h, t in NAV)
    return f"""<body>
<a class="skip" href="#main">मुख्य सामग्री पर जाएँ</a>
<div class="tricolor" aria-hidden="true"></div>
<header class="site-header">
  <div class="wrap bar">
    <a class="brand" href="/" aria-label="{NAME} - होम"><img src="/assets/img/logo-mark.webp" width="120" height="63" alt="Daily भारत लोगो" fetchpriority="high"></a>
    <nav class="nav" id="nav" aria-label="मुख्य मेनू">{links}</nav>
    <a class="btn btn-red btn-sm" href="{SUBSCRIBE}" target="_blank" rel="noopener">{ICON['yt']}<span>सब्सक्राइब</span></a>
    <button class="menu-btn" aria-label="मेनू खोलें" aria-expanded="false" aria-controls="nav">{ICON['menu']}</button>
  </div>
</header>
"""


def ticker(vids):
    items = [v for v in vids if v["kind"] in ("bulletin", "hundred", "story")][:8]
    if not items:
        return ""
    row = "".join(f'<a href="/news/{v["id"]}/">{esc(clean_title(v["title"]))}</a>' for v in items)
    return f"""<div class="ticker" role="region" aria-label="ताज़ा वीडियो">
  <span class="ticker-tag">ताज़ा</span>
  <div class="ticker-track"><div class="ticker-move">{row}{row}</div></div>
</div>
"""


def footer():
    yr = datetime.now(IST).year
    return f"""<footer class="site-footer">
  <div class="wrap foot-grid">
    <div>
      <img src="/assets/img/logo-lockup.webp" width="200" height="127" alt="{NAME} लोगो" loading="lazy">
      <p class="muted-l">देश-दुनिया की हर बड़ी खबर, सरल हिंदी में, हर सुबह।</p>
    </div>
    <div>
      <h3>देखें</h3>
      <a href="{YT}" target="_blank" rel="noopener">YouTube चैनल {HANDLE}</a>
      <a href="{SUBSCRIBE}" target="_blank" rel="noopener">सब्सक्राइब करें</a>
      <a href="{YT}/videos" target="_blank" rel="noopener">सभी वीडियो (YouTube)</a>
      <a href="{YT}/shorts" target="_blank" rel="noopener">Shorts</a>
    </div>
    <div>
      <h3>वेबसाइट</h3>
      <a href="/archive/">वीडियो आर्काइव</a>
      <a href="/privacy-policy.html">Privacy Policy</a>
      <a href="/terms.html">Terms of Service</a>
      <a href="mailto:{EMAIL}">{EMAIL}</a>
    </div>
  </div>
  <div class="wrap foot-note">
    <p>&copy; {yr} {NAME}. सभी वीडियो हमारे YouTube चैनल पर उपलब्ध हैं। कुछ दृश्य AI से बने प्रतीकात्मक चित्र हो सकते हैं; ऐसा हर वीडियो के विवरण में लिखा होता है।</p>
  </div>
</footer>
<script src="/assets/site.js" defer></script>
</body>
</html>
"""


def card(v, size="", show_kind=True):
    label, cls, _ = KINDS[v["kind"]]
    badge = f'<span class="badge {cls}">{label}</span>' if show_kind else ""
    return f"""<article class="card {size} {'is-short' if v['kind']=='short' else ''}" data-kind="{v['kind']}">
  <a class="thumb" href="/news/{v['id']}/" aria-label="{esc(clean_title(v['title']))}">
    <img src="{thumb(v)}" width="480" height="270" loading="lazy" decoding="async" alt="{esc(clean_title(v['title']))}">
    <span class="play">{ICON['play']}</span>{badge}
  </a>
  <div class="card-body">
    <h3><a href="/news/{v['id']}/">{esc(clean_title(v['title']))}</a></h3>
    <time datetime="{v['published']}">{hi_date(v['published'])}</time>
  </div>
</article>
"""


def section(sid, kind, vids, limit, intro=""):
    items = [v for v in vids if v["kind"] == kind][:limit]
    if not items:
        return ""
    label, cls, heading = KINDS[kind]
    cards = "".join(card(v, show_kind=False) for v in items)
    return f"""<section class="sec {cls}" id="{sid}">
  <div class="wrap">
    <div class="sec-head"><span class="sec-bar"></span><div><h2>{heading}</h2>{f'<p>{intro}</p>' if intro else ''}</div>
      <a class="more" href="/archive/?k={kind}">सभी देखें {ICON['arrow']}</a></div>
    <div class="grid {'grid-short' if kind=='short' else ''}">{cards}</div>
  </div>
</section>
"""


FAQ = [
    ("आज की ताज़ा खबर कहाँ देखें?",
     f"हर सुबह हमारा नया बुलेटिन YouTube चैनल {HANDLE} पर आता है, जिसमें देश और दुनिया की करीब 50 बड़ी खबरें होती हैं। इसी वेबसाइट के होम पेज पर सबसे नया वीडियो सबसे ऊपर मिलता है।"),
    ("क्या Daily Bharat News पूरी तरह हिंदी में है?",
     "हाँ। पूरा बुलेटिन, स्क्रीन के शब्द और आवाज़ सरल शुद्ध हिंदी में हैं। अंग्रेज़ी स्रोतों की खबरें भी हिंदी में अनुवाद करके ही दिखाई जाती हैं।"),
    ("खबरें कहाँ से ली जाती हैं?",
     "सरकारी विज्ञप्तियों (जैसे PIB) और प्रमुख हिंदी-अंग्रेज़ी अख़बारों से। हम दलों के आपसी आरोप-प्रत्यारोप और सांप्रदायिक विवाद वाली खबरें नहीं दिखाते; ज़ोर नीति, योजनाओं और तथ्यों पर रहता है।"),
    ("100 ख़बरें 10 मिनट में क्या है?",
     "मुख्य बुलेटिन के बाद की बाकी करीब 100 खबरें हम एक अलग तेज़ वीडियो में देते हैं, ताकि 10 मिनट में आप पूरे दिन की तस्वीर देख सकें।"),
    ("क्या वीडियो में AI का इस्तेमाल होता है?",
     "कुछ वीडियो में प्रतीकात्मक चित्र AI से बनाए जाते हैं। ऐसे हर वीडियो के विवरण में यह साफ़ लिखा होता है, और असली तस्वीरों के लिए चित्र-साभार भी दिया जाता है।"),
    ("नया वीडियो कैसे नहीं छूटेगा?",
     "YouTube पर चैनल सब्सक्राइब करें और घंटी (Bell) आइकन दबाकर \"सभी\" चुनें। फिर हर नया बुलेटिन सीधे आपके फ़ोन पर सूचना के रूप में आएगा।"),
]


def build_home(vids):
    latest = next((v for v in vids if v["kind"] == "bulletin"), vids[0])
    hundred = next((v for v in vids if v["kind"] == "hundred"), None)
    title = f"{NAME} | आज की ताज़ा खबर, Hindi News Today - देश-दुनिया की हर बड़ी खबर"
    desc = ("हर सुबह देश-दुनिया की करीब 50 बड़ी खबरें सरल हिंदी में। आज की ताज़ा खबर, राष्ट्रीय, अंतरराष्ट्रीय, बाज़ार, सोना-चांदी भाव और राज्य समाचार का "
            "पूरा बुलेटिन देखें और Daily Bharat News YouTube चैनल को सब्सक्राइब करें।")
    items = [v for v in vids if v["kind"] != "short"][:10]
    graph = [
        ORG,
        {"@type": "WebSite", "@id": SITE + "/#site", "url": SITE + "/", "name": NAME, "inLanguage": "hi",
         "publisher": {"@id": SITE + "/#org"}},
        {"@type": "WebPage", "@id": SITE + "/#page", "url": SITE + "/", "name": title, "description": desc, "inLanguage": "hi",
         "isPartOf": {"@id": SITE + "/#site"}, "about": {"@id": SITE + "/#org"}},
        {"@type": "ItemList", "name": "ताज़ा वीडियो", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "url": watch_url(v), "name": clean_title(v["title"])}
            for i, v in enumerate(items)]},
        {"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
    ]
    extra = ld({"@context": "https://schema.org", "@graph": graph})
    faq = "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in FAQ)
    why = [
        ("clock", "c-saffron", "हर सुबह, समय पर", "रोज़ सुबह नया बुलेटिन तैयार, ताकि चाय के साथ पूरे दिन की खबरें आपके पास हों।"),
        ("lang", "c-blue", "सरल शुद्ध हिंदी", "आसान भाषा, साफ़ आवाज़ और स्क्रीन पर पढ़ने लायक शब्द। कोई मुश्किल शब्द नहीं।"),
        ("shield", "c-green", "शोर नहीं, तथ्य", "दलगत आरोप-प्रत्यारोप और सांप्रदायिक विवाद नहीं। नीति, योजनाएँ और असली जानकारी।"),
        ("paper", "c-violet", "भरोसेमंद स्रोत", "सरकारी विज्ञप्तियों और प्रमुख अख़बारों की खबरें, एक ही बुलेटिन में।"),
    ]
    why_html = "".join(
        f'<div class="why {c}"><span class="why-ic">{ICON[i]}</span><h3>{t}</h3><p>{p}</p></div>' for i, c, t, p in why)
    hero_card = f"""<a class="feature" href="/news/{latest['id']}/">
      <span class="feature-tag">सबसे नया बुलेटिन</span>
      <span class="feature-img"><img src="{thumb(latest,'maxres')}" onerror="this.onerror=null;this.src='{thumb(latest)}'" width="1280" height="720" alt="{esc(clean_title(latest['title']))}" fetchpriority="high"><span class="play big">{ICON['play']}</span></span>
      <span class="feature-body"><strong>{esc(clean_title(latest['title']))}</strong><time datetime="{latest['published']}">{hi_date(latest['published'])}</time></span>
    </a>"""
    body = f"""{header()}
{ticker(vids)}
<main id="main">
<section class="hero">
  <div class="hero-glow" aria-hidden="true"></div>
  <div class="wrap hero-grid">
    <div class="hero-copy">
      <p class="eyebrow">डेली न्यूज़ बुलेटिन &middot; {HANDLE}</p>
      <h1>देश-दुनिया की <span class="grad">हर बड़ी खबर</span>, हर सुबह, सरल हिंदी में</h1>
      <p class="lead">आज की ताज़ा खबर, राष्ट्रीय और अंतरराष्ट्रीय समाचार, बाज़ार, सोना-चांदी भाव और राज्य समाचार, सब एक ही बुलेटिन में। YouTube पर देखें और नया वीडियो कभी न छोड़ें।</p>
      <div class="cta-row">
        <a class="btn btn-red" href="{SUBSCRIBE}" target="_blank" rel="noopener">{ICON['yt']}<span>YouTube पर सब्सक्राइब करें</span></a>
        <a class="btn btn-ghost" href="/news/{latest['id']}/">{ICON['play']}<span>आज का बुलेटिन देखें</span></a>
      </div>
      <ul class="chips">
        <li class="c-saffron">रोज़ सुबह नया बुलेटिन</li>
        <li class="c-green">करीब 50 बड़ी खबरें</li>
        <li class="c-blue">बाकी 100 ख़बरें, 10 मिनट में</li>
        <li class="c-pink">100% हिंदी</li>
      </ul>
    </div>
    <div class="hero-card">{hero_card}</div>
  </div>
</section>
{section('bulletin','bulletin',vids,4,'हर सुबह की मुख्य खबरें: राष्ट्रीय, अंतरराष्ट्रीय, बाज़ार और राज्य।')}
{section('hundred','hundred',vids,3,'कम समय में ज़्यादा खबरें: पूरे दिन की बाकी सुर्खियाँ।')}
{section('stories','story',vids,6,'एक बड़ी खबर की पूरी पड़ताल, आसान भाषा में।')}
{section('shorts','short',vids,6)}
<section class="sec why-sec">
  <div class="wrap">
    <div class="sec-head center"><div><h2>Daily Bharat News क्यों देखें?</h2><p>समय कम है, खबरें ज़्यादा। हम आपका समय बचाते हैं।</p></div></div>
    <div class="why-grid">{why_html}</div>
  </div>
</section>
<section class="subscribe" id="subscribe">
  <div class="wrap sub-grid">
    <div>
      <h2>एक भी खबर मत छोड़िए</h2>
      <p>चैनल सब्सक्राइब करें और घंटी दबाएँ। हर सुबह का बुलेटिन सीधे आपके फ़ोन पर।</p>
      <ol class="steps">
        <li><b>1</b> YouTube पर {HANDLE} खोलें</li>
        <li><b>2</b> <em>Subscribe</em> दबाएँ</li>
        <li><b>3</b> घंटी {ICON['bell']} दबाकर <em>All</em> चुनें</li>
      </ol>
      <div class="cta-row">
        <a class="btn btn-white" href="{SUBSCRIBE}" target="_blank" rel="noopener">{ICON['yt']}<span>अभी सब्सक्राइब करें</span></a>
        <a class="btn btn-outline" href="{YT}" target="_blank" rel="noopener"><span>चैनल खोलें</span>{ICON['arrow']}</a>
      </div>
    </div>
    <div class="sub-art" aria-hidden="true"><div class="bell">{ICON['bell']}</div><div class="ring r1"></div><div class="ring r2"></div></div>
  </div>
</section>
<section class="sec faq-sec" id="faq">
  <div class="wrap narrow">
    <div class="sec-head center"><div><h2>अक्सर पूछे जाने वाले सवाल</h2></div></div>
    <div class="faq">{faq}</div>
  </div>
</section>
<section class="sec about" id="about">
  <div class="wrap narrow">
    <h2>हमारे बारे में</h2>
    <p><strong>{NAME}</strong> (डेली भारत न्यूज़) एक हिंदी समाचार चैनल है। हम हर सुबह देश और दुनिया की प्रमुख खबरें सरल हिंदी में एक बुलेटिन के रूप में YouTube पर प्रकाशित करते हैं। खबरें सरकारी विज्ञप्तियों और प्रमुख अख़बारों से ली जाती हैं।</p>
    <p class="fine">इस वेबसाइट के बारे में: यह {NAME} चैनल का आधिकारिक होम पेज है। हमारा अपना प्रकाशन टूल Google की YouTube APIs का उपयोग केवल हमारे अपने चैनल पर वीडियो अपलोड करने और हमारे अपने चैनल के एनालिटिक्स पढ़ने के लिए करता है। इसे केवल चैनल-स्वामी उपयोग करता है; यह जनता के लिए साइन-इन नहीं देता और आगंतुकों या दर्शकों का कोई डेटा इकट्ठा नहीं करता। विवरण: <a href="/privacy-policy.html">Privacy Policy</a> और <a href="/terms.html">Terms of Service</a>। संपर्क: <a href="mailto:{EMAIL}">{EMAIL}</a>।</p>
    <p class="fine en">Official home page of the {NAME} YouTube channel: a daily Hindi news bulletin covering India and the world. This site collects no visitor data; see the <a href="/privacy-policy.html">Privacy Policy</a> for how our own publishing tool uses Google YouTube APIs.</p>
  </div>
</section>
</main>
{footer()}"""
    (ROOT / "index.html").write_text(head(title, desc, "/", extra=extra) + body, encoding="utf8")


def build_watch(v, vids):
    label, cls, _ = KINDS[v["kind"]]
    ttl = clean_title(v["title"])
    chapters, paras, bullets, credits = parse_desc(v["desc"])
    summary = paras[0] if paras else ""
    dline = hi_date(v["published"])
    meta_desc = (f"{dline} | {ttl}. " + (summary[:150] + "…" if summary else f"{NAME} पर देखें।"))[:300]
    page_title = f"{ttl} | {NAME}"
    url = watch_url(v)
    video_ld = {
        "@context": "https://schema.org", "@type": "VideoObject", "name": ttl,
        "description": (summary or ttl)[:500], "thumbnailUrl": [thumb(v, "maxres"), thumb(v)],
        "uploadDate": v["published"], "embedUrl": f"https://www.youtube.com/embed/{v['id']}",
        "url": url, "inLanguage": "hi", "publisher": ORG,
        "isFamilyFriendly": True,
    }
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "होम", "item": SITE + "/"},
        {"@type": "ListItem", "position": 2, "name": "वीडियो", "item": SITE + "/archive/"},
        {"@type": "ListItem", "position": 3, "name": ttl, "item": url}]}
    extra = ld(video_ld) + ld(crumbs)
    chap_html = ""
    if chapters:
        rows = "".join(
            f'<li><a href="https://www.youtube.com/watch?v={v["id"]}&amp;t={ts_seconds(t)}s" target="_blank" rel="noopener"><b>{t}</b> {esc(n)}</a></li>'
            for t, n in chapters)
        chap_html = f'<section class="panel"><h2>इस वीडियो में क्या है</h2><ol class="chapters">{rows}</ol></section>'
    sum_html = "".join(f"<p>{esc(p)}</p>" for p in paras[:3])
    bl_html = ""
    if bullets:
        bl_html = ('<section class="panel"><h2>आज की सुर्खियाँ</h2><ul class="heads">'
                   + "".join(f"<li>{esc(b)}</li>" for b in bullets[:120]) + "</ul></section>")
    cr_html = ""
    if credits:
        cr_html = '<section class="panel credits"><h2>चित्र साभार</h2>' + "".join(f"<p>{autolink(c)}</p>" for c in credits) + "</section>"
    related = [x for x in vids if x["id"] != v["id"] and x["kind"] != "short"][:6]
    rel_html = "".join(card(x) for x in related)
    body = f"""{header()}
<main id="main" class="watch">
<div class="wrap narrow2">
  <nav class="crumbs" aria-label="ब्रेडक्रम्ब"><a href="/">होम</a> / <a href="/archive/">वीडियो</a> / <span>{label}</span></nav>
  <span class="badge {cls}">{label}</span>
  <h1>{esc(ttl)}</h1>
  <p class="meta"><time datetime="{v['published']}">{dline}</time> &middot; {NAME}</p>
  <div class="player {'player-short' if v['kind']=='short' else ''}" data-id="{v['id']}">
    <button class="player-btn" type="button" aria-label="वीडियो चलाएँ: {esc(ttl)}">
      <img src="{thumb(v,'maxres')}" onerror="this.onerror=null;this.src='{thumb(v)}'" width="1280" height="720" alt="{esc(ttl)}">
      <span class="play big">{ICON['play']}</span>
    </button>
    <noscript><a href="https://www.youtube.com/watch?v={v['id']}">YouTube पर देखें</a></noscript>
  </div>
  <div class="cta-row center-row">
    <a class="btn btn-red" href="https://www.youtube.com/watch?v={v['id']}" target="_blank" rel="noopener">{ICON['yt']}<span>YouTube पर देखें</span></a>
    <a class="btn btn-ghost-d" href="{SUBSCRIBE}" target="_blank" rel="noopener">{ICON['bell']}<span>सब्सक्राइब करें</span></a>
  </div>
  {f'<section class="panel"><h2>सारांश</h2>{sum_html}</section>' if sum_html else ''}
  {chap_html}
  {bl_html}
  {cr_html}
  <section class="subscribe mini"><div><h2>हर सुबह की खबरें, सीधे फ़ोन पर</h2><p>YouTube पर {HANDLE} को सब्सक्राइब करें और घंटी दबाएँ।</p></div>
    <a class="btn btn-white" href="{SUBSCRIBE}" target="_blank" rel="noopener">{ICON['yt']}<span>सब्सक्राइब करें</span></a></section>
</div>
<section class="sec k-blue"><div class="wrap"><div class="sec-head"><span class="sec-bar"></span><div><h2>और वीडियो देखें</h2></div><a class="more" href="/archive/">सभी देखें {ICON['arrow']}</a></div>
<div class="grid">{rel_html}</div></div></section>
</main>
{footer()}"""
    d = ROOT / "news" / v["id"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(
        head(page_title, meta_desc, f"/news/{v['id']}/", image=thumb(v, "maxres"), extra=extra, og_type="video.other") + body,
        encoding="utf8")


def build_archive(vids):
    chips = '<button class="fchip on" data-k="all">सभी</button>' + "".join(
        f'<button class="fchip {cls}" data-k="{k}">{lab}</button>' for k, (lab, cls, _) in KINDS.items())
    cards = "".join(card(v) for v in vids)
    title = f"सभी वीडियो, आज की ताज़ा खबर आर्काइव | {NAME}"
    desc = f"{NAME} के सभी बुलेटिन, 100 ख़बरें, पूरी कहानी और शॉर्ट्स एक जगह। तारीख़ के हिसाब से पिछली खबरें देखें।"
    extra = ld({"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "url": SITE + "/archive/",
                "inLanguage": "hi", "isPartOf": {"@id": SITE + "/#site"}})
    body = f"""{header()}
<main id="main" class="archive">
<div class="wrap">
  <h1>सभी वीडियो</h1>
  <p class="lead-d">तारीख़ के हिसाब से हमारे सभी बुलेटिन और खास रिपोर्ट।</p>
  <div class="filters" role="group" aria-label="वीडियो प्रकार">{chips}</div>
  <div class="grid" id="all">{cards}</div>
  <p class="more-yt">और पुराने वीडियो के लिए <a href="{YT}/videos" target="_blank" rel="noopener">हमारा YouTube चैनल</a> देखें।</p>
</div>
</main>
{footer()}"""
    d = ROOT / "archive"
    d.mkdir(exist_ok=True)
    (d / "index.html").write_text(head(title, desc, "/archive/", extra=extra) + body, encoding="utf8")


def build_legal():
    pages = {
        "privacy-policy.html": ("Privacy Policy", (ROOT / "content" / "privacy.html").read_text(encoding="utf8")),
        "terms.html": ("Terms of Service", (ROOT / "content" / "terms.html").read_text(encoding="utf8")),
    }
    for fn, (name, content) in pages.items():
        title = f"{name} | {NAME}"
        desc = f"{NAME} {name}: how this website and our publishing tool handle data."
        body = f"""{header()}
<main id="main" class="legal"><div class="wrap narrow2"><h1>{name}</h1>{content}</div></main>
{footer()}"""
        (ROOT / fn).write_text(head(title, desc, "/" + fn) + body, encoding="utf8")


def build_misc(vids):
    urls = [(SITE + "/", vids[0]["published"], None), (SITE + "/archive/", vids[0]["published"], None),
            (SITE + "/privacy-policy.html", None, None), (SITE + "/terms.html", None, None)]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">']
    for u, lm, _ in urls:
        xml.append(f"<url><loc>{u}</loc>" + (f"<lastmod>{lm[:10]}</lastmod>" if lm else "") + "</url>")
    for v in vids:
        ttl = clean_title(v["title"])
        _, paras, _, _ = parse_desc(v["desc"])
        d = (paras[0] if paras else ttl)[:1500]
        xml.append(
            f"<url><loc>{watch_url(v)}</loc><lastmod>{v['published'][:10]}</lastmod><video:video>"
            f"<video:thumbnail_loc>{thumb(v,'maxres')}</video:thumbnail_loc><video:title>{esc(ttl)[:100]}</video:title>"
            f"<video:description>{esc(d)}</video:description>"
            f"<video:player_loc>https://www.youtube.com/embed/{v['id']}</video:player_loc>"
            f"<video:publication_date>{v['published']}</video:publication_date></video:video></url>")
    xml.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(xml), encoding="utf8")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n", encoding="utf8")
    (ROOT / "manifest.webmanifest").write_text(json.dumps({
        "name": NAME, "short_name": "Daily Bharat", "lang": "hi", "start_url": "/", "display": "standalone",
        "background_color": "#0a1233", "theme_color": "#0a1233",
        "icons": [{"src": "/assets/img/favicon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "/assets/img/icon-512.png", "sizes": "512x512", "type": "image/png"}]}, ensure_ascii=False), encoding="utf8")
    body = f"""{header()}
<main id="main" class="legal"><div class="wrap narrow2 nf"><h1>यह पेज नहीं मिला</h1>
<p>आप जो खोज रहे थे वह यहाँ नहीं है। ताज़ा खबरों के लिए होम पेज पर जाएँ या हमारा YouTube चैनल देखें।</p>
<div class="cta-row"><a class="btn btn-red" href="/">होम पेज</a><a class="btn btn-ghost-d" href="{YT}" target="_blank" rel="noopener">YouTube चैनल</a></div></div></main>
{footer()}"""
    (ROOT / "404.html").write_text(
        head(f"पेज नहीं मिला | {NAME}", "यह पेज नहीं मिला।", "/404.html").replace('index,follow', 'noindex') + body, encoding="utf8")


def main():
    vids = load_videos()
    if not vids:
        sys.exit("no videos available")
    build_home(vids)
    for v in vids:
        build_watch(v, vids)
    build_archive(vids)
    build_legal()
    build_misc(vids)
    print(f"built {len(vids)} videos")


if __name__ == "__main__":
    main()
