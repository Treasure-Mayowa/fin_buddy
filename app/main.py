"""
WhatsApp Financial Guidance Bot — FastAPI (Python 3.10+)

⚠️ Important:
- This bot provides GENERAL EDUCATIONAL INFORMATION ONLY. It must NOT give personalized financial advice.
- You are responsible for complying with Meta/WhatsApp policies and your local financial regulations.
- Fill in environment variables before running (see .env section below).

Quick start
-----------
1) Create a WhatsApp Business Account and enable the WhatsApp Cloud API in Meta for Developers.
2) Get: WHATSAPP_PHONE_NUMBER_ID, a permanent META_TOKEN (System User token), and set a VERIFY_TOKEN.
3) Set a webhook URL in your app (e.g., https://yourdomain.com/webhook). During verification, Meta will call GET /webhook.
4) Run: `uvicorn main:app --host 0.0.0.0 --port 8000` (or deploy on Render/Fly/Heroku etc.).
5) In the WhatsApp webhook settings, subscribe to messages events.

.env (example)
---------------
META_TOKEN=EAAT... (long-lived token)
WHATSAPP_PHONE_NUMBER_ID=123456789012345
VERIFY_TOKEN=super-secret-verify-token
BASE_URL=https://graph.facebook.com/v20.0

Notes
-----
- This sample uses in-memory state for conversations. For production, use Redis (recommended), which fits your stack.
- The bot supports: greeting, risk-profiling flow, and pointing users to *educational* investment categories.
- It also demonstrates interactive messages (buttons & list) supported by WhatsApp Cloud API.
"""

from __future__ import annotations

import os
import time
import logging
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv
from app.advice import get_advice
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse

load_dotenv()

# -------------------------
# CONFIG & GLOBALS
# -------------------------
META_TOKEN = os.getenv("META_TOKEN", "")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
BASE_URL = os.getenv("BASE_URL", "https://graph.facebook.com/v22.0")

if not META_TOKEN:
    logging.warning("META_TOKEN is not set. Remember to configure environment variables.")

HEADERS = {
    "Authorization": f"Bearer {META_TOKEN}",
    "Content-Type": "application/json",
}

app = FastAPI(title="FinBuddy")

# In-memory conversation state: { user_id: {"stage": str, "risk": Optional[str]} }
STATE: Dict[str, Dict[str, Any]] = {}

DISCLAIMER = (
    "I am not a financial advisor. I provide general, educational information only. "
    "Nothing here is investment, legal, or tax advice. Always do your own research and, if needed, "
    "consult a licensed professional before making decisions."
)

# -------------------------
# WhatsApp Send Helpers
# -------------------------

def wa_url(path: str) -> str:
    return f"{BASE_URL}/{path}"


def send_text(to: str, text: str) -> requests.Response:
    url = wa_url(f"{PHONE_NUMBER_ID}/messages")
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    print(url, payload)
    resp = requests.post(url, headers=HEADERS, json=payload, timeout=20)
    print(resp.json())
    return resp


def send_buttons(to: str, body: str, buttons: list[dict]) -> requests.Response:
    """buttons: list of up to 3: {"type": "reply", "reply": {"id": "ID", "title": "Title"}}"""
    url = wa_url(f"{PHONE_NUMBER_ID}/messages")
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {"buttons": buttons},
        },
    }
    return requests.post(url, headers=HEADERS, json=payload, timeout=20)


def send_list(to: str, body: str, sections: list[dict]) -> requests.Response:
    """sections: [ {"title": "Title", "rows": [{"id": "row-id", "title": "Row title", "description": "desc"}, ...]} ]"""
    url = wa_url(f"{PHONE_NUMBER_ID}/messages")
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": "Choose",
                "sections": sections,
            },
        },
    }
    res = requests.post(url, headers=HEADERS, json=payload, timeout=20)
    print(res.json())
    return res


# -------------------------
# Domain: Educational Opportunity Catalog (Mock)
# -------------------------

OPPORTUNITIES = {
    "conservative": [
        {
            "id": "T-BILLS",
            "title": "Treasury Bills (Short-term government debt)",
            "desc": "Typically lower risk; earns fixed interest for a set term.",
        },
        {
            "id": "MMF",
            "title": "Money Market Funds",
            "desc": "Targets capital preservation and liquidity with modest returns.",
        },
        {
            "id": "GOV_BOND_FUND",
            "title": "Government Bond Index Fund",
            "desc": "Diversified exposure to government bonds across durations.",
        },
    ],
    "balanced": [
        {
            "id": "BROAD_ETF",
            "title": "Broad-Market Equity Index ETF",
            "desc": "Tracks a large basket of stocks; diversified equity exposure.",
        },
        {
            "id": "BALANCED_FUND",
            "title": "Balanced Index Fund (60/40)",
            "desc": "Mixed stocks/bonds for risk-return balance.",
        },
        {
            "id": "DIVIDEND_ETF",
            "title": "Dividend-Focused Equity ETF",
            "desc": "Companies with a record of paying dividends.",
        },
    ],
    "aggressive": [
        {
            "id": "SMALL_CAP",
            "title": "Small-Cap Equity ETF",
            "desc": "Higher growth potential with higher volatility.",
        },
        {
            "id": "EMERGING_MARKETS",
            "title": "Emerging Markets Equity ETF",
            "desc": "Diversified exposure to developing economies.",
        },
        {
            "id": "THEMATIC_TECH",
            "title": "Thematic Tech ETF (Sector-focused)",
            "desc": "Concentrated exposure to technology themes; high risk/return.",
        },
    ],
}


def opportunities_sections(risk: str) -> list[dict]:
    groups = OPPORTUNITIES.get(risk, [])
    if not groups:
        return []
    rows = [
        {"id": item["id"], "title": item["title"], "description": item["desc"]}
        for item in groups
    ]
    return [{"title": "Educational Categories", "rows": rows}]


# -------------------------
# Intent & Flow Logic (Rule-Based Minimal NLP)
# -------------------------

GREETINGS = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"}


def normalize(text: str) -> str:
    return (text or "").strip().lower()


def get_user_state(uid: str) -> Dict[str, Any]:
    st = STATE.get(uid)
    if not st:
        st = {"stage": "idle", "risk": None, "last": time.time()}
        STATE[uid] = st
    return st


def set_stage(uid: str, stage: str):
    STATE[uid]["stage"] = stage
    STATE[uid]["last"] = time.time()


async def handle_message(from_id: str, text: Optional[str], interactive: Optional[dict] = None):
    state = get_user_state(from_id)

    # Handle interactive replies first
    if interactive:
        itype = interactive.get("type")
        if itype == "button_reply":
            btn = interactive.get("button_reply", {})
            reply_id = btn.get("id")
            if reply_id in {"RISK_LOW", "RISK_MED", "RISK_HIGH"}:
                risk = {"RISK_LOW": "conservative", "RISK_MED": "balanced", "RISK_HIGH": "aggressive"}[reply_id]
                state["risk"] = risk
                set_stage(from_id, "show_opportunities")
                send_text(from_id, f"Great. Logged your risk preference as *{risk}*.")
                send_list(
                    from_id,
                    "Here are educational investment *categories* you can research further. Select one to learn the basics:",
                    opportunities_sections(risk),
                )
                return

        if itype == "list_reply":
            row = interactive.get("list_reply", {})
            row_id = row.get("id")
            # Find the chosen item description
            chosen: Optional[Dict[str, str]] = None
            for items in OPPORTUNITIES.values():
                for it in items:
                    if it["id"] == row_id:
                        chosen = it
                        break
            if chosen:
                send_text(
                    from_id,
                    (
                        f"*{chosen['title']}*\n\n"
                        f"What it is: {chosen['desc']}\n\n"
                        "Next steps (educational):\n"
                        "• Read official fund/issuer docs and fee schedules.\n"
                        "• Compare risks, costs, and liquidity.\n"
                        "• Consider diversification and time horizon.\n\n"
                        f""
                    ),
                )
                return

    msg = normalize(text or "")
    print("in handle", msg)

    # Start / greeting
    if msg in {"start", "menu", *GREETINGS}:
        print("in handle - start / greeting")
        set_stage(from_id, "risk_start")
        send_text(
            from_id,
            (
                "👋 Welcome! I will get to know you and share *personalised educational info* about finance and investment.\n\n"
                "Ask me what you want to know about finance and investments"
            ),
        )
        # send_buttons(
        #     from_id,
        #     "Choose one:",
        #     [
        #         {"type": "reply", "reply": {"id": "RISK_LOW", "title": "Conservative"}},
        #         {"type": "reply", "reply": {"id": "RISK_MED", "title": "Balanced"}},
        #         {"type": "reply", "reply": {"id": "RISK_HIGH", "title": "Aggressive"}},
        #     ],
        # )
        return

    # User directly types risk level
    if msg in {"conservative", "balanced", "aggressive"}:
        STATE[from_id]["risk"] = msg
        set_stage(from_id, "show_opportunities")
        send_text(from_id, f"Got it — *{msg}*.")
        send_list(
            from_id,
            "Here are educational categories to explore:",
            opportunities_sections(msg),
        )
        return

    # Fallback/help
    send_text(
        from_id,
        get_advice(msg),
    )


# -------------------------
# Webhook Endpoints
# -------------------------

@app.get("/webhook", response_class=PlainTextResponse)
async def verify(request: Request):
    """Meta will call this for verification with query params: hub.mode, hub.challenge, hub.verify_token."""
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    challenge = params.get("hub.challenge")
    token = params.get("hub.verify_token")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return PlainTextResponse(content=challenge or "", status_code=200)
    raise HTTPException(status_code=403, detail="Verification failed")


# @app.post("/webhook")
# async def receive_message(request: Request):
#     data = await request.json()
#     print("Incoming message:", data)
#     return {"status": "received"}

@app.post("/webhook")
async def inbound(request: Request):
    try:
        data = await request.json()
        print(data)
        # Basic structure: entry -> changes -> value -> messages
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                if not messages:
                    continue
                for message in messages:
                    from_id = message.get("from")  # user's phone in international format
                    msg_type = message.get("type")

                    text = None
                    interactive = None

                    if msg_type == "text":
                        text = message.get("text", {}).get("body")
                    elif msg_type == "interactive":
                        interactive = message.get("interactive")
                    elif msg_type == "button":
                        # Older formats; normalize to interactive
                        interactive = {"type": "button_reply", "button_reply": message.get("button")}
                    elif msg_type == "image":
                        text = "image"
                    else:
                        text = "unknown"
                    print("\nbefore handle")
                    await handle_message(from_id, text, interactive)
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logging.exception("webhook error: %s", e)
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)


@app.get("/health", response_class=PlainTextResponse)
async def health():
    return "ok"


# -------------------------
# Optional: Send a proactive message (for testing with a sandbox number)
# -------------------------
@app.post("/test/send")
async def test_send(payload: Dict[str, Any]):
    """POST {"to": "+2348...", "text": "hello"} to test direct send."""
    to = payload.get("to")
    text = payload.get("text", "Hello from the bot!")
    if not to:
        raise HTTPException(400, detail="Provide 'to'")
    r = send_text(to, text)
    return {"status_code": r.status_code, "response": r.json() if r.content else {}}


# -------------------------
# Compliance & Safety Tips (readme-style)
# -------------------------
"""
Production hardening checklist:
- Substitute in-memory STATE with Redis. Store: user_id -> {stage, risk, timestamps} with TTL.
- Add rate limiting and message validation.
- Expand NLP with a library or service; keep advice general and educational.
- Log and monitor outbound API errors from Meta; implement retries with backoff.
- Keep your META_TOKEN secure; rotate regularly. Use app secret proof if desired.
- Ensure opt-in/opt-out and privacy policy links are accessible to users.
- If you link to third-party opportunities, only share official issuer pages / regulators; avoid endorsements.
- Consider localization (currencies, examples) and accessibility.
"""
