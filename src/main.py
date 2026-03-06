"""GTMAgent — combined app: seller + buyer + dashboard in one process.

Run locally:  poetry run app
Deploy:       Render (see render.yaml)

All routes served at the same URL:
  GET  /              → Dashboard (chat UI + stats)
  POST /data          → Sell: Autonomous Business Intelligence (1 credit)
                        — describe idea → marketplace + Apify + audit + buy + strategy
                        — or provide endpoint_url for direct audit
  GET  /pricing       → Sell: pricing info (free)
  GET  /stats         → Sell: revenue analytics (free)
  GET  /services      → Sell: machine-readable service discovery (free)
  GET  /health        → Health check
  POST /api/chat      → Buy: interactive chat agent (SSE)
  GET  /api/status    → Buy: buyer status + budget
  GET  /api/decisions → Buy: decision log
  GET  /api/audits    → Buy: audit history
  POST /api/trigger   → Buy: manual audit cycle
"""

import asyncio
import logging
import os

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

# Determine port before any config imports so AUDIT_SERVICE_URL points to self
PORT = int(os.environ.get("PORT", 3000))
# Only set AUDIT_SERVICE_URL if not already provided (Render sets it to the public URL)
if not os.environ.get("AUDIT_SERVICE_URL"):
    os.environ["AUDIT_SERVICE_URL"] = f"http://localhost:{PORT}"

# ---------------------------------------------------------------------------
# Import route handlers from existing modules
# ---------------------------------------------------------------------------

from src.seller import (  # noqa: E402
    data_endpoint,
    sample_endpoint,
    pricing,
    stats,
    services,
    credits_balance,
    chain,
    health as seller_health,
)
from src.buyer import (  # noqa: E402
    api_status,
    api_audits,
    api_decisions,
    api_budget,
    api_trigger,
    api_chat,
    _buyer_loop,
)
from src.web import DASHBOARD_HTML  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gtmagent.main")


# ---------------------------------------------------------------------------
# Lifespan — start buyer loop as background task
# ---------------------------------------------------------------------------

RENDER_URL = "https://gtmagent.onrender.com"


async def _register_with_discovery():
    """Register GTMAgent as a seller in the Nevermined hackathon Discovery API.

    Always registers with the public Render URL so other teams can discover and purchase.
    """
    from src.config import NVM_API_KEY, NVM_PLAN_ID, NVM_AGENT_ID
    if not NVM_API_KEY:
        logger.info("Skipping discovery registration (no NVM_API_KEY)")
        return
    try:
        import httpx
        payload = {
            "side": "sell",
            "name": "GTMAgent",
            "teamName": "GTMAgent",
            "category": "AI/ML",
            "description": (
                "Autonomous Business Intelligence Agent. POST /data with a business idea "
                "(e.g. {\"query\": \"build a fintech AI assistant\"}) and the agent searches "
                "the Nevermined marketplace + Apify, audits candidates with OpenAI + Exa, "
                "purchases the best services via x402, and returns a full business strategy."
            ),
            "keywords": ["audit", "quality", "business intelligence", "orchestration", "evaluation",
                         "comparison", "monitoring", "AI", "strategy", "research", "buyer", "seller"],
            "endpointUrl": RENDER_URL,
            "planIds": [NVM_PLAN_ID] if NVM_PLAN_ID else [],
            "nvmAgentId": NVM_AGENT_ID,
            "pricing": {"perRequest": 1, "meteringUnit": "credits"},
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://nevermined.ai/hackathon/register/api/register",
                headers={"x-nvm-api-key": NVM_API_KEY, "Content-Type": "application/json"},
                json=payload,
            )
            if resp.status_code in (200, 201):
                logger.info(f"Registered with Nevermined Discovery: {RENDER_URL} → {resp.status_code}")
            else:
                logger.warning(f"Discovery registration returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"Discovery registration error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(_register_with_discovery())
    task = asyncio.create_task(_buyer_loop())
    logger.info(f"GTMAgent running on port {PORT}")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="GTMAgent", description="Autonomous Business Intelligence — describe your idea, we find, audit, buy, and deliver a strategy", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dashboard (root)
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML

# Seller routes — single paid endpoint
app.add_api_route("/data",    data_endpoint,    methods=["POST"])
app.add_api_route("/sample",  sample_endpoint,  methods=["GET"])
app.add_api_route("/pricing", pricing,          methods=["GET"])
app.add_api_route("/stats",    stats,           methods=["GET"])
app.add_api_route("/services", services,        methods=["GET"])
app.add_api_route("/credits",  credits_balance, methods=["GET"])
app.add_api_route("/chain",    chain,           methods=["GET"])
app.add_api_route("/health",   seller_health,   methods=["GET"])

# Buyer / chat routes
app.add_api_route("/api/status",    api_status,    methods=["GET"])
app.add_api_route("/api/audits",    api_audits,    methods=["GET"])
app.add_api_route("/api/decisions", api_decisions, methods=["GET"])
app.add_api_route("/api/budget",    api_budget,    methods=["GET"])
app.add_api_route("/api/trigger",   api_trigger,   methods=["POST"])
app.add_api_route("/api/run-now",   api_trigger,   methods=["POST"])
app.add_api_route("/api/chat",      api_chat,      methods=["POST"])


@app.get("/api/keys-status")
async def keys_status():
    """Which API keys are configured — used by the dashboard to show live tool readiness."""
    from src.config import OPENAI_API_KEY, EXA_API_KEY, ZEROCLICK_API_KEY, NVM_API_KEY, NVM_BUYER_API_KEY, MINDRA_API_KEY
    import os as _os
    APIFY_API_KEY = _os.environ.get("APIFY_API_KEY", "")
    return {
        "openai": bool(OPENAI_API_KEY),
        "exa": bool(EXA_API_KEY),
        "zeroclick": bool(ZEROCLICK_API_KEY),
        "nvm": bool(NVM_API_KEY or NVM_BUYER_API_KEY),
        "apify": bool(APIFY_API_KEY),
        "mindra": bool(MINDRA_API_KEY),
    }


@app.get("/api/zeroclick-ad")
async def zeroclick_gate_ad():
    """Fetch a ZeroClick ad for the chat ad-gate (every N messages)."""
    from src.chat import _attach_zeroclick_ad
    ad = await _attach_zeroclick_ad("chat-gate", 0.7)
    if ad:
        return ad
    return {
        "id": "",
        "sponsor": "ZeroClick.ai",
        "title": "ZeroClick — Native AI Ads",
        "message": "Contextual native ads for AI-native services. ZeroClick monetizes every agent interaction.",
        "cta": "Learn about ZeroClick",
        "click_url": "https://zeroclick.ai",
        "source": "zeroclick_gate_fallback",
    }


@app.post("/zeroclick/click")
async def zeroclick_click(offer_id: str = ""):
    """Track a ZeroClick ad click (fire-and-forget from frontend)."""
    if offer_id:
        from src import analytics as _analytics_mod
        _analytics_mod.record_tool_call("zeroclick", "ok")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
