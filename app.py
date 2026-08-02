
import calendar
import html as html_lib
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse

import feedparser
import requests
import streamlit as st
import plotly.graph_objects as go
from streamlit.components.v1 import html as components_html


st.set_page_config(
    page_title="JUGG",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

COMPANIES = {
    "Siemens Healthineers": {
        "tickers": ["SHL.DE"],
        "company_queries": ['"Siemens Healthineers"', '"Siemens Healthineers" OR Varian'],
        "sector_queries": [
            '"medical imaging" OR radiotherapy OR diagnostics OR "healthcare equipment"',
            '"medical devices" OR "hospital spending"',
        ],
        "direct_terms": ["siemens healthineers", "varian"],
        "sector_terms": [
            "medical imaging", "radiotherapy", "diagnostics",
            "healthcare equipment", "medical devices", "hospital spending",
        ],
    },
    "ANTA Sports": {
        "tickers": ["2020.HK"],
        "company_queries": ['"ANTA Sports" OR "Anta Sports Products"', '"FILA China" OR "Amer Sports" OR Salomon'],
        "sector_queries": [
            '"China retail sales" OR "Chinese consumer" OR sportswear',
            '"athletic apparel" OR "China consumer demand"',
        ],
        "direct_terms": ["anta sports", "anta sports products", "fila china", "amer sports", "salomon", "arc'teryx"],
        "sector_terms": [
            "china retail sales", "chinese consumer", "consumer demand",
            "sportswear", "athletic apparel", "china retail",
        ],
    },
    "Tomra": {
        "tickers": ["TOM.OL"],
        "company_queries": ['"Tomra Systems" OR "Tomra"', '"Tomra Systems ASA"'],
        "sector_queries": [
            '"deposit return" OR "reverse vending" OR "recycling regulation"',
            '"waste sorting" OR "circular economy" OR "bottle recycling"',
        ],
        "direct_terms": ["tomra", "tomra systems", "tomra systems asa"],
        "sector_terms": [
            "deposit return", "reverse vending", "recycling regulation",
            "waste sorting", "circular economy", "bottle recycling",
        ],
    },
    "Verbund": {
        "tickers": ["VER.VI"],
        "company_queries": ['"Verbund AG" OR "Verbund" electricity', '"Verbund" hydropower OR "Verbund" Austria'],
        "sector_queries": [
            '"European power prices" OR "Austrian electricity" OR hydropower',
            '"electricity prices" OR "energy regulation" OR "renewable power"',
        ],
        "direct_terms": ["verbund ag", "verbund"],
        "sector_terms": [
            "european power prices", "austrian electricity", "hydropower",
            "electricity prices", "energy regulation", "renewable power",
        ],
    },
}

SOURCE_MAPS = {
    "Strict finance sources": {
        "reuters.com": "Reuters", "bloomberg.com": "Bloomberg", "ft.com": "Financial Times",
        "wsj.com": "Wall Street Journal", "cnbc.com": "CNBC", "marketwatch.com": "MarketWatch",
        "morningstar.com": "Morningstar", "barrons.com": "Barron's",
        "siemens-healthineers.com": "Siemens Healthineers", "antagroup.com": "ANTA Sports",
        "tomra.com": "TOMRA", "verbund.com": "VERBUND",
    },
    "Balanced sources": {
        "reuters.com": "Reuters", "bloomberg.com": "Bloomberg", "ft.com": "Financial Times",
        "wsj.com": "Wall Street Journal", "cnbc.com": "CNBC", "marketwatch.com": "MarketWatch",
        "morningstar.com": "Morningstar", "barrons.com": "Barron's", "apnews.com": "Associated Press",
        "bbc.com": "BBC", "bbc.co.uk": "BBC", "dw.com": "Deutsche Welle",
        "euronews.com": "Euronews", "scmp.com": "South China Morning Post",
        "nikkei.com": "Nikkei Asia", "caixinglobal.com": "Caixin Global",
        "finance.yahoo.com": "Yahoo Finance", "investing.com": "Investing.com",
        "marketscreener.com": "MarketScreener", "nasdaq.com": "Nasdaq",
        "globenewswire.com": "GlobeNewswire", "businesswire.com": "Business Wire",
        "prnewswire.com": "PR Newswire",
        "siemens-healthineers.com": "Siemens Healthineers", "antagroup.com": "ANTA Sports",
        "tomra.com": "TOMRA", "verbund.com": "VERBUND",
    },
    "Broad coverage": {
        "reuters.com": "Reuters", "bloomberg.com": "Bloomberg", "ft.com": "Financial Times",
        "wsj.com": "Wall Street Journal", "cnbc.com": "CNBC", "marketwatch.com": "MarketWatch",
        "morningstar.com": "Morningstar", "barrons.com": "Barron's", "apnews.com": "Associated Press",
        "bbc.com": "BBC", "bbc.co.uk": "BBC", "dw.com": "Deutsche Welle",
        "euronews.com": "Euronews", "scmp.com": "South China Morning Post",
        "nikkei.com": "Nikkei Asia", "caixinglobal.com": "Caixin Global",
        "finance.yahoo.com": "Yahoo Finance", "investing.com": "Investing.com",
        "marketscreener.com": "MarketScreener", "nasdaq.com": "Nasdaq",
        "globenewswire.com": "GlobeNewswire", "businesswire.com": "Business Wire",
        "prnewswire.com": "PR Newswire", "seekingalpha.com": "Seeking Alpha",
        "stocktitan.net": "StockTitan", "finanznachrichten.de": "FinanzNachrichten",
        "zacks.com": "Zacks", "fool.com": "Motley Fool", "tipranks.com": "TipRanks",
        "thestreet.com": "TheStreet", "google.com": "Google News",
        "siemens-healthineers.com": "Siemens Healthineers", "antagroup.com": "ANTA Sports",
        "tomra.com": "TOMRA", "verbund.com": "VERBUND",
    },
}

EVENT_TERMS = [
    "earnings", "results", "profit", "revenue", "sales", "margin", "guidance", "outlook",
    "forecast", "shares", "stock", "dividend", "acquisition", "merger", "deal", "contract",
    "regulation", "tariff", "lawsuit", "ceo", "cfo", "upgrade", "downgrade", "analyst",
    "market", "demand", "prices", "growth", "costs", "investment", "warning",
]
EXCLUDE_TERMS = [
    "job", "jobs", "career", "careers", "hiring", "coupon", "discount", "promo",
    "advertisement", "sponsored", "celebrity", "football match", "basketball game",
]
RECENCY_OPTIONS = {
    "Last 1 day": "1d", "Last 3 days": "3d", "Last 1 week": "7d",
    "Last 2 weeks": "14d", "Last 1 month": "30d", "Last 3 months": "90d",
}
ORDER_OPTIONS = {"Best match first": "relevance", "Newest first": "date"}


GLOBAL_CSS = """
<style>
:root {
    --bg:#050817; --panel:#0b1024; --panel2:#111833; --line:rgba(132,153,255,.20);
    --text:#f5f7ff; --muted:#9ba6c9; --violet:#8f5cff; --blue:#2f80ff; --cyan:#57d6ff;
}
html, body, [class*="css"] { font-family: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }
.stApp {
    background:
      radial-gradient(circle at 20% 5%, rgba(90,52,220,.18), transparent 28%),
      radial-gradient(circle at 80% 10%, rgba(32,96,230,.13), transparent 26%),
      linear-gradient(180deg,#050817 0%,#070b1a 48%,#050817 100%);
    color:var(--text);
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"] { right: 1rem; }
.main .block-container { max-width: 1440px; padding: 1.2rem 2.2rem 4rem; }
[data-testid="stSidebar"] { background:#080c1c; border-right:1px solid var(--line); }
[data-testid="stSidebar"] * { color:var(--text)!important; }
h1,h2,h3,p,label,.stMarkdown { color:var(--text); }
.stButton>button {
    border:1px solid rgba(143,92,255,.55); border-radius:14px;
    background:linear-gradient(135deg,#6f47e8,#3b69ed); color:white;
    min-height:44px; font-weight:650; transition:.25s ease;
    box-shadow:0 8px 30px rgba(76,71,230,.22);
}
.stButton>button:hover { transform:translateY(-2px); border-color:#a98bff; box-shadow:0 12px 34px rgba(100,76,255,.34); }
[data-baseweb="select"]>div, [data-baseweb="input"]>div, .stTextInput input {
    background:#0d1329!important; color:white!important; border-color:rgba(142,160,255,.25)!important;
    border-radius:12px!important;
}
[data-testid="stExpander"] { background:rgba(13,19,41,.76); border:1px solid var(--line); border-radius:14px; }
[data-testid="stProgressBar"]>div>div { background:linear-gradient(90deg,#7e4dff,#2f80ff); }
.small-muted { color:var(--muted); font-size:.92rem; }
.news-heading { margin-top:1.2rem; }
.back-wrap div.stButton > button { background:rgba(255,255,255,.05); border-color:rgba(255,255,255,.14); box-shadow:none; }

[data-baseweb="popover"] *, [role="listbox"] *, [data-baseweb="menu"] * { color:#f5f7ff!important; }
[data-testid="stWidgetLabel"] p, .stRadio label, .stCheckbox label, .stToggle label { color:#eef1ff!important; }
.stAlert, .stAlert p, [data-testid="stNotificationContentInfo"] p { color:#eef1ff!important; }
</style>
"""
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def clean_text(value):
    if not value:
        return ""
    text = html_lib.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_domain(value):
    if not value:
        return ""
    value = value.strip().lower()
    if value.startswith("http"):
        value = urlparse(value).netloc.lower()
    return value.replace("www.", "")


def base_domain(value):
    domain = normalize_domain(value)
    parts = domain.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else domain


def source_name(domain_or_url, source_map, fallback=""):
    domain = normalize_domain(domain_or_url)
    base = base_domain(domain)
    if fallback and fallback.lower() not in {"google news", "news"}:
        return clean_text(fallback)
    if domain in source_map:
        return source_map[domain]
    if base in source_map:
        return source_map[base]
    for trusted_domain, name in source_map.items():
        if domain.endswith("." + trusted_domain):
            return name
    return base.split(".")[0].replace("-", " ").title() if base else (fallback or "Source")


def article_blob(article):
    return " ".join(clean_text(article.get(k, "")) for k in ("title", "summary", "source", "domain", "url")).lower()


def contains_any(text, terms):
    lower = text.lower()
    return [term for term in terms if term.lower() in lower]


def is_excluded(article):
    blob = article_blob(article)
    return any(term in blob for term in EXCLUDE_TERMS)


def is_trusted_source(article, source_map):
    domain = normalize_domain(article.get("domain") or article.get("url") or "")
    base = base_domain(domain)
    source = clean_text(article.get("source", "")).lower()
    return (
        domain in source_map or base in source_map
        or any(domain.endswith("." + d) for d in source_map)
        or any(name.lower() in source for name in source_map.values())
    )


def deduplicate(articles):
    seen, output = set(), []
    for article in articles:
        key = clean_text(article.get("url", "")).lower() or (
            clean_text(article.get("title", "")).lower() + "|" + clean_text(article.get("source", "")).lower()
        )
        if key and key not in seen:
            seen.add(key)
            output.append(article)
    return output


def google_news_rss_url(query, recency):
    return f"https://news.google.com/rss/search?q={quote_plus(f'({query}) when:{recency}')}&hl=en-US&gl=US&ceid=US:en"


def yahoo_finance_rss_url(ticker):
    return f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={quote_plus(ticker)}&region=US&lang=en-US"


def parse_feed_date(entry):
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if parsed:
        try:
            dt = datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
            return dt.strftime("%d %b %Y"), dt.timestamp()
        except Exception:
            pass
    raw = clean_text(getattr(entry, "published", "") or getattr(entry, "updated", ""))
    return raw[:16], 0.0


@st.cache_data(ttl=4 * 60 * 60, show_spinner=False)
def fetch_rss_feed(url):
    start = time.time()
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 JUGGNewsFinder/1.0"}, timeout=20)
    except Exception as exc:
        return {"ok": False, "message": f"Network problem: {exc}", "articles": [], "seconds": round(time.time()-start, 1)}
    seconds = round(time.time()-start, 1)
    if response.status_code != 200:
        return {"ok": False, "message": f"RSS feed returned HTTP {response.status_code}", "articles": [], "seconds": seconds}
    feed = feedparser.parse(response.content)
    if getattr(feed, "bozo", False) and not feed.entries:
        return {"ok": False, "message": "RSS feed could not be parsed.", "articles": [], "seconds": seconds}
    articles = []
    for entry in feed.entries:
        source = ""
        source_obj = getattr(entry, "source", None)
        if source_obj:
            source = clean_text(source_obj.get("title", "") if isinstance(source_obj, dict) else getattr(source_obj, "title", ""))
        link = clean_text(getattr(entry, "link", ""))
        published, published_ts = parse_feed_date(entry)
        articles.append({
            "title": clean_text(getattr(entry, "title", "")),
            "summary": clean_text(getattr(entry, "summary", "") or getattr(entry, "description", "")),
            "url": link, "domain": normalize_domain(link), "source": source,
            "published": published, "published_ts": published_ts,
        })
    return {"ok": True, "message": "OK", "articles": articles, "seconds": seconds}


def fetch_section_feeds(company, section, settings):
    queries = company["company_queries"] if section == "company" else company["sector_queries"]
    feeds = []
    if section == "company" and settings["include_yahoo_finance"]:
        feeds += [("Yahoo Finance", yahoo_finance_rss_url(t)) for t in company["tickers"]]
    feeds += [("Google News", google_news_rss_url(q, settings["recency"])) for q in queries]
    if not settings["use_extra_queries"]:
        feeds = feeds[:2] if section == "company" and settings["include_yahoo_finance"] else feeds[:1]
    raw_articles, requests_log = [], []
    for name, url in feeds:
        result = fetch_rss_feed(url)
        result["feed_name"] = name
        requests_log.append(result)
        raw_articles.extend(result["articles"])
        time.sleep(.25)
    return {"raw_articles": raw_articles, "requests": requests_log}


def score_article(article, company, section, source_map):
    text, title = article_blob(article), clean_text(article.get("title", "")).lower()
    direct_hits = contains_any(text, company["direct_terms"])
    direct_title_hits = contains_any(title, company["direct_terms"])
    sector_hits = contains_any(text, company["sector_terms"])
    event_hits = contains_any(text, EVENT_TERMS)
    score, reasons = 0, []
    if section == "company":
        if direct_title_hits:
            score += 60; reasons.append("company named in title")
        elif direct_hits:
            score += 45; reasons.append("company directly mentioned")
        else:
            score -= 20; reasons.append("weaker direct-company link")
    else:
        if sector_hits:
            score += 40; reasons.append("sector driver: " + ", ".join(sector_hits[:2]))
        if direct_hits:
            score += 15; reasons.append("also mentions company or brand")
    if event_hits:
        score += min(30, len(event_hits)*5); reasons.append("market event: " + ", ".join(event_hits[:3]))
    if is_trusted_source(article, source_map):
        score += 25; reasons.append("trusted source")
    if article.get("published"):
        score += 5; reasons.append("recent article")
    if is_excluded(article):
        score -= 100
    return score, "; ".join(reasons[:4]) + "."


def filter_rank_articles(raw_articles, company, section, settings):
    articles = deduplicate(raw_articles)
    filtered = []
    for article in articles:
        if is_excluded(article):
            continue
        if settings["strict_sources"] and not is_trusted_source(article, settings["source_map"]):
            continue
        score, why = score_article(article, company, section, settings["source_map"])
        if score < (10 if section == "sector" else 15):
            continue
        article["_score"], article["_why"] = score, why
        filtered.append(article)
    if settings["order"] == "date":
        filtered.sort(key=lambda a: (a.get("published_ts", 0), a.get("_score", 0)), reverse=True)
    else:
        filtered.sort(key=lambda a: (a.get("_score", 0), a.get("published_ts", 0)), reverse=True)
    return filtered[:settings["top_n"]], len(articles)


def load_section(company, section, settings):
    feed_result = fetch_section_feeds(company, section, settings)
    ranked, unique_count = filter_rank_articles(feed_result["raw_articles"], company, section, settings)
    return {
        "articles": ranked, "raw_count": len(feed_result["raw_articles"]),
        "unique_count": unique_count, "shown_count": len(ranked),
        "requests": feed_result["requests"],
    }


def short_summary(article):
    summary = clean_text(article.get("summary", ""))
    if len(summary) > 40:
        return summary[:620] + ("…" if len(summary) > 620 else "")
    title = clean_text(article.get("title", ""))
    return "This article discusses: " + title if title else "No short summary was available."


def render_news_table(articles, source_map):
    if not articles:
        st.info("No articles survived filtering. Try Broad coverage, a longer period, and trusted-source filtering OFF.")
        return
    rows = []
    for article in articles:
        url = html_lib.escape(clean_text(article.get("url", "")), quote=True)
        title = html_lib.escape(clean_text(article.get("title", "Untitled article")))
        summary = html_lib.escape(short_summary(article))
        why = html_lib.escape(clean_text(article.get("_why", "")))
        date = html_lib.escape(clean_text(article.get("published", "")))
        publisher = html_lib.escape(source_name(article.get("domain") or url, source_map, article.get("source", "")))
        score = int(article.get("_score", 0))
        rows.append(f"""
        <article class="story">
          <div class="story-main">
            <a class="story-title" href="{url}" target="_blank" rel="noopener noreferrer">{title}</a>
            <div class="story-summary">{summary}</div>
          </div>
          <div class="story-meta">
            <span class="score">Score {score}</span>
            <span>{date}</span><span>{publisher}</span>
          </div>
          <div class="story-why">{why}</div>
        </article>""")
    html = f"""
    <html><head><style>
    *{{box-sizing:border-box}} body{{margin:0;background:transparent;color:#edf1ff;font-family:Inter,Arial,sans-serif}}
    .list{{display:grid;gap:12px}} .story{{padding:18px 19px;border:1px solid rgba(133,151,255,.18);
    border-radius:16px;background:linear-gradient(145deg,rgba(16,23,49,.96),rgba(10,15,34,.96));
    box-shadow:0 10px 28px rgba(0,0,0,.16);transition:.22s ease}}
    .story:hover{{transform:translateY(-2px);border-color:rgba(143,92,255,.52);box-shadow:0 15px 38px rgba(50,34,140,.23)}}
    .story-title{{color:#f7f8ff;text-decoration:none;font-size:17px;font-weight:700;line-height:1.35}}
    .story-title:hover{{color:#a98bff}} .story-summary{{margin-top:9px;color:#b6bfdc;line-height:1.55;font-size:14px}}
    .story-meta{{display:flex;gap:12px;flex-wrap:wrap;margin-top:13px;color:#8793bc;font-size:12px}}
    .score{{color:#d7caff;background:rgba(119,77,255,.15);border:1px solid rgba(143,92,255,.28);padding:3px 8px;border-radius:999px}}
    .story-why{{margin-top:10px;color:#b2bad5;font-size:12px}} </style></head>
    <body><div class="list">{''.join(rows)}</div></body></html>"""
    components_html(html, height=min(1200, 40 + len(articles)*205), scrolling=True)


def render_hub():
    hub_html = """
    <div class="hub-shell">
      <div class="ambient ambient-a"></div><div class="ambient ambient-b"></div>
      <div class="brand-row">
        <div class="brand"><div class="brand-mark">J</div><div><b>JUGG</b></div></div>
        <div class="utility"><span>◌</span><span>⚙</span></div>
      </div>
      <div class="hero"><h1>Welcome back</h1><p>What would you like to explore today?</p><div class="hero-line"></div></div>
      <div class="grid">
        <a class="app-card active-card" href="?page=news" target="_self" aria-label="Open News Finder">
          <div class="shine"></div>
          <div class="icon-wrap">
            <svg viewBox="0 0 64 64" aria-hidden="true">
              <rect x="13" y="11" width="31" height="39" rx="4"></rect>
              <path d="M21 21h15M21 28h15M21 35h10"></path>
              <rect x="21" y="41" width="25" height="12" rx="3"></rect>
            </svg>
          </div>
          <div class="card-title">News Finder</div>
          <div class="card-copy">Find and analyze<br>latest news</div>
        </a>
        <a class="app-card active-card" href="?page=portfolio" target="_self" aria-label="Open Portfolio"><div class="shine"></div><div class="icon-wrap"><svg viewBox="0 0 64 64"><path d="M12 50V28M25 50V18M38 50V34M51 50V11"></path><path d="M8 50h48"></path></svg></div><div class="card-title">Portfolio</div><div class="card-copy">Track allocation and<br>current market values</div></a>
        <a class="app-card active-card" href="?page=briefing&view=overview" target="_self" aria-label="Open Market Briefing"><div class="shine"></div><div class="icon-wrap"><svg viewBox="0 0 64 64"><path d="M10 45l11-12 9 7 12-18 12 8"></path><path d="M10 52h44"></path><circle cx="21" cy="33" r="2"></circle><circle cx="42" cy="22" r="2"></circle></svg></div><div class="card-title">Market Briefing</div><div class="card-copy">Explain market moves and<br>your holdings</div></a>
        <div class="app-card placeholder"><div class="empty-icon">＋</div><div class="card-title">Coming later</div><div class="card-copy">Future program</div></div>
        <div class="app-card placeholder"><div class="empty-icon">＋</div><div class="card-title">Coming later</div><div class="card-copy">Future program</div></div>
        <div class="app-card placeholder"><div class="empty-icon">＋</div><div class="card-title">Coming later</div><div class="card-copy">Future program</div></div>
        <div class="app-card placeholder"><div class="empty-icon">＋</div><div class="card-title">Coming later</div><div class="card-copy">Future program</div></div>
        <div class="app-card placeholder"><div class="empty-icon">＋</div><div class="card-title">Coming later</div><div class="card-copy">Future program</div></div>
      </div>
      <div class="wave-field">
        <div class="wave wave-one"></div><div class="wave wave-two"></div><div class="wave wave-three"></div>
      </div>
    </div>
    <style>
    .hub-shell{position:relative;overflow:hidden;min-height:750px;padding:25px 34px 125px;border:1px solid rgba(132,153,255,.22);border-radius:25px;background:linear-gradient(145deg,rgba(11,16,37,.98),rgba(4,8,21,.99));box-shadow:0 30px 90px rgba(0,0,0,.42)}
    .brand-row{display:flex;align-items:center;justify-content:space-between;position:relative;z-index:4}.brand{display:flex;align-items:center;gap:10px}.brand-mark{width:28px;height:28px;border-radius:9px;display:grid;place-items:center;background:linear-gradient(145deg,#9b5cff,#354feb);box-shadow:0 0 24px rgba(126,77,255,.48);font-weight:800;color:#fff}.brand b{font-size:16px;color:#f8f9ff}.utility{display:flex;gap:10px}.utility span{width:31px;height:31px;border:1px solid rgba(147,161,213,.18);border-radius:50%;display:grid;place-items:center;color:#f6f7ff;background:rgba(255,255,255,.03)}
    .hero{text-align:center;margin:58px 0 40px;position:relative;z-index:3}.hero h1{margin:0;color:#fff;font-size:42px;line-height:1.08;letter-spacing:-.035em;font-weight:700}.hero p{margin:10px 0 0;color:#aeb7d3;font-size:15px}.hero-line{width:38px;height:3px;border-radius:99px;margin:20px auto 0;background:linear-gradient(90deg,#3186ff,#c549f3);box-shadow:0 0 18px rgba(133,82,255,.7)}
    .grid{position:relative;z-index:3;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:17px;max-width:930px;margin:auto}.app-card{position:relative;min-height:154px;padding:23px 17px;border:1px solid rgba(132,153,255,.19);border-radius:15px;background:linear-gradient(145deg,rgba(20,29,61,.90),rgba(11,16,37,.94));overflow:hidden;text-decoration:none!important;text-align:center;transition:transform .32s cubic-bezier(.2,.8,.2,1),border-color .32s,box-shadow .32s,background .32s;animation:cardIn .72s cubic-bezier(.16,1,.3,1) both}
    .app-card:hover{transform:translateY(-7px) scale(1.02);border-color:rgba(143,92,255,.62);box-shadow:0 18px 48px rgba(51,35,150,.34);background:linear-gradient(145deg,rgba(28,39,82,.96),rgba(12,18,42,.97))}.active-card{cursor:pointer}.placeholder{opacity:.30;cursor:default}.placeholder:hover{transform:none;box-shadow:none;border-color:rgba(132,153,255,.19);background:linear-gradient(145deg,rgba(20,29,61,.90),rgba(11,16,37,.94))}
    .placeholder:nth-child(2){animation-delay:.06s}.placeholder:nth-child(3){animation-delay:.12s}.placeholder:nth-child(4){animation-delay:.18s}.placeholder:nth-child(5){animation-delay:.24s}.placeholder:nth-child(6){animation-delay:.30s}.placeholder:nth-child(7){animation-delay:.36s}.placeholder:nth-child(8){animation-delay:.42s}
    .shine{position:absolute;inset:-135% -65%;background:linear-gradient(110deg,transparent 41%,rgba(255,255,255,.14) 50%,transparent 59%);transform:rotate(8deg);animation:shine 5.2s ease-in-out infinite}.icon-wrap,.empty-icon{width:53px;height:53px;margin:0 auto;border-radius:14px;display:grid;place-items:center;background:linear-gradient(145deg,rgba(108,69,239,.38),rgba(35,67,175,.34));border:1px solid rgba(154,119,255,.40);box-shadow:0 0 30px rgba(126,77,255,.31)}.icon-wrap svg{width:34px;fill:none;stroke:#a98cff;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;filter:drop-shadow(0 0 6px #7955ff)}.empty-icon{font-size:22px;color:#7f8bae;box-shadow:none;background:rgba(255,255,255,.025);border-style:dashed}
    .card-title{font-size:15px;font-weight:700;margin-top:15px;color:#f8f9ff!important}.card-copy{font-size:12px;line-height:1.45;color:#a5afcb!important;margin-top:6px}.ambient{position:absolute;width:440px;height:440px;border-radius:50%;filter:blur(90px);opacity:.19;animation:float 9s ease-in-out infinite alternate}.ambient-a{left:-180px;bottom:-180px;background:#8a3cff}.ambient-b{right:-190px;bottom:-170px;background:#147dff;animation-delay:-3s}
    .wave-field{position:absolute;left:0;right:0;bottom:0;height:160px;overflow:hidden;opacity:.95}.wave{position:absolute;left:-8%;right:-8%;height:120px;bottom:-54px;border-radius:50%;border-top:2px solid rgba(115,72,255,.70);filter:drop-shadow(0 0 14px rgba(101,67,255,.70));transform:rotate(-2deg);animation:wave 6s ease-in-out infinite}.wave-two{bottom:-26px;border-color:rgba(31,118,255,.55);animation-delay:-2.2s;opacity:.76}.wave-three{bottom:-42px;border-color:rgba(198,59,245,.48);animation-delay:-4.1s;opacity:.64}
    @keyframes cardIn{from{opacity:0;transform:translateY(22px) scale(.97)}to{transform:none}}@keyframes shine{0%,58%{transform:translateX(-88%) rotate(8deg)}78%,100%{transform:translateX(88%) rotate(8deg)}}@keyframes float{to{transform:translate(38px,-28px) scale(1.08)}}@keyframes wave{50%{transform:translateY(-13px) rotate(2deg) scaleX(1.04)}}
    @media(max-width:980px){.grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:600px){.hub-shell{padding:20px 15px 110px}.grid{grid-template-columns:1fr}.hero{margin-top:45px}.hero h1{font-size:34px}}
    </style>
    """
    st.markdown(hub_html, unsafe_allow_html=True)

def render_news_finder():
    st.markdown('<a class="back-link" href="?page=hub" target="_self">← Back to programs</a><style>.back-link{display:inline-flex;padding:10px 14px;border:1px solid rgba(255,255,255,.14);border-radius:12px;color:#eef1ff!important;text-decoration:none!important;background:rgba(255,255,255,.05);transition:.2s}.back-link:hover{transform:translateY(-1px);border-color:rgba(143,92,255,.5);background:rgba(143,92,255,.10)}</style>', unsafe_allow_html=True)
    st.markdown("""
    <div style="padding:10px 0 20px">
      <div style="font-size:12px;letter-spacing:.13em;text-transform:uppercase;color:#8d9ac3">JUGG · Program 01</div>
      <h1 style="font-size:39px;margin:7px 0 5px">News Finder</h1>
      <div style="color:#9da8ca">Company and sector news, ranked by relevance and source quality.</div>
    </div>""", unsafe_allow_html=True)

    with st.sidebar:
        st.header("News Finder controls")
        view_mode = st.radio("View mode", ["One selected company", "Full portfolio"])
        selected_company = st.selectbox("Company", list(COMPANIES))
        source_mode = st.selectbox("Source quality mode", list(SOURCE_MAPS), index=1)
        strict_sources = st.toggle("Only show selected trusted sources", value=False)
        top_n = st.slider("Articles per section", 3, 12, 5)
        recency_label = st.selectbox("Recency window", list(RECENCY_OPTIONS), index=1)
        order_label = st.selectbox("Article order", list(ORDER_OPTIONS))
        include_yahoo_finance = st.toggle("Use Yahoo Finance company feed", value=True)
        use_extra_queries = st.toggle("Use extra RSS queries", value=True)
        show_debug = st.toggle("Show debug details", value=False)
        load_clicked = st.button("Load Articles", type="primary", use_container_width=True)
        if st.button("Clear saved results / cache", use_container_width=True):
            st.cache_data.clear()
            st.session_state.pop("rss_news_results", None)
            st.session_state.pop("rss_news_settings", None)
            st.rerun()

    settings = {
        "source_map": SOURCE_MAPS[source_mode], "strict_sources": strict_sources,
        "top_n": top_n, "recency": RECENCY_OPTIONS[recency_label],
        "order": ORDER_OPTIONS[order_label], "include_yahoo_finance": include_yahoo_finance,
        "use_extra_queries": use_extra_queries, "show_debug": show_debug,
    }

    with st.expander("What the controls mean"):
        st.markdown("""
- **View mode:** load one company or the complete portfolio.
- **Source quality mode:** changes how broadly trusted publishers are recognized.
- **Trusted sources only:** stricter, but may hide useful articles.
- **Article order:** choose relevance or publication date.
- **Extra RSS queries:** improves coverage but takes longer.
""")

    if load_clicked:
        names = [selected_company] if view_mode == "One selected company" else list(COMPANIES)
        results = {}
        progress = st.progress(0)
        status = st.empty()
        total = len(names) * 2
        step = 0
        for name in names:
            status.info(f"Loading company news for {name}…")
            company_news = load_section(COMPANIES[name], "company", settings)
            step += 1; progress.progress(step / total)
            status.info(f"Loading sector news for {name}…")
            sector_news = load_section(COMPANIES[name], "sector", settings)
            step += 1; progress.progress(step / total)
            results[name] = {"company_news": company_news, "sector_news": sector_news}
        status.success("Finished loading articles.")
        st.session_state["rss_news_results"] = results
        st.session_state["rss_news_settings"] = settings

    results = st.session_state.get("rss_news_results")
    if not results:
        st.info("Choose the controls in the sidebar and press **Load Articles**.")
        return

    for company_name, sections in results.items():
        if len(results) > 1:
            st.markdown(f"## {company_name}")
        for heading, key, note in [
            ("Company News", "company_news", "Direct articles about the company, brands, subsidiaries or stock."),
            ("Sector News / Events Affecting the Company", "sector_news", "Broader sector and market events that may affect the company."),
        ]:
            st.markdown(f'<h2 class="news-heading">{heading}</h2><div class="small-muted">{note}</div>', unsafe_allow_html=True)
            result = sections[key]
            if settings["show_debug"]:
                with st.expander(f"Debug details: {heading}"):
                    st.write({
                        "Raw articles": result["raw_count"],
                        "Unique articles": result["unique_count"],
                        "Articles shown": result["shown_count"],
                    })
            render_news_table(result["articles"], settings["source_map"])



# ============================================================
# Dark & Sleek Portfolio
# ============================================================
PORTFOLIO_HOLDINGS = [
    {"name": "Siemens Healthineers", "ticker": "SHL.DE", "abbr": "SHL", "saved_value_eur": 852.00, "original_investment_eur": 1010.50, "purchase_date": "10.03.2026", "country": "Germany", "country_iso3": "DEU", "area": "Healthcare"},
    {"name": "Verbund", "ticker": "VER.VI", "abbr": "VER", "saved_value_eur": 838.50, "original_investment_eur": 922.50, "purchase_date": "05.05.2026", "country": "Austria", "country_iso3": "AUT", "area": "Renewable Energy"},
    {"name": "Tomra Systems", "ticker": "TOM.OL", "abbr": "TOM", "saved_value_eur": 1011.60, "original_investment_eur": 1033.20, "purchase_date": "27.04.2026", "country": "Norway", "country_iso3": "NOR", "area": "Industrials / Recycling"},
    {"name": "ANTA Sports", "ticker": "2020.HK", "abbr": "ANTA", "saved_value_eur": 944.13, "original_investment_eur": 1051.25, "purchase_date": "01.06.2026", "country": "China / Hong Kong", "country_iso3": "CHN", "area": "Consumer / Sportswear"},
    {"name": "MS Europe 26/27 ABJ", "ticker": None, "abbr": "MS EU 26/27", "saved_value_eur": 1017.40, "original_investment_eur": 1005.00, "purchase_date": "24.04.2026", "country": "Europe exposure", "country_iso3": None, "area": "Structured Product"},
]

@st.cache_data(ttl=15 * 60, show_spinner=False)
def fetch_yahoo_quote(ticker: str) -> dict:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote_plus(ticker)}?range=5d&interval=1d"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 JUGG/1.0"}, timeout=12)
        response.raise_for_status()
        result = response.json()["chart"]["result"][0]
        meta = result.get("meta", {})
        closes = [x for x in result.get("indicators", {}).get("quote", [{}])[0].get("close", []) if x is not None]
        price = float(meta.get("regularMarketPrice") or (closes[-1] if closes else 0))
        previous = float(meta.get("chartPreviousClose") or meta.get("previousClose") or (closes[-2] if len(closes) > 1 else price))
        change_pct = ((price / previous) - 1) * 100 if previous else 0.0
        return {"ok": bool(price), "price": price, "previous": previous, "change_pct": change_pct}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "price": None, "previous": None, "change_pct": 0.0}


def live_portfolio_rows() -> tuple[list[dict], str]:
    rows, live_loaded = [], False
    for item in PORTFOLIO_HOLDINGS:
        row = dict(item)
        if item["ticker"]:
            quote = fetch_yahoo_quote(item["ticker"])
            if quote.get("ok"):
                row["daily_pct"] = quote["change_pct"]
                row["current_value_eur"] = item["saved_value_eur"] * (1 + quote["change_pct"] / 100)
                row["source_status"] = "Latest quote loaded"
                live_loaded = True
            else:
                row.update({"daily_pct": 0.0, "current_value_eur": item["saved_value_eur"], "source_status": "Saved value"})
        else:
            row.update({"daily_pct": 0.0, "current_value_eur": item["saved_value_eur"], "source_status": "Last recorded valuation"})
        rows.append(row)
    return rows, ("Market quotes loaded on opening" if live_loaded else "Using saved portfolio values")


def portfolio_nav() -> str:
    return "".join([
        '<a class="pnav" href="?page=hub" target="_self"><span>⌂</span>Menu</a>',
        '<a class="pnav" href="?page=hub" target="_self"><span>▦</span>Programs</a>',
        '<a class="pnav nav-active" href="?page=portfolio" target="_self"><span>◉</span>Portfolio</a>',
        '<a class="pnav" href="?page=news" target="_self"><span>▥</span>News Finder</a>',
        '<a class="pnav" href="?page=briefing&view=overview" target="_self"><span>⌁</span>Market Briefing</a>',
        '<a class="pnav" href="?page=portfolio" target="_self"><span>⚙</span>Settings</a>',
    ])


def render_portfolio():
    rows, price_status = live_portfolio_rows()
    total = sum(r["current_value_eur"] for r in rows)
    saved_total = sum(r["saved_value_eur"] for r in rows)
    day_change = total - saved_total
    day_pct = (day_change / saved_total * 100) if saved_total else 0

    st.markdown("""
    <style>
    .main .block-container{max-width:1500px;padding:0!important}
    .portfolio-shell{min-height:100vh;background:linear-gradient(145deg,#050817,#071022 55%,#050817);color:#f7f8ff;display:grid;grid-template-columns:190px 1fr;border:1px solid rgba(127,111,255,.16)}
    .portfolio-side{padding:28px 18px;border-right:1px solid rgba(133,151,255,.16);background:rgba(4,8,20,.74)}
    .portfolio-brand{font-size:22px;font-weight:750;margin:4px 8px 32px;color:#fff}.portfolio-brand b{color:#8f63ff;margin-right:8px}
    .pnav{display:flex;gap:12px;align-items:center;padding:13px 14px;margin:7px 0;border-radius:11px;text-decoration:none!important;color:#aeb7d3!important;border:1px solid transparent}
    .pnav:hover,.nav-active{color:#b898ff!important;background:rgba(116,70,239,.12);border-color:rgba(135,91,255,.24)}
    .portfolio-main{padding:28px 30px 38px;min-width:0}.portfolio-title{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:18px}
    .portfolio-title h1{font-size:31px!important;margin:0!important;color:#fff!important}.portfolio-sub{color:#9da8c8;margin-top:5px}
    .live-chip{border:1px solid rgba(82,224,145,.27);color:#65e395;background:rgba(45,180,105,.08);padding:8px 11px;border-radius:999px;font-size:12px;white-space:nowrap}
    .metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:16px}
    .p-card{background:linear-gradient(145deg,rgba(13,22,43,.96),rgba(7,14,30,.98));border:1px solid rgba(133,151,255,.18);border-radius:14px;padding:16px;min-width:0}
    .metric-label{color:#9fa9c8;font-size:12px}.metric-value{font-size:25px;font-weight:680;margin-top:7px;color:#fff}.positive{color:#45df82}.negative{color:#ff6d83}.metric-note{margin-top:5px;font-size:12px;color:#aab3cc}
    .upper-grid{display:grid;grid-template-columns:1.08fr .92fr;gap:14px;margin-bottom:14px}.section-title{font-size:16px;font-weight:650;color:#f7f8ff;margin-bottom:14px}
    .country-list,.area-list{display:grid;gap:10px}.country-row,.area-row{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center;color:#e9ecf7;font-size:13px}
    .bar{height:5px;border-radius:99px;background:#151f3b;overflow:hidden;grid-column:1/-1}.bar span{display:block;height:100%;background:linear-gradient(90deg,#6f48ff,#a76cff);border-radius:99px}
    .holdings-head,.holding-row{display:grid;grid-template-columns:2fr .75fr .8fr .65fr .8fr;gap:12px;align-items:center}.holdings-head{color:#8f9abb;font-size:11px;padding:0 8px 10px}
    .holding-row{padding:13px 8px;border-top:1px solid rgba(133,151,255,.13);font-size:13px;color:#f0f2fa}.asset-name{font-weight:620}.ticker{color:#9ea8c7;font-size:11px;margin-left:7px}.source-tag{font-size:10px;color:#929dbd;margin-top:3px}
    .portfolio-foot{margin-top:14px;text-align:center;color:#a987ff;border:1px solid rgba(127,83,255,.17);background:rgba(99,57,210,.06);padding:13px;border-radius:12px}
    .mobile-bottom{display:none;position:fixed;left:0;right:0;bottom:0;z-index:100;background:#060b19;border-top:1px solid rgba(133,151,255,.2);justify-content:space-around;padding:9px 5px 12px}
    .mobile-bottom a{color:#aab3ce!important;text-decoration:none!important;font-size:10px;text-align:center}.mobile-bottom span{display:block;font-size:17px;margin-bottom:3px}.mobile-bottom .selected{color:#9d74ff!important}
    @media(max-width:900px){.portfolio-shell{grid-template-columns:1fr}.portfolio-side{display:none}.portfolio-main{padding:20px 14px 95px}.metric-grid{grid-template-columns:repeat(2,1fr)}.upper-grid{grid-template-columns:1fr}.holdings-head{display:none}.holding-row{grid-template-columns:1.5fr .75fr .8fr}.holding-row>*:nth-child(4),.holding-row>*:nth-child(5){display:none}.mobile-bottom{display:flex!important}}
    @media(max-width:480px){.portfolio-title{display:block}.live-chip{display:inline-block;margin-top:10px}.metric-grid{gap:9px}.p-card{padding:13px}.metric-value{font-size:19px}.holding-row{font-size:12px}.portfolio-main{padding-left:10px;padding-right:10px}}
    </style>
    """, unsafe_allow_html=True)

    countries, areas = {}, {}
    for row in rows:
        countries[row["country"]] = countries.get(row["country"], 0) + row["current_value_eur"]
        areas[row["area"]] = areas.get(row["area"], 0) + row["current_value_eur"]

    country_rows = "".join(
        f'<div class="country-row"><span>{html_lib.escape(name)}</span><b>{value/total*100:.1f}%</b><div class="bar"><span style="width:{value/total*100:.1f}%"></span></div></div>'
        for name, value in sorted(countries.items(), key=lambda item: item[1], reverse=True)
    )
    area_rows = "".join(
        f'<div class="area-row"><span>{html_lib.escape(name)}</span><b>{value/total*100:.1f}% · €{value:,.0f}</b><div class="bar"><span style="width:{value/total*100:.1f}%"></span></div></div>'
        for name, value in sorted(areas.items(), key=lambda item: item[1], reverse=True)
    )

    st.markdown(f"""
    <div class="portfolio-shell"><aside class="portfolio-side"><div class="portfolio-brand"><b>⌘</b>jugg</div>{portfolio_nav()}</aside>
    <main class="portfolio-main"><div class="portfolio-title"><div><h1>Portfolio</h1><div class="portfolio-sub">Your investments, real impact.</div></div><div class="live-chip">● {price_status}</div></div>
    <div class="metric-grid">
      <div class="p-card"><div class="metric-label">Total Value</div><div class="metric-value">€{total:,.2f}</div><div class="metric-note {'positive' if day_change >= 0 else 'negative'}">{'▲' if day_change >= 0 else '▼'} €{abs(day_change):,.2f} today</div></div>
      <div class="p-card"><div class="metric-label">Daily Change</div><div class="metric-value {'positive' if day_pct >= 0 else 'negative'}">{day_pct:+.2f}%</div><div class="metric-note">Latest available quotes</div></div>
      <div class="p-card"><div class="metric-label">Investments</div><div class="metric-value">{len(rows)}</div><div class="metric-note">4 listed + 1 structured product</div></div>
      <div class="p-card"><div class="metric-label">Saved Portfolio Value</div><div class="metric-value">€{saved_total:,.2f}</div><div class="metric-note">Your last supplied values</div></div>
    </div>
    <div class="upper-grid"><section class="p-card"><div class="section-title">Invested Countries</div>
    """, unsafe_allow_html=True)

    map_values = {row["country_iso3"]: row["current_value_eur"] for row in rows if row.get("country_iso3")}
    fig = go.Figure(go.Choropleth(
        locations=list(map_values.keys()), z=list(map_values.values()), locationmode="ISO-3",
        colorscale=[[0, "#38207a"], [1, "#8c5cff"]], showscale=False,
        marker_line_color="#303b5b", marker_line_width=.45,
        hovertemplate="%{location}<br>€%{z:,.2f}<extra></extra>"
    ))
    fig.update_geos(showframe=False, showcoastlines=False, showcountries=True, countrycolor="#26304b", showland=True, landcolor="#151d33", showocean=True, oceancolor="#091126", bgcolor="rgba(0,0,0,0)", projection_type="natural earth")
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=245)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown(f"""
    <div class="country-list">{country_rows}</div></section>
    <section class="p-card"><div class="section-title">Investment by Area</div><div class="area-list">{area_rows}</div></section></div>
    """, unsafe_allow_html=True)

    holding_rows = []
    for row in rows:
        daily_class = "positive" if row["daily_pct"] >= 0 else "negative"
        holding_rows.append(
            f'<div class="holding-row"><div><span class="asset-name">{html_lib.escape(row["name"])}</span><span class="ticker">{html_lib.escape(row["abbr"])}</span><div class="source-tag">{html_lib.escape(row["source_status"])}</div></div><div>€{row["current_value_eur"]:,.2f}</div><div>{row["current_value_eur"]/total*100:.1f}%</div><div class="{daily_class}">{row["daily_pct"]:+.2f}%</div><div>—</div></div>'
        )

    st.markdown(f"""
    <section class="p-card"><div class="section-title">Holdings Overview</div><div class="holdings-head"><span>Asset</span><span>Value</span><span>Weight</span><span>Daily</span><span>Total Return</span></div>{''.join(holding_rows)}</section>
    <div class="portfolio-foot">✦ More programs coming soon.</div></main></div>
    <nav class="mobile-bottom"><a href="?page=hub" target="_self"><span>⌂</span>Home</a><a href="?page=hub" target="_self"><span>▦</span>Programs</a><a class="selected" href="?page=portfolio" target="_self"><span>◉</span>Portfolio</a><a href="?page=news" target="_self"><span>▥</span>News</a><a href="?page=portfolio" target="_self"><span>⚙</span>Settings</a></nav>
    """, unsafe_allow_html=True)
    st.caption("Quotes refresh every 15 minutes when the app opens. Because the saved portfolio data contains position values but not unit quantities, listed values are adjusted by the latest daily price move rather than presented as falsely exact mark-to-market values. The structured product remains at its last recorded valuation.")


# ============================================================
# Market Briefing
# ============================================================
BRIEFING_LENGTHS = {
    "Short — 100–200 words": (100, 200),
    "Medium — 200–350 words": (200, 350),
    "Long — 350–500 words": (350, 500),
}

MARKET_ASSETS = [
    {"name": "S&P 500", "ticker": "^GSPC", "region": "United States", "role": "Large-cap US market"},
    {"name": "Nasdaq 100", "ticker": "^NDX", "region": "United States", "role": "Growth and technology"},
    {"name": "MSCI World ETF", "ticker": "URTH", "region": "Global", "role": "Developed-market proxy"},
    {"name": "Russell 2000", "ticker": "^RUT", "region": "United States", "role": "Smaller-company health"},
    {"name": "Euro Stoxx 50", "ticker": "^STOXX50E", "region": "Europe", "role": "European blue chips"},
    {"name": "DAX", "ticker": "^GDAXI", "region": "Europe", "role": "German market bellwether"},
    {"name": "Nikkei 225", "ticker": "^N225", "region": "Asia", "role": "Japanese equities"},
    {"name": "Hang Seng", "ticker": "^HSI", "region": "Asia", "role": "Hong Kong / China proxy"},
    {"name": "US 10Y Yield", "ticker": "^TNX", "region": "Rates", "role": "Global valuation benchmark"},
    {"name": "EUR / USD", "ticker": "EURUSD=X", "region": "FX", "role": "Dollar and euro conditions"},
    {"name": "Brent Oil", "ticker": "BZ=F", "region": "Commodities", "role": "Energy and inflation signal"},
    {"name": "Gold", "ticker": "GC=F", "region": "Commodities", "role": "Inflation and safe-haven signal"},
]

MARKET_NEWS_QUERIES = [
    '"global markets" OR "world stocks" OR "European shares" OR "Asian shares"',
    '"Federal Reserve" OR ECB OR "Bank of Japan" OR "bond yields" OR "interest rates"',
    'inflation OR GDP OR PMI OR employment OR recession OR "economic growth"',
    'oil OR gas OR electricity OR gold OR dollar OR euro OR yuan',
    'tariffs OR trade OR sanctions OR geopolitics OR election',
]

DRIVER_DEFINITIONS = {
    "rates": {
        "title": "Interest rates and bond yields",
        "category": "Rates / Valuation",
        "terms": ["interest rate", "rates", "bond yield", "treasury", "ecb", "federal reserve", "fed", "boj", "central bank"],
        "what": "Interest rates are the price of borrowing money. Government-bond yields are the market's continuously updated view of future rates, inflation and economic risk.",
        "meaning": "When yields rise, future company profits are discounted more heavily and financing becomes more expensive. When yields fall, valuation pressure usually eases, although a sharp fall can also signal growth fears.",
        "effects": "High-growth and highly valued shares are often most sensitive. Banks can benefit from higher rates if lending margins improve, while property, utilities and indebted companies can face higher funding costs.",
    },
    "growth": {
        "title": "Growth, inflation and economic data",
        "category": "Macro / Demand",
        "terms": ["inflation", "gdp", "pmi", "employment", "jobs", "consumer", "retail sales", "recession", "growth", "manufacturing"],
        "what": "Economic indicators measure demand, prices, employment and business activity. Markets use them to judge the likely path of profits and central-bank policy.",
        "meaning": "Stronger activity can support company revenue, but unexpectedly high inflation can delay rate cuts. Weak data can lower yields while simultaneously reducing earnings expectations.",
        "effects": "Cyclical industrial, consumer and financial companies usually react most to growth data. Defensive healthcare and utilities can be relatively resilient when growth expectations weaken.",
    },
    "energy": {
        "title": "Energy and commodity prices",
        "category": "Energy / Inflation",
        "terms": ["oil", "brent", "gas", "electricity", "power price", "commodity", "gold", "hydropower", "energy"],
        "what": "Energy and commodity prices reflect physical supply, demand, inventories, weather and geopolitical risk. They also feed directly into inflation and production costs.",
        "meaning": "Higher energy prices can lift producer costs and inflation expectations. Lower prices can help consumers and manufacturers, but may reduce earnings for energy producers and some utilities.",
        "effects": "Utilities, airlines, chemicals, transport and heavy industry can be affected quickly. For Verbund, electricity prices, hydrology and regional power conditions are especially relevant.",
    },
    "china": {
        "title": "China and Asian demand",
        "category": "Asia / Consumption",
        "terms": ["china", "chinese", "hong kong", "yuan", "beijing", "asia", "japan", "nikkei", "hang seng"],
        "what": "China and the wider Asian region are major sources of global manufacturing, consumer demand and supply-chain activity.",
        "meaning": "Stimulus, property-market conditions and consumer confidence can change expectations for regional sales and global trade. Currency moves can also affect reported revenue and competitiveness.",
        "effects": "Consumer brands, luxury goods, industrial exporters and commodity companies are particularly exposed. ANTA Sports is directly sensitive to Chinese consumer demand and retail confidence.",
    },
    "currency": {
        "title": "Currencies and the US dollar",
        "category": "FX / Earnings",
        "terms": ["dollar", "euro", "yen", "yuan", "currency", "foreign exchange", "fx", "eur/usd"],
        "what": "Exchange rates determine how revenue, costs and assets in one currency translate into another.",
        "meaning": "A stronger dollar can tighten global financial conditions. A weaker local currency can help exporters but make imported inputs more expensive.",
        "effects": "International companies can experience translation effects even without a change in underlying sales. European and Asian exporters often react to large euro, dollar, yen or yuan moves.",
    },
    "trade": {
        "title": "Trade policy and geopolitics",
        "category": "Policy / Risk",
        "terms": ["tariff", "trade", "sanction", "geopolit", "war", "conflict", "export control", "regulation", "election"],
        "what": "Trade and geopolitical developments can alter tariffs, supply routes, access to technology and the perceived risk of investing in a region.",
        "meaning": "Markets react before the full economic effect is known because companies may face higher costs, delayed investment or weaker cross-border demand.",
        "effects": "Exporters, semiconductors, industrial companies, shipping and consumer brands with international supply chains can be affected most. Defensive assets may benefit when risk aversion rises.",
    },
    "technology": {
        "title": "Technology and AI leadership",
        "category": "Technology / Risk appetite",
        "terms": ["artificial intelligence", " ai ", "semiconductor", "chip", "technology", "nasdaq", "nvidia", "data center"],
        "what": "Large technology and semiconductor companies have an unusually high weight in major indices and are important indicators of investor risk appetite.",
        "meaning": "Strong earnings or investment plans can lift entire indices. Valuation concerns, export restrictions or weaker demand can quickly reverse that effect.",
        "effects": "The direct impact is strongest on technology suppliers, but broad market indices can move significantly because the largest technology companies carry high index weights.",
    },
    "healthcare": {
        "title": "Healthcare demand and regulation",
        "category": "Healthcare / Defensive growth",
        "terms": ["healthcare", "medical device", "hospital", "diagnostic", "radiotherapy", "drug", "medtech"],
        "what": "Healthcare demand depends on hospital budgets, patient volumes, innovation cycles, reimbursement and regulation.",
        "meaning": "The sector is often defensive, but medical-equipment companies can still be sensitive to capital-spending cycles, China demand and financing conditions.",
        "effects": "Siemens Healthineers can be affected by hospital investment, imaging demand, Varian performance, currencies and changes in valuation multiples.",
    },
}

HOLDING_BRIEFING_DATA = {
    "Siemens Healthineers": {
        "ticker": "SHL.DE", "chart_label": "Siemens Healthineers", "direct_terms": ["siemens healthineers", "varian"],
        "queries": ['"Siemens Healthineers" OR Varian', '"medical imaging" OR radiotherapy OR diagnostics OR "hospital spending"'],
        "context": "medical imaging, diagnostics, Varian, hospital capital spending and healthcare-equipment valuation",
    },
    "Verbund": {
        "ticker": "VER.VI", "chart_label": "Verbund", "direct_terms": ["verbund", "verbund ag"],
        "queries": ['"Verbund AG" OR "Verbund" electricity', '"European power prices" OR hydropower OR "Austrian electricity"'],
        "context": "European electricity prices, hydrology, renewable generation, regulation and interest rates",
    },
    "Tomra Systems": {
        "ticker": "TOM.OL", "chart_label": "Tomra Systems", "direct_terms": ["tomra", "tomra systems"],
        "queries": ['"Tomra Systems" OR Tomra', '"deposit return" OR "reverse vending" OR "waste sorting" OR "recycling regulation"'],
        "context": "recycling regulation, deposit-return systems, order intake, margins and industrial valuation",
    },
    "ANTA Sports": {
        "ticker": "2020.HK", "chart_label": "ANTA Sports", "direct_terms": ["anta sports", "anta sports products", "fila china", "amer sports"],
        "queries": ['"ANTA Sports" OR "Anta Sports Products" OR "FILA China"', '"China retail sales" OR "Chinese consumer" OR sportswear'],
        "context": "Chinese consumer demand, sportswear competition, FILA China, Amer Sports and the yuan",
    },
    "MS Europe 26/27 ABJ": {
        "ticker": "^STOXX50E", "chart_label": "Euro Stoxx 50 proxy", "direct_terms": ["european stocks", "euro stoxx", "european markets"],
        "queries": ['"European stocks" OR "Euro Stoxx" OR "European markets"', 'ECB OR "European bond yields" OR "euro area economy"'],
        "context": "broad European equity conditions, ECB policy, European bond yields and the product's underlying structure",
        "proxy_note": "No public live ticker for the structured product is available in the supplied data. The chart uses the Euro Stoxx 50 only as a market proxy, not as the product's valuation.",
    },
}


def _safe_secret(name: str, default: str = "") -> str:
    env_value = os.getenv(name, "")
    if env_value:
        return env_value
    try:
        value = st.secrets.get(name, default)
        return str(value) if value is not None else default
    except Exception:
        return default


def _query_value(name: str, default: str = "") -> str:
    value = st.query_params.get(name, default)
    if isinstance(value, list):
        return value[0] if value else default
    return str(value or default)


def _navigate_briefing(view: str = "overview", **params) -> None:
    st.query_params.clear()
    st.query_params["page"] = "briefing"
    st.query_params["view"] = view
    for key, value in params.items():
        st.query_params[key] = str(value)
    st.rerun()


def _fetch_yahoo_history_raw(ticker: str, range_period: str = "5d", interval: str = "60m") -> dict:
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{quote_plus(ticker)}?range={range_period}&interval={interval}&includePrePost=false"
    )
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 JUGGMarketBriefing/1.0"}, timeout=14)
        response.raise_for_status()
        result = response.json()["chart"]["result"][0]
        timestamps = result.get("timestamp", [])
        quote = result.get("indicators", {}).get("quote", [{}])[0]
        closes = quote.get("close", [])
        points = [(int(ts), float(close)) for ts, close in zip(timestamps, closes) if close is not None]
        meta = result.get("meta", {})
        if not points:
            return {"ok": False, "ticker": ticker, "error": "No price points returned."}
        current = float(meta.get("regularMarketPrice") or points[-1][1])
        previous = float(meta.get("chartPreviousClose") or meta.get("previousClose") or points[max(0, len(points)-2)][1])
        cutoff = datetime.now(timezone.utc).timestamp() - 48 * 3600
        recent = [point for point in points if point[0] >= cutoff]
        basis_points = recent if len(recent) >= 2 else points[-min(len(points), 14):]
        start_value = basis_points[0][1]
        change_48h = ((current / start_value) - 1) * 100 if start_value else 0.0
        daily_change = ((current / previous) - 1) * 100 if previous else 0.0
        return {
            "ok": True, "ticker": ticker, "points": points, "recent_points": basis_points,
            "price": current, "previous": previous, "change_48h": change_48h,
            "daily_change": daily_change, "currency": meta.get("currency", ""),
            "exchange": meta.get("exchangeName", ""),
            "basis": "48 hours" if len(recent) >= 2 else "latest available trading points",
        }
    except Exception as exc:
        return {"ok": False, "ticker": ticker, "error": str(exc), "points": [], "recent_points": []}


@st.cache_data(ttl=15 * 60, show_spinner=False)
def fetch_yahoo_history(ticker: str, range_period: str = "5d", interval: str = "60m") -> dict:
    return _fetch_yahoo_history_raw(ticker, range_period, interval)


@st.cache_data(ttl=15 * 60, show_spinner=False)
def load_market_snapshot() -> list[dict]:
    snapshot = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(_fetch_yahoo_history_raw, asset["ticker"]): asset for asset in MARKET_ASSETS}
        for future in as_completed(futures):
            asset = futures[future]
            row = dict(asset)
            try:
                row.update(future.result())
            except Exception as exc:
                row.update({"ok": False, "error": str(exc), "points": [], "recent_points": []})
            snapshot.append(row)
    order = {asset["ticker"]: idx for idx, asset in enumerate(MARKET_ASSETS)}
    snapshot.sort(key=lambda item: order.get(item["ticker"], 999))
    return snapshot


def _title_fingerprint(title: str) -> str:
    words = re.findall(r"[a-z0-9]+", clean_text(title).lower())
    return " ".join(words[:14])


def _deduplicate_news(articles: list[dict]) -> list[dict]:
    seen_urls, seen_titles, output = set(), set(), []
    for article in sorted(articles, key=lambda item: item.get("published_ts", 0), reverse=True):
        url_key = clean_text(article.get("url", "")).lower()
        title_key = _title_fingerprint(article.get("title", ""))
        if not title_key or url_key in seen_urls or title_key in seen_titles:
            continue
        if url_key:
            seen_urls.add(url_key)
        seen_titles.add(title_key)
        output.append(article)
    return output


def _within_48_hours(article: dict) -> bool:
    timestamp = float(article.get("published_ts") or 0)
    return timestamp > 0 and timestamp >= datetime.now(timezone.utc).timestamp() - 48 * 3600


def _news_relevance_score(article: dict, focus_terms: list[str] | None = None) -> int:
    blob = article_blob(article)
    title = clean_text(article.get("title", "")).lower()
    score = 0
    if _within_48_hours(article):
        score += 30
    if is_trusted_source(article, SOURCE_MAPS["Balanced sources"]):
        score += 25
    event_hits = contains_any(blob, EVENT_TERMS)
    score += min(25, len(event_hits) * 4)
    if focus_terms:
        direct = [term for term in focus_terms if term.lower() in blob]
        title_direct = [term for term in focus_terms if term.lower() in title]
        score += 35 if title_direct else (20 if direct else 0)
    if is_excluded(article):
        score -= 100
    return score


@st.cache_data(ttl=20 * 60, show_spinner=False)
def fetch_market_news_48h() -> list[dict]:
    articles = []
    for query in MARKET_NEWS_QUERIES:
        result = fetch_rss_feed(google_news_rss_url(query, "2d"))
        articles.extend(result.get("articles", []))
        time.sleep(.12)
    articles = [article for article in _deduplicate_news(articles) if _within_48_hours(article) and not is_excluded(article)]
    for article in articles:
        article["_score"] = _news_relevance_score(article)
    articles.sort(key=lambda item: (item.get("_score", 0), item.get("published_ts", 0)), reverse=True)
    return articles[:30]


@st.cache_data(ttl=20 * 60, show_spinner=False)
def fetch_holding_news_48h(holding_name: str) -> list[dict]:
    config = HOLDING_BRIEFING_DATA.get(holding_name, {})
    articles = []
    for query in config.get("queries", []):
        result = fetch_rss_feed(google_news_rss_url(query, "2d"))
        articles.extend(result.get("articles", []))
        time.sleep(.12)
    ticker = config.get("ticker")
    if ticker and not ticker.startswith("^"):
        result = fetch_rss_feed(yahoo_finance_rss_url(ticker))
        articles.extend(result.get("articles", []))
    articles = [article for article in _deduplicate_news(articles) if _within_48_hours(article) and not is_excluded(article)]
    focus_terms = config.get("direct_terms", [])
    for article in articles:
        article["_score"] = _news_relevance_score(article, focus_terms)
    articles.sort(key=lambda item: (item.get("_score", 0), item.get("published_ts", 0)), reverse=True)
    return articles[:18]


def build_driver_snapshot(articles: list[dict]) -> list[dict]:
    drivers = []
    for driver_id, definition in DRIVER_DEFINITIONS.items():
        matched = []
        for article in articles:
            blob = article_blob(article)
            hits = sum(1 for term in definition["terms"] if term in blob)
            if hits:
                enriched = dict(article)
                enriched["_driver_hits"] = hits
                matched.append(enriched)
        matched.sort(key=lambda item: (item.get("_driver_hits", 0), item.get("_score", 0), item.get("published_ts", 0)), reverse=True)
        if matched:
            drivers.append({
                "id": driver_id, "title": definition["title"], "category": definition["category"],
                "articles": matched[:6], "score": sum(item.get("_driver_hits", 0) for item in matched[:8]),
                "lead": clean_text(matched[0].get("title", "")),
            })
    drivers.sort(key=lambda item: item["score"], reverse=True)
    if len(drivers) < 5:
        for driver_id in ["rates", "growth", "energy", "china", "trade", "technology"]:
            if driver_id not in {driver["id"] for driver in drivers}:
                definition = DRIVER_DEFINITIONS[driver_id]
                drivers.append({"id": driver_id, "title": definition["title"], "category": definition["category"], "articles": [], "score": 0, "lead": "No dominant verified headline in the current window."})
            if len(drivers) >= 5:
                break
    return drivers[:5]


def _sparkline_svg(values: list[float], width: int = 170, height: int = 45) -> str:
    values = [float(value) for value in values if value is not None]
    if len(values) < 2:
        return f'<svg viewBox="0 0 {width} {height}" class="spark"><path d="M4 {height/2:.1f} H{width-4}" /></svg>'
    lo, hi = min(values), max(values)
    span = hi - lo or 1.0
    points = []
    for index, value in enumerate(values):
        x = 4 + index * (width - 8) / (len(values) - 1)
        y = height - 5 - (value - lo) / span * (height - 10)
        points.append(f"{x:.1f},{y:.1f}")
    direction = "up" if values[-1] >= values[0] else "down"
    return f'<svg viewBox="0 0 {width} {height}" class="spark {direction}"><polyline points="{" ".join(points)}" /></svg>'


def _format_market_price(item: dict) -> str:
    if not item.get("ok"):
        return "Unavailable"
    price = float(item.get("price", 0))
    ticker = item.get("ticker", "")
    if ticker == "^TNX":
        return f"{price:.2f}%"
    if ticker == "EURUSD=X":
        return f"{price:.4f}"
    if ticker in {"BZ=F", "GC=F"}:
        return f"{price:,.2f}"
    return f"{price:,.1f}"


def _market_overview_chart(snapshot: list[dict]) -> go.Figure:
    chart_tickers = {"^GSPC": "S&P 500", "^STOXX50E": "Euro Stoxx 50", "^N225": "Nikkei 225", "^HSI": "Hang Seng"}
    fig = go.Figure()
    palette = ["#6de2a0", "#8f6bff", "#49b9ff", "#f6c85f"]
    color_index = 0
    for item in snapshot:
        if item.get("ticker") not in chart_tickers or not item.get("ok"):
            continue
        points = item.get("recent_points") or item.get("points", [])
        if len(points) < 2:
            continue
        first = points[0][1]
        x_values = [datetime.fromtimestamp(ts, tz=timezone.utc) for ts, _ in points]
        y_values = [((value / first) - 1) * 100 for _, value in points]
        fig.add_trace(go.Scatter(
            x=x_values, y=y_values, mode="lines", name=chart_tickers[item["ticker"]],
            line=dict(width=2.2, color=palette[color_index % len(palette)]),
            hovertemplate="%{x|%d %b %H:%M}<br>%{y:+.2f}%<extra>%{fullData.name}</extra>",
        ))
        color_index += 1
    fig.add_hline(y=0, line_width=1, line_dash="dot", line_color="rgba(210,220,255,.25)")
    fig.update_layout(
        height=275, margin=dict(l=8, r=8, t=12, b=4),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#aeb8d5", size=11), hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        xaxis=dict(showgrid=False, zeroline=False, tickformat="%d %b", color="#8390b4"),
        yaxis=dict(showgrid=True, gridcolor="rgba(130,150,210,.10)", zeroline=False, ticksuffix="%", color="#8390b4"),
    )
    return fig


def _holding_chart(holding_name: str, history: dict) -> go.Figure:
    fig = go.Figure()
    points = history.get("recent_points") or history.get("points", [])
    if points:
        x_values = [datetime.fromtimestamp(ts, tz=timezone.utc) for ts, _ in points]
        y_values = [value for _, value in points]
        positive = y_values[-1] >= y_values[0] if len(y_values) >= 2 else True
        line_color = "#55df91" if positive else "#ff6e83"
        fig.add_trace(go.Scatter(
            x=x_values, y=y_values, mode="lines", fill="tozeroy",
            line=dict(width=2.5, color=line_color), fillcolor="rgba(83,223,145,.08)" if positive else "rgba(255,110,131,.08)",
            name=holding_name, hovertemplate="%{x|%d %b %H:%M}<br>%{y:,.2f}<extra></extra>",
        ))
    fig.update_layout(
        height=360, margin=dict(l=12, r=12, t=15, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#aeb8d5"), showlegend=False,
        xaxis=dict(showgrid=False, color="#8390b4"),
        yaxis=dict(showgrid=True, gridcolor="rgba(130,150,210,.10)", color="#8390b4"),
    )
    return fig


def _article_evidence_text(articles: list[dict], max_items: int = 12) -> str:
    lines = []
    for index, article in enumerate(articles[:max_items], start=1):
        publisher = source_name(article.get("domain") or article.get("url", ""), SOURCE_MAPS["Balanced sources"], article.get("source", ""))
        summary = clean_text(article.get("summary", ""))[:650]
        lines.append(
            f"[{index}] {article.get('published', '')} | {publisher} | {clean_text(article.get('title', ''))}\n"
            f"Snippet: {summary or 'No snippet supplied.'}"
        )
    return "\n\n".join(lines) if lines else "No verified articles were found inside the 48-hour window."


def _price_evidence_text(snapshot: list[dict]) -> str:
    lines = []
    for item in snapshot:
        if item.get("ok"):
            lines.append(f"- {item['name']}: {_format_market_price(item)}, change over {item.get('basis', 'latest window')} {item.get('change_48h', 0):+.2f}%")
    return "\n".join(lines) or "No live market data was available."


def _extract_openai_text(payload: dict) -> str:
    if payload.get("output_text"):
        return clean_text(payload["output_text"])
    parts = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(content["text"])
    return "\n".join(parts).strip()


def _call_openai(prompt: str, max_output_tokens: int) -> tuple[str, str]:
    api_key = _safe_secret("OPENAI_API_KEY")
    if not api_key:
        return "", "OPENAI_API_KEY is not configured."
    model = _safe_secret("OPENAI_MODEL", "gpt-5-mini")
    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "input": prompt, "max_output_tokens": max_output_tokens},
            timeout=95,
        )
        if response.status_code >= 400:
            message = clean_text(response.text)[:500]
            return "", f"OpenAI API returned HTTP {response.status_code}: {message}"
        text = _extract_openai_text(response.json())
        return (text, "") if text else ("", "The OpenAI response did not contain text.")
    except Exception as exc:
        return "", f"OpenAI request failed: {exc}"


def _trim_to_max_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    candidate = " ".join(words[:max_words])
    sentence_end = max(candidate.rfind("."), candidate.rfind("!"), candidate.rfind("?"))
    if sentence_end > len(candidate) * .72:
        candidate = candidate[:sentence_end + 1]
    return candidate.strip()


def _fallback_market_digest(snapshot: list[dict], articles: list[dict], limits: tuple[int, int]) -> str:
    available = [item for item in snapshot if item.get("ok")]
    movers = sorted(available, key=lambda item: abs(item.get("change_48h", 0)), reverse=True)
    sentences = [
        "AI generation is not configured, so this is a factual evidence digest built from the live market snapshot and selected 48-hour headlines rather than an AI-written causal conclusion."
    ]
    if movers:
        strongest = movers[0]
        direction = "rose" if strongest.get("change_48h", 0) >= 0 else "fell"
        sentences.append(
            f"The largest move among the monitored indicators was {strongest['name']}, which {direction} {abs(strongest.get('change_48h', 0)):.2f}% over {strongest.get('basis', 'the available window')}."
        )
    for item in movers[1:5]:
        direction = "up" if item.get("change_48h", 0) >= 0 else "down"
        sentences.append(f"{item['name']} was {direction} {abs(item.get('change_48h', 0)):.2f}%.")
    if articles:
        sentences.append("The main verified news themes selected by the app were:")
        for article in articles[:6]:
            publisher = source_name(article.get("domain") or article.get("url", ""), SOURCE_MAPS["Balanced sources"], article.get("source", ""))
            sentences.append(f"{clean_text(article.get('title', ''))} ({publisher}).")
    sentences.append("These items may help explain market direction, but a price move should not be attributed to one headline unless the source makes that connection explicitly.")
    return _trim_to_max_words(" ".join(sentences), limits[1] + 50)


def _fallback_holding_digest(holding_name: str, history: dict, articles: list[dict], market_articles: list[dict], limits: tuple[int, int]) -> str:
    config = HOLDING_BRIEFING_DATA[holding_name]
    text = [
        "AI generation is not configured, so this is an evidence digest rather than an AI-generated attribution.",
        f"For {holding_name}, the monitored market price changed {history.get('change_48h', 0):+.2f}% over {history.get('basis', 'the available period')}.",
        f"The most relevant exposure areas are {config['context']}.",
    ]
    selected = articles[:5] or market_articles[:5]
    if selected:
        text.append("Selected verified headlines from the last 48 hours include:")
        for article in selected:
            publisher = source_name(article.get("domain") or article.get("url", ""), SOURCE_MAPS["Balanced sources"], article.get("source", ""))
            text.append(f"{clean_text(article.get('title', ''))} ({publisher}).")
    else:
        text.append("No sufficiently relevant, timestamped article was found inside the strict 48-hour window.")
    text.append("The evidence does not by itself prove causation. Company-specific news should be separated from sector, macro and broad-market effects.")
    if config.get("proxy_note"):
        text.append(config["proxy_note"])
    return _trim_to_max_words(" ".join(text), limits[1] + 50)


def generate_market_briefing(snapshot: list[dict], articles: list[dict], length_label: str) -> dict:
    limits = BRIEFING_LENGTHS[length_label]
    prompt = f"""
You are writing a 48-hour market briefing for a private investor. Use only the supplied market data and article evidence. Write in plain, easy-to-understand English, but keep it informative.

Length: {limits[0]}–{limits[1]} words. You may exceed the upper limit by at most 50 words only when needed for clarity. Do not pad the answer when evidence is weak.

Required content:
- Explain what moved the overall market and the likely reasons.
- Separate confirmed reporting from reasonable inference.
- Mention the most useful European and Asian signals.
- Explain rates, currencies or commodities only when relevant.
- State clearly when no single cause can be confirmed.
- Use source markers [1], [2], etc. only for claims supported by the numbered evidence.
- Do not provide investment advice or invent figures.

MARKET DATA:
{_price_evidence_text(snapshot)}

SELECTED NEWS FROM THE LAST 48 HOURS:
{_article_evidence_text(articles, 14)}
""".strip()
    text, error = _call_openai(prompt, max_output_tokens={"Short — 100–200 words": 1200, "Medium — 200–350 words": 1800, "Long — 350–500 words": 2400}[length_label])
    generated_by = "OpenAI" if text else "Evidence digest"
    if not text:
        text = _fallback_market_digest(snapshot, articles, limits)
    text = _trim_to_max_words(text, limits[1] + 50)
    return {"text": text, "error": error, "generated_by": generated_by, "length": length_label, "articles": articles[:14], "created_at": datetime.now().astimezone().strftime("%d %b %Y, %H:%M")}


def generate_holding_briefing(holding_name: str, history: dict, articles: list[dict], market_articles: list[dict], length_label: str) -> dict:
    limits = BRIEFING_LENGTHS[length_label]
    config = HOLDING_BRIEFING_DATA[holding_name]
    prompt = f"""
Write a 48-hour briefing for the investor's holding: {holding_name}. Use only the supplied evidence. The goal is to understand why the holding's market price may have moved.

Length: {limits[0]}–{limits[1]} words. You may exceed the upper limit by at most 50 words only when necessary. Use clear, accessible English.

Required structure and reasoning:
1. State the observed price move and the data basis.
2. Explain the most relevant company-specific news, if any.
3. Explain sector and broad-market influences.
4. Classify the explanation as Confirmed cause, Likely contributor, or No clear explanation found. Do not call something a cause unless the supplied evidence explicitly connects it to the move.
5. Explain whether the development looks temporary or potentially important over the medium term, while acknowledging uncertainty.
6. Use source markers [1], [2], etc. only for evidence-backed claims.
7. Do not give buy/sell advice and do not invent facts.

Relevant exposure context: {config['context']}
Price: {history.get('price', 'unavailable')}
Price change over {history.get('basis', 'available window')}: {history.get('change_48h', 0):+.2f}%
Daily change: {history.get('daily_change', 0):+.2f}%
Special note: {config.get('proxy_note', 'None')}

SELECTED HOLDING, SECTOR AND BROADER MARKET NEWS, LAST 48 HOURS:
{_article_evidence_text(_deduplicate_news(articles[:12] + market_articles[:8]), 20)}
""".strip()
    text, error = _call_openai(prompt, max_output_tokens={"Short — 100–200 words": 1200, "Medium — 200–350 words": 1800, "Long — 350–500 words": 2400}[length_label])
    generated_by = "OpenAI" if text else "Evidence digest"
    if not text:
        text = _fallback_holding_digest(holding_name, history, articles, market_articles, limits)
    text = _trim_to_max_words(text, limits[1] + 50)
    combined_articles = _deduplicate_news(articles[:12] + market_articles[:8])
    return {"text": text, "error": error, "generated_by": generated_by, "length": length_label, "articles": combined_articles, "created_at": datetime.now().astimezone().strftime("%d %b %Y, %H:%M")}


def generate_driver_detail(driver: dict) -> dict:
    definition = DRIVER_DEFINITIONS[driver["id"]]
    prompt = f"""
Explain the current market driver '{driver['title']}' using only the supplied 48-hour evidence. Use three short sections with these exact headings:

What it actually is
What this means
Who may be affected and why

Use easy-to-understand but informative English. Distinguish general educational explanation from what the current articles actually report. Do not invent causal links. Keep the full answer between 180 and 320 words and use source markers [1], [2], etc. for current claims.

GENERAL DEFINITION:
What it is: {definition['what']}
Meaning: {definition['meaning']}
Typical effects: {definition['effects']}

CURRENT 48-HOUR EVIDENCE:
{_article_evidence_text(driver.get('articles', []), 8)}
""".strip()
    text, error = _call_openai(prompt, max_output_tokens=1400)
    if not text:
        current = ""
        if driver.get("articles"):
            current = " Current evidence includes " + "; ".join(clean_text(article.get("title", "")) for article in driver["articles"][:3]) + "."
        else:
            current = " No dominant verified headline for this driver was found inside the strict 48-hour window."
        text = (
            f"### What it actually is\n{definition['what']}{current}\n\n"
            f"### What this means\n{definition['meaning']}\n\n"
            f"### Who may be affected and why\n{definition['effects']}"
        )
    return {"text": text, "error": error, "generated_by": "OpenAI" if not error and _safe_secret("OPENAI_API_KEY") else "Educational fallback", "articles": driver.get("articles", []), "created_at": datetime.now().astimezone().strftime("%d %b %Y, %H:%M")}


def _render_briefing_css() -> None:
    st.markdown("""
    <style>
    .main .block-container{max-width:1540px;padding:1.15rem 1.65rem 4rem!important}
    .mb-topbar{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin:8px 0 18px}.mb-kicker{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#8c98bd}.mb-topbar h1{font-size:34px!important;margin:5px 0 3px!important}.mb-sub{color:#9ea9ca;font-size:13px}.mb-status{color:#66e49a;border:1px solid rgba(80,221,143,.25);background:rgba(45,180,105,.08);padding:8px 11px;border-radius:999px;font-size:11px;white-space:nowrap}
    .mb-panel{background:linear-gradient(145deg,rgba(13,22,43,.97),rgba(7,14,30,.99));border:1px solid rgba(133,151,255,.18);border-radius:16px;padding:16px;box-shadow:0 15px 45px rgba(0,0,0,.18)}
    [data-testid="stVerticalBlockBorderWrapper"]{background:linear-gradient(145deg,rgba(13,22,43,.97),rgba(7,14,30,.99))!important;border:1px solid rgba(133,151,255,.18)!important;border-radius:16px!important;box-shadow:0 15px 45px rgba(0,0,0,.18)!important}
    .mb-section-title{font-size:17px;font-weight:680;color:#f5f7ff;margin:4px 0 12px}.mb-section-note{color:#8f9abb;font-size:12px;margin-top:-7px;margin-bottom:12px}
    [data-testid="stForm"]{border:1px solid rgba(69,221,137,.48)!important;background:linear-gradient(145deg,rgba(22,79,52,.18),rgba(9,35,27,.22))!important;border-radius:14px!important;padding:13px 14px 4px!important}
    [data-testid="stForm"] [data-testid="stWidgetLabel"] p{color:#bcebd0!important}
    .proxy-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.proxy-card{min-height:116px;padding:12px;border:1px solid rgba(132,153,255,.17);border-radius:13px;background:linear-gradient(145deg,rgba(17,26,53,.97),rgba(9,15,33,.98));overflow:hidden}.proxy-top{display:flex;justify-content:space-between;gap:8px}.proxy-name{font-size:12px;font-weight:680;color:#f3f5ff}.proxy-region{font-size:9px;color:#7f8db3;text-transform:uppercase;letter-spacing:.08em}.proxy-price{margin-top:7px;font-size:16px;font-weight:700;color:#fff}.proxy-change{font-size:11px;margin-top:2px}.proxy-role{font-size:9.5px;color:#8f9abc;margin-top:3px}.spark{width:100%;height:35px;margin-top:5px}.spark polyline,.spark path{fill:none;stroke:#8b98b8;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}.spark.up polyline{stroke:#4cdf88}.spark.down polyline{stroke:#ff687e}
    .driver-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:11px}.driver-card{display:block;text-decoration:none!important;min-height:136px;padding:14px;border:1px solid rgba(133,151,255,.18);border-radius:14px;background:linear-gradient(145deg,rgba(16,25,51,.96),rgba(8,15,32,.98));transition:.22s}.driver-card:hover{transform:translateY(-3px);border-color:rgba(143,92,255,.62);box-shadow:0 13px 32px rgba(75,48,190,.20)}.driver-category{font-size:9px;text-transform:uppercase;letter-spacing:.1em;color:#9b7eff}.driver-title{font-size:13px;font-weight:680;color:#f5f6ff;margin-top:7px}.driver-lead{font-size:10px;line-height:1.42;color:#9ba5c3;margin-top:8px}.driver-count{font-size:9px;color:#62d995;margin-top:9px}
    .holding-card-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.holding-brief-card{display:block;text-decoration:none!important;min-height:182px;padding:15px;border:1px solid rgba(133,151,255,.18);border-radius:15px;background:linear-gradient(145deg,rgba(17,26,53,.97),rgba(8,14,31,.99));transition:.23s}.holding-brief-card:hover{transform:translateY(-4px);border-color:rgba(143,92,255,.64);box-shadow:0 15px 34px rgba(64,42,170,.23)}.holding-avatar{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;background:linear-gradient(145deg,#7650e7,#254fae);color:#fff;font-size:11px;font-weight:750}.holding-card-name{color:#f5f7ff;font-size:12px;font-weight:680;margin-top:10px;min-height:34px}.holding-card-price{font-size:10px;color:#8794b7;margin-top:3px}.holding-impact{display:flex;align-items:center;justify-content:space-between;font-size:10px;color:#94a0bf;margin-top:8px}.pos{color:#4cdf88!important}.neg{color:#ff687e!important}
    .brief-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:7px 0 20px}.brief-tab{display:inline-flex;padding:9px 13px;border-radius:10px;border:1px solid rgba(133,151,255,.18);background:rgba(255,255,255,.025);text-decoration:none!important;color:#aeb8d4!important;font-size:12px}.brief-tab.active,.brief-tab:hover{color:#fff!important;border-color:rgba(143,92,255,.58);background:rgba(116,70,239,.15)}
    .briefing-copy{font-size:15px;line-height:1.72;color:#e8ebf6}.briefing-meta{display:flex;gap:10px;flex-wrap:wrap;margin:11px 0 18px}.meta-pill{font-size:10px;color:#aab4d2;border:1px solid rgba(133,151,255,.17);border-radius:999px;padding:6px 9px;background:rgba(255,255,255,.025)}
    .source-list{display:grid;gap:8px}.source-row{display:grid;grid-template-columns:28px 1fr auto;gap:10px;align-items:center;padding:10px 12px;border-top:1px solid rgba(133,151,255,.11);color:#dfe4f4}.source-number{color:#9b7eff;font-size:11px}.source-row a{color:#eef1ff!important;text-decoration:none!important;font-size:12px}.source-row a:hover{color:#ac91ff!important}.source-meta{font-size:10px;color:#7f8baa}
    .proxy-note{margin:10px 0;padding:11px 13px;border-radius:11px;border:1px solid rgba(246,200,95,.25);background:rgba(246,200,95,.06);color:#e7d9aa;font-size:11px;line-height:1.5}
    @media(max-width:1120px){.proxy-grid{grid-template-columns:repeat(3,1fr)}.driver-grid{grid-template-columns:repeat(3,1fr)}.holding-card-grid{grid-template-columns:repeat(3,1fr)}}
    @media(max-width:760px){.main .block-container{padding:1rem .75rem 4rem!important}.mb-topbar{display:block}.mb-status{display:inline-block;margin-top:10px}.proxy-grid{grid-template-columns:repeat(2,1fr)}.driver-grid{grid-template-columns:1fr}.holding-card-grid{grid-template-columns:1fr}.source-row{grid-template-columns:24px 1fr}.source-meta{grid-column:2}.briefing-copy{font-size:14px}}
    </style>
    """, unsafe_allow_html=True)


def _render_source_list(articles: list[dict]) -> None:
    unique = _deduplicate_news(articles)
    if not unique:
        st.info("No timestamped, relevant source was found inside the strict 48-hour window.")
        return
    rows = []
    for index, article in enumerate(unique[:16], start=1):
        title = html_lib.escape(clean_text(article.get("title", "Untitled article")))
        url = html_lib.escape(clean_text(article.get("url", "")), quote=True)
        publisher = html_lib.escape(source_name(article.get("domain") or article.get("url", ""), SOURCE_MAPS["Balanced sources"], article.get("source", "")))
        published = html_lib.escape(clean_text(article.get("published", "")))
        rows.append(f'<div class="source-row"><div class="source-number">[{index}]</div><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a><div class="source-meta">{publisher} · {published}</div></div>')
    st.markdown(f'<div class="source-list">{"".join(rows)}</div>', unsafe_allow_html=True)


def _render_market_cards(snapshot: list[dict]) -> None:
    cards = []
    for item in snapshot:
        values = [value for _, value in (item.get("recent_points") or item.get("points", []))]
        change = float(item.get("change_48h", 0)) if item.get("ok") else 0.0
        change_class = "pos" if change >= 0 else "neg"
        change_text = f"{change:+.2f}%" if item.get("ok") else "No quote"
        cards.append(f"""
        <div class="proxy-card">
          <div class="proxy-top"><div><div class="proxy-name">{html_lib.escape(item['name'])}</div><div class="proxy-region">{html_lib.escape(item['region'])}</div></div><div class="proxy-change {change_class}">{change_text}</div></div>
          <div class="proxy-price">{html_lib.escape(_format_market_price(item))}</div>
          <div class="proxy-role">{html_lib.escape(item['role'])}</div>
          {_sparkline_svg(values[-30:])}
        </div>""")
    st.markdown(f'<div class="proxy-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def _render_driver_cards(drivers: list[dict]) -> None:
    cards = []
    for driver in drivers:
        lead = clean_text(driver.get("lead", ""))
        if len(lead) > 120:
            lead = lead[:117] + "…"
        cards.append(f"""
        <a class="driver-card" href="?page=briefing&view=driver&driver={quote_plus(driver['id'])}" target="_self">
          <div class="driver-category">{html_lib.escape(driver['category'])}</div>
          <div class="driver-title">{html_lib.escape(driver['title'])}</div>
          <div class="driver-lead">{html_lib.escape(lead)}</div>
          <div class="driver-count">{len(driver.get('articles', []))} current evidence item(s) · Open explanation →</div>
        </a>""")
    st.markdown(f'<div class="driver-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def _render_holding_cards() -> None:
    cards = []
    for holding in PORTFOLIO_HOLDINGS:
        name = holding["name"]
        config = HOLDING_BRIEFING_DATA[name]
        history = fetch_yahoo_history(config["ticker"])
        values = [value for _, value in (history.get("recent_points") or history.get("points", []))]
        change = float(history.get("change_48h", 0)) if history.get("ok") else 0.0
        change_class = "pos" if change >= 0 else "neg"
        initials = html_lib.escape(holding.get("abbr", name[:3]))
        label = html_lib.escape(config.get("chart_label", name))
        price = _format_market_price({**history, "ticker": config["ticker"]}) if history.get("ok") else "Unavailable"
        cards.append(f"""
        <a class="holding-brief-card" href="?page=briefing&view=holding&asset={quote_plus(name)}" target="_self">
          <div class="holding-avatar">{initials[:8]}</div>
          <div class="holding-card-name">{html_lib.escape(name)}</div>
          <div class="holding-card-price">{label}: {html_lib.escape(price)}</div>
          {_sparkline_svg(values[-30:], width=180, height=47)}
          <div class="holding-impact"><span>48h / latest points</span><b class="{change_class}">{change:+.2f}%</b></div>
          <div class="holding-impact"><span>Open price chart & briefing</span><span>→</span></div>
        </a>""")
    st.markdown(f'<div class="holding-card-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def _render_overview() -> None:
    with st.spinner("Loading the latest market snapshot and 48-hour news…"):
        snapshot = load_market_snapshot()
        market_news = fetch_market_news_48h()
        drivers = build_driver_snapshot(market_news)
    st.session_state["market_snapshot"] = snapshot
    st.session_state["market_news_48h"] = market_news
    st.session_state["market_driver_snapshot"] = drivers

    st.markdown(f"""
    <div class="mb-topbar"><div><div class="mb-kicker">JUGG · Program 03</div><h1>Market Briefing</h1><div class="mb-sub">Live market indicators and selected news from the last 48 hours.</div></div><div class="mb-status">● {len(market_news)} selected news items</div></div>
    """, unsafe_allow_html=True)

    left, right = st.columns([1.05, 1.65], gap="medium")
    with left:
        with st.container(border=True):
            st.markdown('<div class="mb-section-title">Market Overview</div><div class="mb-section-note">Normalized movement of major US, European and Asian indices.</div>', unsafe_allow_html=True)
            st.plotly_chart(_market_overview_chart(snapshot), use_container_width=True, config={"displayModeBar": False})
            with st.form("overall_market_briefing_form", border=True):
                form_left, form_right = st.columns([1.05, .95])
                with form_left:
                    length_label = st.selectbox("Briefing length", list(BRIEFING_LENGTHS), index=1, key="market_briefing_length")
                with form_right:
                    submitted = st.form_submit_button("✦ Generate Briefing", use_container_width=True)
            if submitted:
                with st.spinner("Selecting evidence and writing the market briefing…"):
                    st.session_state["generated_market_briefing"] = generate_market_briefing(snapshot, market_news, length_label)
                _navigate_briefing("market_summary")

    with right:
        with st.container(border=True):
            st.markdown('<div class="mb-section-title">Market Health Indicators</div><div class="mb-section-note">Twelve bellwethers and market proxies, including two European and two Asian indices.</div>', unsafe_allow_html=True)
            _render_market_cards(snapshot)

    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('<div class="mb-section-title">Top Drivers <span style="font-size:11px;color:#8793b7;font-weight:400">· click a card for a clearer explanation</span></div>', unsafe_allow_html=True)
        _render_driver_cards(drivers)

    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('<div class="mb-section-title">Your Holdings</div><div class="mb-section-note">Five cards per row. New holdings will automatically continue on the next row.</div>', unsafe_allow_html=True)
        _render_holding_cards()


def _render_market_summary() -> None:
    result = st.session_state.get("generated_market_briefing")
    st.markdown('<div class="brief-tabs"><a class="brief-tab" href="?page=briefing&view=overview" target="_self">Overview</a><a class="brief-tab active" href="?page=briefing&view=market_summary" target="_self">Generated market briefing</a></div>', unsafe_allow_html=True)
    st.markdown("# Overall Market Briefing")
    if not result:
        st.warning("No market briefing has been generated in this session.")
        if st.button("Return to Market Overview"):
            _navigate_briefing("overview")
        return
    word_count = len(result["text"].split())
    st.markdown(f'<div class="briefing-meta"><span class="meta-pill">{html_lib.escape(result["length"])}</span><span class="meta-pill">{word_count} words</span><span class="meta-pill">Generated {html_lib.escape(result["created_at"])}</span><span class="meta-pill">{html_lib.escape(result["generated_by"])}</span></div>', unsafe_allow_html=True)
    if result.get("error"):
        st.info(f"AI service note: {result['error']} The page therefore shows the evidence-based fallback digest.")
    with st.container(border=True):
        st.markdown(result["text"])
    st.markdown("## Sources used")
    _render_source_list(result.get("articles", []))


def _render_driver_detail(driver_id: str) -> None:
    market_news = st.session_state.get("market_news_48h") or fetch_market_news_48h()
    drivers = st.session_state.get("market_driver_snapshot") or build_driver_snapshot(market_news)
    driver = next((item for item in drivers if item["id"] == driver_id), None)
    if not driver and driver_id in DRIVER_DEFINITIONS:
        definition = DRIVER_DEFINITIONS[driver_id]
        driver = {"id": driver_id, "title": definition["title"], "category": definition["category"], "articles": [], "lead": ""}
    st.markdown('<div class="brief-tabs"><a class="brief-tab" href="?page=briefing&view=overview" target="_self">Overview</a><span class="brief-tab active">Driver explanation</span></div>', unsafe_allow_html=True)
    if not driver:
        st.error("This driver could not be found.")
        return
    cache_key = f"driver_detail_{driver_id}_{driver.get('lead', '')[:35]}"
    if cache_key not in st.session_state:
        with st.spinner("Preparing the driver explanation…"):
            st.session_state[cache_key] = generate_driver_detail(driver)
    result = st.session_state[cache_key]
    st.markdown(f"# {driver['title']}")
    st.caption(f"{driver['category']} · Based on selected news from the last 48 hours")
    if result.get("error"):
        st.info(f"AI service note: {result['error']} The educational fallback is shown instead.")
    with st.container(border=True):
        st.markdown(result["text"])
    st.markdown("## Current evidence")
    _render_source_list(result.get("articles", []))


def _render_holding_detail(holding_name: str) -> None:
    if holding_name not in HOLDING_BRIEFING_DATA:
        st.error("The selected holding is not in the current portfolio.")
        return
    config = HOLDING_BRIEFING_DATA[holding_name]
    history = fetch_yahoo_history(config["ticker"])
    st.markdown(f'<div class="brief-tabs"><a class="brief-tab" href="?page=briefing&view=overview" target="_self">Overview</a><span class="brief-tab active">{html_lib.escape(holding_name)}</span></div>', unsafe_allow_html=True)
    st.markdown(f"# {holding_name}")
    st.caption("Price chart and 48-hour holding briefing")
    if config.get("proxy_note"):
        st.markdown(f'<div class="proxy-note">{html_lib.escape(config["proxy_note"])}</div>', unsafe_allow_html=True)
    chart_col, control_col = st.columns([1.6, .8], gap="medium")
    with chart_col:
        with st.container(border=True):
            st.markdown('<div class="mb-section-title">Recent price movement</div>', unsafe_allow_html=True)
            if history.get("ok"):
                st.plotly_chart(_holding_chart(holding_name, history), use_container_width=True, config={"displayModeBar": False})
                change_class = "pos" if history.get("change_48h", 0) >= 0 else "neg"
                st.markdown(f'<div class="briefing-meta"><span class="meta-pill">Price {_format_market_price({**history, "ticker": config["ticker"]})}</span><span class="meta-pill {change_class}">{history.get("change_48h", 0):+.2f}% over {html_lib.escape(history.get("basis", "available window"))}</span><span class="meta-pill">Daily {history.get("daily_change", 0):+.2f}%</span></div>', unsafe_allow_html=True)
            else:
                st.warning("The price chart could not be loaded. The briefing can still use the selected news evidence.")
    with control_col:
        with st.container(border=True):
            st.markdown('<div class="mb-section-title">Generate holding briefing</div><div class="mb-section-note">Company, sector and market evidence from the last 48 hours.</div>', unsafe_allow_html=True)
            with st.form(f"holding_form_{holding_name}", border=True):
                length_label = st.selectbox("Briefing length", list(BRIEFING_LENGTHS), index=1, key=f"holding_length_{holding_name}")
                submitted = st.form_submit_button("✦ Generate Briefing", use_container_width=True)
            if submitted:
                with st.spinner(f"Selecting news and explaining {holding_name}'s move…"):
                    holding_news = fetch_holding_news_48h(holding_name)
                    market_news = st.session_state.get("market_news_48h") or fetch_market_news_48h()
                    result = generate_holding_briefing(holding_name, history, holding_news, market_news, length_label)
                    st.session_state[f"generated_holding_briefing_{holding_name}"] = result
                _navigate_briefing("holding_summary", asset=holding_name)


def _render_holding_summary(holding_name: str) -> None:
    result = st.session_state.get(f"generated_holding_briefing_{holding_name}")
    st.markdown(f'<div class="brief-tabs"><a class="brief-tab" href="?page=briefing&view=overview" target="_self">Overview</a><a class="brief-tab" href="?page=briefing&view=holding&asset={quote_plus(holding_name)}" target="_self">Price & controls</a><span class="brief-tab active">Generated briefing</span></div>', unsafe_allow_html=True)
    st.markdown(f"# {holding_name} Briefing")
    if not result:
        st.warning("No briefing has been generated for this holding in the current session.")
        return
    word_count = len(result["text"].split())
    st.markdown(f'<div class="briefing-meta"><span class="meta-pill">{html_lib.escape(result["length"])}</span><span class="meta-pill">{word_count} words</span><span class="meta-pill">Generated {html_lib.escape(result["created_at"])}</span><span class="meta-pill">{html_lib.escape(result["generated_by"])}</span></div>', unsafe_allow_html=True)
    if result.get("error"):
        st.info(f"AI service note: {result['error']} The page therefore shows the evidence-based fallback digest.")
    with st.container(border=True):
        st.markdown(result["text"])
    st.markdown("## Sources used")
    _render_source_list(result.get("articles", []))


def render_market_briefing() -> None:
    _render_briefing_css()
    st.markdown('<a class="back-link" href="?page=hub" target="_self">← Back to programs</a><style>.back-link{display:inline-flex;padding:9px 13px;border:1px solid rgba(255,255,255,.13);border-radius:11px;color:#eef1ff!important;text-decoration:none!important;background:rgba(255,255,255,.04);margin-bottom:8px}.back-link:hover{border-color:rgba(143,92,255,.5);background:rgba(143,92,255,.10)}</style>', unsafe_allow_html=True)
    view = _query_value("view", "overview")
    if view == "market_summary":
        _render_market_summary()
    elif view == "driver":
        _render_driver_detail(_query_value("driver", "rates"))
    elif view == "holding":
        _render_holding_detail(_query_value("asset", "Siemens Healthineers"))
    elif view == "holding_summary":
        _render_holding_summary(_query_value("asset", "Siemens Healthineers"))
    else:
        _render_overview()

page = st.query_params.get("page", "hub")
if isinstance(page, list):
    page = page[0] if page else "hub"

if page == "news":
    render_news_finder()
elif page == "portfolio":
    render_portfolio()
elif page == "briefing":
    render_market_briefing()
else:
    render_hub()
