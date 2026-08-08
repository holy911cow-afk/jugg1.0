
import calendar
import bisect
import csv
import html as html_lib
import io
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus, urlparse

import feedparser
import requests
import streamlit as st
import plotly.graph_objects as go
from streamlit.components.v1 import html as components_html


st.set_page_config(
    page_title="JUGG 5.0",
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
    render_app_nav("News Finder")
    st.markdown("""
    <div style="padding:10px 0 20px">
      <div style="font-size:12px;letter-spacing:.13em;text-transform:uppercase;color:#8d9ac3">JUGG · Program 01</div>
      <h1 style="font-size:39px;margin:7px 0 5px">News Finder</h1>
      <div style="color:#9da8ca">Company and sector news, ranked by relevance and source quality.</div>
    </div>""", unsafe_allow_html=True)

    with st.sidebar:
        st.header("News Finder controls")
        view_mode = st.radio("View mode", ["One selected company", "Full portfolio"], key="news_view_mode")
        selected_company = st.selectbox("Company", list(COMPANIES), key="news_company")
        source_mode = st.selectbox("Source quality mode", list(SOURCE_MAPS), index=1, key="news_source_mode")
        strict_sources = st.toggle("Only show selected trusted sources", value=False, key="news_strict_sources")
        top_n = st.slider("Articles per section", 3, 12, 5, key="news_top_n")
        recency_label = st.selectbox("Recency window", list(RECENCY_OPTIONS), index=1, key="news_recency")
        order_label = st.selectbox("Article order", list(ORDER_OPTIONS), key="news_order")
        include_yahoo_finance = st.toggle("Use Yahoo Finance company feed", value=True, key="news_yahoo")
        use_extra_queries = st.toggle("Use extra RSS queries", value=True, key="news_extra_queries")
        show_debug = st.toggle("Show debug details", value=False, key="news_debug")
        load_clicked = st.button("Load Articles", type="primary", use_container_width=True, key="news_load")
        if st.button("Clear saved results / cache", use_container_width=True, key="news_clear"):
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
    {"name": "Siemens Healthineers", "ticker": "SHL.DE", "abbr": "SHL", "saved_value_eur": 852.00, "original_investment_eur": 1010.50, "purchase_date": "10.03.2026", "country": "Germany", "country_iso3": "DEU", "area": "Healthcare", "fx_ticker": None},
    {"name": "Verbund", "ticker": "VER.VI", "abbr": "VER", "saved_value_eur": 838.50, "original_investment_eur": 922.50, "purchase_date": "05.05.2026", "country": "Austria", "country_iso3": "AUT", "area": "Renewable Energy", "fx_ticker": None},
    {"name": "Tomra Systems", "ticker": "TOM.OL", "abbr": "TOM", "saved_value_eur": 1011.60, "original_investment_eur": 1033.20, "purchase_date": "27.04.2026", "country": "Norway", "country_iso3": "NOR", "area": "Industrials / Recycling", "fx_ticker": "EURNOK=X"},
    {"name": "ANTA Sports", "ticker": "2020.HK", "abbr": "ANTA", "saved_value_eur": 944.13, "original_investment_eur": 1051.25, "purchase_date": "01.06.2026", "country": "China / Hong Kong", "country_iso3": "CHN", "area": "Consumer / Sportswear", "fx_ticker": "EURHKD=X"},
    {"name": "MS Europe 26/27 ABJ", "ticker": None, "proxy_ticker": "^STOXX50E", "abbr": "MS EU 26/27", "saved_value_eur": 1017.40, "original_investment_eur": 1005.00, "purchase_date": "24.04.2026", "country": "Europe exposure", "country_iso3": None, "area": "Structured Product", "fx_ticker": None},
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
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key="portfolio_country_chart")

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
# JUGG 5.0 shared navigation and portfolio model
# ============================================================
def render_app_nav(section: str) -> None:
    st.markdown(f"""
    <div class="jugg-app-nav">
      <div class="jugg-app-brand"><span>J</span><b>JUGG</b><em>{html_lib.escape(section)}</em></div>
      <a href="?page=hub" target="_self" aria-label="Return to programs">← Programs</a>
    </div>
    <style>
    .jugg-app-nav{{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:0 0 22px;padding:11px 13px;border:1px solid rgba(133,151,255,.17);border-radius:14px;background:rgba(8,14,31,.82);backdrop-filter:blur(14px)}}
    .jugg-app-brand{{display:flex;align-items:center;gap:9px;color:#f7f8ff}}.jugg-app-brand span{{width:28px;height:28px;display:grid;place-items:center;border-radius:9px;background:linear-gradient(145deg,#8b5cff,#3152cf);box-shadow:0 0 20px rgba(126,77,255,.35);font-weight:800}}.jugg-app-brand b{{font-size:14px}}.jugg-app-brand em{{font-style:normal;color:#7f8bab;font-size:11px;border-left:1px solid rgba(133,151,255,.18);padding-left:9px}}
    .jugg-app-nav a{{display:inline-flex;align-items:center;padding:9px 13px;border:1px solid rgba(133,151,255,.22);border-radius:10px;color:#edf0ff!important;background:rgba(255,255,255,.035);text-decoration:none!important;font-size:12px;transition:.2s}}.jugg-app-nav a:hover{{border-color:rgba(143,92,255,.6);background:rgba(116,70,239,.13);transform:translateY(-1px)}}
    @media(max-width:620px){{.jugg-app-brand em{{display:none}}}}
    </style>
    """, unsafe_allow_html=True)


PORTFOLIO_BASE_VALUE = 5022.45
PORTFOLIO_BASE_TS = int(datetime(2026, 5, 1, tzinfo=timezone.utc).timestamp())


def _point_value(points: list[tuple[int, float]], timestamp: int) -> float | None:
    if not points:
        return None
    stamps = [point[0] for point in points]
    index = bisect.bisect_right(stamps, timestamp) - 1
    if index < 0:
        index = 0
    return float(points[index][1])


def _position_factor(holding: dict, histories: dict, timestamp: int) -> float:
    price_ticker = holding.get("ticker") or holding.get("proxy_ticker")
    history = histories.get(price_ticker, {})
    points = history.get("points", [])
    if not points:
        return 1.0
    anchor = _point_value(points, PORTFOLIO_BASE_TS)
    current = _point_value(points, timestamp)
    if not anchor or current is None:
        return 1.0
    factor = current / anchor
    fx_ticker = holding.get("fx_ticker")
    if fx_ticker:
        fx_points = histories.get(fx_ticker, {}).get("points", [])
        fx_anchor = _point_value(fx_points, PORTFOLIO_BASE_TS)
        fx_current = _point_value(fx_points, timestamp)
        if fx_anchor and fx_current:
            # EURNOK and EURHKD are local-currency units per euro.
            factor *= fx_anchor / fx_current
    return factor


def _latest_trading_session_change(history: dict) -> float | None:
    """Return the move between the latest two valid daily trading points.

    Portfolio history is requested with interval=1d, so this deliberately avoids
    Yahoo's chartPreviousClose field, which can refer to the beginning of the
    requested range and incorrectly turn a one-day column into a multi-month move.
    """
    points = history.get("points", []) if history else []
    if len(points) < 2:
        return None
    latest_close = _as_float(points[-1][1])
    previous_close = _as_float(points[-2][1])
    if not previous_close:
        return None
    return ((latest_close / previous_close) - 1.0) * 100.0


def build_portfolio_snapshot() -> tuple[list[dict], list[tuple[int, float]], str]:
    holdings = get_portfolio_holdings()
    tickers = {item.get("ticker") or item.get("proxy_ticker") for item in holdings}
    tickers.update(item.get("fx_ticker") for item in holdings)
    tickers.discard(None)
    histories = {ticker: fetch_yahoo_history(ticker, "1y", "1d") for ticker in tickers}
    dates = sorted({PORTFOLIO_BASE_TS} | {
        timestamp for ticker, history in histories.items()
        if ticker not in {item.get("fx_ticker") for item in holdings}
        for timestamp, _ in history.get("points", []) if timestamp >= PORTFOLIO_BASE_TS
    })
    if not dates:
        dates = [PORTFOLIO_BASE_TS, int(datetime.now(timezone.utc).timestamp())]
    original_total = sum(max(0.0, _as_float(item.get("original_investment_eur"))) for item in holdings) or PORTFOLIO_BASE_VALUE
    scale = PORTFOLIO_BASE_VALUE / original_total
    series = []
    for timestamp in dates:
        value = sum(
            _as_float(item.get("original_investment_eur")) * scale * _position_factor(item, histories, timestamp)
            for item in holdings
        )
        series.append((timestamp, value))
    series[0] = (series[0][0], PORTFOLIO_BASE_VALUE)
    latest_ts = series[-1][0]
    rows = []
    for item in holdings:
        row = dict(item)
        ticker = item.get("ticker") or item.get("proxy_ticker")
        history = histories.get(ticker, {})
        current_value = _as_float(item.get("original_investment_eur")) * scale * _position_factor(item, histories, latest_ts)
        row["current_value_eur"] = current_value
        row["daily_pct"] = _latest_trading_session_change(history)
        row["market_price"] = history.get("price")
        row["currency"] = history.get("currency", "")
        if item.get("ticker") and history.get("ok"):
            row["source_status"] = "Market-based estimate"
        elif item.get("proxy_ticker") and history.get("ok"):
            row["source_status"] = "Proxy estimate — not product value"
        else:
            row["current_value_eur"] = _as_float(item.get("saved_value_eur"), current_value)
            row["source_status"] = "Saved value — quote unavailable"
        rows.append(row)
    available = sum(1 for item in holdings if histories.get(item.get("ticker") or item.get("proxy_ticker"), {}).get("ok"))
    status = f"{available}/{len(holdings)} market series refreshed"
    return rows, series, status


def live_portfolio_rows() -> tuple[list[dict], str]:
    rows, _, status = build_portfolio_snapshot()
    return rows, status


def _portfolio_chart(points: list[tuple[int, float]]) -> go.Figure:
    x_values = [datetime.fromtimestamp(timestamp, tz=timezone.utc) for timestamp, _ in points]
    y_values = [value for _, value in points]
    positive = y_values[-1] >= y_values[0] if len(y_values) > 1 else True
    color = "#59e09a" if positive else "#ff7186"
    floor = min(y_values) - max(8.0, (max(y_values) - min(y_values)) * .18)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x_values, y=[floor] * len(x_values), mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(
        x=x_values, y=y_values, mode="lines", fill="tonexty", name="Portfolio",
        line=dict(width=2.6, color=color, shape="spline", smoothing=.35),
        fillcolor="rgba(89,224,154,.10)" if positive else "rgba(255,113,134,.10)",
        hovertemplate="%{x|%d %b %Y}<br><b>€%{y:,.2f}</b><extra></extra>",
    ))
    fig.add_hline(y=PORTFOLIO_BASE_VALUE, line_dash="dot", line_width=1, line_color="rgba(169,139,255,.45)", annotation_text="€5,022.45 start", annotation_font_color="#a99ad4")
    fig.update_layout(
        height=390, margin=dict(l=5, r=8, t=20, b=5), hovermode="x unified", showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#aeb8d5", size=11),
        xaxis=dict(showgrid=False, color="#7f8bad", fixedrange=False, showspikes=True, spikemode="across", spikedash="dot", spikecolor="rgba(190,200,235,.35)"),
        yaxis=dict(showgrid=True, gridcolor="rgba(130,150,210,.09)", color="#7f8bad", tickprefix="€", fixedrange=False, rangemode="normal"),
    )
    return fig


def render_portfolio() -> None:
    render_app_nav("Portfolio")
    rows, full_series, price_status = build_portfolio_snapshot()
    total = sum(row["current_value_eur"] for row in rows)
    base_change = total - PORTFOLIO_BASE_VALUE
    base_pct = base_change / PORTFOLIO_BASE_VALUE * 100
    st.markdown("""
    <style>
    .main .block-container{max-width:1420px;padding:1.15rem 1.5rem 4rem!important}.p40-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin:5px 0 18px}.p40-head h1{font-size:36px!important;margin:0!important}.p40-sub{color:#8e9abb;font-size:13px;margin-top:5px}.p40-live{font-size:11px;color:#63df96;border:1px solid rgba(82,224,145,.25);background:rgba(45,180,105,.07);padding:8px 11px;border-radius:999px;white-space:nowrap}
    .p40-value{padding:22px 24px;margin-bottom:16px;border-radius:17px;border:1px solid rgba(133,151,255,.18);background:radial-gradient(circle at 100% 0,rgba(126,77,255,.14),transparent 38%),linear-gradient(145deg,rgba(15,24,49,.98),rgba(7,13,29,.99));box-shadow:0 18px 50px rgba(0,0,0,.2)}.p40-value small{display:block;color:#8f9aba;font-size:11px;letter-spacing:.08em;text-transform:uppercase}.p40-value strong{display:block;color:#fff;font-size:36px;letter-spacing:-.03em;margin-top:6px}.p40-value span{font-size:12px}.p40-note{color:#7f8bad;font-size:10px;margin-top:8px;line-height:1.45}
    .p40-section{margin:20px 0 9px;color:#f4f6ff;font-size:17px;font-weight:680}.p40-grid{display:grid;gap:10px}.p40-row{display:grid;grid-template-columns:1fr auto;gap:9px;color:#e6eaf8;font-size:12px}.p40-bar{grid-column:1/-1;height:5px;border-radius:99px;background:#151f39;overflow:hidden}.p40-bar i{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#6d4cff,#9e73ff)}
    .p40-table-head,.p40-holding{display:grid;grid-template-columns:2fr .8fr .8fr .75fr;gap:12px;align-items:center}.p40-table-head{padding:0 8px 9px;color:#7f8bad;font-size:10px}.p40-holding{padding:13px 8px;border-top:1px solid rgba(133,151,255,.11);font-size:12px;color:#edf0fa}.p40-holding b{font-size:12px}.p40-holding small{display:block;color:#7f8bad;font-size:9px;margin-top:3px}.pos{color:#4cdf88!important}.neg{color:#ff7186!important}
    [data-testid="stVerticalBlockBorderWrapper"]{background:linear-gradient(145deg,rgba(13,22,43,.97),rgba(7,14,30,.99))!important;border:1px solid rgba(133,151,255,.18)!important;border-radius:16px!important;box-shadow:0 15px 45px rgba(0,0,0,.16)!important}
    @media(max-width:760px){.main .block-container{padding:.8rem .75rem 4rem!important}.p40-head{display:block}.p40-live{display:inline-block;margin-top:10px}.p40-value strong{font-size:29px}.p40-table-head{display:none}.p40-holding{grid-template-columns:1.5fr .8fr .7fr}.p40-holding>*:nth-child(4){display:none}}
    </style>
    """, unsafe_allow_html=True)
    st.markdown(f'<div class="p40-head"><div><h1>Portfolio</h1><div class="p40-sub">Current value, allocation and performance since May 2026.</div></div><div class="p40-live">● {html_lib.escape(price_status)}</div></div>', unsafe_allow_html=True)
    change_class = "pos" if base_change >= 0 else "neg"
    st.markdown(f'<div class="p40-value"><small>Current Portfolio Value</small><strong>€{total:,.2f}</strong><span class="{change_class}">{base_change:+,.2f} · {base_pct:+.2f}% since 1 May 2026</span><div class="p40-note">Market-based estimate refreshed on opening. The structured product uses a clearly labelled Euro Stoxx 50 exposure proxy; exact broker valuation requires position quantities and the product quote.</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="p40-section">Portfolio Value</div>', unsafe_allow_html=True)
    timeline = st.radio("Portfolio chart period", ["1M", "3M", "Since May"], index=2, horizontal=True, label_visibility="collapsed", key="jugg40_portfolio_timeline")
    cutoff_days = {"1M": 31, "3M": 93}.get(timeline)
    chart_series = full_series
    if cutoff_days:
        cutoff = full_series[-1][0] - cutoff_days * 86400
        chart_series = [point for point in full_series if point[0] >= cutoff] or full_series
    with st.container(border=True):
        st.plotly_chart(_portfolio_chart(chart_series), use_container_width=True, config={"displayModeBar": False, "scrollZoom": True}, key="jugg40_portfolio_history")
        st.caption("Estimated portfolio series based on market-price and relevant EUR currency movements, normalized to €5,022.45 on 1 May 2026. Drag to zoom; double-click to reset.")

    countries, areas = {}, {}
    for row in rows:
        countries[row["country"]] = countries.get(row["country"], 0.0) + row["current_value_eur"]
        areas[row["area"]] = areas.get(row["area"], 0.0) + row["current_value_eur"]
    left, right = st.columns([1.08, .92], gap="medium")
    with left:
        with st.container(border=True):
            st.markdown('<div class="p40-section" style="margin-top:0">Invested Countries</div>', unsafe_allow_html=True)
            map_values = {}
            for row in rows:
                if row.get("country_iso3"):
                    map_values[row["country_iso3"]] = map_values.get(row["country_iso3"], 0.0) + row["current_value_eur"]
            fig = go.Figure(go.Choropleth(locations=list(map_values), z=list(map_values.values()), locationmode="ISO-3", colorscale=[[0,"#34206f"],[1,"#9566ff"]], showscale=False, marker_line_color="#34405e", marker_line_width=.5, hovertemplate="%{location}<br>€%{z:,.2f}<extra></extra>"))
            fig.update_geos(fitbounds="locations", visible=False, showframe=False, showcoastlines=False, showcountries=True, countrycolor="#26304b", showland=True, landcolor="#141c31", showocean=True, oceancolor="#091126", bgcolor="rgba(0,0,0,0)")
            fig.update_layout(margin=dict(l=0,r=0,t=0,b=0), height=330, paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key="jugg40_country_map")
            country_html = "".join(f'<div class="p40-row"><span>{html_lib.escape(name)}</span><b>{value/total*100:.1f}%</b><div class="p40-bar"><i style="width:{value/total*100:.1f}%"></i></div></div>' for name,value in sorted(countries.items(), key=lambda pair:pair[1], reverse=True))
            st.markdown(f'<div class="p40-grid">{country_html}</div>', unsafe_allow_html=True)
    with right:
        with st.container(border=True):
            st.markdown('<div class="p40-section" style="margin-top:0">Investment by Area</div>', unsafe_allow_html=True)
            area_html = "".join(f'<div class="p40-row"><span>{html_lib.escape(name)}</span><b>{value/total*100:.1f}% · €{value:,.0f}</b><div class="p40-bar"><i style="width:{value/total*100:.1f}%"></i></div></div>' for name,value in sorted(areas.items(), key=lambda pair:pair[1], reverse=True))
            st.markdown(f'<div class="p40-grid">{area_html}</div>', unsafe_allow_html=True)

    st.markdown('<div class="p40-section">Holdings Overview</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('<div class="p40-table-head"><span>Asset</span><span>Estimated value</span><span>Weight</span><span>Latest day</span></div>', unsafe_allow_html=True)
        holding_html = []
        for row in rows:
            daily_pct = row.get("daily_pct")
            daily_class = "pos" if daily_pct is not None and daily_pct >= 0 else ("neg" if daily_pct is not None else "")
            daily_text = f"{daily_pct:+.2f}%" if daily_pct is not None else "—"
            quote = f'{row.get("market_price"):,.2f} {row.get("currency", "")}' if row.get("market_price") is not None else "Quote unavailable"
            holding_html.append(f'<div class="p40-holding"><div><b>{html_lib.escape(row["name"])}</b> · {html_lib.escape(row["abbr"])}<small>{html_lib.escape(row["source_status"])} · {html_lib.escape(quote)}</small></div><div>€{row["current_value_eur"]:,.2f}</div><div>{row["current_value_eur"]/total*100:.1f}%</div><div class="{daily_class}">{daily_text}</div></div>')
        st.markdown("".join(holding_html), unsafe_allow_html=True)


# ============================================================
# Market Briefing
# ============================================================
BRIEFING_LENGTHS = {
    "Short — 100–200 words": (100, 200),
    "Medium — 200–350 words": (200, 350),
    "Long — 350–500 words": (350, 500),
}

MARKET_ASSETS = [
    {"name":"S&P 500","ticker":"^GSPC","category":"Equities","role":"Broad US shares","up":"Broad US risk appetite is improving.","down":"Investors are reducing exposure to large US shares."},
    {"name":"Nasdaq-100","ticker":"^NDX","category":"Equities","role":"Technology and growth shares","up":"Technology and growth shares are leading.","down":"Investors are becoming less willing to pay for growth."},
    {"name":"Euro Stoxx 50","ticker":"^STOXX50E","category":"Equities","role":"Large euro-area companies","up":"Large euro-area companies are attracting buying.","down":"Large euro-area companies are under pressure."},
    {"name":"MSCI Emerging Markets ETF","ticker":"EEM","category":"Equities","role":"Emerging-market share proxy","up":"Emerging-market risk appetite is improving.","down":"Investors are reducing emerging-market exposure."},
    {"name":"Gold","ticker":"GC=F","category":"Safe Havens","role":"Perceived financial safety","up":"Safe-haven demand is increasing.","down":"Demand for gold as protection is easing."},
    {"name":"US 10-Year Treasury yield","ticker":"^TNX","category":"Safe Havens","role":"Long-term US interest-rate benchmark","up":"Long-term borrowing costs are rising, which can pressure growth shares.","down":"Markets expect lower rates or weaker growth; bonds are attracting demand.","unit":"yield"},
    {"name":"Japanese yen","ticker":"JPY=X","category":"Safe Havens","role":"Yen strength versus US dollar","up":"Yen weakening: defensive currency demand is easing.","down":"Yen strengthening: investors may be becoming more cautious.","invert":True},
    {"name":"Swiss franc","ticker":"CHF=X","category":"Safe Havens","role":"Franc strength versus US dollar","up":"Swiss franc weakening: demand for currency safety is easing.","down":"Swiss franc strengthening: defensive demand is increasing.","invert":True},
    {"name":"Brent oil","ticker":"BZ=F","category":"Economic Drivers","role":"Energy and inflation pressure","up":"Oil is adding to energy costs and inflation pressure.","down":"Lower oil may ease inflation, but can also signal weaker demand."},
    {"name":"European natural gas / TTF","ticker":"TTF=F","category":"Economic Drivers","role":"European energy-cost reference","up":"European gas costs are increasing.","down":"Lower gas prices may help European consumers and industry."},
    {"name":"Copper","ticker":"HG=F","category":"Economic Drivers","role":"Industrial-demand signal","up":"Copper suggests firmer industrial demand.","down":"Copper points to softer industrial-demand expectations."},
    {"name":"EUR/USD","ticker":"EURUSD=X","category":"Economic Drivers","role":"Euro strength versus US dollar","up":"Euro strengthening: imports get cheaper, while exporters face a currency headwind.","down":"Euro weakening: exporters may benefit, but imports become more expensive."},
    {"name":"Hang Seng","ticker":"^HSI","category":"Asia","role":"Hong Kong-listed China exposure","up":"Hong Kong and China-linked shares are attracting buying.","down":"Investors are reducing Hong Kong and China-linked exposure."},
    {"name":"CSI 300","ticker":"000300.SS","category":"Asia","role":"Large mainland Chinese shares","up":"Mainland Chinese blue chips are strengthening.","down":"Mainland Chinese blue chips are weakening."},
    {"name":"Nikkei 225","ticker":"^N225","category":"Asia","role":"Large Japanese shares","up":"Japanese equities are attracting buying.","down":"Japanese equities are losing momentum."},
    {"name":"Chinese yuan","ticker":"CNY=X","category":"Asia","role":"Yuan strength versus US dollar","up":"Yuan weakening: Chinese confidence may be under pressure, while exporters gain support.","down":"Yuan strengthening: confidence in Chinese assets may be improving.","invert":True},
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


def _as_float(value, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return default


@st.cache_data(ttl=5 * 60, show_spinner=False)
def _fetch_external_holdings_csv(url: str) -> list[dict]:
    """Load a public CSV so holdings can be changed without redeploying the app."""
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 JUGG/5.0"}, timeout=15)
    response.raise_for_status()
    rows = []
    for raw in csv.DictReader(io.StringIO(response.text)):
        name = clean_text(raw.get("name", ""))
        ticker = clean_text(raw.get("ticker", "")) or None
        if not name:
            continue
        rows.append({
            "name": name,
            "ticker": ticker,
            "proxy_ticker": clean_text(raw.get("proxy_ticker", "")) or None,
            "abbr": clean_text(raw.get("abbr", "")) or (ticker or name[:8]),
            "saved_value_eur": _as_float(raw.get("saved_value_eur")),
            "original_investment_eur": _as_float(raw.get("original_investment_eur")),
            "purchase_date": clean_text(raw.get("purchase_date", "")),
            "country": clean_text(raw.get("country", "")) or "Not specified",
            "country_iso3": clean_text(raw.get("country_iso3", "")).upper() or None,
            "area": clean_text(raw.get("area", "")) or "Other",
            "fx_ticker": clean_text(raw.get("fx_ticker", "")) or None,
            "news_terms": clean_text(raw.get("news_terms", "")),
            "proxy_note": clean_text(raw.get("proxy_note", "")),
        })
    if not rows:
        raise ValueError("The holdings CSV contains no valid rows.")
    return rows


def get_portfolio_holdings() -> list[dict]:
    url = _safe_secret("PORTFOLIO_DATA_URL")
    if url:
        try:
            return _fetch_external_holdings_csv(url)
        except Exception:
            # Keep the app usable if the external sheet is temporarily unavailable.
            pass
    return [dict(item) for item in PORTFOLIO_HOLDINGS]


def get_holding_config(holding_name: str) -> dict:
    if holding_name in HOLDING_BRIEFING_DATA:
        return dict(HOLDING_BRIEFING_DATA[holding_name])
    holding = next((item for item in get_portfolio_holdings() if item["name"] == holding_name), None)
    if not holding:
        return {}
    ticker = holding.get("ticker") or holding.get("proxy_ticker")
    terms = [term.strip().lower() for term in holding.get("news_terms", "").split("|") if term.strip()]
    if not terms:
        terms = [holding_name.lower()]
    area = holding.get("area", "the relevant sector")
    country = holding.get("country", "its home market")
    proxy_note = holding.get("proxy_note")
    if not holding.get("ticker") and ticker and not proxy_note:
        proxy_note = "The chart uses a configured market proxy. It is not the product's live valuation."
    return {
        "ticker": ticker,
        "chart_label": holding_name if holding.get("ticker") else f"{holding_name} proxy",
        "direct_terms": terms,
        "queries": [f'"{holding_name}"', f'"{area}" OR "{country}"'],
        "context": f"{area}, {country}, company developments, sector demand, currencies and market valuation",
        "proxy_note": proxy_note,
    }


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
    config = get_holding_config(holding_name)
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
    points = history.get("points", [])
    if points:
        x_values = [datetime.fromtimestamp(ts, tz=timezone.utc) for ts, _ in points]
        y_values = [value for _, value in points]
        positive = y_values[-1] >= y_values[0] if len(y_values) >= 2 else True
        line_color = "#55df91" if positive else "#ff6e83"
        floor = min(y_values) - max((max(y_values) - min(y_values)) * .18, abs(min(y_values)) * .006)
        fig.add_trace(go.Scatter(x=x_values, y=[floor] * len(x_values), mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(
            x=x_values, y=y_values, mode="lines", fill="tonexty",
            line=dict(width=2.5, color=line_color, shape="spline", smoothing=.3), fillcolor="rgba(83,223,145,.09)" if positive else "rgba(255,110,131,.09)",
            name=holding_name, hovertemplate="%{x|%d %b %H:%M}<br>%{y:,.2f}<extra></extra>",
        ))
    fig.update_layout(
        height=410, margin=dict(l=10, r=10, t=16, b=8), hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#aeb8d5"), showlegend=False,
        xaxis=dict(showgrid=False, color="#8390b4", showspikes=True, spikemode="across", spikedash="dot", spikecolor="rgba(190,200,235,.4)"),
        yaxis=dict(showgrid=True, gridcolor="rgba(130,150,210,.10)", color="#8390b4", fixedrange=False),
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
        return "", "AI_NOT_CONFIGURED"
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
    sentences = ["This evidence briefing combines the live market snapshot with selected, timestamped headlines from the previous 48 hours."]
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
    config = get_holding_config(holding_name)
    text = [
        "This evidence briefing combines the observed market move with selected company, sector and broader-market headlines.",
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
    config = get_holding_config(holding_name)
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
Explain the current market driver '{driver['title']}' using only the supplied 48-hour evidence. Use four short sections with these exact headings:

What it actually is
What this means
Who may be affected and why
Relevance to my portfolio

Use easy-to-understand but informative English. Distinguish general educational explanation from what the current articles actually report. Do not invent causal links. Keep the full answer between 180 and 320 words and use source markers [1], [2], etc. for current claims.

GENERAL DEFINITION:
What it is: {definition['what']}
Meaning: {definition['meaning']}
Typical effects: {definition['effects']}
Portfolio: MS Europe 26/27 ABJ, ANTA Sports Products, Siemens Healthineers, Tomra Systems and Verbund. Explain only plausible links and label interpretation as interpretation.

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
            f"\n\n### Relevance to my portfolio\nThis driver may affect the five holdings through regional demand, interest rates, currencies, energy prices or sector valuation. The exact link depends on the holding and is an interpretation unless a current source explicitly confirms it."
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
    .driver-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:11px;padding-bottom:15px}.driver-card{display:block;text-decoration:none!important;min-height:136px;padding:14px;border:1px solid rgba(133,151,255,.18);border-radius:14px;background:linear-gradient(145deg,rgba(16,25,51,.96),rgba(8,15,32,.98));transition:.22s}.driver-card:hover{transform:translateY(-3px);border-color:rgba(143,92,255,.62);box-shadow:0 13px 32px rgba(75,48,190,.20)}.driver-category{font-size:9px;text-transform:uppercase;letter-spacing:.1em;color:#9b7eff}.driver-title{font-size:13px;font-weight:680;color:#f5f6ff;margin-top:7px}.driver-lead{font-size:10px;line-height:1.42;color:#9ba5c3;margin-top:8px}.driver-count{font-size:9px;color:#62d995;margin-top:9px}
    .holding-card-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;padding-bottom:15px}.holding-brief-card{display:block;text-decoration:none!important;min-height:182px;padding:15px;border:1px solid rgba(133,151,255,.18);border-radius:15px;background:linear-gradient(145deg,rgba(17,26,53,.97),rgba(8,14,31,.99));transition:.23s}.holding-brief-card:hover{transform:translateY(-4px);border-color:rgba(143,92,255,.64);box-shadow:0 15px 34px rgba(64,42,170,.23)}.holding-avatar{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;background:linear-gradient(145deg,#7650e7,#254fae);color:#fff;font-size:11px;font-weight:750}.holding-card-name{color:#f5f7ff;font-size:12px;font-weight:680;margin-top:10px;min-height:34px}.holding-card-price{font-size:10px;color:#8794b7;margin-top:3px}.holding-impact{display:flex;align-items:center;justify-content:space-between;font-size:10px;color:#94a0bf;margin-top:8px}.pos{color:#4cdf88!important}.neg{color:#ff687e!important}
    .brief-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:7px 0 20px}.brief-tab{display:inline-flex;padding:9px 13px;border-radius:10px;border:1px solid rgba(133,151,255,.18);background:rgba(255,255,255,.025);text-decoration:none!important;color:#aeb8d4!important;font-size:12px}.brief-tab.active,.brief-tab:hover{color:#fff!important;border-color:rgba(143,92,255,.58);background:rgba(116,70,239,.15)}
    .briefing-copy{font-size:15px;line-height:1.72;color:#e8ebf6}.briefing-meta{display:flex;gap:10px;flex-wrap:wrap;margin:11px 0 18px}.meta-pill{font-size:10px;color:#aab4d2;border:1px solid rgba(133,151,255,.17);border-radius:999px;padding:6px 9px;background:rgba(255,255,255,.025)}
    .source-list{display:grid;gap:8px}.source-row{display:grid;grid-template-columns:28px 1fr auto;gap:10px;align-items:center;padding:10px 12px;border-top:1px solid rgba(133,151,255,.11);color:#dfe4f4}.source-number{color:#9b7eff;font-size:11px}.source-row a{color:#eef1ff!important;text-decoration:none!important;font-size:12px}.source-row a:hover{color:#ac91ff!important}.source-meta{font-size:10px;color:#7f8baa}
    .proxy-note{margin:10px 0;padding:11px 13px;border-radius:11px;border:1px solid rgba(246,200,95,.25);background:rgba(246,200,95,.06);color:#e7d9aa;font-size:11px;line-height:1.5}
    .section-spacer{height:26px}.estimate-pill{font-size:8px;letter-spacing:.1em;color:#bfaeff;border:1px solid rgba(155,126,255,.35);border-radius:999px;padding:4px 7px;vertical-align:middle}.regime-name{font-size:28px;font-weight:750;color:#fff;margin:9px 0}.regime-name span{display:block;font-size:12px;color:#b3bdd8;margin-top:4px}.plain-copy{color:#dce1f0;font-size:13px;line-height:1.55}.signal-pill{display:inline-flex;margin:4px 5px 0 0;padding:6px 8px;border-radius:999px;background:rgba(143,92,255,.1);border:1px solid rgba(143,92,255,.24);color:#d8cffd;font-size:10px}.flow-row{display:grid;grid-template-columns:minmax(150px,1fr) minmax(100px,.8fr) 110px;gap:12px;align-items:center;padding:7px 0;border-bottom:1px solid rgba(133,151,255,.08);color:#e9ecf8;font-size:11px}.flow-row small{display:block;color:#8f9abb;margin-top:2px}.flow-track{height:6px;background:rgba(255,255,255,.07);border-radius:99px;overflow:hidden}.flow-track i{display:block;height:100%;border-radius:99px}.flow-in{background:#52d78c}.flow-out{background:#ff7186}.flow-flat{background:#d2aa58}.category-heading{margin:18px 0 8px}.category-heading b{color:#f5f7ff;font-size:15px}.category-heading small{display:block;color:#8f9abb;font-size:11px;margin-top:3px}.indicator-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:11px}.indicator-card{display:block;min-height:178px;padding:14px;border:1px solid rgba(133,151,255,.17);border-radius:14px;background:linear-gradient(145deg,rgba(17,26,53,.97),rgba(8,15,32,.99));text-decoration:none!important;transition:.2s}.indicator-card:hover{transform:translateY(-3px);border-color:rgba(143,92,255,.62)}.indicator-card.status-good{border-top-color:rgba(76,223,136,.55)}.indicator-card.status-bad{border-top-color:rgba(255,104,126,.55)}.indicator-card.status-neutral{border-top-color:rgba(210,170,88,.55)}.indicator-top{display:flex;justify-content:space-between;gap:8px}.indicator-top b{color:#f5f7ff;font-size:12px}.indicator-top span{color:#cbd3e9;font-size:10px}.indicator-value{font-size:17px;font-weight:700;color:#fff;margin-top:8px}.indicator-card p{color:#aeb8d1;font-size:10px;line-height:1.45;min-height:29px;margin:5px 0}.indicator-card small{color:#a78aff;font-size:9px}
    @media(max-width:1120px){.proxy-grid,.indicator-grid{grid-template-columns:repeat(2,1fr)}.driver-grid{grid-template-columns:repeat(3,1fr)}.holding-card-grid{grid-template-columns:repeat(3,1fr)}}
    @media(max-width:760px){.main .block-container{padding:1rem .75rem 4rem!important}.mb-topbar{display:block}.mb-status{display:inline-block;margin-top:10px}.proxy-grid,.indicator-grid{grid-template-columns:1fr}.driver-grid{grid-template-columns:1fr}.holding-card-grid{grid-template-columns:1fr}.flow-row{grid-template-columns:1fr}.source-row{grid-template-columns:24px 1fr}.source-meta{grid-column:2}.briefing-copy{font-size:14px}}
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
    for holding in get_portfolio_holdings():
        name = holding["name"]
        config = get_holding_config(name)
        if not config.get("ticker"):
            continue
        history = fetch_yahoo_history(config["ticker"])
        values = [value for _, value in (history.get("recent_points") or history.get("points", []))]
        change = float(history.get("change_48h", 0)) if history.get("ok") else 0.0
        change_class = "pos" if change >= 0 else "neg"
        initials = html_lib.escape(holding.get("abbr", name[:3]))
        label = html_lib.escape(config.get("chart_label", name))
        price = _format_market_price({**history, "ticker": config["ticker"]}) if history.get("ok") else "Unavailable"
        driver = "Broad market and valuation"
        explanation = "The latest move is assessed against company news, sector conditions and the wider market."
        confidence = "Medium" if history.get("ok") else "Low"
        if name == "ANTA Sports": driver, explanation = "China demand and yuan", "Chinese consumer confidence, regional shares and the yuan can influence ANTA's outlook."
        elif name == "Siemens Healthineers": driver, explanation = "Healthcare demand and rates", "Hospital spending, sector sentiment and interest rates can affect the shares."
        elif name == "Tomra Systems": driver, explanation = "Industrial growth and regulation", "Demand, recycling rules and growth-stock valuation are the main channels checked."
        elif name == "Verbund": driver, explanation = "Power markets and interest rates", "Electricity, gas, hydrology and bond yields can change earnings and valuation expectations."
        elif name == "MS Europe 26/27 ABJ": driver, explanation, confidence = "European market exposure", "The displayed move is only a market-exposure reference, not the product's live value.", "Low"
        cards.append(f"""
        <a class="holding-brief-card" href="?page=briefing&view=holding&asset={quote_plus(name)}" target="_self">
          <div class="holding-avatar">{initials[:8]}</div>
          <div class="holding-card-name">{html_lib.escape(name)}</div>
          <div class="holding-card-price">{label}: {html_lib.escape(price)}</div>
          {_sparkline_svg(values[-30:], width=180, height=47)}
          <div class="holding-impact"><span>48h / latest points</span><b class="{change_class}">{change:+.2f}%</b></div>
          <div class="holding-impact"><span>Main driver</span><b>{html_lib.escape(driver)}</b></div>
          <div class="holding-card-price">{html_lib.escape(explanation)}</div>
          <div class="holding-impact"><span>Confidence</span><b>{confidence}</b></div>
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
            st.plotly_chart(_market_overview_chart(snapshot), use_container_width=True, config={"displayModeBar": False}, key="legacy_market_chart")
            with st.form("overall_market_briefing_form", border=True):
                form_left, form_right = st.columns([1.05, .95])
                with form_left:
                    length_label = st.selectbox("Briefing length", list(BRIEFING_LENGTHS), index=1, key="market_briefing_length")
                with form_right:
                    submitted = st.form_submit_button("✦ Generate Briefing", use_container_width=True, key="legacy_market_submit")
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
        if st.button("Return to Market Overview", key="market_summary_return"):
            _navigate_briefing("overview")
        return
    word_count = len(result["text"].split())
    st.markdown(f'<div class="briefing-meta"><span class="meta-pill">{html_lib.escape(result["length"])}</span><span class="meta-pill">{word_count} words</span><span class="meta-pill">Generated {html_lib.escape(result["created_at"])}</span><span class="meta-pill">{html_lib.escape(result["generated_by"])}</span></div>', unsafe_allow_html=True)
    if result.get("error") == "AI_NOT_CONFIGURED":
        st.caption("Evidence mode · Add OPENAI_API_KEY in Streamlit Secrets to enable AI-written causal synthesis. The factual digest below remains fully usable.")
    elif result.get("error"):
        st.warning("AI synthesis was temporarily unavailable, so JUGG produced the evidence digest instead.")
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
    if result.get("error") == "AI_NOT_CONFIGURED":
        st.caption("Evidence explanation · Configure OPENAI_API_KEY in Streamlit Secrets for AI-written synthesis.")
    elif result.get("error"):
        st.warning("AI synthesis was temporarily unavailable; the evidence explanation is shown instead.")
    with st.container(border=True):
        st.markdown(result["text"])
    st.markdown("## Current evidence")
    _render_source_list(result.get("articles", []))


def _render_holding_detail(holding_name: str) -> None:
    if holding_name not in {item["name"] for item in get_portfolio_holdings()}:
        st.error("The selected holding is not in the current portfolio.")
        return
    config = get_holding_config(holding_name)
    timeline_options = {
        "1D": ("1d", "5m"), "5D": ("5d", "30m"), "1M": ("1mo", "1d"),
        "6M": ("6mo", "1d"), "YTD": ("ytd", "1d"), "1Y": ("1y", "1d"),
        "5Y": ("5y", "1wk"), "MAX": ("max", "1mo"),
    }
    timeline = st.radio("Chart period", list(timeline_options), index=1, horizontal=True, label_visibility="collapsed", key=f"jugg40_holding_timeline_{holding_name}")
    range_period, interval = timeline_options[timeline]
    history = fetch_yahoo_history(config["ticker"], range_period, interval)
    holding_news = fetch_holding_news_48h(holding_name)
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
                st.plotly_chart(_holding_chart(holding_name, history), use_container_width=True, config={"displayModeBar": False, "scrollZoom": True}, key=f"holding_chart_{holding_name}_{timeline}")
                change_class = "pos" if history.get("change_48h", 0) >= 0 else "neg"
                st.markdown(f'<div class="briefing-meta"><span class="meta-pill">Price {_format_market_price({**history, "ticker": config["ticker"]})}</span><span class="meta-pill {change_class}">{history.get("change_48h", 0):+.2f}% over {html_lib.escape(history.get("basis", "available window"))}</span><span class="meta-pill">Daily {history.get("daily_change", 0):+.2f}%</span></div>', unsafe_allow_html=True)
                st.caption("Drag to zoom, scroll to zoom and double-click to reset. The briefing always evaluates the previous 48 hours, regardless of the chart period.")
            else:
                st.warning("The price chart could not be loaded. The briefing can still use the selected news evidence.")
    with control_col:
        with st.container(border=True):
            st.markdown('<div class="mb-section-title">Generate holding briefing</div><div class="mb-section-note">Company, sector and market evidence from the last 48 hours.</div>', unsafe_allow_html=True)
            with st.form(f"holding_form_{holding_name}", border=True):
                length_label = st.selectbox("Briefing length", list(BRIEFING_LENGTHS), index=1, key=f"holding_length_{holding_name}")
                submitted = st.form_submit_button("✦ Generate Briefing", use_container_width=True, key=f"holding_submit_{holding_name}")
            if submitted:
                with st.spinner(f"Selecting news and explaining {holding_name}'s move…"):
                    market_news = st.session_state.get("market_news_48h") or fetch_market_news_48h()
                    result = generate_holding_briefing(holding_name, history, holding_news, market_news, length_label)
                    st.session_state[f"generated_holding_briefing_{holding_name}"] = result
                _navigate_briefing("holding_summary", asset=holding_name)
    st.markdown("## Company and sector news · previous 48 hours")
    direct_terms = config.get("direct_terms", [])
    direct_news = [a for a in holding_news if any(term in article_blob(a) for term in direct_terms)]
    if not direct_news:
        st.info("No meaningful company-specific news was found in the selected 48-hour sources. Sector and broader-market evidence will still be checked when a briefing is generated.")
    _render_source_list(holding_news[:10])


def _render_holding_summary(holding_name: str) -> None:
    result = st.session_state.get(f"generated_holding_briefing_{holding_name}")
    st.markdown(f'<div class="brief-tabs"><a class="brief-tab" href="?page=briefing&view=overview" target="_self">Overview</a><a class="brief-tab" href="?page=briefing&view=holding&asset={quote_plus(holding_name)}" target="_self">Price & controls</a><span class="brief-tab active">Generated briefing</span></div>', unsafe_allow_html=True)
    st.markdown(f"# {holding_name} Briefing")
    if not result:
        st.warning("No briefing has been generated for this holding in the current session.")
        return
    word_count = len(result["text"].split())
    st.markdown(f'<div class="briefing-meta"><span class="meta-pill">{html_lib.escape(result["length"])}</span><span class="meta-pill">{word_count} words</span><span class="meta-pill">Generated {html_lib.escape(result["created_at"])}</span><span class="meta-pill">{html_lib.escape(result["generated_by"])}</span></div>', unsafe_allow_html=True)
    if result.get("error") == "AI_NOT_CONFIGURED":
        st.caption("Evidence mode · Add OPENAI_API_KEY in Streamlit Secrets to enable AI-written causal synthesis. The factual digest below remains fully usable.")
    elif result.get("error"):
        st.warning("AI synthesis was temporarily unavailable, so JUGG produced the evidence digest instead.")
    with st.container(border=True):
        st.markdown(result["text"])
    st.markdown("## Sources used")
    _render_source_list(result.get("articles", []))


# JUGG 3.1 dashboard logic -------------------------------------------------
def _market_period() -> tuple[str, str]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=48)
    return start.strftime("%d %b %Y, %H:%M UTC"), end.strftime("%d %b %Y, %H:%M UTC")


def _item(snapshot: list[dict], name: str) -> dict:
    return next((row for row in snapshot if row.get("name") == name), {})


def _signal_change(item: dict) -> float:
    change = float(item.get("change_48h", 0.0)) if item.get("ok") else 0.0
    return -change if item.get("invert") else change


def calculate_market_regime(snapshot: list[dict]) -> dict:
    # Positive score means risk-taking; weights prevent one market from deciding the result.
    rules = [
        ("S&P 500", .16, 1), ("Nasdaq-100", .12, 1), ("Euro Stoxx 50", .10, 1),
        ("MSCI Emerging Markets ETF", .10, 1), ("Gold", .12, -1),
        ("US 10-Year Treasury yield", .10, 1), ("Japanese yen", .08, -1),
        ("Swiss franc", .07, -1), ("Copper", .07, 1), ("Brent oil", .03, 1),
        ("Hang Seng", .03, 1), ("Chinese yuan", .02, 1),
    ]
    scored, signals = 0.0, []
    for name, weight, direction in rules:
        row = _item(snapshot, name)
        if not row.get("ok"):
            continue
        move = max(-2.0, min(2.0, _signal_change(row))) / 2.0
        contribution = move * weight * direction
        scored += contribution
        signals.append((abs(contribution), name, _signal_change(row), direction))
    if scored >= .12:
        label = "Risk-On"
        explanation = "Investors appear more willing to take risk. Shares and economically sensitive assets are generally receiving support, while demand for perceived safety is less dominant. This is a weighted indicator, not a prediction or guaranteed conclusion."
    elif scored <= -.12:
        label = "Risk-Off"
        explanation = "Investors appear more cautious. Defensive assets and currencies are gaining relative support while shares or economically sensitive markets are weaker. This is a weighted indicator, not a prediction or guaranteed conclusion."
    else:
        label = "Mixed / Neutral"
        explanation = "Markets are sending conflicting signals. Some areas show confidence while others point to caution, so there is no broad, convincing move toward either risk or safety. This is a weighted indicator, not a prediction or guaranteed conclusion."
    confidence = min(92, max(52, round(52 + abs(scored) * 145)))
    supporting = []
    for _, name, move, direction in sorted(signals, reverse=True)[:5]:
        if name in ("Japanese yen", "Swiss franc", "Chinese yuan"):
            supporting.append(f"{name} {'strengthening' if move > 0 else 'weakening'}")
        elif name == "US 10-Year Treasury yield":
            supporting.append(f"US 10-year yield {'rising' if move > 0 else 'falling'}")
        else:
            supporting.append(f"{name} {'rising' if move > 0 else 'falling'}")
    return {"label": label, "confidence": confidence, "explanation": explanation, "signals": supporting, "score": scored}


def calculate_money_flow(snapshot: list[dict]) -> list[dict]:
    groups = {
        "Equities": ["S&P 500", "Nasdaq-100", "Euro Stoxx 50", "MSCI Emerging Markets ETF"],
        "Bonds": ["US 10-Year Treasury yield"], "Gold": ["Gold"],
        "US dollar": ["EUR/USD", "Japanese yen", "Swiss franc"], "Oil": ["Brent oil"],
        "China": ["Hang Seng", "CSI 300", "Chinese yuan"], "Europe": ["Euro Stoxx 50", "EUR/USD"],
    }
    output = []
    for group, names in groups.items():
        values = [_signal_change(_item(snapshot, n)) for n in names if _item(snapshot, n).get("ok")]
        score = sum(values) / len(values) if values else 0.0
        if group == "Bonds": score *= -1  # falling yields normally imply bond buying
        if group == "US dollar": score *= -1  # weaker counterparts imply a stronger dollar
        level = "Strong inflow" if score >= 1.2 else "Moderate inflow" if score >= .3 else "Strong outflow" if score <= -1.2 else "Moderate outflow" if score <= -.3 else "Neutral"
        verb = "moving into" if "inflow" in level else "moving out of" if "outflow" in level else "balanced in"
        output.append({"name": group, "score": score, "level": level, "text": f"Estimated positioning appears {verb} {group.lower()}."})
    return output


def _indicator_interpretation(item: dict) -> str:
    if not item.get("ok"):
        return "Current market data is unavailable; no direction is inferred."
    return item.get("up") if float(item.get("change_48h", 0)) >= 0 else item.get("down")


def _render_regime_and_flow(snapshot: list[dict]) -> None:
    regime = calculate_market_regime(snapshot)
    flows = calculate_money_flow(snapshot)
    left, right = st.columns([1, 1.35], gap="medium")
    with left:
        with st.container(border=True):
            st.markdown(f"<div class='mb-section-title'>Market Regime <span class='estimate-pill'>INDICATOR</span></div><div class='regime-name'>{regime['label']} <span>Confidence {regime['confidence']}%</span></div><p class='plain-copy'>{regime['explanation']}</p>", unsafe_allow_html=True)
            st.markdown("".join(f"<span class='signal-pill'>{html_lib.escape(s)}</span>" for s in regime["signals"]), unsafe_allow_html=True)
    with right:
        with st.container(border=True):
            st.markdown("<div class='mb-section-title'>Where Is Money Moving?</div><div class='mb-section-note'>Estimated market positioning inferred from prices — not measured fund flows.</div>", unsafe_allow_html=True)
            rows = []
            for flow in flows:
                width = min(100, 20 + abs(flow['score']) * 35)
                cls = "flow-in" if "inflow" in flow['level'] else "flow-out" if "outflow" in flow['level'] else "flow-flat"
                rows.append(f"<div class='flow-row'><div><b>{flow['name']}</b><small>{flow['text']}</small></div><div class='flow-track'><i class='{cls}' style='width:{width:.0f}%'></i></div><span>{flow['level']}</span></div>")
            st.markdown("".join(rows), unsafe_allow_html=True)


def _render_market_cards(snapshot: list[dict]) -> None:
    purposes = {
        "Equities":"Shows whether investors are buying shares and which regions or styles are leading.",
        "Safe Havens":"Shows whether investors are becoming more cautious and moving toward perceived safety.",
        "Economic Drivers":"Shows inflation pressure, industrial demand, European energy conditions and currency effects.",
        "Asia":"Shows China, Hong Kong and Japan — especially relevant for ANTA Sports and global growth.",
    }
    for category in purposes:
        st.markdown(f"<div class='category-heading'><div><b>{category}</b><small>{purposes[category]}</small></div></div>", unsafe_allow_html=True)
        cards = []
        for item in [x for x in snapshot if x.get("category") == category]:
            values = [value for _, value in (item.get("recent_points") or item.get("points", []))]
            change = float(item.get("change_48h", 0)) if item.get("ok") else 0.0
            if item.get("unit") == "yield" and item.get("ok"):
                change_text = f"{(float(item.get('price',0))-float((item.get('recent_points') or [(0,item.get('price',0))])[0][1]))*10:+.0f} bp"
            else:
                change_text = f"{change:+.2f}%" if item.get("ok") else "Unavailable"
            semantic = _signal_change(item)
            cls = "status-good" if semantic > .15 else "status-bad" if semantic < -.15 else "status-neutral"
            cards.append(f"<a class='indicator-card {cls}' href='?page=briefing&view=indicator&indicator={quote_plus(item['name'])}' target='_self'><div class='indicator-top'><b>{html_lib.escape(item['name'])}</b><span>{change_text}</span></div><div class='indicator-value'>{html_lib.escape(_format_market_price(item))}</div>{_sparkline_svg(values[-30:])}<p>{html_lib.escape(_indicator_interpretation(item))}</p><small>Open detailed view →</small></a>")
        st.markdown(f"<div class='indicator-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)


def _render_indicator_detail(name: str) -> None:
    snapshot = st.session_state.get("market_snapshot") or load_market_snapshot()
    item = _item(snapshot, name)
    if not item:
        st.error("This market indicator could not be found.")
        return
    st.markdown('<div class="brief-tabs"><a class="brief-tab" href="?page=briefing&view=overview" target="_self">Overview</a><span class="brief-tab active">Indicator detail</span></div>', unsafe_allow_html=True)
    st.markdown(f"# {name}")
    st.caption(f"Market data source: Yahoo Finance · {item.get('exchange','source unavailable')} · {_market_period()[0]} to {_market_period()[1]}")
    timeline_options = {"1D": ("1d", "5m"), "5D": ("5d", "30m"), "1M": ("1mo", "1d"), "6M": ("6mo", "1d"), "YTD": ("ytd", "1d"), "1Y": ("1y", "1d"), "5Y": ("5y", "1wk"), "MAX": ("max", "1mo")}
    timeline = st.radio("Chart period", list(timeline_options), index=1, horizontal=True, label_visibility="collapsed", key=f"jugg40_indicator_timeline_{item['ticker']}")
    detail_history = fetch_yahoo_history(item["ticker"], *timeline_options[timeline])
    if detail_history.get("ok"):
        st.plotly_chart(_holding_chart(name, detail_history), use_container_width=True, config={"displayModeBar": False, "scrollZoom": True}, key=f"indicator_chart_{item['ticker']}_{timeline}")
        st.caption("Drag or scroll to zoom; double-click the chart to reset.")
    else:
        st.warning("Current data is unavailable. The app will not display an old value as live.")
    increase = item.get("up", "The effect depends on the surrounding market context.")
    decrease = item.get("down", "The effect depends on the surrounding market context.")
    relevance = {
        "Asia":"Most directly relevant to ANTA Sports; it can also affect Tomra and Siemens Healthineers through Chinese demand.",
        "Economic Drivers":"May affect Verbund through power markets and all European holdings through inflation, costs and currencies.",
        "Safe Havens":"Changes in risk appetite and interest rates can affect valuation across all five holdings.",
        "Equities":"Shows the market backdrop around the holdings; it does not prove why an individual holding moved.",
    }.get(item.get("category"), "The effect depends on each holding's exposure.")
    st.markdown(f"### Current status\n{_indicator_interpretation(item)}\n\n### What it is\n{item.get('role')}. It is used here as a market indicator, not a certain forecast.\n\n### What an increase usually means\n{increase}\n\n### What a decrease usually means\n{decrease}\n\n### Why it matters for markets\nThe move can change expectations for growth, inflation, interest rates or investor risk appetite. Its meaning depends on what caused it and on other indicators.\n\n### Possible relevance to my holdings\n{relevance}")
    news = st.session_state.get("market_news_48h") or fetch_market_news_48h()
    terms = [w.lower() for w in re.findall(r"[A-Za-z]+", name) if len(w) > 3]
    related = [a for a in news if any(t in article_blob(a) for t in terms)][:8]
    st.markdown("## Relevant news and sources")
    _render_source_list(related)


def _render_overview() -> None:
    with st.spinner("Loading market prices and selecting news from the previous 48 hours…"):
        snapshot, market_news = load_market_snapshot(), fetch_market_news_48h()
        drivers = build_driver_snapshot(market_news)
    st.session_state.update(market_snapshot=snapshot, market_news_48h=market_news, market_driver_snapshot=drivers)
    start, end = _market_period()
    st.markdown(f"<div class='mb-topbar'><div><div class='mb-kicker'>JUGG 5.0 · MARKET INTELLIGENCE</div><h1>Market Briefing</h1><div class='mb-sub'>Previous 48 hours: {start} — {end}</div></div><div class='mb-status'>● {len(market_news)} selected news items</div></div>", unsafe_allow_html=True)
    st.caption("Market data: Yahoo Finance chart endpoint · refreshed up to every 15 minutes. News: publisher RSS links selected from the strict 48-hour window. Unavailable quotes are not replaced with stale values.")
    _render_regime_and_flow(snapshot)
    st.markdown("<div class='section-spacer'></div><div class='mb-section-title'>Market Indicators</div><div class='mb-section-note'>Price moves are interpreted by economic meaning, not coloured mechanically.</div>", unsafe_allow_html=True)
    _render_market_cards(snapshot)
    st.markdown("<div class='section-spacer'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(f"<div class='mb-section-title'>Generate Overall Market Briefing</div><div class='mb-section-note'>Exact period: {start} — {end}</div>", unsafe_allow_html=True)
        with st.form("jugg40_overall_market_form", border=False):
            a, b = st.columns([1.35, 1])
            with a: length_label = st.selectbox("Briefing length", list(BRIEFING_LENGTHS), index=1, key="jugg40_market_length")
            with b: submitted = st.form_submit_button("✦ Generate Briefing", use_container_width=True, key="jugg40_market_submit")
        last = st.session_state.get("generated_market_briefing", {}).get("created_at", "Not generated in this session")
        st.caption(f"Last generated: {last}")
        if submitted:
            with st.spinner("Ranking evidence and generating the briefing…"):
                st.session_state["generated_market_briefing"] = generate_market_briefing(snapshot, market_news, length_label)
            _navigate_briefing("market_summary")
    st.markdown("<div class='section-spacer'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("<div class='mb-section-title'>Top Drivers <span class='estimate-pill'>FACTS + INTERPRETATION</span></div>", unsafe_allow_html=True)
        _render_driver_cards(drivers[:5])
    st.markdown("<div class='section-spacer'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("<div class='mb-section-title'>My Holdings</div><div class='mb-section-note'>Click a card for its price view, evidence and 48-hour briefing.</div>", unsafe_allow_html=True)
        _render_holding_cards()


def render_market_briefing() -> None:
    _render_briefing_css()
    render_app_nav("Market Briefing")
    view = _query_value("view", "overview")
    if view == "market_summary":
        _render_market_summary()
    elif view == "indicator":
        _render_indicator_detail(_query_value("indicator", "S&P 500"))
    elif view == "driver":
        _render_driver_detail(_query_value("driver", "rates"))
    elif view == "holding":
        _render_holding_detail(_query_value("asset", "Siemens Healthineers"))
    elif view == "holding_summary":
        _render_holding_summary(_query_value("asset", "Siemens Healthineers"))
    else:
        _render_overview()


def render_organizer() -> None:
    render_app_nav("Organizer")
    st.markdown("""
    <style>
    .main .block-container{max-width:1500px;padding:1.05rem 1.25rem 3rem!important}
    .jugg-app-nav{margin-bottom:12px!important}
    [data-testid="stIFrame"]{border:1px solid rgba(132,153,255,.16)!important;border-radius:19px!important;background:rgba(5,9,24,.72)!important;box-shadow:0 24px 75px rgba(0,0,0,.28)!important;overflow:hidden!important}
    </style>
    """, unsafe_allow_html=True)

    organizer_html = r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#070b19;--panel:#0d1429;--panel2:#111a34;--line:rgba(132,153,255,.18);--text:#f5f7ff;--muted:#8e9abb;--violet:#9163ff;--blue:#5b8dff;--green:#55dda0;--red:#ff7186}
*{box-sizing:border-box}html,body{margin:0;min-height:100%;background:transparent;color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}button,input{font:inherit}
.app{min-height:748px;padding:22px;background:radial-gradient(circle at 18% -5%,rgba(112,65,235,.16),transparent 34%),linear-gradient(155deg,rgba(7,12,29,.99),rgba(5,9,21,.99));overflow:hidden}
.topbar{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:18px}.kicker{font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:#8f7adb;margin-bottom:5px}.title{font-size:28px;font-weight:720;letter-spacing:-.035em}.subtitle{margin-top:5px;color:var(--muted);font-size:12px}.actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
.btn{border:1px solid rgba(145,99,255,.38);border-radius:11px;background:linear-gradient(145deg,rgba(111,71,232,.92),rgba(49,82,207,.92));color:white;padding:9px 12px;cursor:pointer;font-size:11px;font-weight:650;box-shadow:0 8px 22px rgba(66,56,190,.17);transition:.18s}.btn:hover{transform:translateY(-1px);border-color:rgba(176,151,255,.7)}.btn.secondary{background:rgba(255,255,255,.035);border-color:var(--line);box-shadow:none;color:#dfe4f6}.btn.danger{background:rgba(255,113,134,.08);border-color:rgba(255,113,134,.24);color:#ff9cac}.btn.icon{padding:6px 8px;min-width:30px}
.crumbs{display:flex;align-items:center;gap:7px;margin:0 0 14px;color:#7f8bad;font-size:11px}.crumb{color:#b5bde0;cursor:pointer}.crumb:hover{color:white}.sep{color:#46516f}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}.folder,.board-card{position:relative;min-height:132px;padding:17px;border:1px solid var(--line);border-radius:15px;background:linear-gradient(145deg,rgba(18,27,55,.94),rgba(9,15,33,.98));cursor:pointer;transition:.2s;overflow:hidden}.folder:hover,.board-card:hover{transform:translateY(-3px);border-color:rgba(145,99,255,.5);box-shadow:0 16px 36px rgba(35,25,110,.22)}.folder:before,.board-card:before{content:"";position:absolute;inset:auto -20% -55% 38%;height:130px;background:radial-gradient(circle,rgba(111,90,239,.12),transparent 66%);pointer-events:none}.folder-icon{width:40px;height:34px;border:1px solid rgba(153,121,255,.32);border-radius:8px;background:linear-gradient(145deg,rgba(119,76,237,.24),rgba(38,82,179,.16));display:grid;place-items:center;color:#b79fff;font-size:18px;margin-bottom:14px}.card-name{font-size:15px;font-weight:680;line-height:1.25}.meta{margin-top:6px;color:#7f8bad;font-size:10px}.card-tools{position:absolute;right:9px;top:9px;display:flex;gap:4px;opacity:.72}.mini{border:1px solid rgba(132,153,255,.14);background:rgba(4,8,20,.5);color:#aab3cf;border-radius:8px;padding:4px 6px;cursor:pointer;font-size:10px}.mini:hover{color:white;border-color:rgba(145,99,255,.42)}
.empty{border:1px dashed rgba(132,153,255,.22);border-radius:16px;padding:48px 20px;text-align:center;color:#7682a2;background:rgba(255,255,255,.018)}.empty b{display:block;color:#cfd5e9;font-size:14px;margin-bottom:6px}
.board-shell{position:relative}.board-scroll{display:flex;align-items:flex-start;gap:12px;overflow-x:auto;overflow-y:hidden;padding:2px 2px 18px;min-height:555px;scrollbar-color:#313b63 transparent;scrollbar-width:thin}.list{flex:0 0 286px;border:1px solid rgba(132,153,255,.18);border-radius:14px;background:linear-gradient(160deg,rgba(15,23,47,.97),rgba(8,14,30,.99));box-shadow:0 13px 36px rgba(0,0,0,.18);max-height:540px;display:flex;flex-direction:column}.list-head{display:flex;align-items:center;justify-content:space-between;gap:7px;padding:12px 12px 8px}.list-title{font-size:12px;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.list-actions{display:flex;gap:3px}.cards{padding:3px 8px 7px;overflow-y:auto;min-height:45px;scrollbar-width:thin;scrollbar-color:#303a61 transparent}.task{position:relative;margin:7px 0;padding:11px 30px 11px 11px;border:1px solid rgba(132,153,255,.13);border-radius:10px;background:#151d34;color:#e9ecf8;font-size:11px;line-height:1.42;cursor:grab;box-shadow:0 5px 14px rgba(0,0,0,.13)}.task:active{cursor:grabbing}.task:hover{border-color:rgba(145,99,255,.34)}.task .x{position:absolute;right:7px;top:7px;border:0;background:transparent;color:#606b89;cursor:pointer;font-size:13px}.task .x:hover{color:#ff8ea0}.add-card{margin:0 8px 9px;border:1px dashed rgba(132,153,255,.2);border-radius:9px;background:rgba(255,255,255,.018);color:#8995b5;padding:9px;text-align:left;cursor:pointer;font-size:10px}.add-card:hover{color:#dce1f4;border-color:rgba(145,99,255,.38);background:rgba(111,71,232,.06)}.new-list{flex:0 0 250px;border:1px dashed rgba(132,153,255,.23);border-radius:14px;background:rgba(255,255,255,.02);padding:14px;color:#8894b5;cursor:pointer;font-size:11px;text-align:left}.new-list:hover{color:#dce1f4;border-color:rgba(145,99,255,.42);background:rgba(111,71,232,.06)}
.notice{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-top:14px;padding:10px 12px;border:1px solid rgba(132,153,255,.12);border-radius:11px;background:rgba(255,255,255,.018);color:#74809f;font-size:9px;line-height:1.45}.notice strong{color:#aab3ce;font-weight:600}.drop-active{outline:1px solid rgba(145,99,255,.55);outline-offset:-3px;background:rgba(111,71,232,.06)}
.modal-wrap{position:fixed;inset:0;display:none;align-items:center;justify-content:center;padding:20px;background:rgba(2,5,14,.72);backdrop-filter:blur(7px);z-index:50}.modal{width:min(420px,100%);border:1px solid rgba(132,153,255,.24);border-radius:16px;background:linear-gradient(150deg,#111a34,#090f22);box-shadow:0 30px 90px rgba(0,0,0,.5);padding:18px}.modal h3{margin:0 0 5px;font-size:17px}.modal p{margin:0 0 13px;color:#7f8bad;font-size:10px}.modal input{width:100%;border:1px solid rgba(132,153,255,.23);border-radius:10px;background:#0b1228;color:white;padding:11px 12px;outline:none}.modal input:focus{border-color:rgba(145,99,255,.7);box-shadow:0 0 0 3px rgba(145,99,255,.08)}.modal-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:13px}
.toast{position:fixed;right:18px;bottom:18px;z-index:80;opacity:0;transform:translateY(8px);pointer-events:none;border:1px solid rgba(82,224,145,.22);border-radius:10px;background:#0d1b25;color:#a9f0ca;padding:9px 11px;font-size:10px;transition:.2s}.toast.show{opacity:1;transform:none}
@media(max-width:650px){.app{padding:14px;min-height:740px}.topbar{display:block}.actions{justify-content:flex-start;margin-top:11px}.title{font-size:23px}.grid{grid-template-columns:1fr}.board-scroll{min-height:575px}.list{flex-basis:270px}}
</style>
</head>
<body>
<div class="app" id="app"></div>
<div class="modal-wrap" id="modalWrap"><div class="modal"><h3 id="modalTitle"></h3><p id="modalHint"></p><input id="modalInput" autocomplete="off"><div class="modal-actions"><button class="btn secondary" onclick="closeModal()">Cancel</button><button class="btn" id="modalSave">Save</button></div></div></div>
<div class="toast" id="toast">Saved</div>
<input type="file" id="restoreInput" accept="application/json" style="display:none">
<script>
const STORAGE_KEY='jugg_organizer_v1';
let currentGroupId=null,currentBoardId=null,modalCallback=null,storageOK=true;
function uid(){return (window.crypto&&window.crypto.randomUUID)?window.crypto.randomUUID():'id-'+Date.now()+'-'+Math.random().toString(16).slice(2)}
function fresh(){return {version:1,groups:[]}}
function readRaw(){try{return window.localStorage.getItem(STORAGE_KEY)}catch(e){}try{return window.parent.localStorage.getItem(STORAGE_KEY)}catch(e){}return null}
function writeRaw(raw){try{window.localStorage.setItem(STORAGE_KEY,raw);return true}catch(e){}try{window.parent.localStorage.setItem(STORAGE_KEY,raw);return true}catch(e){}return false}
function load(){try{const raw=readRaw();if(!raw)return fresh();const data=JSON.parse(raw);return data&&Array.isArray(data.groups)?data:fresh()}catch(e){return fresh()}}
let data=load();
function save(){storageOK=writeRaw(JSON.stringify(data));showToast(storageOK?'Saved':'Browser storage unavailable')}
function showToast(message='Saved'){const t=document.getElementById('toast');t.textContent=message;t.classList.add('show');clearTimeout(showToast.timer);showToast.timer=setTimeout(()=>t.classList.remove('show'),1200)}
function esc(v){return String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
function group(){return data.groups.find(g=>g.id===currentGroupId)}
function board(){const g=group();return g?g.boards.find(b=>b.id===currentBoardId):null}
function statsBoard(b){const lists=b.lists||[];return {lists:lists.length,cards:lists.reduce((n,l)=>n+(l.cards||[]).length,0)}}
function openModal(title,hint,initial,cb){modalCallback=cb;document.getElementById('modalTitle').textContent=title;document.getElementById('modalHint').textContent=hint||'';const input=document.getElementById('modalInput');input.value=initial||'';document.getElementById('modalWrap').style.display='flex';setTimeout(()=>{input.focus();input.select()},30)}
function closeModal(){document.getElementById('modalWrap').style.display='none';modalCallback=null}
document.getElementById('modalSave').onclick=()=>{const v=document.getElementById('modalInput').value.trim();if(!v)return;const cb=modalCallback;closeModal();if(cb)cb(v)};
document.getElementById('modalInput').addEventListener('keydown',e=>{if(e.key==='Enter')document.getElementById('modalSave').click();if(e.key==='Escape')closeModal()});
function backup(){const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='JUGG_Organizer_Backup_'+new Date().toISOString().slice(0,10)+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),500)}
function restore(){document.getElementById('restoreInput').click()}
document.getElementById('restoreInput').addEventListener('change',e=>{const file=e.target.files[0];if(!file)return;const r=new FileReader();r.onload=()=>{try{const candidate=JSON.parse(r.result);if(!candidate||!Array.isArray(candidate.groups))throw new Error('Invalid backup');if(confirm('Replace the current JUGG Organizer data with this backup?')){data=candidate;currentGroupId=null;currentBoardId=null;save();renderGroups()}}catch(err){alert('This file is not a valid JUGG Organizer backup.')}};r.readAsText(file);e.target.value=''})
function shellHeader(title,sub,primaryLabel,primaryAction,crumbs=''){
  return `<div class="topbar"><div><div class="kicker">JUGG 5.0 · PROGRAM 04</div><div class="title">${esc(title)}</div><div class="subtitle">${esc(sub)}</div></div><div class="actions"><button class="btn secondary" onclick="backup()">Backup</button><button class="btn secondary" onclick="restore()">Restore</button>${primaryLabel?`<button class="btn" onclick="${primaryAction}">＋ ${esc(primaryLabel)}</button>`:''}</div></div>${crumbs}`
}
function renderGroups(){currentGroupId=null;currentBoardId=null;const app=document.getElementById('app');const cards=data.groups.map(g=>`<div class="folder" onclick="openGroup('${g.id}')"><div class="card-tools"><button class="mini" onclick="event.stopPropagation();renameGroup('${g.id}')">Rename</button><button class="mini" onclick="event.stopPropagation();deleteGroup('${g.id}')">×</button></div><div class="folder-icon">▰</div><div class="card-name">${esc(g.name)}</div><div class="meta">${g.boards.length} board${g.boards.length===1?'':'s'}</div></div>`).join('');
 app.innerHTML=shellHeader('Organizer','Groups are folders for your boards. Everything saves automatically in this browser.','Add group','addGroup()')+(cards?`<div class="grid">${cards}</div>`:`<div class="empty"><b>No groups yet</b>Create your first group to start organizing boards.</div>`)+notice();}
function addGroup(){openModal('New group','Use groups like folders — for example JUGG, School or Personal.','',name=>{data.groups.push({id:uid(),name,boards:[]});save();renderGroups()})}
function renameGroup(id){const g=data.groups.find(x=>x.id===id);if(!g)return;openModal('Rename group','',g.name,name=>{g.name=name;save();renderGroups()})}
function deleteGroup(id){const g=data.groups.find(x=>x.id===id);if(!g)return;if(confirm(`Delete “${g.name}” and every board inside it?`)){data.groups=data.groups.filter(x=>x.id!==id);save();renderGroups()}}
function openGroup(id){currentGroupId=id;currentBoardId=null;renderBoards()}
function renderBoards(){const g=group();if(!g){renderGroups();return}const cards=g.boards.map(b=>{const st=statsBoard(b);return `<div class="board-card" onclick="openBoard('${b.id}')"><div class="card-tools"><button class="mini" onclick="event.stopPropagation();renameBoard('${b.id}')">Rename</button><button class="mini" onclick="event.stopPropagation();deleteBoard('${b.id}')">×</button></div><div class="folder-icon">▦</div><div class="card-name">${esc(b.name)}</div><div class="meta">${st.lists} list${st.lists===1?'':'s'} · ${st.cards} card${st.cards===1?'':'s'}</div></div>`}).join('');const crumbs=`<div class="crumbs"><span class="crumb" onclick="renderGroups()">Groups</span><span class="sep">›</span><span>${esc(g.name)}</span></div>`;document.getElementById('app').innerHTML=shellHeader(g.name,'Boards inside this group.','Add board','addBoard()',crumbs)+(cards?`<div class="grid">${cards}</div>`:`<div class="empty"><b>No boards in this group</b>Add a board, then build the lists you need inside it.</div>`)+notice()}
function addBoard(){const g=group();if(!g)return;openModal('New board','Give this board a clear project or workflow name.','',name=>{g.boards.push({id:uid(),name,lists:[]});save();renderBoards()})}
function renameBoard(id){const b=group()?.boards.find(x=>x.id===id);if(!b)return;openModal('Rename board','',b.name,name=>{b.name=name;save();renderBoards()})}
function deleteBoard(id){const g=group(),b=g?.boards.find(x=>x.id===id);if(!b)return;if(confirm(`Delete board “${b.name}”?`)){g.boards=g.boards.filter(x=>x.id!==id);save();renderBoards()}}
function openBoard(id){currentBoardId=id;renderBoard()}
function renderBoard(){const g=group(),b=board();if(!g||!b){renderGroups();return}const crumbs=`<div class="crumbs"><span class="crumb" onclick="renderGroups()">Groups</span><span class="sep">›</span><span class="crumb" onclick="renderBoards()">${esc(g.name)}</span><span class="sep">›</span><span>${esc(b.name)}</span></div>`;const lists=(b.lists||[]).map(l=>listHtml(l)).join('');document.getElementById('app').innerHTML=shellHeader(b.name,'Drag cards between lists. Add only the workflow you actually need.','Add list','addList()',crumbs)+`<div class="board-shell"><div class="board-scroll">${lists}<button class="new-list" onclick="addList()">＋ Add another list</button></div></div>`+notice()}
function listHtml(l){const cards=(l.cards||[]).map(c=>`<div class="task" draggable="true" ondragstart="dragCard(event,'${l.id}','${c.id}')" ondblclick="renameCard('${l.id}','${c.id}')">${esc(c.text)}<button class="x" onclick="event.stopPropagation();deleteCard('${l.id}','${c.id}')">×</button></div>`).join('');return `<section class="list"><div class="list-head"><div class="list-title">${esc(l.name)}</div><div class="list-actions"><button class="mini" onclick="renameList('${l.id}')">✎</button><button class="mini" onclick="deleteList('${l.id}')">×</button></div></div><div class="cards" ondragover="dragOver(event)" ondragleave="dragLeave(event)" ondrop="dropCard(event,'${l.id}')">${cards}</div><button class="add-card" onclick="addCard('${l.id}')">＋ Add a card</button></section>`}
function addList(){const b=board();if(!b)return;openModal('New list','Examples: To do, In progress, Waiting, Done.','',name=>{b.lists.push({id:uid(),name,cards:[]});save();renderBoard()})}
function renameList(id){const l=board()?.lists.find(x=>x.id===id);if(!l)return;openModal('Rename list','',l.name,name=>{l.name=name;save();renderBoard()})}
function deleteList(id){const b=board(),l=b?.lists.find(x=>x.id===id);if(!l)return;if(confirm(`Delete list “${l.name}” and its ${l.cards.length} card(s)?`)){b.lists=b.lists.filter(x=>x.id!==id);save();renderBoard()}}
function addCard(listId){const l=board()?.lists.find(x=>x.id===listId);if(!l)return;openModal('New card','Keep the card short and actionable.','',text=>{l.cards.push({id:uid(),text});save();renderBoard()})}
function renameCard(listId,cardId){const l=board()?.lists.find(x=>x.id===listId),c=l?.cards.find(x=>x.id===cardId);if(!c)return;openModal('Edit card','',c.text,text=>{c.text=text;save();renderBoard()})}
function deleteCard(listId,cardId){const l=board()?.lists.find(x=>x.id===listId);if(!l)return;l.cards=l.cards.filter(x=>x.id!==cardId);save();renderBoard()}
function dragCard(e,listId,cardId){e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',JSON.stringify({listId,cardId}))}
function dragOver(e){e.preventDefault();e.currentTarget.classList.add('drop-active');e.dataTransfer.dropEffect='move'}
function dragLeave(e){e.currentTarget.classList.remove('drop-active')}
function dropCard(e,targetListId){e.preventDefault();e.currentTarget.classList.remove('drop-active');let payload;try{payload=JSON.parse(e.dataTransfer.getData('text/plain'))}catch(_){return}const b=board(),source=b?.lists.find(x=>x.id===payload.listId),target=b?.lists.find(x=>x.id===targetListId);if(!source||!target)return;const idx=source.cards.findIndex(x=>x.id===payload.cardId);if(idx<0)return;const [card]=source.cards.splice(idx,1);target.cards.push(card);save();renderBoard()}
function notice(){const state=storageOK?'groups, boards, lists and cards are stored in this browser':'browser storage is unavailable in this session';return `<div class="notice"><span><strong>Auto-save:</strong> ${state} — no Trello or Google account required.</span><span>Use <strong>Backup</strong> if you want a portable copy.</span></div>`}
renderGroups();
</script>
</body>
</html>
    """
    components_html(organizer_html, height=800, scrolling=True)


def render_hub() -> None:
    st.markdown("""
    <div class="j40-shell">
      <div class="j40-gridlines"></div><div class="j40-orbit orbit-a"></div><div class="j40-orbit orbit-b"></div>
      <header class="j40-header"><div class="j40-brand"><span>J</span><b>JUGG</b><small>5.0</small></div><div class="j40-pulse"><i></i> Market workspace</div></header>
      <section class="j40-hero"><div class="j40-eyebrow">YOUR FINANCIAL COMMAND CENTRE</div><h1>See the signal.<br><em>Understand the move.</em></h1><p>Four focused tools. One coherent view of your markets and portfolio.</p></section>
      <nav class="j40-apps" aria-label="JUGG programs">
        <a class="j40-card" href="?page=news" target="_self"><span class="j40-index">01</span><div class="j40-icon"><svg viewBox="0 0 56 56"><path d="M13 10h29v36H13zM20 19h15M20 26h15M20 33h10"></path></svg></div><h2>News Finder</h2><p>Find and rank company and sector news.</p><b>Open program <i>↗</i></b></a>
        <a class="j40-card" href="?page=portfolio" target="_self"><span class="j40-index">02</span><div class="j40-icon"><svg viewBox="0 0 56 56"><path d="M10 44h38M15 39V27M25 39V17M35 39V23M45 39V11"></path></svg></div><h2>Portfolio</h2><p>Track value, allocation and market performance.</p><b>Open program <i>↗</i></b></a>
        <a class="j40-card" href="?page=briefing&view=overview" target="_self"><span class="j40-index">03</span><div class="j40-icon"><svg viewBox="0 0 56 56"><path d="M9 39l11-12 9 7 11-17 8 6M9 46h39"></path><circle cx="20" cy="27" r="2"></circle><circle cx="40" cy="17" r="2"></circle></svg></div><h2>Market Briefing</h2><p>Explain risk, flows, drivers and your holdings.</p><b>Open program <i>↗</i></b></a>
        <a class="j40-card" href="?page=organizer" target="_self"><span class="j40-index">04</span><div class="j40-icon"><svg viewBox="0 0 56 56"><path d="M10 15h15l4 5h17v25H10z"></path><path d="M16 28h10M16 34h18M16 40h14"></path></svg></div><h2>Organizer</h2><p>Organize projects in groups, boards, lists and cards.</p><b>Open program <i>↗</i></b></a>
      </nav>
      <footer class="j40-footer"><span>LIVE DATA LAYER</span><i></i><span>48H INTELLIGENCE</span><i></i><span>DARK & SLEEK SYSTEM</span></footer>
    </div>
    <style>
    .main .block-container{max-width:1500px;padding:.75rem 1.15rem 1rem!important}
    .stApp:before,.stApp:after{content:"";position:fixed;pointer-events:none;z-index:0;border-radius:48% 52% 57% 43%;filter:blur(78px);opacity:.34;will-change:transform}
    .stApp:before{width:48vw;height:46vw;left:-12vw;top:8vh;background:radial-gradient(circle at 45% 45%,rgba(103,61,226,.72) 0%,rgba(65,73,205,.34) 38%,transparent 72%);animation:j50-flow-a 18s ease-in-out infinite alternate}
    .stApp:after{width:46vw;height:43vw;right:-13vw;bottom:-8vh;background:radial-gradient(circle at 50% 50%,rgba(35,102,218,.64) 0%,rgba(78,52,201,.30) 43%,transparent 72%);animation:j50-flow-b 21s ease-in-out infinite alternate}
    [data-testid="stAppViewContainer"]>.main{position:relative;z-index:1}
    .j40-shell{position:relative;min-height:calc(100vh - 4.2rem);overflow:hidden;padding:24px 32px 18px;border:1px solid rgba(132,153,255,.18);border-radius:25px;background:radial-gradient(circle at 50% -15%,rgba(112,65,235,.18),transparent 38%),linear-gradient(150deg,#091026 0%,#050918 62%,#071022 100%);box-shadow:0 35px 110px rgba(0,0,0,.48);display:flex;flex-direction:column}
    .j40-gridlines{position:absolute;inset:0;background-image:linear-gradient(rgba(117,136,207,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(117,136,207,.045) 1px,transparent 1px);background-size:52px 52px;mask-image:linear-gradient(to bottom,black,transparent 86%);animation:j40-grid 16s linear infinite}.j40-header{position:relative;z-index:3;display:flex;align-items:center;justify-content:space-between}.j40-brand{display:flex;align-items:center;gap:10px;color:#f8f9ff}.j40-brand>span{width:32px;height:32px;display:grid;place-items:center;border-radius:10px;background:linear-gradient(145deg,#9661ff,#3151cf);font-weight:800;box-shadow:0 0 25px rgba(125,77,255,.42)}.j40-brand b{font-size:15px;letter-spacing:.04em}.j40-brand small{font-size:9px;color:#9b83e8;border:1px solid rgba(155,126,255,.3);border-radius:999px;padding:3px 6px}.j40-pulse{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:#8290b5}.j40-pulse i{display:inline-block;width:6px;height:6px;border-radius:50%;background:#58db94;box-shadow:0 0 12px #58db94;margin-right:7px;animation:j40-pulse 2.2s ease-in-out infinite}
    .j40-hero{position:relative;z-index:2;text-align:center;margin:34px auto 28px;animation:j40-rise .85s cubic-bezier(.16,1,.3,1) both}.j40-eyebrow{font-size:9px;letter-spacing:.22em;color:#8e7bd2;margin-bottom:12px}.j40-hero h1{margin:0!important;color:#f8f9ff!important;font-size:clamp(34px,4vw,55px)!important;line-height:1.01!important;letter-spacing:-.045em!important;font-weight:700!important}.j40-hero h1 em{font-style:normal;background:linear-gradient(90deg,#b5a1ff,#6db9ff);-webkit-background-clip:text;background-clip:text;color:transparent}.j40-hero p{margin:12px 0 0;color:#8f9abb;font-size:13px}
    .j40-apps{position:relative;z-index:3;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;width:100%;max-width:1120px;margin:0 auto}.j40-card{position:relative;display:block;min-height:220px;padding:20px 19px 17px;border:1px solid rgba(132,153,255,.18);border-radius:17px;background:linear-gradient(150deg,rgba(20,30,61,.9),rgba(8,14,31,.96));text-decoration:none!important;overflow:hidden;transition:transform .32s cubic-bezier(.2,.8,.2,1),border-color .32s,box-shadow .32s;animation:j40-card .7s cubic-bezier(.16,1,.3,1) both}.j40-card:nth-child(2){animation-delay:.08s}.j40-card:nth-child(3){animation-delay:.16s}.j40-card:nth-child(4){animation-delay:.24s}.j40-card:before{content:"";position:absolute;inset:-100% -40%;background:linear-gradient(112deg,transparent 42%,rgba(255,255,255,.09) 50%,transparent 58%);transform:translateX(-60%) rotate(7deg);transition:.75s}.j40-card:hover{transform:translateY(-7px);border-color:rgba(143,92,255,.58);box-shadow:0 20px 48px rgba(49,35,137,.31)}.j40-card:hover:before{transform:translateX(60%) rotate(7deg)}.j40-index{position:absolute;right:16px;top:15px;color:#596783;font:600 10px/1 monospace;letter-spacing:.12em}.j40-icon{width:48px;height:48px;border:1px solid rgba(152,117,255,.35);border-radius:14px;display:grid;place-items:center;background:linear-gradient(145deg,rgba(112,69,236,.28),rgba(36,76,171,.22));box-shadow:0 0 28px rgba(113,71,240,.18)}.j40-icon svg{width:29px;fill:none;stroke:#ab91ff;stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round;filter:drop-shadow(0 0 6px rgba(122,84,255,.5))}.j40-card h2{margin:17px 0 7px!important;color:#f6f7ff!important;font-size:16px!important}.j40-card p{min-height:38px;margin:0;color:#94a0bf;font-size:11px;line-height:1.55}.j40-card>b{display:flex;align-items:center;justify-content:space-between;margin-top:17px;padding-top:12px;border-top:1px solid rgba(132,153,255,.1);color:#a990ff;font-size:10px;font-weight:600}.j40-card>b i{font-style:normal;font-size:15px}.j40-soon{opacity:.52}.j40-soon:hover{transform:none;border-color:rgba(132,153,255,.18);box-shadow:none}.j40-soon .j40-icon{filter:grayscale(.5)}
    .j40-footer{position:relative;z-index:2;margin:auto auto 0;padding-top:22px;display:flex;align-items:center;justify-content:center;gap:12px;color:#5f6d8b;font-size:8px;letter-spacing:.15em}.j40-footer i{width:3px;height:3px;border-radius:50%;background:#765bd7}.j40-orbit{position:absolute;border:1px solid rgba(124,91,240,.12);border-radius:50%;pointer-events:none}.orbit-a{width:410px;height:410px;left:-220px;bottom:-250px;animation:j40-orbit 18s linear infinite}.orbit-b{width:520px;height:520px;right:-300px;top:-320px;animation:j40-orbit 24s linear infinite reverse}
    @keyframes j40-rise{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:none}}@keyframes j40-card{from{opacity:0;transform:translateY(24px) scale(.975)}to{opacity:1;transform:none}}@keyframes j40-pulse{50%{opacity:.35;box-shadow:0 0 4px #58db94}}@keyframes j40-grid{to{background-position:52px 52px}}@keyframes j40-orbit{to{transform:rotate(360deg)}}@keyframes j50-flow-a{0%{transform:translate3d(0,0,0) scale(1) rotate(0deg)}45%{transform:translate3d(22vw,-5vh,0) scale(1.12,.92) rotate(18deg)}100%{transform:translate3d(35vw,15vh,0) scale(.92,1.14) rotate(42deg)}}@keyframes j50-flow-b{0%{transform:translate3d(0,0,0) scale(1.05,.95) rotate(0deg)}55%{transform:translate3d(-24vw,-12vh,0) scale(.9,1.13) rotate(-22deg)}100%{transform:translate3d(-36vw,4vh,0) scale(1.12,.9) rotate(-46deg)}}
    @media(max-width:980px){.j40-shell{min-height:auto;padding:22px 22px 30px}.j40-apps{grid-template-columns:repeat(2,1fr)}.j40-footer{margin-top:24px}}@media(max-width:580px){.main .block-container{padding:.5rem!important}.j40-shell{padding:18px 13px 28px;border-radius:18px}.j40-apps{grid-template-columns:1fr}.j40-hero{margin:34px auto 25px}.j40-card{min-height:190px}.j40-footer{display:none}}
    </style>
    """, unsafe_allow_html=True)

page = st.query_params.get("page", "hub")
if isinstance(page, list):
    page = page[0] if page else "hub"

if page == "news":
    render_news_finder()
elif page == "portfolio":
    render_portfolio()
elif page == "briefing":
    render_market_briefing()
elif page == "organizer":
    render_organizer()
else:
    render_hub()
