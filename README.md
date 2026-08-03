# JUGG 4.0

JUGG 4.0 updates the existing Streamlit application in place. It preserves News Finder and the JUGG 3.1 Market Briefing logic while introducing a compact animated four-program hub, consistent navigation, finance-style charts and a rebuilt Portfolio page.

## Main improvements

- Four-card opening screen designed to fit on a normal laptop viewport without scrolling.
- One consistent top navigation component on News Finder, Portfolio and Market Briefing.
- One current portfolio-value panel instead of four summary tiles.
- Interactive portfolio history beginning at **€5,022.45 on 1 May 2026**.
- Rebuilt Invested Countries map with correct Streamlit/Plotly alignment.
- Changeable 1D, 5D, 1M, 6M, YTD, 1Y, 5Y and MAX timelines on holding and indicator detail charts.
- Weighted **Market Regime** indicator: Risk-On, Risk-Off or Mixed / Neutral, with confidence and supporting signals.
- **Where Is Money Moving?** estimated-positioning panel. This is inferred from market prices and is never described as measured fund flow.
- Four groups of four clickable indicators: Equities, Safe Havens, Economic Drivers and Asia.
- Context-aware interpretations (for example, a lower gas price is not treated mechanically as negative).
- Clickable indicator detail views with charts, explanations, portfolio relevance and current sources.
- Short, Medium and Long overall-market briefings stored in Streamlit session state. Without an API key, JUGG shows a fully usable evidence digest without an alarming error panel.
- Clickable Top Drivers with facts, interpretation and portfolio relevance.
- Five responsive holding cards and individual holding detail/briefing views.
- Clear proxy labelling for **MS Europe 26/27 ABJ**; the Euro Stoxx 50 reference is not presented as the product price.
- Cached market/news calls, guarded external requests, loading states and readable errors.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## AI briefing configuration

The price dashboard, regime, positioning estimate, navigation, RSS news and evidence-based fallback briefings work without an AI key. For AI-written briefings, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and add:

```toml
OPENAI_API_KEY = "your-key"
OPENAI_MODEL = "gpt-5-mini"
```

The same values can be added in Streamlit Community Cloud under **App settings → Secrets**. Never commit the real secrets file. `OPENAI_MODEL` is optional. JUGG uses the OpenAI Responses API and keeps the key server-side.

## Add holdings without editing GitHub

JUGG 4.0 can load holdings from a public CSV export URL. A practical setup is a Google Sheet published as CSV. Add the URL to Streamlit Secrets:

```toml
PORTFOLIO_DATA_URL = "https://docs.google.com/spreadsheets/d/.../export?format=csv"
```

Use these column names:

```text
name,ticker,abbr,saved_value_eur,original_investment_eur,purchase_date,country,country_iso3,area,fx_ticker,proxy_ticker,news_terms,proxy_note
```

The repository includes `holdings_template.csv` with the current five holdings as a ready-to-import template.

Required for a listed holding: `name`, `ticker`, `abbr`, `original_investment_eur`, `country`, `country_iso3` and `area`. Use Yahoo Finance ticker notation, for example `SHL.DE`. Separate optional `news_terms` with `|`. For a product without a public ticker, leave `ticker` empty and provide `proxy_ticker` plus a clear `proxy_note`.

After this one-time setup, adding or deleting a row in the sheet updates Portfolio and Market Briefing automatically (cached for up to five minutes) without changing GitHub files. Static built-in holdings remain the fallback if the sheet cannot be reached.

## Data and reliability limitations

- Market charts use the public Yahoo Finance chart endpoint. Quotes may be delayed, exchange calendars differ, and the endpoint provides market prices—not institutional-grade real-time data.
- The displayed portfolio value is a market-based estimate. It normalizes the supplied investments to €5,022.45 on 1 May 2026 and includes relevant EUR/NOK and EUR/HKD currency movement. Exact broker valuation requires actual position quantities, transaction prices, cash flows and a live quote for the structured product.
- The 48-hour change uses available trading points within the period. If markets were closed, the app labels the basis as the latest available trading points.
- European TTF data availability depends on the public symbol. If unavailable, the card says so and no stale value is shown as live.
- News comes from Google News and Yahoo RSS links, is deduplicated, time-filtered and ranked. RSS snippets may omit important context.
- Price-based positioning is an estimate, not actual ETF or mutual-fund flow data. A paid flow provider would be required for measured flows.
- Market regime, drivers and causal explanations are indicators or interpretations, not guaranteed conclusions. The AI prompt distinguishes confirmed drivers, likely contributors, possible background factors and cases with no clear explanation.
- **MS Europe 26/27 ABJ** has no public live product ticker in the supplied project. Its Euro Stoxx 50 chart is explicitly a market-exposure reference only.
- AI calls require a valid OpenAI API key and may incur provider costs. Without one, the app produces a labelled evidence digest; this is normal evidence mode, not an application crash.

## Deployment

Upload the folder contents to GitHub, select `app.py` as the Streamlit entry point, add optional secrets in the hosting settings, and deploy. Python dependencies are listed in `requirements.txt`.
