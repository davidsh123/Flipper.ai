"""
Step 1: the Haggle Bot.
Opens the Driftboard pricing page (a scripted mock SaaS target with a live sales chat),
then negotiates with the chat bot turn by turn using an LLM, trying to get the lowest price.
"""

import os
from dotenv import load_dotenv
from openai import OpenAI
from steel import Steel
from playwright.sync_api import sync_playwright

load_dotenv()

STEEL_API_KEY = os.environ["STEEL_API_KEY"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]

# Swap this if OpenRouter says the model isn't found — check https://openrouter.ai/models
# for a current cheap/fast option. Keeping it cheap matters: the agent calls this every turn.
MODEL = "openai/gpt-4o-mini"

# Paste the SHARED (public) link to your published Driftboard Pricing artifact here.
TARGET_URL = "https://claude.ai/code/artifact/ba314c85-a45a-4cb2-b8d8-6eb31379b3d9"

MAX_TURNS = 5

SYSTEM_PROMPT = """You are a savvy but friendly customer negotiating the price of a SaaS \
subscription in a live sales chat. Your only goal: get the lowest possible monthly price on \
the "Driftboard Pro" plan.

Tactics you can use: mention you're comparing competitor pricing, ask about \
student/nonprofit/loyalty discounts, mention you might have to cancel or downgrade if the \
price doesn't work, politely ask if there's any way to do better, ask to speak with a manager \
if you get the same offer twice in a row.

Stay warm and human, never robotic or rude. Keep replies short (1-3 sentences), like a real \
chat message.

Reply with ONLY the exact message to send in the chat — no quotes, no stage directions, no \
explanation of your strategy.

If the rep says a price is their final offer and repeats it, accept gracefully in one short \
message and stop pushing.
"""


def get_last_bot_text(page):
    bot_messages = page.query_selector_all("#chat-messages .msg.bot")
    return bot_messages[-1].inner_text() if bot_messages else ""


def send_message(page, text):
    page.fill("#chat-input", text)
    page.click("#send-btn")
    page.wait_for_selector("#chat-messages .msg.typing", state="attached", timeout=3000)
    page.wait_for_selector("#chat-messages .msg.typing", state="detached", timeout=8000)


def main():
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
    steel = Steel(steel_api_key=STEEL_API_KEY)

    print("Creating Steel session...")
    session = steel.sessions.create()
    print(f"Watch it live: {session.session_viewer_url}\n")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    deal_reached = False

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(
                f"wss://connect.steel.dev?apiKey={STEEL_API_KEY}&sessionId={session.id}"
            )
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()

            page.goto(TARGET_URL)
            page.wait_for_selector("#chat-messages .msg.bot", timeout=15000)

            for turn in range(1, MAX_TURNS + 1):
                if page.is_visible("#deal-banner"):
                    deal_reached = True
                    break

                rep_text = get_last_bot_text(page)
                print(f"[Rep]   {rep_text}")

                messages.append({"role": "user", "content": f"[Sales rep says]: {rep_text}"})
                response = client.chat.completions.create(
                    model=MODEL, messages=messages, max_tokens=150
                )
                reply = response.choices[0].message.content.strip()
                messages.append({"role": "assistant", "content": reply})

                print(f"[Agent] {reply}\n")
                send_message(page, reply)

                if page.is_visible("#deal-banner"):
                    deal_reached = True
                    break

            final_price = page.inner_text("#current-price")
            deal_price = page.inner_text("#deal-price") if deal_reached else None
            browser.close()

        if deal_reached:
            print(f"Deal locked in! {deal_price}")
        else:
            print(f"Ran out of turns. Best price reached: {final_price}/month")

    finally:
        steel.sessions.release(session.id)
        print("Session released.")


if __name__ == "__main__":
    main()
