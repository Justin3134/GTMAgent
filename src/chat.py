"""Chat agent — OpenAI function-calling agent with 5 tools for interactive marketplace interaction."""

import asyncio
import json
import logging
from typing import AsyncGenerator
from urllib.parse import urlparse as _urlparse

import httpx
from openai import AsyncOpenAI, OpenAI

from src.auditor import analyze_with_exa, run_audit
from src import subgraph as _subgraph
from src.config import (
    APIFY_API_KEY,
    AUDIT_SERVICE_URL,
    DEMO_MODE,
    EXA_API_KEY,
    KNOWN_PURCHASABLE,
    MARKETPLACE_CSV_URL,
    MODEL_ID,
    NVM_API_KEY,
    NVM_BUYER_API_KEY,
    NVM_AGENT_ID,
    NVM_PLAN_ID,
    OPENAI_API_KEY,
    ZEROCLICK_API_KEY,
    get_payments,
    get_buyer_payments,
)
from src.apify_tools import search_apify_store, run_best_apify_actor
from src.marketplace import fetch_marketplace
from src import analytics as _analytics_mod
from src import mindra as _mindra

logger = logging.getLogger("gtmagent.chat")


async def _track_zc_impression_bg(offer_id: str) -> None:
    """Fire-and-forget ZeroClick impression API call for chat-triggered audits."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(
                "https://zeroclick.dev/api/v2/impressions",
                headers={"Content-Type": "application/json"},
                json={"ids": [offer_id]},
            )
            if resp.status_code == 204:
                logger.info("[ZeroClick] Chat impression tracked")
            else:
                logger.warning(f"[ZeroClick] Chat impression returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"[ZeroClick] Chat impression error: {e}")


_zc_last_live_ad: dict | None = None


async def _attach_zeroclick_ad(endpoint_url: str, score: float) -> dict | None:
    """Fetch a ZeroClick ad for a high-scoring result (chat/strategy path).

    Retries up to 3 times with backoff, and caches the last successful live ad
    so transient API failures still serve a real ad.
    """
    global _zc_last_live_ad
    import uuid as _uuid

    if ZEROCLICK_API_KEY:
        domain = endpoint_url.split("//")[-1].split("/")[0] if endpoint_url.startswith("http") else endpoint_url
        query = f"{endpoint_url} AI service {score:.0%} quality score Nevermined marketplace"
        context = (
            f"AI agent marketplace. Autonomous buyer purchasing AI services via Nevermined x402 protocol. "
            f"Service domain: {domain}. Quality score: {score:.0%}. "
            "Show ads for competing AI tools, developer tools, or SaaS alternatives."
        )
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        "https://zeroclick.dev/api/v2/offers",
                        headers={"x-zc-api-key": ZEROCLICK_API_KEY, "Content-Type": "application/json"},
                        json={"method": "client", "query": query, "context": context, "limit": 1},
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
                        logger.warning("[ZeroClick] Publisher account pending approval — retrying")
            except Exception as e:
                logger.warning(f"[ZeroClick] Chat ad fetch error (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                await asyncio.sleep(1.0 * (attempt + 1))

    if _zc_last_live_ad:
        ad = {**_zc_last_live_ad, "id": str(_uuid.uuid4())}
        _analytics_mod.record_tool_call("zeroclick", "ok")
        _analytics_mod.record_zeroclick_ad_served(ad, endpoint_url, score)
        logger.info("[ZeroClick] Served cached live ad after API failure")
        return ad

    logger.warning("[ZeroClick] No live ad available and no cache — skipping ad")
    return None


OWN_SERVICES = [
    {
        "team_name": "GTMAgent",
        "endpoint_url": AUDIT_SERVICE_URL,
        "description": "Autonomous Business Intelligence — describe a business idea and get marketplace search, Apify tools, quality audits, purchases, and actionable strategy.",
        "plan_id": NVM_PLAN_ID,
        "agent_id": NVM_AGENT_ID,
        "price_credits": "1 credit per call",
        "category": "business intelligence, marketplace, audit, strategy, purchasing, automation",
        "endpoints": {
            "data": f"{AUDIT_SERVICE_URL}/data",
        },
    },
]

def sanitize_user_input(user_input: str) -> str:
    """Sanitize user input to prevent prompt injection attacks."""
    if not isinstance(user_input, str):
        return ""
    
    # Remove potential injection markers
    dangerous_patterns = [
        "ignore previous instructions",
        "ignore above",
        "new instructions:",
        "forget everything above",
        "you are now",
        "act as",
        "pretend to be",
        "role:",
        "system:",
        "assistant:",
        "human:",
        "<|system|>",
        "<|user|>",
        "<|assistant|>",
        "```",
        "---",
    ]
    
    sanitized = user_input.lower()
    for pattern in dangerous_patterns:
        if pattern in sanitized:
            logger.warning(f"Potentially malicious input detected: {pattern}")
            # Replace with safe placeholder
            user_input = user_input.replace(pattern, "[FILTERED]")
    
    # Truncate to reasonable length
    if len(user_input) > 2000:
        user_input = user_input[:2000] + "..."
        
    return user_input

SYSTEM_PROMPT = """\
You are GTMAgent — an Autonomous Business Intelligence Agent that searches the Nevermined marketplace, evaluates AI agents, purchases the best ones, and delivers a synthesized business strategy.

## TOOL SELECTION

| User intent | Tool |
|---|---|
| Any business goal / "I want X" / "build Y" / "create Z" | **execute_business_strategy** |
| "run multiple agents" / "parallel" / "simultaneously" | **parallel_agents** |
| "search marketplace" / "what's available" | **search_marketplace** |
| "audit this URL" | **audit_service** |
| "compare X and Y" | **compare_services** |
| "buy from X" | **buy_service** |
| "orchestrate" / "Mindra" / "workflow" / "self-healing" | **mindra_orchestrate** |

## Greetings and small-talk

If the user says "hi", "hello", "hey", or any message that does NOT contain a business goal, respond with a short friendly intro — do NOT ask about a budget, do NOT assume any goal. Example:
> "Hey! Describe a business or goal you want to build and I'll find, evaluate, and purchase the best AI agents for it — then deliver you a strategy."

## Budget — ask ONLY when user has stated a goal

When the user describes a specific business goal and has NOT mentioned a budget or credit amount in their message,
respond with ONE short message asking for budget BEFORE calling any tool:

> "Got it — **[goal]**. What's your budget?
> e.g. **3 credits** (quick test) · **5 credits** (solid foundation) · **10 credits** (full coverage)
> *(1 credit ≈ $0.05–$1 depending on the plan)*"

Once the user replies with a number (e.g. "5", "5 credits", "10 credits"), extract that number and call
`execute_business_strategy` with `budget_credits` set to that number.

If the user's message already contains a budget (e.g. "build X with 5 credits", "budget 10"), skip asking and
call `execute_business_strategy` directly with the specified `budget_credits`.

## How to present strategy results

After execute_business_strategy completes, lead with a compact **receipt block**, then the briefing:

### Receipt (always show this first)
```
PURCHASES — [N] agent(s) · [total_credits] credits spent
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ [Team Name]          [NEW / REPEAT]
  Score: [0.XX] · Paid: [price] · [credits] credits
  tx: [first 20 chars of tx_hash]…

✓ [Team Name 2]        [NEW / REPEAT]
  Score: [0.XX] · Paid: [price] · [credits] credits
  tx: [first 20 chars of tx_hash]…
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Budget used: [spent]/[budget] credits
```

If price_per_credit is 0 or unknown, write "Paid: free plan" or "Paid: 1 USDC/request".

Then continue with:
1. **Why I bought these** — 1 sentence per agent, citing their score vs. alternatives
2. **What I skipped** — briefly note any AVOID decisions and why (score, latency, etc.)
3. **Agent output** — paste real execution results from `execution_results` or `execution_synthesis`

Key: `purchased: true` = a REAL Nevermined blockchain transaction (order_plan).
`repeat_purchase: true` = re-invested in a top performer (ROI-based repeat buy).

## Error reporting — BE ACCURATE
- If error contains "sandbox" or "500" → "Nevermined sandbox temporarily unavailable, retry later"  
- If error contains "NotEnoughBalance" or "insufficient" → "Wallet needs more USDC at https://nevermined.app/account"
- Never say "insufficient credits" for server errors

## Payment setup (accurate)
- Buyer wallet: 0x8b2714... (justin.07823@gmail.com) — has ~18 USDC
- Subscribed plans: TrinityOS Nexus/Social Monitor on us14.abilityai.dev (81 credits), WAGMI AgentBank (2000 credits)
- Card 4242 is set up for fiat/card-delegation plans
- The Nevermined sandbox is sometimes unstable — endpoint errors are often infrastructure issues, not user errors

## ZeroClick native ads (sponsor tool)
- After each strategy run, ZeroClick serves a contextual ad based on the service being evaluated
- The ad is relevant to what was bought — not a generic banner, a native market alternative
- The ad appears in both the chat result AND the Flow View graph visualization
- Impressions are tracked and shown in the sidebar

## Exa competitive analysis
- When Exa API key is present, used to research the business domain before buying
- Provides web-sourced competitive context to inform BUY/AVOID decisions

## Mindra GTM Agents (5 parallel agents — always active when Mindra is configured)
- When execute_business_strategy runs, Mindra fires **5 agents in parallel**:
  1. **Web Search** — market research, competitors, trends, pricing, funding
  2. **LinkedIn** — connections, industry posts, potential partners, hiring signals
  3. **Google Workspace** — emails, docs, prior work, meeting context
  4. **GitHub** — relevant repos, open-source tools, frameworks, developer communities
  5. **Content Creator** — elevator pitch, landing page copy, LinkedIn post ideas, messaging
- All 5 run simultaneously alongside the existing pipeline (Exa, marketplace, audit, purchase)
- Results appear in `mindra_agents` in the report with per-agent answers
- `mindra_gtm_synthesis` contains the combined GTM strategy from all 5 agents
- The Flow view shows all 5 agents with live running/done/failed status
- When presenting results, cite which Mindra agent provided which insight
- When the user asks to "orchestrate", "run a workflow", or "use Mindra" directly, use **mindra_orchestrate**

## AbilityAI Trinity integration
- "Full Stack Agents" = Trinity Nexus agent (us14.abilityai.dev) — multi-agent orchestration
- "TrinityAgents" = Trinity Social Monitor — social media and market intelligence
- Purchasing these plans = buying into the Trinity agent network
- The orchestration grid in the UI shows Trinity: Nexus and Trinity: Social as live agents

## What GTMAgent sells (your own product)
- `/audit` — quality score any AI endpoint. 2 credits
- `/compare` — compare two endpoints. 3 credits  
- `/monitor` — health check. 1 credit
- Deployed at https://gtmagent.onrender.com

## CONTINUOUS OPERATION — YOU ARE A BUSINESS, NOT A CHATBOT

After execute_business_strategy completes, DO NOT STOP. You must continue working:

### Phase 1 — Brief (3–4 lines max)
- State what was purchased and the 2 tx hashes
- State the ROI reason in 1 sentence
- Mention Exa competitive insight in 1 sentence

### Phase 2 — Mindra GTM Intelligence (IMMEDIATELY after briefing)
Present REAL outputs from the 5 Mindra agents. Check `mindra_agents` in the report:
- For each agent that succeeded, show a 2-3 line summary: "Web Search: [key finding]", "LinkedIn: [connections/posts found]", etc.
- If `mindra_gtm_synthesis` exists, present it as the combined GTM strategy
- If an agent failed, briefly note it: "Google Workspace: unavailable"
- NEVER fabricate Mindra output — only show what agents actually returned

### Phase 3 — Live Agent Intelligence (after Mindra results)
Present REAL outputs from marketplace agents that were called:

**TrinityOS agents** — check `trinity_agents` in the report:
- If agents responded (`status: ok`), show their ACTUAL content: "TrinityOS Nexus: [real output]"
- If agents failed, say so: "TrinityOS Social Monitor: connection timeout (sandbox may be unstable)"
- NEVER fabricate Trinity output — only show what they actually returned

**Marketplace agents** — check `execution_results` and `business_outputs`:
- Show each agent's real response with their team name

**Synthesis** — use `execution_synthesis` which combines all real outputs + Exa research

If ALL agents failed to respond, say so honestly and present the Exa competitive research instead.

### Phase 3 — Next action + related suggestions (always end with both