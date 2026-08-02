# JUGG Application Hub — Market Briefing Update

This version keeps the existing **News Finder** and **Portfolio** programs and adds a third active program: **Market Briefing**.

## What was added

### Market Briefing overview

- A large **Market Overview** chart comparing the recent normalized movement of the S&P 500, Euro Stoxx 50, Nikkei 225 and Hang Seng.
- A green briefing-control area with:
  - **Short — 100–200 words**
  - **Medium — 200–350 words**
  - **Long — 350–500 words**
  - **Generate Briefing**
- A routed in-app briefing tab opens after generation.

### Market health grid

The right side contains twelve live bellwethers and market proxies in a **3 × 4 desktop grid**:

- S&P 500
- Nasdaq 100
- MSCI World ETF
- Russell 2000
- Euro Stoxx 50
- DAX
- Nikkei 225
- Hang Seng
- US 10-year yield
- EUR/USD
- Brent oil
- Gold

This includes exactly two dedicated European indices and two dedicated Asian indices.

### Top Drivers

The app selects current driver categories from timestamped news published in the preceding 48 hours. Clicking a driver opens an explanation covering:

1. What it actually is
2. What it means
3. Which companies or markets may be affected and why

### Holdings

The five current holdings appear in one row on desktop. Additional holdings automatically wrap to the next row.

Clicking a holding opens:

- A recent price chart
- The latest available 48-hour or recent-trading-point price change
- The three briefing-length choices
- A Generate Briefing action
- A separate generated-briefing tab with the selected sources

For **MS Europe 26/27 ABJ**, the chart uses the Euro Stoxx 50 only as a market proxy because the supplied project data does not include a public live ticker for the structured product. The app labels this explicitly and does not present the proxy as the product valuation.

## News and attribution rules

The briefing system:

- Uses timestamped articles inside a strict 48-hour window
- Deduplicates repeated stories
- Scores company, sector, macro and source relevance
- Separates company-specific evidence from broader market evidence
- Instructs the AI to distinguish:
  - Confirmed cause
  - Likely contributor
  - No clear explanation found
- Displays the sources used beneath each briefing
- Avoids padding a briefing with speculation when evidence is limited

## AI configuration

The app calls the OpenAI Responses API directly with `requests`, so no additional OpenAI Python package is required.

Create `.streamlit/secrets.toml` locally or add the same values in **Streamlit Community Cloud → App settings → Secrets**:

```toml
OPENAI_API_KEY = "your-api-key"
OPENAI_MODEL = "gpt-5-mini"
```

`OPENAI_MODEL` is optional. The code defaults to `gpt-5-mini` and lets you override the model without editing `app.py`.

Do not commit the real `secrets.toml` file to GitHub. A safe template is included as `.streamlit/secrets.toml.example`.

When no API key is configured, the program remains usable and shows a clearly labelled factual **evidence digest** instead of pretending that an AI briefing was generated.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Upload the contents of this folder to the GitHub repository.
2. Select `app.py` as the Streamlit entry point.
3. Add `OPENAI_API_KEY` under the app's Secrets settings.
4. Reboot the app after changing secrets.

## Existing programs retained

- Animated JUGG program-selection hub
- News Finder with company and sector RSS search
- Dark & Sleek Portfolio page
- Yahoo Finance quote loading with caching and saved-value fallbacks

## Important limitations

- Market prices and RSS feeds can occasionally be delayed or unavailable.
- News snippets may not contain every detail of a full article.
- A price move can have several causes; the app is deliberately instructed not to claim certainty without evidence.
- The current portfolio data does not contain unit quantities, so the existing Portfolio page retains its previous saved-value methodology.
