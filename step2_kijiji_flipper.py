"""
Step 2: the Kijiji Flipper.
Scans a Kijiji search results page, estimates a fair price from the listings themselves
(median of everything in the same search), flags anything priced well below that, and
drafts a friendly outreach message for each flagged deal.

This does NOT message anyone automatically — it only drafts messages for you to review and
send yourself. That's a deliberate choice, not a missing feature: see the README for why.
"""

import json
import os
import re
import sys
import time
import statistics
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
from openai import OpenAI
from steel import Steel
from playwright.sync_api import sync_playwright

from report import generate_report, open_report

load_dotenv()

STEEL_API_KEY = os.environ["STEEL_API_KEY"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]

MODEL = "openai/gpt-4o-mini"

# Any Kijiji search results page — change category/city/keyword freely.
SEARCH_URL = "https://www.kijiji.ca/b-bikes/city-of-toronto/c645l1700273"

# Flag a listing if its price is below this fraction of the search's median price.
DEAL_THRESHOLD = 0.6

# Skip listings that are obviously parts/accessories, not the full item — otherwise a $10
# handlebar drags the median down and gets compared against complete bikes. Tune this list
# per category (e.g. for a laptop search you'd exclude "charger", "case", "battery only").
EXCLUDE_KEYWORDS = [
    "wheel", "tire", "tyre", "stem", "handlebar", "pegs", "frame only", "seat post",
    "seatpost", "pedals", "chain", "sprocket", "forks", "brake", "grips", "parts",
]

CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "listings_cache.json")
FALLBACK_MESSAGE = "Hey! Is this still available? Would love to know more about the condition and how pickup works."

DRAFT_PROMPT = """You are drafting a short, friendly Kijiji message from a buyer to a seller.
Listing title: {title}
Listing price: {price}

Write a casual, human, 2-3 sentence message asking if it's still available, showing genuine
interest, and asking one relevant follow-up question about condition or pickup. No greetings
like "Dear seller," keep it casual like a real DM. Reply with ONLY the message text."""


def parse_price(text):
    match = re.search(r"\$\s*([\d,]+(?:\.\d{2})?)", text or "")
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    return value if value > 0 else None


def scrape_listings(page, attempts=3):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            page.goto(SEARCH_URL, timeout=20000)
            page.wait_for_selector('a[data-testid="rich-card-link"]', timeout=15000)
            return _extract_cards(page)
        except Exception as e:
            last_error = e
            print(f"   Scrape attempt {attempt}/{attempts} failed ({e}); retrying...")
            time.sleep(2)
    raise last_error


def _extract_cards(page):

    cards = page.evaluate("""
        () => Array.from(document.querySelectorAll('li'))
            .filter(li => li.querySelector('a[data-testid="rich-card-link"]'))
            .map(li => ({
                title: li.querySelector('[data-testid="listing-title"]')?.innerText || '',
                price_text: li.querySelector('[data-testid="listing-price"]')?.innerText || '',
                location: li.querySelector('[data-testid="listing-location"]')?.innerText || '',
                date: li.querySelector('[data-testid="listing-date"]')?.innerText || '',
                url: li.querySelector('a[data-testid="rich-card-link"]')?.getAttribute('href') || '',
                image: li.querySelector('[data-testid="rich-card-image"]')?.getAttribute('src') || '',
            }))
    """)

    listings = []
    for c in cards:
        price = parse_price(c["price_text"])
        if price is None:
            continue
        if any(kw in c["title"].lower() for kw in EXCLUDE_KEYWORDS):
            continue
        listings.append({**c, "price": price})
    return listings


def save_cache(listings):
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(listings, f)


def load_cache():
    if not os.path.exists(CACHE_PATH):
        return []
    with open(CACHE_PATH, encoding="utf-8") as f:
        return json.load(f)


def find_deals(listings):
    if len(listings) < 5:
        return [], None
    median_price = statistics.median(l["price"] for l in listings)
    deals = [l for l in listings if l["price"] < median_price * DEAL_THRESHOLD]
    deals.sort(key=lambda l: l["price"])
    return deals, median_price


def draft_message(client, listing):
    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=120,
            messages=[{
                "role": "user",
                "content": DRAFT_PROMPT.format(title=listing["title"], price=listing["price_text"]),
            }],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"   (message draft failed: {e} — using fallback message)")
        return FALLBACK_MESSAGE


def scrape_via_steel():
    steel = Steel(steel_api_key=STEEL_API_KEY)
    print("Creating Steel session...")
    session = steel.sessions.create()
    print(f"Watch it live: {session.session_viewer_url}\n")

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(
                f"wss://connect.steel.dev?apiKey={STEEL_API_KEY}&sessionId={session.id}"
            )
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()

            print("Scraping listings...")
            listings = scrape_listings(page)
            browser.close()
        return listings
    finally:
        steel.sessions.release(session.id)
        print("Session released.")


def get_listings():
    try:
        listings = scrape_via_steel()
        save_cache(listings)
        return listings, False
    except Exception as e:
        print(f"Live scrape failed after retries ({e}).")
        cached = load_cache()
        if cached:
            print(f"Falling back to {len(cached)} listings cached from the last successful run.\n")
            return cached, True
        print("No cached data available either — nothing to show.")
        return [], True


def main():
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)

    listings, used_cache = get_listings()
    if not listings:
        return

    if used_cache:
        print("(Showing cached results — live site was unreachable this run.)\n")

    print(f"Found {len(listings)} listings with a real price.\n")
    deals, median_price = find_deals(listings)

    if median_price is None:
        print("Not enough priced listings to estimate a fair market value.")
        return

    print(f"Median price in this search: ${median_price:,.2f}")
    print(f"Flagging anything under ${median_price * DEAL_THRESHOLD:,.2f} ({int(DEAL_THRESHOLD * 100)}% of median)\n")

    messages_by_url = {}
    if not deals:
        print("No underpriced listings found this run.")
    print(f"{len(deals)} potential deal(s):\n")
    for d in deals:
        print(f"${d['price']:,.2f}  —  {d['title']}")
        print(f"   {d['location']} · {d['date']}")
        print(f"   {d['url']}")
        message = draft_message(client, d)
        messages_by_url[d["url"]] = message
        print(f"   Drafted message: \"{message}\"\n")

    report_path = generate_report(listings, deals, median_price, DEAL_THRESHOLD, messages_by_url)
    print(f"Report written to {report_path}")
    open_report(report_path)


if __name__ == "__main__":
    main()
