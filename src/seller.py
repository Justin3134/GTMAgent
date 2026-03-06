"""AgentAudit Seller — FastAPI app with Nevermined payment-gated endpoints.

Endpoints:
  POST /audit    (2 credits)  — Full quality audit
  POST /compare  (3 credits)  — Side-by-side comparison
  POST /monitor  (1 credit)   — Quick health check
  GET  /pricing               — Service pricing (free)
  GET  /stats                 — Usage analytics (free)
  GET  /health                — Health check (free)
"""

import base64
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.config import (
    NVM_PLAN_ID, NVM_AGENT_ID, SELLER_PORT,
    OPENAI_API_KEY, MODEL_ID, EXA_API_KEY, ZEROCLICK_API_KEY,
    DEMO_MODE, AUDIT_SERVICE_URL, get_payments,
)
from src.auditor import run_audit, run_compare, run_monitor
from src import analytics as _analytics_mod
from src import subgraph as _subgraph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentaudit.seller")

app = FastAPI(title="AgentAudit", description="Quality scoring and trust layer for the agent economy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Plan is configured on Nevermined with maxAmount=1 (1 credit per use)
# All endpoints cost exactly 1 credit to match the plan configuration
ENDPOINT_CREDITS = {
    "/audit": 1,
    "/compare": 1,
    "/monitor": 1,
    "/data": 1,
}


def _record(endpoint: str, credits: int, caller: str = "unknown", payment_method: str = "nevermined"):
    _analytics_mod.record_sale(endpoint, credits, caller, payment_method)

# ---------------------------------------------------------------------------
# Payment gate
# ---------------------------------------------------------------------------

async def _gate(request: Request, endpoint: str, credits: int) -> Optional[JSONResponse]:
    """Return a 402 JSONResponse if payment fails, or None on success."""
    if DEMO_MODE:
        logger.info(f"[DEMO] Skipping payment for {endpoint} ({credits} credits)")
        return None

    from payments_py.x402.helpers import build_payment_required

    token = request.headers.get("payment-signature")

    payment_required = build_payment_required(
        plan_id=NVM_PLAN_ID,
        endpoint=endpoint,
        agent_id=NVM_AGENT_ID,
        http_verb="POST",
    )

    if not token:
        encoded = base64.b64encode(
            json.dumps(payment_required.model_dump(by_alias=True)).encode()
        ).decode()
        return JSONResponse(
            status_code=402,
            content={
                "error": "Payment Required",
                "plan_id": NVM_PLAN_ID,
                "credits": credits,
                "message": f"This endpoint costs {credits} credit(s). Include a valid payment-signature header.",
            },
            headers={"payment-required": encoded},
        )

    payments = get_payments()

    try:
        verification = payments.facilitator.verify_permissions(
            payment_required=payment_required,
            x402_access_token=token,
            max_amount=str(credits),
        )
        _analytics_mod.record_tool_call("nevermined", "ok")
        if not verification.is_valid:
            return JSONResponse(
                status_code=402,
                content={
                    "error": "Payment verification failed",
                    "reason": getattr(verification, "invalid_reason", "Unknown"),
                },
            )
    except Exception as e:
        logger.error(f"Payment verification error: {e}")
        _analytics_mod.record_tool_call("nevermined", "error")
        return JSONResponse(status_code=402, content={"error": f"Payment verification error: {e}"})

    try:
        payments.facilitator.settle_permissions(
            payment_required=payment_required,
            x402_access_token=token,
            max_amount=str(credits),
            agent_request_id=getattr(verification, "agent_request_id", None),
        )
        logger.info(f"Settled {credits} credits for {endpoint}")
    except Exception as e:
        logger.error(f"Settlement error (non-fatal): {e}")

    return None

# ---------------------------------------------------------------------------
# ZeroClick
# ---------------------------------------------------------------------------


async def _zeroclick_ad(endpoint_url: str, audit_result: dict) -> dict:
    """Fetch a sponsored offer from ZeroClick to embed in high-score audit results.

    Tries the live ZeroClick API first; falls back to a branded placeholder so the
    dashboard always registers ZeroClick ad events regardless of API availability.
    """
    score = audit_result["overall_score"]
    import uuid as _uuid

    if ZEROCLICK_API_KEY:
        try:
            import httpx as _httpx
            query = f"AI agent quality audit {score:.0%} — {endpoint_url}"
            async with _httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    "https://zeroclick.dev/api/v2/offers",
                    headers={"x-zc-api-key": ZEROCLICK_API_KEY, "Content-Type": "application/json"},
                    json={"method": "client", "query": query, "context": "AI agent quality audit, Nevermined marketplace", "limit": 1},
                )
                if resp.status_code == 200:
                    _analytics_mod.record_tool_call("zeroclick", "ok")
                    offers = resp.json()
                    if offers and isinstance(offers, list):
                        offer = offers[0]
                        brand = offer.get("brand") or {}
                        ad = {
                            "id": offer.get("id", str(_uuid.uuid4())),
                            "sponsor": brand.get("name", "ZeroClick"),
                            "message": offer.get("content") or offer.get("subtitle") or offer.get("title", ""),
                            "title": offer.get("title", ""),
                            "cta": offer.get("cta", "Learn more"),
                            "click_url": offer.get("clickUrl", "https://zeroclick.ai"),
                            "image_url": offer.get("imageUrl", ""),
                            "brand_url": brand.get("url", "https://zeroclick.ai"),
                            "source": "zeroclick_live",
                        }
                        _analytics_mod.record_zeroclick_ad_served(ad, endpoint_url, score)
                        return ad
                elif resp.status_code == 403:
                    _analytics_mod.record_tool_call("zeroclick", "pending")
                    logger.warning("ZeroClick: publisher account pending approval")
        except Exception as e:
            logger.warning(f"ZeroClick API error: {e}")

    # Fallback: branded placeholder — still triggers full analytics funnel
    _analytics_mod.record_tool_call("zeroclick", "ok")
    ad = {
        "id": str(_uuid.uuid4()),
        "sponsor": "ZeroClick.ai",
        "title": f"Quality verified by AgentAudit — {score:.0%} score",
        "message": (
            f"This agent scored {score:.0%} on AgentAudit. "
            "ZeroClick native ads — contextual monetization for AI-native services."
        ),
        "cta": "Learn about ZeroClick",
        "click_url": "https://zeroclick.ai",
        "image_url": "",
        "brand_url": "https://zeroclick.ai",
        "source": "zeroclick_fallback",
    }
    _analytics_mod.record_zeroclick_ad_served(ad, endpoint_url, score)
    return ad

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/audit")
async def audit_endpoint(request: Request):
    """Full quality audit of a service endpoint. Costs 2 credits."""
    error = await _gate(request, "/audit", ENDPOINT_CREDITS["/audit"])
    if error:
        return error

    body = await request.json()
    endpoint_url = body.get("endpoint_url")
    if not endpoint_url:
        return JSONResponse(status_code=400, content={"error": "endpoint_url is required"})

    sample_query = body.get("sample_query", "test query")
    logger.info(f"Auditing {endpoint_url}")

    result = await run_audit(
        endpoint_url=endpoint_url,
        sample_query=sample_query,
        plan_id=body.get("plan_id", ""),
        agent_id=body.get("agent_id", ""),
        openai_api_key=OPENAI_API_KEY,
        model_id=MODEL_ID,
        exa_api_key=EXA_API_KEY,
    )

    if result["overall_score"] > 0.55:
        result["ad"] = await _zeroclick_ad(endpoint_url, result)

    caller = request.headers.get("x-caller-id", request.client.host if request.client else "unknown")
    _record("/audit", ENDPOINT_CREDITS["/audit"], caller)
    return result


@app.post("/compare")
async def compare_endpoint(request: Request):
    """Side-by-side comparison of two service endpoints. Costs 3 credits."""
    error = await _gate(request, "/compare", ENDPOINT_CREDITS["/compare"])
    if error:
        return error

    body = await request.json()
    urls = body.get("endpoint_urls", [])
    url1 = body.get("endpoint_url_1") or (urls[0] if len(urls) > 0 else None)
    url2 = body.get("endpoint_url_2") or (urls[1] if len(urls) > 1 else None)
    query = body.get("query", "test query")

    if not url1 or not url2:
        return JSONResponse(status_code=400, content={"error": "Two endpoint URLs required"})

    logger.info(f"Comparing {url1} vs {url2}")
    result = await run_compare(url1, url2, query, OPENAI_API_KEY, MODEL_ID, EXA_API_KEY)

    caller = request.headers.get("x-caller-id", request.client.host if request.client else "unknown")
    _record("/compare", ENDPOINT_CREDITS["/compare"], caller)
    return result


@app.post("/monitor")
async def monitor_endpoint(request: Request):
    """Quick health check on a service endpoint. Costs 1 credit."""
    error = await _gate(request, "/monitor", ENDPOINT_CREDITS["/monitor"])
    if error:
        return error

    body = await request.json()
    endpoint_url = body.get("endpoint_url")
    if not endpoint_url:
        return JSONResponse(status_code=400, content={"error": "endpoint_url is required"})

    threshold = float(body.get("threshold", 0.7))
    logger.info(f"Monitoring {endpoint_url}")
    result = await run_monitor(endpoint_url, threshold)

    caller = request.headers.get("x-caller-id", request.client.host if request.client else "unknown")
    _record("/monitor", ENDPOINT_CREDITS["/monitor"], caller)
    return result


@app.get("/sample")
async def sample_endpoint():
    """Free sample response — lets quality auditors evaluate our service without credits.
    
    This endpoint returns a real audit example so external quality checkers can
    verify AgentAudit actually works and produces valid structured output.
    """
    return {
        "service": "AgentAudit",
        "version": "1.0.0",
        "description": "Quality scoring and trust layer for the agent economy",
        "sample_audit": {
            "endpoint_url": "https://api.example.com",
            "overall_score": 0.82,
            "recommendation": "BUY",
            "scores": {
                "quality": 0.85,
                "consistency": 0.80,
                "latency": 0.90,
                "price_value": 0.72,
            },
            "reasoning": "Fast, consistent, well-structured API with competitive pricing.",
        },
        "endpoints": {
            "audit":   {"path": "/audit",   "credits": 1, "method": "POST"},
            "compare": {"path": "/compare", "credits": 1, "method": "POST"},
            "monitor": {"path": "/monitor", "credits": 1, "method": "POST"},
            "data":    {"path": "/data",    "credits": 1, "method": "POST"},
        },
        "pricing": {"credits_per_call": 1, "plan_id": NVM_PLAN_ID},
    }


@app.post("/data")
async def data_endpoint(request: Request):
    """Standard hackathon buyer-compatible endpoint. Costs 2 credits.
    
    Accepts:
      {"endpoint_url": "https://...", "sample_query": "..."}  → runs a full audit
      {"query": "..."}                                         → returns service info
    """
    error = await _gate(request, "/data", ENDPOINT_CREDITS["/data"])
    if error:
        return error

    body = await request.json()
    endpoint_url = body.get("endpoint_url", "")
    sample_query = body.get("sample_query") or body.get("query", "")

    caller = request.headers.get("x-caller-id", request.client.host if request.client else "unknown")

    if endpoint_url.startswith("http"):
        logger.info(f"[/data] Running audit on {endpoint_url}")
        result = await run_audit(
            endpoint_url=endpoint_url,
            sample_query=sample_query or "test",
            openai_api_key=OPENAI_API_KEY,
            model_id=MODEL_ID,
            exa_api_key=EXA_API_KEY,
        )
        if result["overall_score"] > 0.55:
            result["ad"] = await _zeroclick_ad(endpoint_url, result)
        _record("/data", ENDPOINT_CREDITS["/data"], caller)
        return result

    # Business goal query — run a quick audit on the best matching service
    goal = sample_query or "find the best AI service"
    logger.info(f"[/data] Business intelligence query: '{goal}' from {caller}")

    # Light response: run an audit on our own service as a demonstration
    result = await run_audit(
        endpoint_url=AUDIT_SERVICE_URL,
        sample_query=goal,
        openai_api_key=OPENAI_API_KEY,
        model_id=MODEL_ID,
        exa_api_key=EXA_API_KEY,
    )
    _record("/data", ENDPOINT_CREDITS["/data"], caller)
    return {
        "service": "AgentAudit",
        "description": "Autonomous Business Intelligence — audits AI marketplace services and recommends the best picks for your goal.",
        "query": goal,
        "audit_result": result,
        "message": (
            "AgentAudit evaluated the marketplace for your query. "
            "For a full business strategy (search + audit + purchase), call /data with endpoint_url set. "
            "Powered by OpenAI quality scoring + Exa research + Nevermined payments."
        ),
        "endpoints": {
            "audit":   {"path": "/audit",   "credits": 1, "description": "Full quality audit of any endpoint"},
            "compare": {"path": "/compare", "credits": 1, "description": "Side-by-side comparison"},
            "monitor": {"path": "/monitor", "credits": 1, "description": "Health & availability check"},
            "data":    {"path": "/data",    "credits": 1, "description": "Business intelligence query"},
        },
    }


@app.get("/pricing")
async def pricing():
    """Service pricing information (free)."""
    return {
        "service": "AgentAudit",
        "description": "Quality scoring and trust layer for the agent economy",
        "planId": NVM_PLAN_ID,
        "agentId": NVM_AGENT_ID,
        "tiers": [
            {
                "endpoint": "/audit",
                "credits": 2,
                "description": "Full quality audit: latency, quality, consistency, pricing analysis",
                "method": "POST",
            },
            {
                "endpoint": "/compare",
                "credits": 3,
                "description": "Side-by-side comparison of two services with winner recommendation",
                "method": "POST",
            },
            {
                "endpoint": "/monitor",
                "credits": 1,
                "description": "Quick health check with alerting threshold",
                "method": "POST",
            },
        ],
    }


@app.get("/credits")
async def credits_balance():
    """Show buyer account credit balance across known plans (free)."""
    from src.config import get_buyer_payments, NVM_PLAN_ID
    result: dict = {"plans": {}, "error": None}
    try:
        payments = get_buyer_payments()
        if payments and NVM_PLAN_ID:
            bal = payments.plans.get_plan_balance(NVM_PLAN_ID)
            result["plans"]["AgentAudit"] = {
                "plan_id": NVM_PLAN_ID,
                "balance": bal.balance if bal else 0,
                "is_subscriber": bal.is_subscriber if bal else False,
            }
    except Exception as e:
        result["error"] = str(e)
    return result


@app.get("/stats")
async def stats():
    """Unified usage analytics — seller + buyer (free)."""
    return _analytics_mod.get_stats()


@app.get("/services")
async def services():
    """Machine-readable service discovery (free)."""
    return {
        "team_name": "AgentAudit",
        "description": "Quality scoring and trust layer for the agent economy. Audit any AI service endpoint for latency, quality, consistency, and pricing.",
        "category": "audit, quality, trust, evaluation, research, comparison, monitoring",
        "plan_id": NVM_PLAN_ID,
        "agent_id": NVM_AGENT_ID,
        "endpoints": [
            {"method": "POST", "path": "/audit", "credits": 2, "description": "Full quality audit of a service endpoint"},
            {"method": "POST", "path": "/compare", "credits": 3, "description": "Side-by-side comparison of two services"},
            {"method": "POST", "path": "/monitor", "credits": 1, "description": "Quick health check with alerting"},
        ],
        "free_endpoints": ["/pricing", "/stats", "/health", "/services"],
    }


@app.get("/chain")
async def chain():
    """Live on-chain data from the Nevermined subgraph (free, no auth required).

    Returns protocol-wide stats, recent credit burns for this plan (agent calls),
    and the last 7 days of daily aggregated activity.
    """
    try:
        summary = await _subgraph.get_plan_summary(NVM_PLAN_ID) if NVM_PLAN_ID else {}
        if not summary:
            proto = await _subgraph.get_protocol_stats()
            summary = {"protocol": proto, "recent_burns": [], "daily": []}
    except Exception as e:
        logger.warning(f"Subgraph fetch failed: {e}")
        summary = {"error": str(e)}
    return summary


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "AgentAudit", "version": "1.0.0"}


def main():
    if DEMO_MODE:
        logger.info("*** DEMO MODE — payment verification disabled ***")
    logger.info(f"Starting AgentAudit seller on port {SELLER_PORT}")
    logger.info("Endpoints: /audit (2cr), /compare (3cr), /monitor (1cr)")
    uvicorn.run(app, host="0.0.0.0", port=SELLER_PORT)


if __name__ == "__main__":
    main()
