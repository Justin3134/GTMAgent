"""GTMAgent Buyer — LangGraph state machine for autonomous marketplace purchasing.

Nodes:
  fetch_marketplace → filter_new → audit_services → mindra_validate
                    → score_and_decide → execute_purchases → log_decisions → END

Run:  poetry run buyer
API:  http://localhost:8000/api/{status,audits,decisions,budget,trigger}
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import TypedDict

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from langgraph.graph import END, START, StateGraph
from sse_starlette.sse import EventSourceResponse

from src.budget import Budget
from src.chat import chat_stream
from src.config import (
    AUDIT_INTERVAL_SECONDS,
    AUDIT_SERVICE_URL,
    BUYER_PORT,
    DEMO_MODE,
    MAX_DAILY_SPEND,
    MAX_PER_REQUEST,
    MAX_VENDOR_PERCENT,
    MARKETPLACE_CSV_URL,
    NVM_API_KEY,
    NVM_AGENT_ID,
    NVM_PLAN_ID,
    get_buyer_payments,
)
from src.marketplace import fetch_marketplace
from src import analytics as _analytics_mod
from src import mindra as _mindra
from src.config import ZEROCLICK_API_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gtmagent.buyer")

# ---------------------------------------------------------------------------
# Persistent state
# ---------------------------------------------------------------------------

audit_history: dict[str, list[dict]] = {}
decision_log: list[dict] = []
budget = Budget(
    max_daily=MAX_DAILY_SPEND,
    max_per_request=MAX_PER_REQUEST,
    max_vendor_percent=MAX_VENDOR_PERCENT,
)

# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------


class BuyerState(TypedDict):
    marketplace: list[dict]
    unaudited: list[dict]
    audit_results: list[dict]
    decisions: list[dict]
    executed: list[dict]
    logs: list[str]
    iteration: int
    ad_impressions: list[dict]


def _log(state: BuyerState, msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    logger.info(entry)
    state["logs"].append(entry)


async def _track_zeroclick_impressions(offer_ids: list[str]) -> None:
    """Notify ZeroClick that offers were displayed to the buyer agent.

    Per the ZeroClick API spec, impressions MUST be tracked for every
    offer that is rendered/shown to the user (here: the buyer agent).
    No auth required on this endpoint.
    """
    if not offer_ids:
        return
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(
                "https://zeroclick.dev/api/v2/impressions",
                headers={"Content-Type": "application/json"},
                json={"ids": offer_ids},
            )
            if resp.status_code == 204:
                logger.info(f"[ZeroClick] Tracked {len(offer_ids)} impression(s)")
            else:
                logger.warning(f"[ZeroClick] Impression tracking returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"[ZeroClick] Impression tracking error: {e}")

# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


async def fetch_marketplace_node(state: BuyerState) -> dict:
    _log(state, "Fetching marketplace via Discovery API...")
    entries = await fetch_marketplace(MARKETPLACE_CSV_URL, nvm_api_key=NVM_API_KEY)

    _log(state, f"Found {len(entries)} services in marketplace")
    return {"marketplace": entries}


async def filter_new_node(state: BuyerState) -> dict:
    unaudited = []
    for entry in state.get("marketplace", []):
        url = entry.get("endpoint_url", "")
        if not url:
            continue
        history = audit_history.get(url, [])
        if not history:
            unaudited.append(entry)
            continue
        last_ts = history[-1].get("timestamp", "2000-01-01T00:00:00+00:00")
        try:
            last_time = datetime.fromisoformat(last_ts)
        except ValueError:
            unaudited.append(entry)
            continue
        if (datetime.now(timezone.utc) - last_time).total_seconds() > 1800:
            unaudited.append(entry)
    _log(state, f"Services needing audit: {len(unaudited)}")
    return {"unaudited": unaudited}


async def audit_services_node(state: BuyerState) -> dict:
    """Call our own /data endpoint on each unaudited service."""
    results = []

    for service in state.get("unaudited", [])[:5]:
        url = service.get("endpoint_url", "")
        team = service.get("team_name", "Unknown")

        ok, reason = budget.can_spend(2, "self-audit")
        if not ok:
            _log(state, f"Budget block for {team}: {reason}")
            continue

        _log(state, f"Auditing {team} ({url})...")

        try:
            headers = {"x-caller-id": "GTMAgent-Buyer"}
            if not DEMO_MODE:
                buyer_payments = get_buyer_payments()
                if buyer_payments:
                    try:
                        token_resp = buyer_payments.x402.get_x402_access_token(
                            plan_id=NVM_PLAN_ID,
                            agent_id=NVM_AGENT_ID or None,
                        )
                        headers["payment-signature"] = token_resp.get("accessToken", "")
                    except Exception as te:
                        _log(state, f"  token error for {team}: {te}")

            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{AUDIT_SERVICE_URL.rstrip('/')}/data",
                    json={
                        "endpoint_url": url,
                        "sample_query": service.get("description", "test query")[:100],
                        "plan_id": service.get("plan_id", ""),
                        "agent_id": service.get("agent_id", ""),
                    },
                    headers=headers,
                )

                if resp.status_code == 200:
                    result = resp.json()
                    result["team_name"] = team
                    results.append(result)
                    audit_history.setdefault(url, []).append(result)
                    budget.record_purchase(2, "self-audit", f"Audit of {team}")
                    _log(state, f"  {team}: score={result['overall_score']:.2f} rec={result['recommendation']}")
                else:
                    _log(state, f"  {team}: audit failed (HTTP {resp.status_code})")
        except Exception as e:
            _log(state, f"  {team}: audit error — {e}")

    return {"audit_results": results}


async def mindra_validate_node(state: BuyerState) -> dict:
    """Optional Mindra-powered anomaly detection on audit results.

    Sends audit scores to Mindra for hallucination/anomaly checks.
    If Mindra is unavailable, passes through unchanged.
    """
    audit_results = state.get("audit_results", [])
    if not audit_results or not _mindra.is_available():
        return {}

    _log(state, f"[Mindra] Validating {len(audit_results)} audit results for anomalies...")
    _analytics_mod.record_tool_call("mindra", "ok")

    scores_summary = "\n".join(
        f"- {r.get('team_name', 'unknown')}: score={r.get('overall_score', 0):.2f}, "
        f"latency={r.get('latency_p50', 'N/A')}ms, rec={r.get('recommendation', 'N/A')}"
        for r in audit_results
    )
    task = (
        f"Validate these AI service audit results for anomalies or hallucinations:\n"
        f"{scores_summary}\n\n"
        "Flag any scores that seem inconsistent, suspiciously high/low, "
        "or where the recommendation doesn't match the score."
    )

    try:
        result = await _mindra.run_and_collect(
            task=task,
            metadata={"source": "gtmagent_buyer", "step": "anomaly_detection"},
            auto_approve=True,
            timeout_seconds=30.0,
        )

        if result.get("final_answer"):
            _log(state, f"[Mindra] Anomaly check: {result['final_answer'][:200]}")
            for r in audit_results:
                r["mindra_validated"] = True
                r["mindra_anomaly_check"] = result.get("status", "unknown")
        else:
            _log(state, "[Mindra] Anomaly check returned no answer (workflow may not have completed)")

    except Exception as e:
        _log(state, f"[Mindra] Validation error (non-fatal): {e}")

    return {}


async def score_and_decide_node(state: BuyerState) -> dict:
    """ROI-based decision engine.
    
    Decision logic:
    - Score >= 0.75: BUY immediately (high confidence)
    - Score >= 0.65 + improving trend: BUY (momentum)
    - Score >= 0.5: WATCH (need more data)
    - Score < 0.5: AVOID (preserve budget)
    - Previously bought + score degraded >15%: SWITCH (exit position)
    - Already bought from 3+ times and score stable: BUY_REPEAT (loyalty efficiency)
    - ZeroClick ad in audit result: track impression, BUY_AD if endpoint provided
    """
    decisions = []
    ad_impressions = []
    zeroclick_offer_ids: list[str] = []
    vendor_purchases = _analytics_mod._store.get("vendors_bought_from", set())

    for result in state.get("audit_results", []):
        url = result.get("endpoint_url", "")
        team = result.get("team_name", "Unknown")
        score = result.get("overall_score", 0)
        history = audit_history.get(url, [])
        scores_in_history = [h.get("overall_score", 0) for h in history]

        # Trend: is quality improving or degrading?
        trend = 0.0
        if len(scores_in_history) >= 2:
            trend = scores_in_history[-1] - scores_in_history[-2]

        # ROI check: how much have we spent on this vendor vs value received?
        ph = _analytics_mod._store.get("purchase_history", [])
        vendor_spend = sum(p["credits"] for p in ph if p.get("vendor", "") == team)
        repeat_count = sum(1 for p in ph if p.get("vendor", "") == team)

        # Exit condition: degrading quality on a vendor we've already bought from
        if repeat_count > 0 and len(scores_in_history) >= 2 and trend < -0.15:
            d = {
                "action": "SWITCH",
                "endpoint_url": url,
                "team_name": team,
                "score": score,
                "previous_score": scores_in_history[-2],
                "score_delta": round(trend, 3),
                "roi_spent": vendor_spend,
                "roi_repeat_count": repeat_count,
                "reason": (
                    f"Quality degraded {scores_in_history[-2]:.2f}→{score:.2f} ({trend:+.2f}). "
                    f"Spent {vendor_spend} credits across {repeat_count} purchases. Switching."
                ),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            decisions.append(d)
            _analytics_mod._store["roi_decisions"]["SWITCH"] = _analytics_mod._store["roi_decisions"].get("SWITCH", 0) + 1
            _log(state, f"SWITCH: {team} degraded {scores_in_history[-2]:.2f}→{score:.2f}, spent={vendor_spend}cr")
            continue

        # Buy decision
        if score >= 0.75:
            action = "BUY"
            reason = f"Score {score:.2f} ≥ 0.75 threshold. High ROI confidence."
        elif score >= 0.65 and trend > 0.05:
            action = "BUY"
            reason = f"Score {score:.2f} with improving trend (+{trend:.2f}). Buying into momentum."
        elif score >= 0.65 and repeat_count >= 3:
            action = "BUY"
            reason = f"Score {score:.2f}, {repeat_count} prior purchases. Repeat buyer — proven ROI."
        elif score >= 0.5:
            action = "WATCH"
            reason = f"Score {score:.2f} borderline. Monitoring for trend before budget commitment."
        else:
            action = "AVOID"
            reason = f"Score {score:.2f} below minimum 0.5. Preserving budget for higher-ROI services."

        decisions.append({
            "action": action,
            "endpoint_url": url,
            "team_name": team,
            "score": score,
            "score_trend": round(trend, 3),
            "roi_prior_spend": vendor_spend,
            "roi_repeat_count": repeat_count,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        _analytics_mod._store["roi_decisions"][action] = _analytics_mod._store["roi_decisions"].get(action, 0) + 1
        _log(state, f"DECISION: {action} {team} score={score:.2f} trend={trend:+.2f} roi_spend={vendor_spend}cr")

        # ---------------------------------------------------------------
        # ZeroClick: process any ad attached to this audit result
        # ZeroClick returns general sponsored offers (not Nevermined-specific).
        # We track impressions for analytics; click_url is the advertiser's URL.
        # ---------------------------------------------------------------
        ad = result.get("ad")
        if ad and ad.get("sponsor") != "GTMAgent":
            # Normalize: support both old cta_url/endpoint_url and new click_url field
            ad_url = ad.get("click_url") or ad.get("endpoint_url") or ad.get("cta_url", "")
            sponsor = ad.get("sponsor", "Unknown")
            message = ad.get("message") or ad.get("title", "")

            impression = {
                "ad": ad,
                "source_url": url,
                "source_team": team,
                "source_score": score,
                "ad_url": ad_url,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            ad_impressions.append(impression)
            _analytics_mod.record_zeroclick_impression(ad, url, score)
            _log(state, f"[ZeroClick] Impression — {sponsor}: {message[:60]}")

            # Collect offer IDs for ZeroClick impression tracking API call
            offer_id = ad.get("id") or ad.get("offer_id", "")
            if offer_id:
                zeroclick_offer_ids.append(offer_id)

    # Fire impression tracking to ZeroClick API (required per their spec)
    if zeroclick_offer_ids:
        await _track_zeroclick_impressions(zeroclick_offer_ids)

    decision_log.extend(decisions)
    return {"decisions": decisions, "ad_impressions": ad_impressions}


async def execute_purchases_node(state: BuyerState) -> dict:
    executed = []

    for decision in state.get("decisions", []):
        if decision["action"] not in ("BUY", "BUY_AD"):
            continue

        is_ad_driven = decision["action"] == "BUY_AD"
        url = decision["endpoint_url"]
        team = decision["team_name"]

        # BUY_AD carries plan_id/agent_id directly from the ad; BUY looks them up in marketplace
        if is_ad_driven:
            plan_id = decision.get("plan_id", "")
            agent_id = decision.get("agent_id", "")
        else:
            plan_id = ""
            agent_id = ""
            for entry in state.get("marketplace", []):
                if entry.get("endpoint_url") == url:
                    plan_id = entry.get("plan_id", "")
                    agent_id = entry.get("agent_id", "")
                    break

        if not plan_id:
            _log(state, f"SKIP {team}: no plan_id")
            continue

        price = 1
        ok, reason = budget.can_spend(price, url)
        if not ok:
            _log(state, f"BUDGET BLOCK for {team}: {reason}")
            continue

        try:
            headers = {"x-caller-id": "GTMAgent-Buyer"}
            used_scheme = "no_payment"
            if not DEMO_MODE:
                buyer_payments = get_buyer_payments()
                if buyer_payments:
                    # Probe the endpoint first to detect the required payment scheme
                    probe_scheme = "nvm:erc4337"
                    try:
                        async with httpx.AsyncClient(timeout=8.0) as probe_client:
                            probe = await probe_client.post(
                                f"{url.rstrip('/')}/data",
                                json={"query": "probe"},
                                headers={"x-caller-id": "GTMAgent-Buyer"},
                            )
                            if probe.status_code == 402:
                                import base64 as _b64
                                hdr = probe.headers.get("payment-required", "")
                                if hdr:
                                    try:
                                        decoded = json.loads(_b64.b64decode(hdr + "==").decode())
                                        for a in decoded.get("accepts", []):
                                            if a.get("scheme") == "nvm:card-delegation":
                                                probe_scheme = "nvm:card-delegation"
                                                break
                                    except Exception:
                                        pass
                    except Exception:
                        pass

                    try:
                        if probe_scheme == "nvm:card-delegation":
                            from payments_py.x402.types import CardDelegationConfig, X402TokenOptions
                            methods = buyer_payments.delegation.list_payment_methods()
                            if methods:
                                pm = methods[0]
                                token_resp = buyer_payments.x402.get_x402_access_token(
                                    plan_id=plan_id,
                                    agent_id=agent_id or None,
                                    token_options=X402TokenOptions(
                                        scheme="nvm:card-delegation",
                                        delegation_config=CardDelegationConfig(
                                            provider_payment_method_id=pm.id,
                                            spending_limit_cents=50,
                                            duration_secs=300,
                                            max_transactions=1,
                                        ),
                                    ),
                                )
                                headers["payment-signature"] = token_resp.get("accessToken", "")
                                used_scheme = "card-delegation"
                                _log(state, f"  card-delegation token obtained ({pm.brand} ending {pm.last4})")
                            else:
                                _log(state, f"  no enrolled cards for card-delegation plan, skipping")
                        else:
                            token_resp = buyer_payments.x402.get_x402_access_token(
                                plan_id=plan_id,
                                agent_id=agent_id or None,
                            )
                            headers["payment-signature"] = token_resp.get("accessToken", "")
                            used_scheme = "nevermined_x402"
                    except Exception as te:
                        _log(state, f"  token error for {team}: {te}")

            query = (
                "GTMAgent ZeroClick referral purchase" if is_ad_driven
                else "GTMAgent ROI verification purchase"
            )

            # Build a richer body using service metadata so endpoints that
            # require specific fields (brand, goal, etc.) don't 422.
            svc_desc = ""
            for entry in state.get("marketplace", []):
                if entry.get("endpoint_url") == url:
                    svc_desc = entry.get("description", "")[:200]
                    break
            body: dict = {
                "query": query,
                "message": query,
                "prompt": query,
                "input": query,
                "description": svc_desc or query,
                "brand": "GTMAgent",
                "brand_name": "GTMAgent",
                "goal": query,
                "campaign_goal": query,
                "task": query,
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{url.rstrip('/')}/data",
                    json=body,
                    headers=headers,
                )

                # On 422, try a simpler body as fallback
                if resp.status_code == 422:
                    _log(state, f"  {team}: 422 with rich body, retrying with minimal body")
                    resp = await client.post(
                        f"{url.rstrip('/')}/data",
                        json={"query": query},
                        headers=headers,
                    )

                if resp.status_code == 200:
                    purchase_note = "zeroclick referral" if is_ad_driven else "verification purchase"
                    budget.record_purchase(price, url, purchase_note, decision["reason"])

                    base_method = used_scheme if used_scheme != "no_payment" else ("nevermined_x402" if headers.get("payment-signature") else "no_payment")
                    payment_method = f"zeroclick_{base_method}" if is_ad_driven else base_method

                    entry = {
                        "team_name": team,
                        "endpoint_url": url,
                        "credits": price,
                        "score": decision.get("score", 0),
                        "roi_reason": decision.get("reason", ""),
                        "payment_method": payment_method,
                        "zeroclick_ad_driven": is_ad_driven,
                        "status": "success",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    if is_ad_driven:
                        entry["zeroclick_ad"] = decision.get("ad", {})

                    executed.append(entry)
                    _analytics_mod.record_purchase(
                        vendor=team,
                        endpoint=f"{url}/data",
                        credits=price,
                        score=decision.get("score", 0),
                        recommendation=decision.get("action", "BUY"),
                        payment_method=payment_method,
                    )

                    if is_ad_driven:
                        _analytics_mod.record_zeroclick_conversion(
                            decision.get("ad", {}), price, decision.get("source_url", url)
                        )
                        _log(state, f"[ZeroClick] CONVERSION: purchased from {team} — {price}cr via {payment_method}")
                    else:
                        _log(state, f"PURCHASED from {team}: {price} credit(s) via {payment_method}")
                else:
                    _log(state, f"PURCHASE FAILED {team}: HTTP {resp.status_code}")
        except Exception as e:
            _log(state, f"PURCHASE ERROR {team}: {e}")

    return {"executed": executed}


async def log_decisions_node(state: BuyerState) -> dict:
    decisions = state.get("decisions", [])
    executed = state.get("executed", [])
    ad_impressions = state.get("ad_impressions", [])
    n_buy = sum(1 for d in decisions if d["action"] == "BUY")
    n_buy_ad = sum(1 for d in decisions if d["action"] == "BUY_AD")
    n_watch = sum(1 for d in decisions if d["action"] == "WATCH")
    n_avoid = sum(1 for d in decisions if d["action"] == "AVOID")
    n_switch = sum(1 for d in decisions if d["action"] == "SWITCH_AWAY")
    n_zc_conversions = sum(1 for e in executed if e.get("zeroclick_ad_driven"))

    _log(state, f"--- Iteration {state.get('iteration', 0)} summary ---")
    _log(state, f"Audited: {len(state.get('audit_results', []))}")
    _log(state, f"Decisions: BUY={n_buy} BUY_AD={n_buy_ad} WATCH={n_watch} AVOID={n_avoid} SWITCH={n_switch}")
    _log(state, f"Purchases: {len(executed)} (ZeroClick conversions: {n_zc_conversions})")
    if ad_impressions:
        _log(state, f"[ZeroClick] {len(ad_impressions)} impression(s), {n_zc_conversions} conversion(s) this cycle")
    _log(state, f"Budget: {json.dumps(budget.get_status(), default=str)}")

    return {"iteration": state.get("iteration", 0) + 1}

# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


def build_buyer_graph():
    g = StateGraph(BuyerState)
    g.add_node("fetch_marketplace", fetch_marketplace_node)
    g.add_node("filter_new", filter_new_node)
    g.add_node("audit_services", audit_services_node)
    g.add_node("mindra_validate", mindra_validate_node)
    g.add_node("score_and_decide", score_and_decide_node)
    g.add_node("execute_purchases", execute_purchases_node)
    g.add_node("log_decisions", log_decisions_node)

    g.add_edge(START, "fetch_marketplace")
    g.add_edge("fetch_marketplace", "filter_new")
    g.add_edge("filter_new", "audit_services")
    g.add_edge("audit_services", "mindra_validate")
    g.add_edge("mindra_validate", "score_and_decide")
    g.add_edge("score_and_decide", "execute_purchases")
    g.add_edge("execute_purchases", "log_decisions")
    g.add_edge("log_decisions", END)

    return g.compile()


async def _buyer_loop():
    graph = build_buyer_graph()
    iteration = 0
    while True:
        logger.info(f"\n{'='*60}\nBUYER LOOP — iteration {iteration}\n{'='*60}")
        try:
            await graph.ainvoke({
                "marketplace": [],
                "unaudited": [],
                "audit_results": [],
                "decisions": [],
                "executed": [],
                "logs": [],
                "iteration": iteration,
                "ad_impressions": [],
            })
            logger.info(f"Iteration {iteration} done. Sleeping {AUDIT_INTERVAL_SECONDS}s")
        except Exception as e:
            logger.error(f"Iteration {iteration} failed: {e}")
        iteration += 1
        await asyncio.sleep(AUDIT_INTERVAL_SECONDS)

# ---------------------------------------------------------------------------
# Dashboard API
# ---------------------------------------------------------------------------

buyer_app = FastAPI(title="GTMAgent Buyer")
buyer_app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@buyer_app.get("/api/status")
async def api_status():
    zc = _analytics_mod._store
    return {
        "budget": budget.get_status(),
        "audit_history_count": sum(len(v) for v in audit_history.values()),
        "services_tracked": len(audit_history),
        "total_decisions": len(decision_log),
        "recent_decisions": decision_log[-20:],
        "zeroclick": {
            "ads_served": zc["zeroclick_ads_served"],
            "impressions": zc["zeroclick_impressions"],
            "conversions": zc["zeroclick_conversions"],
            "conversion_rate": round(
                zc["zeroclick_conversions"] / max(zc["zeroclick_impressions"], 1), 3
            ),
            "revenue_driven": zc["zeroclick_revenue_driven"],
        },
    }


@buyer_app.get("/api/audits")
async def api_audits():
    return {url: results[-1] for url, results in audit_history.items() if results}


@buyer_app.get("/api/decisions")
async def api_decisions():
    return decision_log[-50:]


@buyer_app.get("/api/budget")
async def api_budget():
    return budget.get_status()


@buyer_app.post("/api/trigger")
@buyer_app.post("/api/run-now")
async def api_trigger():
    """Manually trigger one audit cycle."""
    asyncio.create_task(_run_once())
    return {"status": "ok", "message": "Buyer loop triggered in background"}


async def _run_once():
    try:
        graph = build_buyer_graph()
        await graph.ainvoke({
            "marketplace": [],
            "unaudited": [],
            "audit_results": [],
            "decisions": [],
            "executed": [],
            "logs": [],
            "iteration": len(decision_log),
            "ad_impressions": [],
        })
    except Exception as e:
        logger.error(f"run-now error: {e}")


_chat_histories: dict[str, list[dict]] = {}


@buyer_app.post("/api/chat")
async def api_chat(request: Request):
    """Interactive chat endpoint — streams SSE events."""
    body = await request.json()
    message = body.get("message", "")
    session_id = body.get("session_id", "default")
    if not message:
        return {"error": "message is required"}

    history = _chat_histories.get(session_id, [])

    async def event_generator():
        full_response = ""
        try:
            async for event in chat_stream(message, history):
                yield {"event": event["event"], "data": json.dumps(event["data"])}
                if event["event"] == "token":
                    full_response += event["data"].get("text", "")
                # Yield a keepalive comment during long operations to prevent browser timeout
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"chat_stream error: {e}")
            yield {"event": "token", "data": json.dumps({"text": f"\n\n*Error: {e}*"})}
        finally:
            yield {"event": "done", "data": "{}"}
            history.append({"role": "user", "content": message})
            if full_response:
                history.append({"role": "assistant", "content": full_response})
            if len(history) > 40:
                history[:] = history[-30:]
            _chat_histories[session_id] = history

    return EventSourceResponse(event_generator(), ping=5)  # ping every 5s to keep Render connection alive


@buyer_app.get("/health")
async def health():
    return {"status": "healthy", "service": "GTMAgent-Buyer"}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def _start():
    config = uvicorn.Config(buyer_app, host="0.0.0.0", port=BUYER_PORT, log_level="info")
    server = uvicorn.Server(config)
    await asyncio.gather(server.serve(), _buyer_loop())


def main():
    logger.info(f"Starting GTMAgent buyer on port {BUYER_PORT}")
    logger.info(f"Marketplace: {MARKETPLACE_CSV_URL or '(not set)'}")
    logger.info(f"Audit interval: {AUDIT_INTERVAL_SECONDS}s")
    logger.info(f"Budget: {MAX_DAILY_SPEND}/day, {MAX_PER_REQUEST}/req, {MAX_VENDOR_PERCENT*100:.0f}% vendor cap")
    asyncio.run(_start())


if __name__ == "__main__":
    main()
