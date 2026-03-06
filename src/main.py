"""AgentAudit — combined app: seller + buyer + dashboard in one process.

Run locally:  poetry run app
Deploy:       Render (see render.yaml)

All routes served at the same URL:
  GET  /              → Dashboard (chat UI + stats)
  POST /audit         → Sell: full quality audit (2 credits)
  POST /compare       → Sell: side-by-side comparison (3 credits)
  POST /monitor       → Sell: health check (1 credit)
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
from fastapi import FastAPI, Request
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
    audit_endpoint,
    compare_endpoint,
    monitor_endpoint,
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
logger = logging.getLogger("agentaudit.main")


# ---------------------------------------------------------------------------
# Lifespan — start buyer loop as background task
# ---------------------------------------------------------------------------

async def _register_with_discovery():
    """Register AgentAudit as a seller in the Nevermined hackathon Discovery API."""
    from src.config import NVM_API_KEY, NVM_PLAN_ID, NVM_AGENT_ID, AUDIT_SERVICE_URL
    if not NVM_API_KEY or not AUDIT_SERVICE_URL or "localhost" in AUDIT_SERVICE_URL:
        logger.info("Skipping discovery registration (localhost or missing key)")
        return
    try:
        import httpx
        payload = {
            "side": "sell",
            "name": "AgentAudit",
            "teamName": "AgentAudit",
            "category": "AI/ML",
            "description": (
                "Autonomous Business Intelligence Agent. Describe a business goal — the agent searches "
                "the marketplace, audits candidates with OpenAI + Exa, purchases the best services via "
                "Nevermined, and returns a synthesized strategy. Also sells standalone: audit, compare, monitor."
            ),
            "keywords": ["audit", "quality", "business intelligence", "orchestration", "evaluation", "comparison", "monitoring", "AI", "strategy", "research"],
            "endpointUrl": AUDIT_SERVICE_URL,
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
                logger.info(f"Registered with Nevermined Discovery API: {resp.status_code}")
            else:
                logger.warning(f"Discovery registration returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"Discovery registration error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(_register_with_discovery())
    task = asyncio.create_task(_buyer_loop())
    logger.info(f"AgentAudit running on port {PORT}")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="AgentAudit", description="Quality scoring and trust layer for the agent economy", lifespan=lifespan)

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

# Seller routes
app.add_api_route("/audit",   audit_endpoint,   methods=["POST"])
app.add_api_route("/compare", compare_endpoint, methods=["POST"])
app.add_api_route("/monitor", monitor_endpoint, methods=["POST"])
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
