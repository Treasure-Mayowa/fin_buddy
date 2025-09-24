from __future__ import annotations
from .core.rate_limiter import  RateLimiter
from .core.session_manager import SessionManager

import os
import logging
import datetime
from typing import Any, Optional

import requests
from dotenv import load_dotenv
from app.advice import get_advice
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse, Response

import redis
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST


load_dotenv()

# -------------------------
# CONFIG & GLOBALS
# -------------------------
META_TOKEN = os.getenv("META_TOKEN", "")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
BASE_URL = os.getenv("BASE_URL", "https://graph.facebook.com/v22.0")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SCHEDULE_PROMPT = "Click the attahced link to schedule a consultation with one of our experts.\n\nhttps://calendar.app.google/WmSWjb33sXf8taLe6"

# Check for required environment variables
required_vars = ["META_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "VERIFY_TOKEN"]  
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    message: str = f"Missing required environment variables: {', '.join(missing_vars)}"
    logging.error(message)
    raise ValueError(message)

HEADERS = {
    "Authorization": f"Bearer {META_TOKEN}",
    "Content-Type": "application/json",
}

# Initialise redis connection
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Test Redis connection
try:
    redis_client.ping()
    logging.info("Redis connection established")
except redis.ConnectionError:
    logging.error("Failed to connect to Redis")
    raise

# -------------------------
# PROMETHEUS METRICS
# -------------------------
# Counters
message_counter = Counter('whatsapp_messages_total', 'Total messages processed', ['message_type', 'status'])
rate_limit_counter = Counter('whatsapp_rate_limits_total', 'Total rate limit hits', ['user'])
api_calls_counter = Counter('whatsapp_api_calls_total', 'Total WhatsApp API calls', ['endpoint', 'status'])

# Histograms
message_processing_time = Histogram('whatsapp_message_processing_seconds', 'Time spent processing messages')
api_response_time = Histogram('whatsapp_api_response_seconds', 'WhatsApp API response time')

# Gauges
active_sessions = Gauge('whatsapp_active_sessions', 'Number of active user sessions')
redis_connections = Gauge('redis_connections_active', 'Active Redis connections')

app = FastAPI(title="FinBuddy")

rate_limiter = RateLimiter(redis_client)
session_manager = SessionManager(redis_client, active_sessions=active_sessions)


# -------------------------
# WhatsApp Send Helpers
# -------------------------

def wa_url(path: str) -> str:
    return f"{BASE_URL}/{path}"

def make_api_request(method: str, url: str, **kwargs) -> requests.Response:
    with api_response_time.time():
        try:
            response = requests.request(method, url, **kwargs)
            api_calls_counter.labels(endpoint=url.split('/')[-2], status=response.status_code).inc()
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            api_calls_counter.labels(endpoint=url.split('/')[-2], status='error').inc()
            logging.error(f"API request failed: {e}")
            raise


def send_text(to: str, text: str) -> requests.Response:
    url = wa_url(f"{PHONE_NUMBER_ID}/messages")
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    resp = make_api_request("post", url, headers=HEADERS, json=payload, timeout=20)
    return resp


GREETINGS = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "start"}


def normalize_message(text: str) -> str:
    if not text:
        return ""
    text = text.strip().lower()
    text = ' '.join(text.split())
    return text[:500]

@message_processing_time
async def handle_message(from_id: str, text: Optional[str]) -> Any:
    try:
        # Log message for monitoring
        session_manager.add_message(from_id, {
            "from": from_id,
            "text": text,
            "type": "incoming"
        })
        
        session = session_manager.get_session(from_id)
        msg = normalize_message(text or "")
        
        
        # Handle text messages
        message_counter.labels(message_type='text', status='processed').inc()

        if msg in GREETINGS:
            session_manager.set_stage(from_id, "active")
            send_text(
            from_id,
            "👋 Welcome! I am FinBuddy! I will get to know you and share *personalised educational info* about finance and investment.\n\n"
            "Ask me what you want to know about finance and investments"
            "Or type 'schedule' to book a consultation with our experts."         
            )
            return

        if msg == "schedule":
            send_text(
            from_id,
            SCHEDULE_PROMPT,
            )
            return 
    
        # Fallback/help
        schedule_ask = "\n\n\nType and send \"schedule\" if you want to book a consultation with one of our experts"
        advice = get_advice(msg)
        send_text(
            from_id,
            advice + schedule_ask,
        )

        # Log outgoing message
        session_manager.add_message(from_id, {
            "to": from_id,
            "text": advice,
            "type": "outgoing"
        })
        return
    except Exception as e:
        logging.error(f"Error handling message from {from_id}: {e}")
        message_counter.labels(message_type='error', status='failed').inc()
        # Send fallback message
        send_text(from_id, 
            "Sorry, I encountered an issue processing your message. Please try again"
        )
        

async def check_rate_limit(request: Request):
    # Extract user ID from request 
    user_id = request.headers.get("X-User-ID", "anonymous")
    
    if not rate_limiter.is_allowed(user_id):
        raise HTTPException(
            status_code=429, 
            detail="Rate limit exceeded. Please try again later."
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


@app.post("/webhook")
async def inbound(request: Request):
    try:
        data = await request.json()
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

                    if msg_type == "text":
                        text = message.get("text", {}).get("body")
                    elif msg_type == "image":
                        text = "image"
                    else:
                        text = "unknown"
                    print("\nbefore handle")
                    await handle_message(from_id, text)
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logging.exception("webhook error: %s", e)
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)

       
# -------------------------
# MONITORING ENDPOINTS
# -------------------------

# Monitoring endpoint
@app.get("/metrics")
async def get_metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health_check():
    try:
        # Check Redis connection
        redis_client.ping()
        redis_status = "healthy"
    except Exception:
        redis_status = "unhealthy"
    
    return JSONResponse({
        "status": "healthy" if redis_status == "healthy" else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "redis": redis_status,
        }
    })

# Basic stats endpoint
@app.get("/stats")
async def get_stats():
    try:
        session_keys = redis_client.keys("session:*")
        rate_limit_keys = redis_client.keys("rate_limit:*")
        
        return JSONResponse({
            "active_sessions": len(session_keys),
            "rate_limited_users": len(rate_limit_keys),
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        logging.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Unable to retrieve stats")

# -------------------------
# LOGGING CONFIGURATION
# -------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('finbuddy.log')
    ]
)