"""Core audit logic: latency testing, quality scoring, consistency checking, price analysis."""

import asyncio
import json
import statistics
import time
from datetime import datetime, timezone
import httpx
from openai import AsyncOpenAI, OpenAI
from src import analytics as _analytics_mod


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------

async def run_audit(
    endpoint_url: str,
    sample_query: str,
    plan_id: str = "",
    agent_id: str = "",
    openai_api_key: str = "",
    model_id: str = "gpt-4o-mini",
    exa_api_key: str = "",
) -> dict:
    """Run a full quality audit on a service endpoint."""
    timestamp = datetime.now(timezone.utc).isoformat()

    latency_result, price_result = await asyncio.gather(
        test_latency(endpoint_url, sample_query),
        analyze_price(endpoint_url),
    )

    quality_result = await score_quality(
        latency_result.get("responses", []),
        sample_query,
        openai_api_key,
        model_id,
        exa_api_key,
    )

    consistency_result = await check_consistency(
        latency_result.get("responses", []),
        openai_api_key,
        model_id,
    )

    weights = {"quality": 0.40, "consistency": 0.25, "latency": 0.20, "price_value": 0.15}
    overall_score = (
        quality_result["score"] * weights["quality"]
        + consistency_result["score"] * weights["consistency"]
        + latency_result["score"] * weights["latency"]
        + price_result["score"] * weights["price_value"]
    )

    if overall_score >= 0.75:
        recommendation = "STRONG_BUY"
        reasoning = (
            f"Excellent quality ({quality_result['score']:.2f}), "
            f"good consistency ({consistency_result['score']:.2f}), "
            f"acceptable latency ({latency_result['avg_ms']:.0f}ms)."
        )
    elif overall_score >= 0.6:
        recommendation = "BUY"
        reasoning = (
            f"Good overall performance — quality: {quality_result['score']:.2f}, "
            f"latency: {latency_result['avg_ms']:.0f}ms."
        )
    elif overall_score >= 0.45:
        recommendation = "CAUTIOUS"
        reasoning = (
            f"Mixed signals — quality {quality_result['score']:.2f}, "
            f"consistency {consistency_result['score']:.2f}. Monitor before committing budget."
        )
    else:
        recommendation = "AVOID"
        reasoning = (
            f"Below threshold — quality {quality_result['score']:.2f}, "
            f"consistency {consistency_result['score']:.2f}, "
            f"latency {latency_result['avg_ms']:.0f}ms."
        )

    return {
        "endpoint_url": endpoint_url,
        "timestamp": timestamp,
        "overall_score": round(overall_score, 3),
        "recommendation": recommendation,
        "reasoning": reasoning,
        "scores": {
            "quality": round(quality_result["score"], 3),
            "consistency": round(consistency_result["score"], 3),
            "latency": round(latency_result["score"], 3),
            "price_value": round(price_result["score"], 3),
        },
        "details": {
            "latency": {
                "avg_ms": round(latency_result["avg_ms"], 1),
                "p95_ms": round(latency_result["p95_ms"], 1),
                "min_ms": round(latency_result["min_ms"], 1),
                "samples": latency_result["samples"],
                "successes": latency_result["successes"],
            },
            "quality": {
                "score": quality_result["score"],
                "analysis": quality_result["analysis"],
            },
            "consistency": {
                "score": consistency_result["score"],
                "analysis": consistency_result["analysis"],
            },
            "pricing": {
                "score": price_result["score"],
                "analysis": price_result["analysis"],
            },
        },
    }


async def run_compare(
    url1: str,
    url2: str,
    query: str,
    openai_api_key: str = "",
    model_id: str = "gpt-4o-mini",
    exa_api_key: str = "",
) -> dict:
    """Compare two service endpoints side by side."""
    audit1, audit2 = await asyncio.gather(
        run_audit(url1, query, openai_api_key=openai_api_key, model_id=model_id, exa_api_key=exa_api_key),
        run_audit(url2, query, openai_api_key=openai_api_key, model_id=model_id, exa_api_key=exa_api_key),
    )

    winner = url1 if audit1["overall_score"] >= audit2["overall_score"] else url2
    margin = abs(audit1["overall_score"] - audit2["overall_score"])

    return {
        "query": query,
        "endpoint_1": {"url": url1, **audit1},
        "endpoint_2": {"url": url2, **audit2},
        "winner": winner,
        "margin": round(margin, 3),
        "recommendation": (
            f"{'Strong' if margin > 0.15 else 'Slight'} preference for {winner} "
            f"(score difference: {margin:.3f})"
        ),
    }


async def run_monitor(endpoint_url: str, threshold: float = 0.7) -> dict:
    """Quick health check on a service endpoint."""
    latency = await test_latency(endpoint_url, "health check ping", num_calls=1)

    is_up = latency["successes"] > 0
    latency_ms = latency["avg_ms"] if is_up else None

    if not is_up:
        score, status = 0.0, "DOWN"
    elif latency_ms and latency_ms < 1000:
        score, status = 1.0, "HEALTHY"
    elif latency_ms and latency_ms < 3000:
        score, status = 0.7, "DEGRADED"
    else:
        score, status = 0.4, "SLOW"

    alert = score < threshold

    return {
        "endpoint_url": endpoint_url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "score": round(score, 3),
        "status": status,
        "latency_ms": round(latency_ms, 1) if latency_ms else None,
        "threshold": threshold,
        "alert": alert,
        "alert_message": f"Score {score:.2f} below threshold {threshold}" if alert else None,
    }


# ---------------------------------------------------------------------------
# Sub-checks
# ---------------------------------------------------------------------------

async def test_latency(
    endpoint_url: str,
    query: str,
    num_calls: int = 3,
) -> dict:
    """Call endpoint multiple times and measure latency."""
    latencies: list[float] = []
    responses: list[dict] = []
    errors: list[dict] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Resolve target endpoint:
        # - If the URL already has a non-trivial path, call it directly
        # - Otherwise try /sample first (free), then fall back to /data
        from urllib.parse import urlparse as _urlparse
        _parsed = _urlparse(endpoint_url)
        _path = (_parsed.path or "").strip("/")
        base = endpoint_url.rstrip("/")

        if _path:
            # Full path given — team already provides their exact endpoint
            direct_url = base
            sample_body = None
        else:
            # Root URL — probe /sample for free quality data
            direct_url = f"{base}/data"
            sample_body = None
            try:
                sr = await client.get(f"{base}/sample", headers={"Content-Type": "application/json"})
                if sr.status_code == 200:
                    sample_body = sr.json()
            except Exception:
                pass

        for _ in range(num_calls):
            start = time.monotonic()
            try:
                if sample_body is not None:
                    resp = await client.get(f"{base}/sample", headers={"Content-Type": "application/json"})
                else:
                    resp = await client.post(
                        direct_url,
                        json={"query": query, "message": query},
                        headers={"Content-Type": "application/json"},
                    )
                elapsed_ms = (time.monotonic() - start) * 1000
                latencies.append(elapsed_ms)

                if resp.status_code == 402:
                    responses.append({"status": 402, "payment_required": True, "elapsed_ms": elapsed_ms})
                else:
                    try:
                        body = resp.json()
                    except Exception:
                        body = resp.text[:2000]
                    responses.append({"status": resp.status_code, "body": body, "elapsed_ms": elapsed_ms})
            except Exception as e:
                elapsed_ms = (time.monotonic() - start) * 1000
                latencies.append(elapsed_ms)
                errors.append({"error": str(e), "elapsed_ms": elapsed_ms})

    if not latencies:
        return {
            "score": 0.0, "avg_ms": 99999, "p95_ms": 99999, "min_ms": 99999,
            "samples": num_calls, "successes": 0, "responses": [], "errors": errors,
        }

    avg_ms = statistics.mean(latencies)
    sorted_lat = sorted(latencies)
    p95_ms = sorted_lat[int(len(sorted_lat) * 0.95)] if len(sorted_lat) > 1 else sorted_lat[0]
    min_ms = min(latencies)

    if avg_ms < 200:
        score = 1.0
    elif avg_ms < 500:
        score = 0.95 - (avg_ms - 200) / 300 * 0.1
    elif avg_ms < 1000:
        score = 0.85 - (avg_ms - 500) / 500 * 0.15
    elif avg_ms < 2000:
        score = 0.70 - (avg_ms - 1000) / 1000 * 0.2
    elif avg_ms < 5000:
        score = 0.50 - (avg_ms - 2000) / 3000 * 0.2
    elif avg_ms < 10000:
        score = 0.30 - (avg_ms - 5000) / 5000 * 0.2
    else:
        score = 0.1

    successes = sum(1 for r in responses if r.get("status") in (200, 402))

    return {
        "score": score,
        "avg_ms": avg_ms,
        "p95_ms": p95_ms,
        "min_ms": min_ms,
        "samples": num_calls,
        "successes": successes,
        "responses": responses,
        "errors": errors,
    }


async def score_quality(
    responses: list,
    query: str,
    openai_api_key: str,
    model_id: str = "gpt-4o-mini",
    exa_api_key: str = "",
) -> dict:
    """Score the quality of endpoint responses using LLM evaluation."""
    successful = [r for r in responses if r.get("status") == 200 and r.get("body")]

    if not successful:
        payment_only = [r for r in responses if r.get("status") == 402]
        if payment_only:
            latencies = [r.get("elapsed_ms", 5000) for r in payment_only]
            avg_lat = sum(latencies) / len(latencies) if latencies else 5000
            if avg_lat < 300:
                lat_bonus = 0.12
            elif avg_lat < 800:
                lat_bonus = 0.08
            elif avg_lat < 2000:
                lat_bonus = 0.03
            else:
                lat_bonus = -0.05
            variance_penalty = 0.0
            if len(latencies) >= 2:
                spread = max(latencies) - min(latencies)
                if spread > avg_lat * 0.5:
                    variance_penalty = -0.04
            base = 0.45 + lat_bonus + variance_penalty
            return {
                "score": round(min(max(base, 0.3), 0.7), 3),
                "analysis": f"Payment-gated — quality estimated from latency profile ({avg_lat:.0f}ms avg).",
            }
        return {"score": 0.1, "analysis": "No successful responses received. Endpoint may be down."}

    body = successful[0]["body"]
    response_text = json.dumps(body, indent=2)[:3000] if isinstance(body, dict) else str(body)[:3000]

    ground_truth = ""
    if exa_api_key:
        try:
            ground_truth = await _exa_ground_truth(query, exa_api_key)
        except Exception:
            pass

    if not openai_api_key:
        score = 0.5 + (0.1 if len(response_text) > 100 else 0) + (0.1 if len(response_text) > 500 else 0)
        return {"score": min(score, 1.0), "analysis": "Heuristic scoring (no LLM). Length and structure evaluated."}

    prompt = (
        f'You are evaluating an AI service response.\n\n'
        f'Query: "{query}"\n\n'
        f'Response:\n{response_text}\n\n'
    )
    if ground_truth:
        prompt += f'Ground truth (web search):\n{ground_truth[:2000]}\n\n'
    prompt += (
        'Rate quality 0.0–1.0 on relevance, completeness, accuracy, structure.\n'
        'Respond with ONLY: {"score": 0.XX, "analysis": "brief explanation"}'
    )

    try:
        client = AsyncOpenAI(api_key=openai_api_key)
        completion = await client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
        )
        _analytics_mod.record_tool_call("openai", "ok")
        result = json.loads(completion.choices[0].message.content.strip())
        return {"score": float(result["score"]), "analysis": result["analysis"]}
    except Exception as e:
        _analytics_mod.record_tool_call("openai", "error")
        return {"score": 0.5, "analysis": f"LLM scoring failed: {e}"}


async def check_consistency(
    responses: list,
    openai_api_key: str,
    model_id: str = "gpt-4o-mini",
) -> dict:
    """Check consistency across multiple responses from the same endpoint."""
    successful = [r for r in responses if r.get("status") == 200 and r.get("body")]

    if len(successful) < 2:
        if successful:
            return {"score": 0.7, "analysis": "Single successful response — cannot fully assess consistency."}
        payment_responses = [r for r in responses if r.get("status") == 402]
        if payment_responses:
            latencies = [r.get("elapsed_ms", 5000) for r in payment_responses]
            if len(latencies) >= 2:
                spread = max(latencies) - min(latencies)
                avg = sum(latencies) / len(latencies) if latencies else 1
                rel_spread = spread / avg if avg > 0 else 1
                score = max(0.5, min(0.85, 0.8 - rel_spread * 0.3))
                return {"score": round(score, 3), "analysis": f"Payment-gated — consistency from latency stability (spread {spread:.0f}ms / {rel_spread:.1%} relative)."}
            return {"score": 0.7, "analysis": "Payment-gated endpoint — consistency assessed on availability only."}
        return {"score": 0.2, "analysis": "Insufficient successful responses for consistency check."}

    bodies = []
    for r in successful:
        b = r["body"]
        bodies.append(json.dumps(b)[:1500] if isinstance(b, dict) else str(b)[:1500])

    if not openai_api_key:
        lengths = [len(b) for b in bodies]
        var = statistics.variance(lengths) if len(lengths) > 1 else 0
        avg = statistics.mean(lengths)
        rel_var = var / (avg ** 2) if avg > 0 else 1
        return {"score": min(max(0.3, 1.0 - rel_var * 10), 1.0), "analysis": f"Heuristic check — length variance {var:.0f}"}

    pairs = "\n---\n".join(f"Response {i+1}:\n{b}" for i, b in enumerate(bodies))
    prompt = (
        f'Compare these {len(bodies)} responses from the same service to the same query.\n\n'
        f'{pairs}\n\n'
        'Rate consistency 0.0–1.0 (1.0 = identical, 0.1 = contradictory).\n'
        'Respond with ONLY: {"score": 0.XX, "analysis": "brief explanation"}'
    )

    try:
        client = AsyncOpenAI(api_key=openai_api_key)
        completion = await client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
        )
        result = json.loads(completion.choices[0].message.content.strip())
        return {"score": float(result["score"]), "analysis": result["analysis"]}
    except Exception as e:
        return {"score": 0.5, "analysis": f"LLM consistency check failed: {e}"}


async def analyze_price(endpoint_url: str) -> dict:
    """Analyze the pricing of a service endpoint."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{endpoint_url.rstrip('/')}/pricing")
            if resp.status_code == 200:
                data = resp.json()
                tiers = data.get("tiers", [])
                if tiers:
                    credits = [t.get("credits", 0) for t in tiers]
                    lo, hi = min(credits), max(credits)
                    if lo <= 1:
                        score = 0.9
                    elif lo <= 3:
                        score = 0.75
                    elif lo <= 5:
                        score = 0.6
                    elif lo <= 10:
                        score = 0.4
                    else:
                        score = 0.25
                    return {
                        "score": score,
                        "analysis": f"{len(tiers)} tier(s), {lo}–{hi} credits. {'Competitive' if score >= 0.7 else 'Above average'} pricing.",
                    }
        except Exception:
            pass
    host = endpoint_url.split("//")[-1].split("/")[0].lower() if "//" in endpoint_url else endpoint_url.lower()
    if "abilityai" in host or "trinity" in host:
        return {"score": 0.55, "analysis": "AbilityAI/Trinity agent — competitive multi-agent pricing."}
    elif "vercel" in host or "netlify" in host:
        return {"score": 0.6, "analysis": "Hosted on managed platform — typically free-tier friendly pricing."}
    elif "agentbank" in host or "wagmi" in host:
        return {"score": 0.45, "analysis": "Agent bank — variable pricing depending on underlying agents."}
    return {"score": 0.5, "analysis": "No pricing endpoint found — using default score."}


# ---------------------------------------------------------------------------
# Exa helper
# ---------------------------------------------------------------------------

async def _exa_ground_truth(query: str, api_key: str) -> str:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json={"query": query, "numResults": 3, "contents": {"text": {"maxCharacters": 500}}},
        )
        if resp.status_code == 200:
            _analytics_mod.record_tool_call("exa", "ok")
            results = resp.json().get("results", [])
            return "\n".join(f"- {r.get('title', '')}: {r.get('text', '')[:300]}" for r in results)
        _analytics_mod.record_tool_call("exa", "error")
    return ""


async def analyze_with_exa(url: str, query: str = "", exa_api_key: str = "") -> dict:
    """Crawl a URL with Exa and return structured content summary."""
    if not exa_api_key:
        return {"url": url, "error": "No Exa API key", "summary": "", "highlights": []}

    result: dict = {"url": url, "title": "", "summary": "", "highlights": [], "search_context": []}

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                "https://api.exa.ai/contents",
                headers={"x-api-key": exa_api_key, "Content-Type": "application/json"},
                json={
                    "urls": [url],
                    "text": {"maxCharacters": 5000},
                    "highlights": {"numSentences": 5, "query": query or "what does this service do"},
                },
            )
            if resp.status_code == 200:
                _analytics_mod.record_tool_call("exa", "ok")
                data = resp.json()
                pages = data.get("results", [])
                if pages:
                    page = pages[0]
                    result["title"] = page.get("title", "")
                    result["summary"] = (page.get("text") or "")[:3000]
                    result["highlights"] = [h for h in page.get("highlights", []) if h]
        except Exception:
            pass

        if query:
            try:
                resp = await client.post(
                    "https://api.exa.ai/search",
                    headers={"x-api-key": exa_api_key, "Content-Type": "application/json"},
                    json={"query": query, "numResults": 3, "type": "auto",
                           "contents": {"highlights": {"numSentences": 2}}},
                )
                if resp.status_code == 200:
                    for r in resp.json().get("results", []):
                        result["search_context"].append({
                            "title": r.get("title", ""),
                            "url": r.get("url", ""),
                            "highlights": r.get("highlights", []),
                        })
            except Exception:
                pass

    return result
