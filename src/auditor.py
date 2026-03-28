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
            "Excellent quality ({:.2f}), "
            "good consistency ({:.2f}), "
            "acceptable latency ({:.0f}ms).".format(
                quality_result['score'], consistency_result['score'], latency_result['avg_ms']
            )
        )
    elif overall_score >= 0.6:
        recommendation = "BUY"
        reasoning = (
            "Good overall performance — quality: {:.2f}, "
            "latency: {:.0f}ms.".format(
                quality_result['score'], latency_result['avg_ms']
            )
        )
    elif overall_score >= 0.45:
        recommendation = "CAUTIOUS"
        reasoning = (
            "Mixed signals — quality {:.2f}, "
            "consistency {:.2f}. Monitor before committing budget.".format(
                quality_result['score'], consistency_result['score']
            )
        )
    else:
        recommendation = "AVOID"
        reasoning = (
            "Below threshold — quality {:.2f}, "
            "consistency {:.2f}, "
            "latency {:.0f}ms.".format(
                quality_result['score'], consistency_result['score'], latency_result['avg_ms']
            )
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
            "{} preference for {} "
            "(score difference: {:.3f})".format(
                'Strong' if margin > 0.15 else 'Slight', winner, margin
            )
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
        "alert_message": "Score {:.2f} below threshold {}".format(score, threshold) if alert else None,
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
            direct_url = "{}/data".format(base)
            sample_body = None
            try:
                sr = await client.get("{}/sample".format(base), headers={"Content-Type": "application/json"})
                if sr.status_code == 200:
                    sample_body = sr.json()
            except Exception:
                pass

        for _ in range(num_calls):
            start = time.monotonic()
            try:
                if sample_body is not None:
                    resp = await client.get("{}/sample".format(base), headers={"Content-Type": "application/json"})
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
                "analysis": "Payment-gated — quality estimated from latency profile ({:.0f}ms avg).".format(avg_lat),
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

    sanitized_query = query.replace('"', '\\"').replace('\n', '\\n')
    sanitized_text = response_text.replace('"', '\\"').replace('\n', '\\n')
    
    prompt = (
        'You are evaluating an AI service response.\n\n'
        'Query: "{}"\n\n'
        'Response:\n{}\n\n'.format(sanitized_query, sanitized_text)
    )
    if ground_truth:
        sanitized_truth = ground_truth[:2000].replace('"', '\\"').replace('\n', '\\n')
        prompt += 'Ground truth (web search):\n{}\n\n'.format(sanitized_truth)
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
        return {"score": 0.5, "analysis": "LLM scoring failed: {}".format(str(e))}


async def check_consistency(
    responses: list,
    openai_api_key: str,
    model_id: str = "gpt-4o-mini",
) -> dict:
    """Check consistency across multiple responses from the same