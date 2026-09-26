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
FACEBOOK = "https://www.facebook.com/dailybharat10/"   # the Page, not the personal profile
INSTAGRAM = "https://www.instagram.com/dailybharat10/"
FEED = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
NAME = "Daily Bharat News"
EMAIL = "dailybharat10@gmail.com"
DATA = ROOT / "data" / "videos.json"
IST = timezone(timedelta(hours=5, minutes=30))
WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTH = ["January", "February", "March", "April", "May", "June", "July", "August",
         "September", "October", "November", "December"]

KINDS = {  # key: (label, css colour class, section heading)
    "bulletin": ("Daily Bulletin", "k-saffron", "Today's News Bulletin"),
    "hundred": ("100 News", "k-blue", "100 More Headlines in 10 Minutes"),
    "story": ("Full Story", "k-violet", "Full Story: One News, Explained"),
    "short": ("Short", "k-pink", "Quick Shorts"),
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
    global PLAYLISTS
    try:
        PLAYLISTS = sync_playlists(vids)
    except Exception as exc:  # never lose the video pages over a playlist problem
        print("playlist sync failed:", exc, file=sys.stderr)
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


def seo_parts(desc):
    """The description's own SEO layer: hashtags and the keyword line(s)."""
    tags = list(dict.fromkeys(re.findall(r"#[^\s#]+", desc)))
    kw = []
    for raw in desc.replace("\r", "").split("\n"):
        line = raw.strip()
        if re.match(r"^\d{1,2} \w+ \d{4} \|", line) and ("Aaj Ki" in line or "Khabar" in line or "Hindi" in line):
            kw.append(line)
    return tags, kw


def ts_seconds(ts):
    parts = [int(x) for x in ts.split(":")]
    s = 0
    for p in parts:
        s = s * 60 + p
    return s


def autolink(text):
    return re.sub(r"(https?://[^\s<]+)", r'<a href="\1" rel="nofollow noopener" target="_blank">\1</a>', esc(text))


# ------------------------------------------------------- translations ---
# data/translations.json maps video id -> English title/summary/chapters/bullets/
# keywords. Written by translate.py; a video without an entry falls back to its
# original Hindi text (tagged lang="hi") so nothing is ever blank.
TR_FILE = ROOT / "data" / "translations.json"
TR = json.loads(TR_FILE.read_text(encoding="utf8")) if TR_FILE.exists() else {}


def vt(v):
    return (TR.get(v["id"], {}).get("title") or "").strip() or clean_title(v["title"])


def vl(v):
    return "" if (TR.get(v["id"], {}).get("title") or "").strip() else ' lang="hi"'


def tr_list(v, key, orig):
    """(items, lang_attr): the English list if it matches the original's length, else the original."""
    t = TR.get(v["id"], {}).get(key)
    if t and len(t) == len(orig) and all(str(x).strip() for x in t):
        return list(t), ""
    return list(orig), ' lang="hi"'


# -------------------------------------------------------------- layout ---
NAV = [("/", "Home"), ("/#bulletin", "Daily Bulletin"), ("/#hundred", "100 News"),
       ("/current-affairs/", "Current Affairs"), ("/topics/", "Topics"), ("/archive/", "All Videos"), ("/#about", "About")]


def hi(s):
    """Hindi content (video titles, summaries) is tagged lang=hi inside the English page."""
    return f'<span lang="hi">{esc(s)}</span>'


def head(title, desc, path, image=None, extra="", og_type="website"):
    image = image or f"{SITE}/assets/img/og-default.png"
    url = SITE + path
    return f"""<!DOCTYPE html>
<html lang="en">
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
<meta property="og:locale" content="en_IN">
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
    "sameAs": [YT, f"https://www.youtube.com/channel/{CHANNEL_ID}", FACEBOOK, INSTAGRAM],
    "email": EMAIL,
    "description": "A daily Hindi news bulletin on YouTube covering India and the world.",
    "ethicsPolicy": SITE + "/#about",
}


def header(active_path=""):
    links = "".join(f'<a href="{h}">{esc(t)}</a>' for h, t in NAV)
    return f"""<body>
<a class="skip" href="#main">Skip to main content</a>
<div class="tricolor" aria-hidden="true"></div>
<header class="site-header">
  <div class="wrap bar">
    <a class="brand" href="/" aria-label="{NAME} - Home"><img src="/assets/img/logo-mark.webp" width="120" height="63" alt="Daily Bharat logo" fetchpriority="high"></a>
    <nav class="nav" id="nav" aria-label="Main menu">{links}</nav>
    <a class="btn btn-red btn-sm" href="{SUBSCRIBE}" target="_blank" rel="noopener">{ICON['yt']}<span>Subscribe</span></a>
    <button class="menu-btn" aria-label="Open menu" aria-expanded="false" aria-controls="nav">{ICON['menu']}</button>
  </div>
</header>
<script src="https://apis.google.com/js/platform.js" async defer></script>
"""


def yt_subscribe_widget(layout="full", count="default", cls="yt-sub-widget"):
    """YouTube's own subscribe button (Google-hosted): it already knows whether the
    visitor is subscribed and shows "Subscribed" for them automatically, with no
    detection logic of our own — that state is private and our JS can't read it.
    The loader script (apis.google.com/js/platform.js) is loaded once, in header()
    since that runs on every page; callers here only need the button's own div."""
    return (f'<div class="{cls}"><div class="g-ytsubscribe" data-channelid="{CHANNEL_ID}" '
            f'data-layout="{layout}" data-count="{count}"></div></div>')


def ticker(vids):
    items = [v for v in vids if v["kind"] in ("bulletin", "hundred", "story")][:8]
    if not items:
        return ""
    row = "".join(f'<a href="/news/{v["id"]}/"{vl(v)}>{esc(vt(v))}</a>' for v in items)
    return f"""<div class="ticker" role="region" aria-label="Latest videos">
  <span class="ticker-tag">LATEST</span>
  <div class="ticker-track"><div class="ticker-move">{row}{row}</div></div>
</div>
"""


def footer():
    yr = datetime.now(IST).year
    return f"""<footer class="site-footer">
  <div class="wrap foot-grid">
    <div>
      <img src="/assets/img/logo-lockup.webp" width="200" height="127" alt="{NAME} logo" loading="lazy">
      <p class="muted-l">The big news from India and the world, in simple Hindi, every morning.</p>
    </div>
    <div>
      <h3>Watch</h3>
      <a href="{YT}" target="_blank" rel="noopener">YouTube channel {HANDLE}</a>
      <a href="{SUBSCRIBE}" target="_blank" rel="noopener">Subscribe</a>
      <a href="{YT}/videos" target="_blank" rel="noopener">All videos on YouTube</a>
      <a href="{YT}/shorts" target="_blank" rel="noopener">Shorts</a>
    </div>
    <div>
      <h3>Follow us</h3>
      <a href="{FACEBOOK}" target="_blank" rel="noopener">Facebook Page</a>
      <a href="{INSTAGRAM}" target="_blank" rel="noopener">Instagram {HANDLE}</a>
    </div>
    <div>
      <h3>Website</h3>
      <a href="/current-affairs/">Daily current affairs</a>
      <a href="/topics/">Topics</a>
      <a href="/archive/">Video archive</a>
      <a href="/privacy-policy.html">Privacy Policy</a>
      <a href="/terms.html">Terms of Service</a>
      <a href="mailto:{EMAIL}">{EMAIL}</a>
    </div>
  </div>
  <div class="wrap foot-note">
    <p>&copy; {yr} {NAME}. All videos are on our YouTube channel. Some visuals may be AI-generated symbolic images; this is always stated in the video description.</p>
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
  <div class="thumb" data-id="{v['id']}" data-subscribe="1">
    <button class="player-btn" type="button" aria-label="Play video: {esc(vt(v))}">
      <img src="{thumb(v)}" width="480" height="270" loading="lazy" decoding="async" alt="{esc(vt(v))}">
      <span class="play">{ICON['play']}</span>{badge}
    </button>
    <noscript><a href="https://www.youtube.com/watch?v={v['id']}">Watch on YouTube</a></noscript>
  </div>
  <div class="card-body">
    <h3><a href="/news/{v['id']}/"{vl(v)}>{esc(vt(v))}</a></h3>
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
      <a class="more" href="/archive/?k={kind}">View all {ICON['arrow']}</a></div>
    <div class="grid {'grid-short' if kind=='short' else ''}">{cards}</div>
  </div>
</section>
"""


FAQ = [
    ("Where can I watch today's Hindi news bulletin?",
     f"A new bulletin is published every morning on our YouTube channel {HANDLE}, with about 50 top stories from India and the world. The newest video is always at the top of this website's home page."),
    ("Is Daily Bharat News only in Hindi?",
     "Yes. The bulletin, the on-screen text and the voice are all in simple Hindi. News from English-language sources is translated into Hindi before it is shown. This website's menus are in English so it is easy to find your way; video titles stay in Hindi, exactly as on YouTube."),
    ("Where does the news come from?",
     "From government releases (such as the Press Information Bureau) and leading Hindi and English newspapers. We do not cover party-versus-party attacks or communal disputes; the focus is on policies, schemes and facts."),
    ("What is '100 News in 10 Minutes'?",
     "After the main bulletin we publish a second, faster video with the rest of the day's roughly 100 headlines, so you can get the full picture of the day in 10 minutes."),
    ("Can I use this for UPSC, SSC, bank or state exam current affairs?",
     "Many aspirants watch it as a quick daily revision of what happened, because the bulletin covers government decisions, schemes, appointments, agreements and world news. It is a news bulletin, not a full exam-preparation course, so use it alongside your regular study material. See the Current Affairs page for how it is organised."),
    ("Do the videos use AI?",
     "Some videos use AI-generated symbolic images. Every such video says so clearly in its description, and real photographs are credited."),
    ("How do I make sure I never miss a video?",
     "Subscribe to the channel on YouTube, tap the bell icon and choose \"All\". Every new bulletin then arrives as a notification on your phone."),
]


def build_home(vids):
    latest = next((v for v in vids if v["kind"] == "bulletin"), vids[0])
    title = "Daily Bharat News: Today's Hindi News Bulletin, Top India & World Headlines"
    desc = ("Watch the Daily Bharat News Hindi bulletin every morning: about 50 top headlines from India and the world, "
            "plus 100 more in 10 minutes. Aaj ki taaza khabar, markets, gold and silver rates and state news. Subscribe on YouTube.")
    items = [v for v in vids if v["kind"] != "short"][:10]
    graph = [
        ORG,
        {"@type": "WebSite", "@id": SITE + "/#site", "url": SITE + "/", "name": NAME, "inLanguage": "en",
         "publisher": {"@id": SITE + "/#org"}},
        {"@type": "WebPage", "@id": SITE + "/#page", "url": SITE + "/", "name": title, "description": desc, "inLanguage": "en",
         "isPartOf": {"@id": SITE + "/#site"}, "about": {"@id": SITE + "/#org"}},
        {"@type": "ItemList", "name": "Latest videos", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "url": watch_url(v), "name": vt(v)}
            for i, v in enumerate(items)]},
        {"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
    ]
    extra = ld({"@context": "https://schema.org", "@graph": graph})
    faq = "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in FAQ)
    why = [
        ("clock", "c-saffron", "On time, every morning", "A fresh bulletin is ready every morning, so you have the whole day's news with your tea."),
        ("lang", "c-blue", "Simple Hindi", "Easy language, a clear voice and readable on-screen text. No difficult words."),
        ("shield", "c-green", "Facts, not noise", "No party-versus-party attacks or communal disputes. Policies, schemes and real information."),
        ("paper", "c-violet", "Trusted sources", "News from government releases and leading newspapers, all in one bulletin."),
    ]
    why_html = "".join(
        f'<div class="why {c}"><span class="why-ic">{ICON[i]}</span><h3>{t}</h3><p>{p}</p></div>' for i, c, t, p in why)
    hero_card = f"""<div class="feature">
      <span class="feature-tag">Latest bulletin</span>
      <div class="player feature-img" data-id="{latest['id']}" data-subscribe="1">
        <button class="player-btn" type="button" aria-label="Play video: {esc(vt(latest))}">
          <img src="{thumb(latest,'maxres')}" onerror="this.onerror=null;this.src='{thumb(latest)}'" width="1280" height="720" alt="{esc(vt(latest))}" fetchpriority="high">
          <span class="play big">{ICON['play']}</span>
        </button>
        <noscript><a href="https://www.youtube.com/watch?v={latest['id']}">Watch on YouTube</a></noscript>
      </div>
      <a class="feature-body" href="/news/{latest['id']}/"><strong{vl(latest)}>{esc(vt(latest))}</strong><time datetime="{latest['published']}">{hi_date(latest['published'])}</time></a>
    </div>"""
    body = f"""{header()}
{ticker(vids)}
<main id="main">
<section class="hero">
  <div class="hero-glow" aria-hidden="true"></div>
  <div class="wrap hero-grid">
    <div class="hero-copy">
      <p class="eyebrow">Daily Hindi news bulletin &middot; {HANDLE}</p>
      <h1>The <span class="grad">biggest news</span> from India and the world, every morning, in simple Hindi</h1>
      <p class="lead">Today's top headlines (aaj ki taaza khabar), national and international news, markets, gold and silver rates and state news, all in one short bulletin. Watch on YouTube and never miss a new video.</p>
      <div class="cta-row">
        <a class="btn btn-red" href="{SUBSCRIBE}" target="_blank" rel="noopener">{ICON['yt']}<span>Subscribe on YouTube</span></a>
        <a class="btn btn-ghost" href="/news/{latest['id']}/">{ICON['play']}<span>Watch today's bulletin</span></a>
      </div>
      <ul class="chips">
        <li class="c-saffron">New bulletin every morning</li>
        <li class="c-green">About 50 top stories</li>
        <li class="c-blue">100 more in 10 minutes</li>
        <li class="c-pink">Simple Hindi</li>
      </ul>
    </div>
    <div class="hero-card">{hero_card}</div>
  </div>
</section>
{section('bulletin','bulletin',vids,4,"The morning's top stories: national, international, markets and states.")}
{section('hundred','hundred',vids,3,"More news in less time: the rest of the day's headlines.")}
{section('stories','story',vids,6,"One big story, investigated and explained clearly.")}
{section('shorts','short',vids,6)}
{topics_section(vids)}
<section class="sec why-sec">
  <div class="wrap">
    <div class="sec-head center"><div><h2>Why watch Daily Bharat News?</h2><p>Less time, more news. We save yours.</p></div></div>
    <div class="why-grid">{why_html}</div>
  </div>
</section>
<section class="subscribe" id="subscribe">
  <div class="wrap sub-grid">
    <div>
      <h2>Never miss a story</h2>
      <p>Subscribe to the channel and tap the bell. Every morning's bulletin comes straight to your phone.</p>
      <ol class="steps">
        <li><b>1</b> Open {HANDLE} on YouTube</li>
        <li><b>2</b> Tap <em>Subscribe</em></li>
        <li><b>3</b> Tap the bell {ICON['bell']} and choose <em>All</em></li>
      </ol>
      <div class="cta-row">
        <a class="btn btn-white" href="{SUBSCRIBE}" target="_blank" rel="noopener">{ICON['yt']}<span>Subscribe now</span></a>
        <a class="btn btn-outline" href="{YT}" target="_blank" rel="noopener"><span>Open channel</span>{ICON['arrow']}</a>
      </div>
    </div>
    <div class="sub-art" aria-hidden="true"><div class="bell">{ICON['bell']}</div><div class="ring r1"></div><div class="ring r2"></div></div>
  </div>
</section>
<section class="sec faq-sec" id="faq">
  <div class="wrap narrow">
    <div class="sec-head center"><div><h2>Frequently asked questions</h2></div></div>
    <div class="faq">{faq}</div>
  </div>
</section>
<section class="sec about" id="about">
  <div class="wrap narrow">
    <h2>About Daily Bharat News</h2>
    <p><strong>{NAME}</strong> is a Hindi news channel. Every morning we publish the day's main news from India and the world, in simple Hindi, as one bulletin on YouTube. News is drawn from government releases and leading newspapers.</p>
    <p class="fine">About this website: this is the official home page of the {NAME} channel. Our own publishing tool uses Google's YouTube APIs only to upload videos to our own channel and to read our own channel's analytics. It is used only by the channel owner, offers no public sign-in, and collects no data from visitors or viewers. See the <a href="/privacy-policy.html">Privacy Policy</a> and <a href="/terms.html">Terms of Service</a>. Contact: <a href="mailto:{EMAIL}">{EMAIL}</a>.</p>
  </div>
</section>
</main>
{footer()}"""
    (ROOT / "index.html").write_text(head(title, desc, "/", extra=extra) + body, encoding="utf8")


def build_watch(v, vids):
    label, cls, _ = KINDS[v["kind"]]
    ttl = vt(v)
    chapters, paras, bullets, credits = parse_desc(v["desc"])
    tags, kwlines = seo_parts(v["desc"])
    chap_names, chap_lang = tr_list(v, "chapters", [n for _, n in chapters])
    paras3, para_lang = tr_list(v, "summary", paras[:3])
    bullets_e, bul_lang = tr_list(v, "bullets", bullets[:120])
    kw_e, kw_lang = tr_list(v, "keywords", kwlines)
    paras = paras3 + paras[3:]
    phrases = [p.strip() for ln in kwlines for p in ln.split("|")[-1].split(",") if p.strip()]
    summary = paras[0] if paras else ""
    dline = hi_date(v["published"])
    meta_desc = f"{label} from Daily Bharat News, {dline}: {ttl}. " + (summary[:120] + "…" if summary else "Watch on YouTube.")
    page_title = f"{ttl} | {label}, {dline} | {NAME}"
    url = watch_url(v)
    video_ld = {
        "@context": "https://schema.org", "@type": "VideoObject", "name": ttl,
        "description": (summary or ttl)[:500], "thumbnailUrl": [thumb(v, "maxres"), thumb(v)],
        "uploadDate": v["published"], "embedUrl": f"https://www.youtube.com/embed/{v['id']}",
        "url": url, "inLanguage": "hi", "publisher": ORG,
        "isFamilyFriendly": True,
        "keywords": ", ".join(dict.fromkeys([t.lstrip("#") for t in tags] + phrases))[:500],
    }
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
        {"@type": "ListItem", "position": 2, "name": "Videos", "item": SITE + "/archive/"},
        {"@type": "ListItem", "position": 3, "name": ttl, "item": url}]}
    extra = ld(video_ld) + ld(crumbs)
    chap_html = ""
    if chapters:
        rows = "".join(
            f'<li><a href="https://www.youtube.com/watch?v={v["id"]}&amp;t={ts_seconds(t)}s" target="_blank" rel="noopener"><b>{t}</b> <span{chap_lang}>{esc(n)}</span></a></li>'
            for (t, _), n in zip(chapters, chap_names))
        chap_html = f'<section class="panel"><h2>What is in this video</h2><ol class="chapters">{rows}</ol></section>'
    sum_html = "".join(f'<p{para_lang}>{esc(p)}</p>' for p in paras3)
    bl_html = ""
    if bullets:
        bl_html = ('<section class="panel"><h2>Headlines covered</h2><ul class="heads">'
                   + "".join(f'<li{bul_lang}>{esc(b)}</li>' for b in bullets_e) + "</ul></section>")
    cr_html = ""
    en_credits = []
    for c in credits:  # credit lines are bilingual "Hindi / English": keep the English half
        if " / " not in c and re.search("[ऀ-ॿ]", c):
            continue  # a Hindi/English keyword line, not a credit
        english = [p.strip() for p in c.split(" / ") if re.search(r"[A-Za-z]", p)]
        if english:
            line = re.sub(r"\s*\([^)]*[ऀ-ॿ][^)]*\)", "", english[-1]).strip()
            if line:
                en_credits.append(line)
    if not any(("http" in c or "AI-generated" in c) for c in en_credits):
        en_credits = []
    credits = en_credits
    if credits:
        cr_html = '<section class="panel credits"><h2>Image credits</h2>' + "".join(f"<p>{autolink(c)}</p>" for c in credits) + "</section>"
    kw_html = ""
    if kwlines or any(re.fullmatch(r"#[A-Za-z0-9_]+", t) for t in tags):
        kw_html = ('<section class="panel seo"><h2>Video keywords and tags</h2>'
                   + "".join(f'<p{kw_lang}>{esc(k)}</p>' for k in kw_e)
                   + ('<p class="tags">' + " ".join(f'<span>{esc(t)}</span>' for t in tags if re.fullmatch(r"#[A-Za-z0-9_]+", t)) + "</p>" if tags else "")
                   + "</section>")
    related = [x for x in vids if x["id"] != v["id"] and x["kind"] != "short"][:6]
    rel_html = "".join(card(x) for x in related)
    body = f"""{header()}
<main id="main" class="watch">
<div class="wrap narrow2">
  <nav class="crumbs" aria-label="Breadcrumb"><a href="/">Home</a> / <a href="/archive/">Videos</a> / <span>{label}</span></nav>
  <span class="badge {cls}">{label}</span>
  <h1{vl(v)}>{esc(ttl)}</h1>
  <p class="meta"><time datetime="{v['published']}">{dline}</time> &middot; {label} &middot; Hindi news by {NAME}</p>
  {topic_chips(v, vids)}
  <div class="player {'player-short' if v['kind']=='short' else ''}" data-id="{v['id']}" data-subscribe="1">
    <button class="player-btn" type="button" aria-label="Play video: {esc(ttl)}">
      <img src="{thumb(v,'maxres')}" onerror="this.onerror=null;this.src='{thumb(v)}'" width="1280" height="720" alt="{esc(ttl)}">
      <span class="play big">{ICON['play']}</span>
    </button>
    <noscript><a href="https://www.youtube.com/watch?v={v['id']}">Watch on YouTube</a></noscript>
  </div>
  {yt_subscribe_widget()}
  <div class="cta-row center-row">
    <a class="btn btn-red" href="https://www.youtube.com/watch?v={v['id']}" target="_blank" rel="noopener">{ICON['yt']}<span>Watch on YouTube</span></a>
    <a class="btn btn-ghost-d" href="{SUBSCRIBE}" target="_blank" rel="noopener">{ICON['bell']}<span>Subscribe</span></a>
  </div>
  {f'<section class="panel"><h2>Summary</h2>{sum_html}</section>' if sum_html else ''}
  {chap_html}
  {bl_html}
  {kw_html}
  {cr_html}
  <section class="subscribe mini"><div><h2>Get every morning's news on your phone</h2><p>Subscribe to {HANDLE} on YouTube and tap the bell.</p></div>
    <a class="btn btn-white" href="{SUBSCRIBE}" target="_blank" rel="noopener">{ICON['yt']}<span>Subscribe</span></a></section>
</div>
<section class="sec k-blue"><div class="wrap"><div class="sec-head"><span class="sec-bar"></span><div><h2>More videos</h2></div><a class="more" href="/archive/">View all {ICON['arrow']}</a></div>
<div class="grid">{rel_html}</div></div></section>
</main>
{footer()}"""
    d = ROOT / "news" / v["id"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(
        head(page_title, meta_desc, f"/news/{v['id']}/", image=thumb(v, "maxres"), extra=extra, og_type="video.other") + body,
        encoding="utf8")


def build_archive(vids):
    chips = '<button class="fchip on" data-k="all">All</button>' + "".join(
        f'<button class="fchip {cls}" data-k="{k}">{lab}</button>' for k, (lab, cls, _) in KINDS.items())
    cards = "".join(card(v) for v in vids)
    title = f"All Videos: Daily Hindi News Bulletin Archive | {NAME}"
    desc = f"Every {NAME} bulletin, 100 News video, full story and Short in one place. Browse past Hindi news by date."
    extra = ld({"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "url": SITE + "/archive/",
                "inLanguage": "en", "isPartOf": {"@id": SITE + "/#site"}})
    body = f"""{header()}
<main id="main" class="archive">
<div class="wrap">
  <h1>All videos</h1>
  <p class="lead-d">Every bulletin and special report, by date.</p>
  <div class="filters" role="group" aria-label="Video type">{chips}</div>
  <div class="grid" id="all">{cards}</div>
  <p class="more-yt">For older videos, visit <a href="{YT}/videos" target="_blank" rel="noopener">our YouTube channel</a>.</p>
</div>
</main>
{footer()}"""
    d = ROOT / "archive"
    d.mkdir(exist_ok=True)
    (d / "index.html").write_text(head(title, desc, "/archive/", extra=extra) + body, encoding="utf8")


# ------------------------------------------------------------- topics ---
# Every public YouTube playlist on the channel becomes a "topic" on the site
# (Gold & Silver Rates, Share Market, International, ... and any future
# Finance / Lifestyle / etc.). Nothing here is hard-coded per topic: a new
# playlist on the channel appears on the next scheduled build.
PL_FILE = ROOT / "data" / "playlists.json"
PLAYLISTS: list[dict] = []
PALETTE = 8


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (dailybharat10.com site build)",
                                               "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def discover_playlist_ids():
    """Public playlist ids from the channel's Playlists tab (order preserved)."""
    page = _get(YT + "/playlists").decode("utf8", "replace")
    return list(dict.fromkeys(re.findall(r'"contentId":"(PL[\w-]+)"', page)))


def fetch_playlist(pid):
    root = ET.fromstring(_get(f"https://www.youtube.com/feeds/videos.xml?playlist_id={pid}"))
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
          "m": "http://search.yahoo.com/mrss/"}
    vids = []
    for e in root.findall("a:entry", ns):
        vids.append({"id": e.find("yt:videoId", ns).text, "title": e.find("a:title", ns).text or "",
                     "published": e.find("a:published", ns).text,
                     "desc": e.find("m:group/m:description", ns).text or ""})
    return root.find("a:title", ns).text or pid, vids


def sync_playlists(vids):
    """Refresh playlists (stored list + newly discovered), fold their videos into `vids`."""
    stored = {}
    if PL_FILE.exists():
        stored = {p["id"]: p for p in json.loads(PL_FILE.read_text(encoding="utf8"))}
    try:
        ids = list(dict.fromkeys(discover_playlist_ids() + list(stored)))
    except Exception as exc:  # layout change / offline: keep what we know
        print("playlist discovery failed, using stored list:", exc, file=sys.stderr)
        ids = list(stored)
    out = []
    for pid in ids:
        p = stored.get(pid) or {"id": pid, "color": len(stored) % PALETTE, "video_ids": []}
        try:
            title, pv = fetch_playlist(pid)
            p["title"] = title
            for v in pv:
                vids.setdefault(v["id"], v)
            p["video_ids"] = list(dict.fromkeys([v["id"] for v in pv] + p.get("video_ids", [])))
        except Exception as exc:
            if "title" not in p:
                print("skipping playlist", pid, exc, file=sys.stderr)
                continue
            print("playlist fetch failed, keeping stored data:", pid, exc, file=sys.stderr)
        stored[pid] = p
        out.append(p)
    used = set()
    for p in out:  # slugs are assigned once and never change afterwards
        if not p.get("slug") or p["slug"] in used:
            base = re.sub(r"[^a-z0-9]+", "-", pl_en(p).lower()).strip("-") or p["id"].lower()
            slug, n = base, 2
            while slug in used:
                slug, n = f"{base}-{n}", n + 1
            p["slug"] = slug
        used.add(p["slug"])
    PL_FILE.parent.mkdir(exist_ok=True)
    PL_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf8")
    return out


def _segments(p):
    return [x.strip() for x in p.get("title", "").split("|") if x.strip()]


def pl_en(p):
    segs = _segments(p)
    return next((x for x in segs if re.search(r"[A-Za-z]", x)), segs[0] if segs else p.get("id", ""))


def pl_hi(p):
    return next((x for x in _segments(p) if re.search("[ऀ-ॿ]", x) and x != pl_en(p)), "")


def pl_url(p):
    return f"{SITE}/topics/{p['slug']}/"


def pl_videos(p, vids):
    byid = {v["id"]: v for v in vids}
    return sorted((byid[i] for i in p["video_ids"] if i in byid), key=lambda v: v["published"], reverse=True)


def topic_card(p, vids):
    vs = pl_videos(p, vids)
    if not vs:
        return ""
    hi_name = ""
    return f"""<a class="tcard p-{p['color'] % PALETTE}" href="/topics/{p['slug']}/">
  <span class="t-img"><img src="{thumb(vs[0])}" width="480" height="270" loading="lazy" decoding="async" alt="{esc(pl_en(p))}"><span class="t-count">{len(vs)} videos</span></span>
  <span class="t-body"><strong>{esc(pl_en(p))}</strong>{hi_name}</span>
</a>
"""


def build_topics(vids):
    live = [p for p in PLAYLISTS if pl_videos(p, vids)]
    cards = "".join(topic_card(p, vids) for p in live)
    title = f"Topics: Gold Rates, Share Market, World News & More | {NAME}"
    desc = f"Browse {NAME} by topic: " + ", ".join(pl_en(p) for p in live[:5]) + " and more. Hindi news videos on YouTube."
    extra = ld({"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "url": SITE + "/topics/",
                "inLanguage": "en", "isPartOf": {"@id": SITE + "/#site"}})
    body = f"""{header()}
<main id="main" class="archive">
<div class="wrap">
  <h1>Browse by topic</h1>
  <p class="lead-d">Every series on our YouTube channel in one place. New topics appear here automatically.</p>
  <div class="tgrid">{cards}</div>
</div>
</main>
{footer()}"""
    d = ROOT / "topics"
    d.mkdir(exist_ok=True)
    (d / "index.html").write_text(head(title, desc, "/topics/", extra=extra) + body, encoding="utf8")
    for p in live:
        build_topic(p, vids)


def build_topic(p, vids):
    vs = pl_videos(p, vids)
    name, hin = pl_en(p), pl_hi(p)
    title = f"{name} | Hindi News Videos | {NAME}"
    desc = f"{name}: watch the {len(vs)} latest videos in this {NAME} series. Latest: {vt(vs[0])}."[:300]
    yt_pl = f"https://www.youtube.com/playlist?list={p['id']}"
    extra = ld({"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "name": name, "url": pl_url(p), "description": desc, "inLanguage": "en",
         "isPartOf": {"@id": SITE + "/#site"}, "publisher": {"@id": SITE + "/#org"}},
        {"@type": "ItemList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "url": watch_url(v), "name": vt(v)}
            for i, v in enumerate(vs[:20])]},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Topics", "item": SITE + "/topics/"},
            {"@type": "ListItem", "position": 3, "name": name, "item": pl_url(p)}]}]})
    cards = "".join(card(v) for v in vs)
    body = f"""{header()}
<main id="main" class="archive">
<div class="wrap">
  <nav class="crumbs" aria-label="Breadcrumb"><a href="/">Home</a> / <a href="/topics/">Topics</a> / <span>{esc(name)}</span></nav>
  <div class="topic-head p-{p['color'] % PALETTE}">
    <h1>{esc(name)}</h1>
    <p>{len(vs)} videos from {NAME}. Watch the full series on YouTube and subscribe to get each new episode.</p>
    <div class="cta-row">
      <a class="btn btn-white" href="{yt_pl}" target="_blank" rel="noopener">{ICON['yt']}<span>Open playlist on YouTube</span></a>
      <a class="btn btn-outline" href="{SUBSCRIBE}" target="_blank" rel="noopener">{ICON['bell']}<span>Subscribe</span></a>
    </div>
  </div>
  <div class="grid">{cards}</div>
</div>
</main>
{footer()}"""
    d = ROOT / "topics" / p["slug"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(head(title, desc, f"/topics/{p['slug']}/", extra=extra) + body, encoding="utf8")


def topics_section(vids):
    live = [p for p in PLAYLISTS if pl_videos(p, vids)]
    if not live:
        return ""
    cards = "".join(topic_card(p, vids) for p in live[:8])
    return f"""<section class="sec k-teal" id="topics">
  <div class="wrap">
    <div class="sec-head"><span class="sec-bar"></span><div><h2>Browse by Topic</h2><p>Gold and silver rates, share market, world news, weather and more. Pick a series.</p></div>
      <a class="more" href="/topics/">All topics {ICON['arrow']}</a></div>
    <div class="tgrid">{cards}</div>
  </div>
</section>
"""


def topic_chips(v, vids):
    ps = [p for p in PLAYLISTS if v["id"] in p["video_ids"]]
    if not ps:
        return ""
    chips = " ".join(f'<a class="tchip p-{p["color"] % PALETTE}" href="/topics/{p["slug"]}/">{esc(pl_en(p))}</a>' for p in ps)
    return f'<p class="tchips"><span>Series:</span> {chips}</p>'


# ------------------------------------------------- current affairs (exams) ---
# Aimed at students preparing for government / defence / bank / UPSC / state
# exams that carry a current-affairs paper. Honest by design: we are a daily
# news bulletin, not an exam-prep course, and the page says so. The per-state
# table comes from the channel's pipeline (data/exam_states.json, exported from
# core/exam_relevance.py there); the regional-language phrases are search
# keywords only, tagged with their own lang attribute.
EXAM_FILE = ROOT / "data" / "exam_states.json"
EXAM_STATES = json.loads(EXAM_FILE.read_text(encoding="utf8")) if EXAM_FILE.exists() else []

EXAM_TOPICS = [
    ("Government schemes and policies", "New schemes, eligibility, cabinet decisions and PIB releases."),
    ("Appointments and oaths", "Who was appointed, elected or sworn in."),
    ("Awards and honours", "National and international awards and recognitions."),
    ("Summits and agreements", "Bilateral visits, MoUs and international meetings."),
    ("Indices, reports and rankings", "Surveys, reports and where India stands."),
    ("Defence and security", "Exercises, missile tests and defence deals."),
    ("Science and technology", "Space missions, launches and new technology."),
    ("Economy and markets", "RBI decisions, budget and GST updates, market movement."),
    ("Sports", "Major results and tournaments."),
]

EXAM_FAQ = [
    ("Is Daily Bharat News a complete current affairs course?",
     "No. It is a daily Hindi news bulletin. We flag the exam-useful stories from the day's news, but we do not cover every story and we skip party-versus-party and communal disputes, so use it as quick daily revision next to your regular study material and official notifications."),
    ("Which exams is this useful for?",
     "Students preparing for UPSC, SSC CGL and CHSL, IBPS and SBI bank exams, RRB NTPC, NDA, CDS, CAPF, Agniveer, CUET and state exams such as State PSC, state police, patwari and teaching (TET/CTET) exams, wherever there is a general knowledge or current affairs paper."),
    ("Is the daily current affairs in Hindi or English?",
     "The videos are in simple Hindi. This website is in English so it is easy to find your way around."),
    ("Where can I find today's current affairs?",
     "Watch the latest Daily Bulletin (about 50 top stories) and the 100 News video (the rest of the day's headlines in 10 minutes) listed on this page. Each video's description also lists the exam-useful topics of the day, and a comment under each video recaps them."),
    ("Do you have state-wise current affairs?",
     "Every bulletin includes state news, and we group videos into state playlists on YouTube. The table below lists the main state exam bodies we tag against."),
]


def build_current_affairs(vids):
    ca = [v for v in vids if v["kind"] in ("bulletin", "hundred")]
    bull = [v for v in ca if v["kind"] == "bulletin"][:4]
    hund = [v for v in ca if v["kind"] == "hundred"][:4]
    topics = "".join(f"<li><strong>{esc(a)}</strong>: {esc(b)}</li>" for a, b in EXAM_TOPICS)
    pls = [p for p in PLAYLISTS if "current affairs" in pl_en(p).lower() and pl_videos(p, vids)]
    pl_cards = "".join(topic_card(p, vids) for p in pls)
    rows = ""
    for r in EXAM_STATES:
        reg = (f'<span lang="{r["lang_code"]}">{esc(r["regional"])}</span> ({esc(r["language"])})'
               if r.get("regional") and r.get("lang_code") else "&mdash;")
        rows += (f'<tr><th scope="row">{esc(r["state"])}</th><td>{esc(", ".join(r["bodies"]))}</td>'
                 f'<td>{hi(r["hi"] + " करेंट अफेयर्स")}</td><td>{reg}</td></tr>')
    table = (f'<div class="tbl-wrap"><table class="ca-table"><thead><tr><th>State</th><th>Exam bodies</th>'
             f'<th>In Hindi</th><th>In the state language</th></tr></thead><tbody>{rows}</tbody></table></div>'
             if rows else "")
    title = "Daily Current Affairs in Hindi for UPSC, SSC, Bank, Railway, Defence & State Exams | " + NAME
    desc = ("Daily current affairs in Hindi from the day's news for UPSC, SSC CGL, IBPS, SBI, RRB NTPC, NDA, CDS, Agniveer and "
            "State PSC aspirants: schemes, appointments, agreements, defence, economy and more. Watch the latest bulletin free.")
    url = SITE + "/current-affairs/"
    extra = ld({"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "name": title, "url": url, "description": desc, "inLanguage": "en",
         "isPartOf": {"@id": SITE + "/#site"}, "publisher": {"@id": SITE + "/#org"}},
        {"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in EXAM_FAQ]},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Current Affairs", "item": url}]}]})
    faq = "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in EXAM_FAQ)

    def block(heading, vs):
        return (f'<h2>{heading}</h2><div class="grid">{"".join(card(v) for v in vs)}</div>' if vs else "")

    body = f"""{header()}
<main id="main" class="archive ca">
<div class="wrap">
  <nav class="crumbs" aria-label="Breadcrumb"><a href="/">Home</a> / <span>Current Affairs</span></nav>
  <h1>Daily current affairs in Hindi</h1>
  <p class="lead-d">For students preparing for UPSC, SSC, bank, railway, defence (NDA, CDS, CAPF, Agniveer) and state government exams.
  Every day's news, with the exam-useful stories called out.</p>
  <div class="cta-row"><a class="btn btn-red" href="{SUBSCRIBE}" target="_blank" rel="noopener">{ICON['bell']}<span>Subscribe for daily updates</span></a></div>
  {block("Latest Daily Bulletin", bull)}
  {block("Latest 100 News in 10 minutes", hund)}
  <h2>What we flag as exam-useful</h2>
  <p>We are a daily news bulletin, not a full exam-preparation course. Each day we list the categories below that today's stories genuinely fall in, in the video description and in a comment under the video.</p>
  <ul class="ca-list">{topics}</ul>
  {f'<h2>Current affairs playlists</h2><div class="tgrid">{pl_cards}</div>' if pl_cards else ""}
  <h2>State exams</h2>
  <p>Preparing for a state exam? State news is part of every bulletin, and state playlists are on our YouTube channel. Exam bodies we tag against:</p>
  {table}
  <h2>Frequently asked questions</h2>
  <div class="faq">{faq}</div>
</div>
</main>
{footer()}"""
    d = ROOT / "current-affairs"
    d.mkdir(exist_ok=True)
    (d / "index.html").write_text(head(title, desc, "/current-affairs/", extra=extra) + body, encoding="utf8")


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
    urls = [(SITE + "/", vids[0]["published"], None), (SITE + "/archive/", vids[0]["published"], None), (SITE + "/topics/", vids[0]["published"], None),
            (SITE + "/current-affairs/", vids[0]["published"], None),
            *[(pl_url(p), None, None) for p in PLAYLISTS if pl_videos(p, vids)],
            (SITE + "/privacy-policy.html", None, None), (SITE + "/terms.html", None, None)]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">']
    for u, lm, _ in urls:
        xml.append(f"<url><loc>{u}</loc>" + (f"<lastmod>{lm[:10]}</lastmod>" if lm else "") + "</url>")
    for v in vids:
        ttl = vt(v)
        _, paras, _, _ = parse_desc(v["desc"])
        paras = tr_list(v, "summary", paras[:3])[0] + paras[3:]
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
<main id="main" class="legal"><div class="wrap narrow2 nf"><h1>Page not found</h1>
<p>The page you were looking for is not here. Go to the home page for the latest news, or visit our YouTube channel.</p>
<div class="cta-row"><a class="btn btn-red" href="/">Home page</a><a class="btn btn-ghost-d" href="{YT}" target="_blank" rel="noopener">YouTube channel</a></div></div></main>
{footer()}"""
    (ROOT / "404.html").write_text(
        head(f"Page not found | {NAME}", "Page not found.", "/404.html").replace('index,follow', 'noindex') + body, encoding="utf8")


def main():
    vids = load_videos()
    if not vids:
        sys.exit("no videos available")
    build_home(vids)
    for v in vids:
        build_watch(v, vids)
    build_archive(vids)
    build_topics(vids)
    build_current_affairs(vids)
    build_legal()
    build_misc(vids)
    print(f"built {len(vids)} videos")


if __name__ == "__main__":
    main()
