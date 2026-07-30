# JUGG Application Hub

This Streamlit project contains:

- A polished animated program-selection hub
- News Finder as the first active program
- Seven reserved program cards for later modules
- RSS-based company and sector news search

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

Upload the files to a GitHub repository and select `app.py` as the entry point.

## Portfolio update

The Portfolio program uses the Dark & Sleek responsive layout, with a laptop sidebar and an iPhone bottom navigation. Quotes load from Yahoo Finance when the page opens and are cached for 15 minutes. Saved values are used if a quote is unavailable. The structured product remains at its last recorded valuation.
