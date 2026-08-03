# JUGG 3.1 — Market Briefing

JUGG 3.1 preserves the existing animated program hub, News Finder and Portfolio, and upgrades Market Briefing into a fast, plain-language 48-hour dashboard.

## Included

- Weighted **Market Regime** indicator: Risk-On, Risk-Off or Mixed / Neutral, with confidence and supporting signals.
- **Where Is Money Moving?** estimated-positioning panel. This is inferred from market prices and is never described as measured fund flow.
- Four groups of four clickable indicators: Equities, Safe Havens, Economic Drivers and Asia.
- Context-aware interpretations (for example, a lower gas price is not treated mechanically as negative).
- Clickable indicator detail views with charts, explanations, portfolio relevance and current sources.
- Short, Medium and Long overall-market briefings stored in Streamlit session state.
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

## Optional AI configuration

The price dashboard, regime, positioning estimate, navigation, RSS news and evidence-based fallback briefings work without an AI key. For AI-written briefings, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and add:

```toml
OPENAI_API_KEY = "your-key"
OPENAI_MODEL = "gpt-5-mini"
```

The same values can be added in Streamlit Community Cloud under **App settings → Secrets**. Never commit the real secrets file. `OPENAI_MODEL` is optional.

## Data and reliability limitations

- Market charts use the public Yahoo Finance chart endpoint. Quotes may be delayed, exchange calendars differ, and the endpoint provides market prices—not institutional-grade real-time data.
- The 48-hour change uses available trading points within the period. If markets were closed, the app labels the basis as the latest available trading points.
- European TTF data availability depends on the public symbol. If unavailable, the card says so and no stale value is shown as live.
- News comes from Google News and Yahoo RSS links, is deduplicated, time-filtered and ranked. RSS snippets may omit important context.
- Price-based positioning is an estimate, not actual ETF or mutual-fund flow data. A paid flow provider would be required for measured flows.
- Market regime, drivers and causal explanations are indicators or interpretations, not guaranteed conclusions. The AI prompt distinguishes confirmed drivers, likely contributors, possible background factors and cases with no clear explanation.
- **MS Europe 26/27 ABJ** has no public live product ticker in the supplied project. Its Euro Stoxx 50 chart is explicitly a market-exposure reference only.
- AI calls require a valid OpenAI API key and may incur provider costs. Without one, the app produces a labelled evidence digest.

## Deployment

Upload the folder contents to GitHub, select `app.py` as the Streamlit entry point, add optional secrets in the hosting settings, and deploy. Python dependencies are listed in `requirements.txt`.
