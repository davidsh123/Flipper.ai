"""
Step 0: prove the Steel.dev pipe works.
Launches a cloud browser session, opens one page, prints its title, closes the session.
Nothing agent-y yet — just confirming your API key and connection work before building on top.
"""

import os
from dotenv import load_dotenv
from steel import Steel
from playwright.sync_api import sync_playwright

load_dotenv()

STEEL_API_KEY = os.environ["STEEL_API_KEY"]

client = Steel(steel_api_key=STEEL_API_KEY)

print("Creating Steel session...")
session = client.sessions.create()
print(f"Session created: {session.id}")
print(f"Live viewer (watch it in your browser): {session.session_viewer_url}")

try:
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(
            f"wss://connect.steel.dev?apiKey={STEEL_API_KEY}&sessionId={session.id}"
        )
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()

        page.goto("https://example.com")
        print(f"Page title: {page.title()}")

        browser.close()
finally:
    client.sessions.release(session.id)
    print("Session released.")
