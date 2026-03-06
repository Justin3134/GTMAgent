"""Marketplace discovery — Nevermined hackathon Discovery API + CSV fallback."""

import csv
import io
import logging

import httpx

logger = logging.getLogger("agentaudit.marketplace")

DISCOVERY_URL = "https://nevermined.ai/hackathon/register/api/discover"


async def fetch_marketplace(csv_url: str = "", nvm_api_key: str = "") -> list[dict]:
    """Fetch live sellers from the Nevermined hackathon Discovery API.

    Falls back to CSV if the API is unavailable.
    Returns a list of normalised service dicts compatible with the buyer/chat logic.
    """
    entries = await _fetch_discovery_api(nvm_api_key)
    if entries:
        logger.info(f"[marketplace] Discovery API returned {len(entries)} sellers")
        return entries

    # Fallback: CSV sheet (old method)
    if csv_url:
        entries = await _fetch_csv(csv_url)
        if entries:
            logger.info(f"[marketplace] CSV fallback returned {len(entries)} entries")
            return entries

    logger.warning("[marketplace] No entries from discovery API or CSV")
    return []


async def _fetch_discovery_api(nvm_api_key: str) -> list[dict]:
    """Call the Nevermined Discovery API and return normalised seller entries."""
    if not nvm_api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                DISCOVERY_URL,
                params={"side": "sell"},
                headers={"x-nvm-api-key": nvm_api_key},
            )
            if resp.status_code != 200:
                logger.warning(f"[marketplace] Discovery API returned {resp.status_code}: {resp.text[:200]}")
                return []

            data = resp.json()
            sellers = data.get("sellers", [])
            entries = []
            seen_eps = set()
            for s in sellers:
                endpoint = s.get("endpointUrl", "").strip()
                if not endpoint:
                    continue
                # Skip non-reachable endpoints
                if "localhost" in endpoint or not endpoint.startswith("http"):
                    continue
                if endpoint in seen_eps:
                    continue
                seen_eps.add(endpoint)

                # Extract plan info from planPricing (correct field, not planIds)
                plan_pricing = s.get("planPricing") or []
                plan_id = ""
                payment_type = "crypto"
                price_per_request = ""
                if plan_pricing:
                    # Prefer fiat plan if available (card-delegation, no USDC needed)
                    fiat_plans = [p for p in plan_pricing if p.get("paymentType") == "fiat"]
                    crypto_plans = [p for p in plan_pricing if p.get("paymentType") != "fiat"]
                    chosen = fiat_plans[0] if fiat_plans else (crypto_plans[0] if crypto_plans else {})
                    plan_id = chosen.get("planDid", "")
                    payment_type = chosen.get("paymentType", "crypto")
                    price_per_request = chosen.get("pricePerRequestFormatted", "")

                entries.append({
                    "team_name": s.get("teamName") or s.get("name", "Unknown"),
                    "endpoint_url": endpoint,
                    "description": s.get("description", ""),
                    "plan_id": plan_id,
                    "agent_id": s.get("agentDid", "") or s.get("nvmAgentId", ""),
                    "price_credits": price_per_request or str(s.get("pricing", {}).get("perRequest", "")),
                    "payment_type": payment_type,
                    "category": s.get("category", ""),
                    "keywords": s.get("keywords", []),
                    "wallet_address": s.get("walletAddress", ""),
                })
            return entries
    except Exception as e:
        logger.warning(f"[marketplace] Discovery API error: {e}")
        return []


async def _fetch_csv(csv_url: str) -> list[dict]:
    """Legacy CSV fallback."""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(csv_url)
            if resp.status_code != 200:
                return []
        reader = csv.DictReader(io.StringIO(resp.text))
        entries = []
        for row in reader:
            entry = {
                "team_name": _pick(row, "Team Name", "team_name", "Team"),
                "endpoint_url": _pick(row, "Endpoint URL", "endpoint_url", "URL", "Endpoint"),
                "description": _pick(row, "Description", "description", "Service"),
                "plan_id": _pick(row, "Plan ID", "plan_id", "NVM Plan ID", "Asset DID"),
                "agent_id": _pick(row, "Agent ID", "agent_id", "NVM Agent ID"),
                "price_credits": _pick(row, "Price", "price", "Credits"),
                "category": _pick(row, "Category", "category"),
            }
            if entry["endpoint_url"]:
                entries.append(entry)
        return entries
    except Exception as e:
        logger.warning(f"[marketplace] CSV error: {e}")
        return []


def _pick(row: dict, *keys: str) -> str:
    for k in keys:
        v = row.get(k, "")
        if v:
            return str(v).strip()
    return ""
