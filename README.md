# Flipper.ai

A web agent for flipping sales on Kijiji — Battle of the Schools, Steel.dev web agents track.

Flipper.ai opens a real Kijiji search with a Steel.dev cloud browser, reads every listing on
the page, works out a fair market price from the listings themselves (the median of the
search), flags anything priced well below that, and drafts a friendly outreach message for
each one using an LLM. Results open automatically as a visual report — no messages are ever
sent automatically, drafts are for you to review and send yourself.

## Setup

1. Create a virtual environment and install deps:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   playwright install chromium
   ```

2. Copy `.env.example` to `.env` and fill in your real API keys:
   ```
   copy .env.example .env
   ```
   Then edit `.env` and paste in your Steel.dev and OpenRouter keys.

3. Smoke test the pipe:
   ```
   python step0_steel_test.py
   ```
   If it prints a session ID, a viewer URL, and "Page title: Example Domain", it works.

## Running the flipper

```
python step2_kijiji_flipper.py
```

This scrapes a live Kijiji search (see `SEARCH_URL` at the top of the file — change it to any
category/city/keyword), flags underpriced listings, drafts outreach messages, and
automatically opens a report page in your browser with photo cards for each deal.

If the live scrape fails, it automatically falls back to the last successful run's cached
results (`listings_cache.json`), so a demo never dies to a flaky page load.

## Other files

- `step1_haggle_agent.py` — a negotiation agent that argues for a discount over live chat,
  built and tested against a mock target page (kept separate from the flipper).
- `report.py` — builds the self-contained HTML report the flipper opens.

## If step0 fails

- `KeyError: STEEL_API_KEY` — your `.env` file is missing or the key name doesn't match.
- Import error on `steel` — check steel.dev's docs quickstart for the current SDK import name.
- Connection/auth error — double check the API key has no trailing space and your Steel
  account has active credits.
