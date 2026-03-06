"""GTMAgent Seller — FastAPI app with Nevermined payment-gated endpoint.

Primary endpoint:
  POST /data  (1 credit)  — Autonomous Business Intelligence
    Mode A: {"query": "build a fintech AI assistant"} → full pipeline
            (marketplace search + Apify + audit + buy + strategy)
    Mode B: {"endpoint_url": "https://..."} → direct quality audit

Free endpoints:
  GET  /pricing, /stats, /health, /services, /sample, /chain, /credits
"""

import asyncio
import base64
import json
import logging
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.config import (
    NVM_PLAN_ID, NVM_AGENT_ID, NVM_ACCEPTED_PLAN_IDS, SELLER_PORT,
    OPENAI_API_KEY, MODEL_ID, EXA_API_KEY, ZEROCLICK_API_KEY,
    DEMO_MODE, AUDIT_SERVICE_URL, get_payments,
)
from src.auditor import run_audit
from src import analytics as _analytics_mod
from src import subgraph as _subgraph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gtmagent.seller")

app = FastAPI(title="GTMAgent", description="Autonomous Business Intelligence — describe your idea, we find, audit, buy, and deliver a strategy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ENDPOINT_CREDITS = {
    "/data": 1,
}


def _record(endpoint: str, credits: int, caller: str = "unknown", payment_method: str = "nevermined"):
    _analytics_mod.record_sale(endpoint, credits, caller, payment_method)

# ---------------------------------------------------------------------------
# Payment gate
# ---------------------------------------------------------------------------

async def _gate(request: Request, endpoint: str, credits: int) -> Optional[JSONResponse]:
    """Return a 402 JSONResponse if payment fails, or None on success.

    Tries each plan in NVM_ACCEPTED_PLAN_IDS in order so that both the primary
    GTMAgent plan and the GTMAgentUSDC plan (and any future plans) are
    accepted without requiring buyers to use a specific plan.
    """
    if DEMO_MODE:
        logger.info(f"[DEMO] Skipping payment for {endpoint} ({credits} credits)")
        return None

    from payments_py.x402.helpers import build_payment_required

    token = request.headers.get("payment-signature")

    # Use primary plan for the 402 challenge header shown to unauthenticated callers
    primary_payment_required = build_payment_required(
        plan_id=NVM_PLAN_ID,
        endpoint=endpoint,
        agent_id=NVM_AGENT_ID,
        http_verb="POST",
    )

    if not token:
        encoded = base64.b64encode(
            json.dumps(primary_payment_required.model_dump(by_alias=True)).encode()
        ).decode()
        return JSONResponse(
            status_code=402,
            content={
                "error": "Payment Required",
                "plan_id": NVM_PLAN_ID,
                "accepted_plan_ids": NVM_ACCEPTED_PLAN_IDS,
                "credits": credits,
                "message": f"This endpoint costs {credits} credit(s). Include a valid payment-signature header.",
            },
            headers={"payment-required": encoded},
        )

    payments = get_payments()
    last_error: str = "No accepted plans configured"
    verified_payment_required = None
    verification = None

    for plan_id in NVM_ACCEPTED_PLAN_IDS:
        payment_required = build_payment_required(
            plan_id=plan_id,
            endpoint=endpoint,
            agent_id=NVM_AGENT_ID,
            http_verb="POST",
        )
        try:
            result = payments.facilitator.verify_permissions(
                payment_required=payment_required,
                x402_access_token=token,
                max_amount=str(credits),
            )
            if result.is_valid:
                verified_payment_required = payment_required
                verification = result
                logger.info(f"Payment verified via plan {plan_id} for {endpoint}")
                break
            else:
                last_error = getattr(result, "invalid_reason", "Invalid token")
                logger.debug(f"Plan {plan_id} rejected token: {last_error}")
        except Exception as e:
            last_error = str(e)
            logger.debug(f"Plan {plan_id} verification error: {e}")

    _analytics_mod.record_tool_call("nevermined", "ok" if verified_payment_required else "error")

    if not verified_payment_required:
        logger.error(f"Payment verification failed for all plans: {last_error}")
        return JSONResponse(
            status_code=402,
            content={"error": "Payment verification failed", "reason": last_error},
        )

    try:
        payments.facilitator.settle_permissions(
            payment_required=verified_payment_required,
            x402_access_token=token,
            max_amount=str(credits),
            agent_request_id=getattr(verification, "agent_request_id", None),
        )
        logger.info(f"Settled {credits} credits for {endpoint}")
    except Exception as e:
        logger.error(f"Settlement error (non-fatal): {e}")

    return None

# ---------------------------------------------------------------------------
# ZeroClick — always-live with retry + cache
# ---------------------------------------------------------------------------

_zc_last_live_ad: dict | None = None


async def _zeroclick_ad(endpoint_url: str, audit_result: dict) -> dict:
    """Fetch a sponsored offer from ZeroClick to embed in audit results.

    Retries up to 3 times with backoff, and caches the last successful live ad
    so transient API failures still serve a real ad.
    """
    global _zc_last_live_ad
    score = audit_result["overall_score"]
    import uuid as _uuid

    if ZEROCLICK_API_KEY:
        import httpx as _httpx
        query = f"AI agent quality audit {score:.0%} — {endpoint_url}"
        for attempt in range(3):
            try:
                async with _httpx.AsyncClient(timeout=15.0) as client:
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
                            _zc_last_live_ad = ad.copy()
                            _analytics_mod.record_zeroclick_ad_served(ad, endpoint_url, score)
                            return ad
                    elif resp.status_code == 403:
                        _analytics_mod.record_tool_call("zeroclick", "pending")
                        logger.warning("ZeroClick: publisher account pending approval — retrying")
            except Exception as e:
                logger.warning(f"ZeroClick API error (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                await asyncio.sleep(1.0 * (attempt + 1))

    if _zc_last_live_ad:
        ad = {**_zc_last_live_ad, "id": str(_uuid.uuid4())}
        _analytics_mod.record_tool_call("zeroclick", "ok")
        _analytics_mod.record_zeroclick_ad_served(ad, endpoint_url, score)
        logger.info("ZeroClick: served cached live ad after API failure")
        return ad

    logger.warning("ZeroClick: no live ad available and no cache — skipping ad")
    return {}

# ---------------------------------------------------------------------------
# Main endpoint
# ---------------------------------------------------------------------------

@app.get("/sample")
async def sample_endpoint():
    """Free sample — shows buyers what GTMAgent returns before they pay."""
    return {
        "service": "GTMAgent",
        "version": "2.0.0",
        "description": (
            "Autonomous Business Intelligence — describe your business idea and "
            "GTMAgent searches the Nevermined marketplace + Apify, audits candidates, "
            "purchases the best services, and delivers an actionable strategy."
        ),
        "how_to_use": {
            "endpoint": "POST /data",
            "credits": 1,
            "examples": [
                {"query": "I want to build a fintech AI assistant"},
                {"goal": "help me find the best AI tools for social media marketing"},
                {"query": "start a SaaS business for automated customer support"},
                {"endpoint_url": "https://some-service.com", "query": "test this service"},
            ],
        },
        "sample_result": {
            "goal": "build a social media marketing agency",
            "credits_spent": 2,
            "marketplace_services_found": 12,
            "apify_tools_found": 5,
            "candidates_audited": 3,
            "purchases": [
                {"team": "ContentAI", "score": 0.85, "purchased": True},
                {"team": "SocialBot", "score": 0.78, "purchased": True},
            ],
            "recommendation": "Purchased 2 services. ContentAI scored highest for content generation...",
        },
        "pricing": {"credits_per_call": 1, "plan_id": NVM_PLAN_ID},
    }


@app.post("/data")
async def data_endpoint(request: Request):
    """Autonomous Business Intelligence endpoint. Costs 1 credit.

    Two modes:
      {"query": "I want to build X"} → full pipeline: marketplace + Apify + audit + buy + strategy
      {"endpoint_url": "https://..."} → direct quality audit of that specific service
    """
    error = await _gate(request, "/data", ENDPOINT_CREDITS["/data"])
    if error:
        return error

    body = await request.json()
    endpoint_url = body.get("endpoint_url", "")
    query = body.get("query") or body.get("goal") or body.get("sample_query") or body.get("message", "")
    caller = request.headers.get("x-caller-id", request.client.host if request.client else "unknown")

    # --- Mode A: Direct audit (backward compatible — when endpoint_url is provided) ---
    if endpoint_url.startswith("http"):
        logger.info(f"[/data] Direct audit on {endpoint_url}")
        result = await run_audit(
            endpoint_url=endpoint_url,
            sample_query=query or "test",
            plan_id=body.get("plan_id", ""),
            agent_id=body.get("agent_id", ""),
            openai_api_key=OPENAI_API_KEY,
            model_id=MODEL_ID,
            exa_api_key=EXA_API_KEY,
        )
        if result["overall_score"] > 0.55:
            result["ad"] = await _zeroclick_ad(endpoint_url, result)
        _record("/data", ENDPOINT_CREDITS["/data"], caller)
        return result

    # --- Mode B: Full Business Intelligence pipeline ---
    if not query:
        return JSONResponse(status_code=400, content={
            "error": "Describe your business idea or provide an endpoint_url to audit",
            "usage": {
                "business_idea": {"query": "I want to build a fintech AI assistant"},
                "direct_audit": {"endpoint_url": "https://some-service.com"},
            },
        })

    budget = min(int(body.get("budget_credits", 5)), 10)
    logger.info(f"[/data] Business strategy: '{query}' budget={budget} from {caller}")

    try:
        from src.chat import _exec_business_strategy
        result_json = await _exec_business_strategy(query, budget)
        result = json.loads(result_json)
    except Exception as e:
        logger.error(f"[/data] Business strategy pipeline failed: {e}")
        return JSONResponse(status_code=500, content={
            "error": "Business strategy pipeline encountered an error",
            "detail": str(e)[:200],
            "query": query,
        })

    _record("/data", ENDPOINT_CREDITS["/data"], caller)
    return result


@app.get("/pricing")
async def pricing():
    """Service pricing information (free)."""
    return {
        "service": "GTMAgent",
        "description": (
            "Autonomous Business Intelligence — describe your idea, "
            "we search the marketplace, audit services, buy the best ones, "
            "and deliver an actionable strategy."
        ),
        "planId": NVM_PLAN_ID,
        "agentId": NVM_AGENT_ID,
        "endpoint": {
            "path": "/data",
            "method": "POST",
            "credits": 1,
            "description": (
                "Send a business idea and get back: marketplace search results, "
                "Apify tool matches, quality audits, purchased services, "
                "competitive analysis, and a synthesized business strategy."
            ),
            "input_examples": [
                {"query": "I want to build a fintech AI assistant"},
                {"goal": "find the best AI tools for social media marketing"},
                {"endpoint_url": "https://some-service.com"},
            ],
        },
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
            result["plans"]["GTMAgent"] = {
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
        "team_name": "GTMAgent",
        "description": (
            "Autonomous Business Intelligence agent. Describe your business idea "
            "and GTMAgent searches the Nevermined marketplace + Apify, audits "
            "candidates, purchases the best services via x402, and delivers a "
            "synthesized business strategy with ROI analysis."
        ),
        "category": "business intelligence, marketplace, audit, strategy, purchasing, automation",
        "plan_id": NVM_PLAN_ID,
        "agent_id": NVM_AGENT_ID,
        "endpoints": [
            {
                "method": "POST",
                "path": "/data",
                "credits": 1,
                "description": (
                    "Send a business idea → get marketplace search, Apify tools, "
                    "quality audits, purchases, and actionable strategy. "
                    "Or send an endpoint_url for a direct quality audit."
                ),
            },
        ],
        "free_endpoints": ["/pricing", "/stats", "/health", "/services", "/sample", "/chain", "/credits"],
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
    return {"status": "healthy", "service": "GTMAgent", "version": "1.0.0"}


def main():
    if DEMO_MODE:
        logger.info("*** DEMO MODE — payment verification disabled ***")
    logger.info(f"Starting GTMAgent seller on port {SELLER_PORT}")
    logger.info("Endpoint: POST /data (1 credit) — business idea → full strategy pipeline")
    uvicorn.run(app, host="0.0.0.0", port=SELLER_PORT)


if __name__ == "__main__":
    main()
