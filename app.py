
import html as html_lib
import re
import time
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
            dt = datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc)
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
        <div class="app-card placeholder"><div class="empty-icon">＋</div><div class="card-title">Coming later</div><div class="card-copy">Future program</div></div>
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
    {"name": "Siemens Healthineers", "ticker": "SHL.DE", "abbr": "SHL", "saved_value_eur": 852.00, "country": "Germany", "country_iso3": "DEU", "area": "Healthcare"},
    {"name": "Verbund", "ticker": "VER.VI", "abbr": "VER", "saved_value_eur": 838.50, "country": "Austria", "country_iso3": "AUT", "area": "Renewable Energy"},
    {"name": "Tomra Systems", "ticker": "TOM.OL", "abbr": "TOM", "saved_value_eur": 1011.60, "country": "Norway", "country_iso3": "NOR", "area": "Industrials / Recycling"},
    {"name": "ANTA Sports", "ticker": "2020.HK", "abbr": "ANTA", "saved_value_eur": 944.13, "country": "China / Hong Kong", "country_iso3": "CHN", "area": "Consumer / Sportswear"},
    {"name": "MS Europe 26/27 ABJ", "ticker": None, "abbr": "MS EU 26/27", "saved_value_eur": 1017.40, "country": "Europe exposure", "country_iso3": None, "area": "Structured Product"},
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


page = st.query_params.get("page", "hub")
if isinstance(page, list):
    page = page[0] if page else "hub"

if page == "news":
    render_news_finder()
elif page == "portfolio":
    render_portfolio()
else:
    render_hub()
