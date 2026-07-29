
import html as html_lib
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse

import feedparser
import requests
import streamlit as st
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
      <div class="brand"><div class="brand-mark">J</div><div><b>JUGG</b><span>Personal application hub</span></div></div>
      <div class="hero"><h1>Welcome back</h1><p>What would you like to explore today?</p><div class="hero-line"></div></div>
      <div class="grid">
        <div class="app-card active-card">
          <div class="shine"></div>
          <div class="icon-wrap">
            <svg viewBox="0 0 64 64" aria-hidden="true">
              <rect x="13" y="11" width="31" height="39" rx="4"></rect>
              <path d="M21 21h15M21 28h15M21 35h10"></path>
              <rect x="21" y="41" width="25" height="12" rx="3"></rect>
            </svg>
          </div>
          <div class="card-title">News Finder</div>
          <div class="card-copy">Find and analyze the latest company and sector news.</div>
          <div class="open-hint">Open program <span>→</span></div>
        </div>
        <div class="app-card placeholder"><div class="plus">+</div><div class="card-title">Future program</div><div class="card-copy">Reserved for the next module.</div></div>
        <div class="app-card placeholder"><div class="plus">+</div><div class="card-title">Future program</div><div class="card-copy">Reserved for the next module.</div></div>
        <div class="app-card placeholder"><div class="plus">+</div><div class="card-title">Future program</div><div class="card-copy">Reserved for the next module.</div></div>
        <div class="app-card placeholder"><div class="plus">+</div><div class="card-title">Future program</div><div class="card-copy">Reserved for the next module.</div></div>
        <div class="app-card placeholder"><div class="plus">+</div><div class="card-title">Future program</div><div class="card-copy">Reserved for the next module.</div></div>
        <div class="app-card placeholder"><div class="plus">+</div><div class="card-title">Future program</div><div class="card-copy">Reserved for the next module.</div></div>
        <div class="app-card placeholder"><div class="plus">+</div><div class="card-title">Future program</div><div class="card-copy">Reserved for the next module.</div></div>
      </div>
      <div class="wave wave-one"></div><div class="wave wave-two"></div>
    </div>
    <style>
    .hub-shell{position:relative;overflow:hidden;min-height:790px;padding:22px 34px 120px;border:1px solid rgba(132,153,255,.18);
    border-radius:25px;background:linear-gradient(155deg,rgba(12,17,38,.94),rgba(5,9,23,.98));box-shadow:0 30px 90px rgba(0,0,0,.38)}
    .brand{display:flex;align-items:center;gap:11px;position:relative;z-index:3}.brand-mark{width:35px;height:35px;border-radius:12px;
    display:grid;place-items:center;background:linear-gradient(145deg,#8c5cff,#334ee9);box-shadow:0 0 28px rgba(126,77,255,.42);font-weight:800}
    .brand b{display:block;font-size:15px}.brand span{display:block;color:#8994ba;font-size:10px;letter-spacing:.12em;text-transform:uppercase;margin-top:2px}
    .hero{text-align:center;margin:54px 0 39px;position:relative;z-index:3}.hero h1{margin:0;font-size:42px;letter-spacing:-.035em}
    .hero p{margin:9px 0;color:#a5afcf}.hero-line{width:38px;height:3px;border-radius:99px;margin:18px auto 0;background:linear-gradient(90deg,#3186ff,#bb4df3)}
    .grid{position:relative;z-index:3;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:20px;max-width:1060px;margin:auto}
    .app-card{position:relative;min-height:210px;padding:25px;border:1px solid rgba(132,153,255,.18);border-radius:17px;
    background:linear-gradient(145deg,rgba(20,29,61,.88),rgba(11,16,37,.92));overflow:hidden;transition:transform .32s cubic-bezier(.2,.8,.2,1),border-color .32s,box-shadow .32s}
    .app-card:hover{transform:translateY(-7px) scale(1.015);border-color:rgba(143,92,255,.6);box-shadow:0 18px 50px rgba(38,25,120,.32)}
    .active-card{animation:cardIn .75s cubic-bezier(.16,1,.3,1) both}.placeholder{opacity:.48;animation:cardIn .75s cubic-bezier(.16,1,.3,1) both}
    .placeholder:nth-child(2){animation-delay:.06s}.placeholder:nth-child(3){animation-delay:.12s}.placeholder:nth-child(4){animation-delay:.18s}
    .placeholder:nth-child(5){animation-delay:.24s}.placeholder:nth-child(6){animation-delay:.30s}.placeholder:nth-child(7){animation-delay:.36s}.placeholder:nth-child(8){animation-delay:.42s}
    .shine{position:absolute;inset:-120% -50%;background:linear-gradient(110deg,transparent 40%,rgba(255,255,255,.12) 50%,transparent 60%);transform:rotate(8deg);animation:shine 5s ease-in-out infinite}
    .icon-wrap{width:58px;height:58px;border-radius:15px;display:grid;place-items:center;background:linear-gradient(145deg,rgba(108,69,239,.38),rgba(35,67,175,.34));
    border:1px solid rgba(154,119,255,.38);box-shadow:0 0 30px rgba(126,77,255,.30)}
    .icon-wrap svg{width:36px;fill:none;stroke:#a98cff;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;filter:drop-shadow(0 0 5px #7955ff)}
    .card-title{font-size:18px;font-weight:700;margin-top:18px}.card-copy{font-size:13px;line-height:1.5;color:#9ca7ca;margin-top:7px}
    .open-hint{position:absolute;left:25px;right:25px;bottom:20px;color:#c9baff;font-size:12px}.open-hint span{float:right;font-size:18px;transition:.25s}.active-card:hover .open-hint span{transform:translateX(5px)}
    .plus{width:58px;height:58px;border:1px dashed rgba(155,166,210,.35);border-radius:15px;display:grid;place-items:center;font-size:28px;color:#7e89ae}
    .ambient{position:absolute;width:420px;height:420px;border-radius:50%;filter:blur(85px);opacity:.20;animation:float 9s ease-in-out infinite alternate}
    .ambient-a{left:-170px;bottom:-170px;background:#8a3cff}.ambient-b{right:-180px;bottom:-160px;background:#147dff;animation-delay:-3s}
    .wave{position:absolute;left:-8%;right:-8%;height:120px;bottom:-35px;border-radius:50%;border-top:2px solid rgba(112,74,255,.65);
    filter:drop-shadow(0 0 16px rgba(101,67,255,.7));transform:rotate(-2deg);animation:wave 6s ease-in-out infinite}
    .wave-two{bottom:-5px;border-color:rgba(31,118,255,.5);animation-delay:-2.4s;opacity:.7}
    @keyframes cardIn{from{opacity:0;transform:translateY(24px) scale(.97)}to{opacity:1;transform:none}}
    @keyframes shine{0%,58%{transform:translateX(-80%) rotate(8deg)}78%,100%{transform:translateX(80%) rotate(8deg)}}
    @keyframes float{to{transform:translate(35px,-30px) scale(1.08)}} @keyframes wave{50%{transform:translateY(-12px) rotate(2deg) scaleX(1.04)}}
    @media(max-width:980px){.grid{grid-template-columns:repeat(2,1fr)}} @media(max-width:600px){.hub-shell{padding:20px 16px 100px}.grid{grid-template-columns:1fr}.hero h1{font-size:33px}}
    </style>
    """
    components_html(hub_html, height=835, scrolling=False)
    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    cols = st.columns([1.25, 1, 1, 1])
    with cols[0]:
        if st.button("Open News Finder", type="primary", use_container_width=True):
            st.session_state.page = "news"
            st.rerun()
    for col in cols[1:]:
        with col:
            st.button("Coming later", disabled=True, use_container_width=True)


def render_news_finder():
    st.markdown('<div class="back-wrap">', unsafe_allow_html=True)
    if st.button("← Back to programs"):
        st.session_state.page = "hub"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
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


if "page" not in st.session_state:
    st.session_state.page = "hub"

if st.session_state.page == "news":
    render_news_finder()
else:
    render_hub()
