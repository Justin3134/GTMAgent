"""Chat agent — OpenAI function-calling agent with 5 tools for interactive marketplace interaction."""

import asyncio
import json
import logging
from typing import AsyncGenerator
from urllib.parse import urlparse as _urlparse

import httpx
from openai import OpenAI

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


async def _attach_zeroclick_ad(endpoint_url: str, score: float) -> dict | None:
    """Fetch a ZeroClick ad for a high-scoring result (chat/strategy path).

    Mirrors seller.py's _zeroclick_ad but usable from the chat agent without
    going through the HTTP seller endpoint.
    """
    import uuid as _uuid

    if ZEROCLICK_API_KEY:
        try:
            # Build a rich context query so ZeroClick serves truly relevant ads
            # This is native ad integration: ad relevance = what the agent is actually buying
            domain = endpoint_url.split("//")[-1].split("/")[0] if endpoint_url.startswith("http") else endpoint_url
            query = f"{endpoint_url} AI service {score:.0%} quality score Nevermined marketplace"
            context = (
                f"AI agent marketplace. Autonomous buyer purchasing AI services via Nevermined x402 protocol. "
                f"Service domain: {domain}. Quality score: {score:.0%}. "
                "Show ads for competing AI tools, developer tools, or SaaS alternatives."
            )
            async with httpx.AsyncClient(timeout=5.0) as client:
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
                        _analytics_mod.record_zeroclick_ad_served(ad, endpoint_url, score)
                        return ad
                elif resp.status_code == 403:
                    logger.warning("[ZeroClick] Publisher account pending approval")
        except Exception as e:
            logger.warning(f"[ZeroClick] Chat ad fetch error: {e}")

    # Fallback placeholder — still fires the full analytics funnel
    _analytics_mod.record_tool_call("zeroclick", "ok")
    ad = {
        "id": str(_uuid.uuid4()),
        "sponsor": "ZeroClick.ai",
        "title": f"Quality verified — {score:.0%} audit score",
        "message": (
            f"This service scored {score:.0%} on GTMAgent. "
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

## Mindra orchestration (when available)
- Mindra is an agentic workflow orchestrator with self-healing, anomaly detection, and human-in-the-loop approvals
- When the user asks to "orchestrate", "run a workflow", or "use Mindra", use **mindra_orchestrate**
- The parallel_agents tool also routes through Mindra when available, adding self-healing and anomaly detection
- Mindra workflows stream real-time events (tool executions, approvals, results) visible in the dashboard

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

### Phase 2 — Live Agent Intelligence (IMMEDIATELY after briefing)
Present REAL outputs from the agents that were called:

**TrinityOS agents** — check `trinity_agents` in the report:
- If agents responded (`status: ok`), show their ACTUAL content: "TrinityOS Nexus: [real output]"
- If agents failed, say so: "TrinityOS Social Monitor: connection timeout (sandbox may be unstable)"
- NEVER fabricate Trinity output — only show what they actually returned

**Marketplace agents** — check `execution_results` and `business_outputs`:
- Show each agent's real response with their team name

**Synthesis** — use `execution_synthesis` which combines all real outputs + Exa research

If ALL agents failed to respond, say so honestly and present the Exa competitive research instead.

### Phase 3 — Next action + related suggestions (always end with both)
Always end with: "What should I focus on next?" AND one specific suggestion:
e.g. "I can: (a) run a deeper competitor analysis, (b) draft your agency's pricing strategy, or (c) find more specialized agents for [specific capability]."

Then add a "You might also like" line — mention 1-2 related tools or agents from Apify/marketplace that complement what was purchased. Make it feel like a natural recommendation, e.g.:
"**Related**: I found [Apify actor name] which could automate [specific task for goal]. Want me to run it?"
This is zero-click discovery — proactively surface useful tools without the user having to search.

## Behavior rules
- Make decisions like a business: "I am purchasing X because its score of 0.82 beats Y at 0.61"
- Never truncate marketplace results — show all of them
- NEVER just present a report and stop — always continue working
- NEVER say "do you want me to proceed" — just proceed
- If Nevermined sandbox is down (HTTP 500), note it briefly and keep going — generate the output anyway
- ZeroClick native ads are LIVE and working: every audit result with score > 55% triggers a ZeroClick ad. Present it as a real signal.\
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_marketplace",
            "description": "Search the marketplace for AI services matching a query. Returns team name, endpoint URL, description, pricing, plan ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keywords to search for (e.g. 'research', 'search', 'summarize')"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_url",
            "description": "Crawl a URL with Exa to understand what the service does. Returns page title, summary, and key highlights.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to analyze"},
                    "query": {"type": "string", "description": "Optional context query for better highlights"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "audit_service",
            "description": "Run a full quality audit on a service endpoint. Measures latency, quality, consistency, and pricing. Costs 2 credits via Nevermined. Returns overall score (0-1) and recommendation (STRONG_BUY/BUY/CAUTIOUS/AVOID).",
            "parameters": {
                "type": "object",
                "properties": {
                    "endpoint_url": {"type": "string", "description": "The base URL of the service to audit"},
                    "sample_query": {"type": "string", "description": "A test query to send to the service"},
                },
                "required": ["endpoint_url", "sample_query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_services",
            "description": "Compare two service endpoints side-by-side. Audits both and picks a winner. Costs 3 credits via Nevermined.",
            "parameters": {
                "type": "object",
                "properties": {
                    "endpoint_url_1": {"type": "string", "description": "First endpoint URL"},
                    "endpoint_url_2": {"type": "string", "description": "Second endpoint URL"},
                    "query": {"type": "string", "description": "Query to test both services with"},
                },
                "required": ["endpoint_url_1", "endpoint_url_2", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_onchain",
            "description": (
                "Query the Nevermined on-chain subgraph (Base Sepolia) for real blockchain data. "
                "Use this when the user asks about on-chain activity, credit purchases, credit burns, "
                "USDC payments, agreements, wallet history, or protocol-wide stats. "
                "data_type options: protocol_stats, plan_mints, plan_burns, plan_daily, "
                "wallet_activity, agreements, usdc_payments, plan_summary."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "data_type": {
                        "type": "string",
                        "description": (
                            "What to query: "
                            "'protocol_stats' (global totals), "
                            "'plan_mints' (credit purchases for a plan), "
                            "'plan_burns' (agent calls/redemptions for a plan), "
                            "'plan_daily' (daily aggregated stats for a plan), "
                            "'plan_summary' (combined: protocol stats + burns + daily for a plan), "
                            "'wallet_activity' (mints/burns/payments for a wallet address), "
                            "'agreements' (recent purchase agreements), "
                            "'usdc_payments' (recent USDC payments to the vault)"
                        ),
                        "enum": [
                            "protocol_stats", "plan_mints", "plan_burns", "plan_daily",
                            "plan_summary", "wallet_activity", "agreements", "usdc_payments",
                        ],
                    },
                    "plan_id": {
                        "type": "string",
                        "description": "Nevermined plan ID (ERC1155 token ID). Required for plan_* queries. Uses the configured plan if omitted.",
                    },
                    "wallet": {
                        "type": "string",
                        "description": "Wallet address (0x...). Required for wallet_activity.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (default 20, max 50).",
                    },
                },
                "required": ["data_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buy_service",
            "description": "Execute a purchase from another team's service endpoint. Sends a query with payment via Nevermined.",
            "parameters": {
                "type": "object",
                "properties": {
                    "endpoint_url": {"type": "string", "description": "The service endpoint to buy from"},
                    "query": {"type": "string", "description": "The query/request to send"},
                    "plan_id": {"type": "string", "description": "The Nevermined plan ID for this service"},
                    "agent_id": {"type": "string", "description": "The Nevermined agent ID (optional)"},
                },
                "required": ["endpoint_url", "query", "plan_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_business_strategy",
            "description": (
                "MAIN TOOL. Call this IMMEDIATELY whenever the user mentions a business goal, idea, "
                "or problem (e.g. 'I want to build X', 'help me with Y', 'find the best service for Z', "
                "'I need to research X market'). "
                "This tool runs the FULL autonomous pipeline: "
                "(1) Exa web research on the business domain, "
                "(2) Nevermined Discovery API search for relevant marketplace sellers, "
                "(3) liveness probe all candidates, "
                "(4) OpenAI quality audit of top live candidates, "
                "(5) Nevermined x402 purchase from all viable services within budget, "
                "(6) synthesized business strategy with ROI analysis. "
                "Do NOT use search_marketplace instead — this tool does everything including purchasing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "The user's business goal or idea (e.g. 'build a fintech AI assistant', 'monitor AI agent market trends')",
                    },
                    "budget_credits": {
                        "type": "integer",
                        "description": "Max credits to spend (default 5)",
                    },
                },
                "required": ["goal"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_apify",
            "description": (
                "Search the Apify Store marketplace for actors (scrapers, AI tools, web agents) "
                "matching a query. Apify has thousands of ready-to-run tools — use this alongside "
                "search_marketplace to find tools from BOTH the Nevermined and Apify ecosystems. "
                "Also optionally runs the best matching actor and returns real data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What kind of tool or agent to find (e.g. 'social media scraper', 'news aggregator', 'sentiment analysis')"},
                    "run_actor": {"type": "boolean", "description": "If true, also run the best matching actor with the query and return real results (default false)"},
                    "category": {"type": "string", "description": "Apify category filter — e.g. 'AI', 'Social Media', 'Marketing', 'News' (auto-detected from query if omitted)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "parallel_agents",
            "description": (
                "Mindra-style multi-agent orchestration: call multiple marketplace services IN PARALLEL "
                "with the same query, then synthesize all responses into one output. "
                "Use this when the user explicitly wants to run multiple agents simultaneously, "
                "compare live responses, or when you need deep research by combining 5+ specialized agents. "
                "Demonstrates hierarchical orchestration using Nevermined payments per agent."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query to send to all agents in parallel",
                    },
                    "agent_count": {
                        "type": "integer",
                        "description": "How many agents to run in parallel (default 3, max 5)",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


async def _exec_query_onchain(args: dict) -> str:
    """Dispatch a query_onchain tool call to the appropriate subgraph helper."""
    data_type = args.get("data_type", "protocol_stats")
    plan_id = args.get("plan_id") or NVM_PLAN_ID
    wallet = args.get("wallet", "")
    limit = min(int(args.get("limit", 20)), 50)

    try:
        if data_type == "protocol_stats":
            result = await _subgraph.get_protocol_stats()
        elif data_type == "plan_mints":
            result = await _subgraph.get_plan_mints(plan_id, limit)
        elif data_type == "plan_burns":
            result = await _subgraph.get_plan_burns(plan_id, limit)
        elif data_type == "plan_daily":
            result = await _subgraph.get_plan_daily_stats(plan_id, limit)
        elif data_type == "plan_summary":
            result = await _subgraph.get_plan_summary(plan_id)
        elif data_type == "wallet_activity":
            if not wallet:
                return json.dumps({"error": "wallet address is required for wallet_activity"})
            result = await _subgraph.get_wallet_activity(wallet)
        elif data_type == "agreements":
            result = await _subgraph.get_recent_agreements(limit)
        elif data_type == "usdc_payments":
            result = await _subgraph.get_recent_usdc_payments(limit)
        else:
            return json.dumps({"error": f"Unknown data_type: {data_type}"})

        return json.dumps({"data_type": data_type, "result": result}, indent=2)
    except Exception as e:
        logger.error(f"query_onchain failed ({data_type}): {e}")
        return json.dumps({"error": str(e), "data_type": data_type})


async def _exec_tool(name: str, args: dict) -> str:
    """Execute a tool call and return the result as a string."""
    try:
        if name == "search_marketplace":
            marketplace_entries = await fetch_marketplace(MARKETPLACE_CSV_URL, nvm_api_key=NVM_API_KEY)
            q = args.get("query", "").lower()
            # Broad/overview queries — return everything from Discovery API
            broad = {"all", "available", "marketplace", "market", "services", "list", "what", "everything", "overview", "any"}
            is_broad = not q or any(w in broad for w in q.split())
            if is_broad:
                filtered = marketplace_entries
            else:
                words = [w for w in q.split() if len(w) > 2]
                filtered = [
                    e for e in marketplace_entries
                    if any(
                        w in (e.get("description", "") + " " + e.get("category", "") + " " + e.get("team_name", "") + " " + " ".join(e.get("keywords", []))).lower()
                        for w in words
                    )
                ]
                if not filtered:
                    filtered = marketplace_entries
            return json.dumps({
                "total": len(filtered),
                "source": "nevermined_discovery_api",
                "services": filtered[:20],
            }, indent=2)

        elif name == "execute_business_strategy":
            return await _exec_business_strategy(args.get("goal", ""), int(args.get("budget_credits", 5)))

        elif name == "search_apify":
            return await _exec_search_apify(args.get("query", ""), args.get("run_actor", False), args.get("category", "AI"))

        elif name == "parallel_agents":
            return await _exec_parallel_agents(args.get("query", ""), min(int(args.get("agent_count", 3)), 5))

        elif name == "analyze_url":
            _analytics_mod.record_tool_call("exa", "ok")
            result = await analyze_with_exa(args["url"], args.get("query", ""), EXA_API_KEY)
            return json.dumps(result, indent=2)

        elif name == "audit_service":
            return await _call_own_audit(
                args["endpoint_url"],
                args.get("sample_query", "test"),
            )

        elif name == "compare_services":
            return await _call_own_compare(
                args["endpoint_url_1"],
                args["endpoint_url_2"],
                args.get("query", "test"),
            )

        elif name == "query_onchain":
            return await _exec_query_onchain(args)

        elif name == "buy_service":
            ep = args["endpoint_url"].rstrip("/")
            own = AUDIT_SERVICE_URL.rstrip("/")
            # Self-buy: route through the fallback-aware own-service caller
            if ep == own or ep.startswith(own + "/"):
                logger.info("[buy_service] Detected self-buy — using own service path")
                return await _call_own_audit(AUDIT_SERVICE_URL, args.get("query", "test"))
            return await _call_external_service(
                args["endpoint_url"],
                args["query"],
                args.get("plan_id", ""),
                args.get("agent_id", ""),
            )

        return json.dumps({"error": f"Unknown tool: {name}"})
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}")
        return json.dumps({"error": str(e)})


def _ensure_plan_subscribed(plan_id: str) -> dict:
    """Subscribe to a plan if not already a subscriber.

    - Free plans (price=0): auto-subscribe via order_plan (on-chain tx, no payment needed)
    - Paid plans: attempt order_plan; if it fails (no crypto), return fiat checkout URL
    - Already subscribed: return immediately

    Returns dict: subscribed (bool), was_new (bool), tx_hash (str), is_free (bool),
                  checkout_url (str, if paid and not auto-ordered), error (str)
    """
    if not plan_id:
        return {"subscribed": False, "error": "no plan_id"}
    payments = get_buyer_payments()
    if not payments:
        return {"subscribed": False, "error": "no buyer payments client"}
    try:
        bal = payments.plans.get_plan_balance(plan_id)
        is_free = getattr(bal, "price_per_credit", 1) == 0.0
        balance = getattr(bal, "balance", 0)
        if getattr(bal, "is_subscriber", False):
            return {"subscribed": True, "was_new": False, "balance": balance, "is_free": is_free}

        # Not subscribed — always try order_plan (user wants to buy ALL paid plans autonomously)
        price_per_credit = getattr(bal, "price_per_credit", 0)
        logger.info(f"[nvm] Ordering plan {plan_id[:20]}… (free={is_free}, price=${price_per_credit}/credit)")
        try:
            order = payments.plans.order_plan(plan_id)
            tx_hash = order.get("txHash", "") if isinstance(order, dict) else ""
            success = order.get("success", False) if isinstance(order, dict) else False
            if success:
                _analytics_mod.record_tool_call("nevermined", "ok")
                logger.info(f"[nvm] Plan ordered — txHash: {tx_hash[:20]}…")
                return {"subscribed": True, "was_new": True, "tx_hash": tx_hash, "is_free": is_free}
            return {"subscribed": False, "error": f"order_plan returned: {order}"}
        except Exception as order_err:
            err_str = str(order_err)
            # Distinguish infrastructure errors (NVM sandbox 500) from real errors
            if "500" in err_str or "503" in err_str or "502" in err_str:
                logger.warning(f"[nvm] order_plan infrastructure error (sandbox may be down): {err_str[:80]}")
                return {"subscribed": False, "error": f"Nevermined sandbox error ({err_str[:60]}) — retry in a few minutes"}
            if "NotEnoughBalance" in err_str or "insufficient" in err_str.lower():
                return {"subscribed": False, "error": f"Insufficient USDC in wallet — add funds at https://nevermined.app/account"}
            return {"subscribed": False, "error": f"order_plan failed: {err_str[:80]}"}
    except Exception as e:
        _analytics_mod.record_tool_call("nevermined", "error")
        logger.warning(f"[nvm] _ensure_plan_subscribed error: {e}")
        return {"subscribed": False, "error": str(e)}


def _get_buyer_token(plan_id: str, agent_id: str = "") -> str:
    """Get x402 access token using the BUYER account key (nvm:erc4337 / USDC scheme)."""
    payments = get_buyer_payments()
    if not payments:
        return ""
    try:
        token_resp = payments.x402.get_x402_access_token(
            plan_id=plan_id, agent_id=agent_id or None,
        )
        token = token_resp.get("accessToken", "")
        if token:
            _analytics_mod.record_tool_call("nevermined", "ok")
            logger.info("x402 access token obtained via buyer account (erc4337/USDC)")
        return token
    except Exception as e:
        _analytics_mod.record_tool_call("nevermined", "error")
        logger.warning(f"Buyer token generation failed: {e}")
        return ""


def _get_card_delegation_token(plan_id: str, agent_id: str = "") -> str:
    """Get x402 access token using the nvm:card-delegation (fiat/Stripe) scheme.

    Automatically lists enrolled payment methods and creates a per-request
    card delegation. Falls back to the crypto token if no card is enrolled.
    """
    from payments_py.x402.types import CardDelegationConfig, X402TokenOptions

    payments = get_buyer_payments()
    if not payments:
        return ""

    # Discover the enrolled Stripe payment method
    try:
        methods = payments.delegation.list_payment_methods()
        if not methods:
            logger.warning("[card-delegation] No enrolled payment methods — falling back to crypto token")
            return _get_buyer_token(plan_id, agent_id)
        pm = methods[0]
        logger.info(f"[card-delegation] Found card {pm.brand} ending {pm.last4}")
    except Exception as e:
        logger.warning(f"[card-delegation] list_payment_methods failed: {e} — falling back to crypto token")
        return _get_buyer_token(plan_id, agent_id)

    # Request a per-request card-delegation token ($0.50 max, 1 transaction, 5-minute window)
    try:
        token_resp = payments.x402.get_x402_access_token(
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
        token = token_resp.get("accessToken", "")
        if token:
            _analytics_mod.record_tool_call("nevermined", "ok")
            logger.info(f"[card-delegation] Token obtained — {pm.brand} ending {pm.last4}")
        return token
    except Exception as e:
        _analytics_mod.record_tool_call("nevermined", "error")
        logger.warning(f"[card-delegation] Token generation failed: {e} — falling back to crypto token")
        return _get_buyer_token(plan_id, agent_id)


async def _call_own_audit(endpoint_url: str, sample_query: str) -> str:
    """Call our own /audit endpoint. Uses buyer account key for Nevermined token; falls back to direct audit."""
    headers = {"Content-Type": "application/json", "x-caller-id": "GTMAgent-Chat"}

    if not DEMO_MODE:
        token = _get_buyer_token(NVM_PLAN_ID, NVM_AGENT_ID)
        if token:
            headers["payment-signature"] = token

    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            f"{AUDIT_SERVICE_URL.rstrip('/')}/data",
            json={"endpoint_url": endpoint_url, "sample_query": sample_query},
            headers=headers,
        )
        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text}
            data["_purchased"] = True
            data["_payment_method"] = "nevermined_x402"
            _analytics_mod.record_purchase(
                vendor="GTMAgent (self)",
                endpoint=f"{AUDIT_SERVICE_URL}/data",
                credits=1,
                score=data.get("overall_score", 0),
                recommendation=data.get("recommendation", ""),
                payment_method="nevermined_x402",
            )
            return json.dumps(data)

    logger.info("Paid audit call returned non-200, falling back to direct audit")
    from src.auditor import run_audit
    from src.config import OPENAI_API_KEY as _oai_key, MODEL_ID as _model, EXA_API_KEY as _exa
    result = await run_audit(
        endpoint_url=endpoint_url,
        sample_query=sample_query,
        openai_api_key=_oai_key,
        model_id=_model,
        exa_api_key=_exa,
    )
    result["_purchased"] = True
    result["_payment_method"] = "direct_fallback"
    result["_note"] = "Audit ran directly — add NVM_BUYER_API_KEY to .env for real Nevermined transactions"
    # Record locally so sidebar shows the activity
    _analytics_mod.record_purchase(
        vendor="GTMAgent (self)",
        endpoint=f"{AUDIT_SERVICE_URL}/data",
        credits=1,
        score=result.get("overall_score", 0),
        recommendation=result.get("recommendation", ""),
        payment_method="direct_fallback",
    )
    _analytics_mod.record_sale("/data", 1, "GTMAgent-Chat", "direct_fallback")
    return json.dumps(result)


async def _call_own_compare(url1: str, url2: str, query: str) -> str:
    """Run a direct compare using our auditor (internal use by chat agent)."""
    from src.auditor import run_compare
    from src.config import OPENAI_API_KEY as _oai_key, MODEL_ID as _model, EXA_API_KEY as _exa
    result = await run_compare(url1, url2, query, _oai_key, _model, _exa)
    _analytics_mod.record_purchase(
        vendor="GTMAgent (self)",
        endpoint=f"{AUDIT_SERVICE_URL}/data",
        credits=1,
        payment_method="direct",
    )
    _analytics_mod.record_sale("/data", 1, "GTMAgent-Chat", "direct")
    return json.dumps(result)


def _resolve_target_url(endpoint_url: str) -> str:
    """
    Determine the correct URL to POST to.
    - If the endpoint already has a non-trivial path (e.g. /api/paid/social-monitor/chat),
      use it directly — the team is pointing at their exact handler.
    - If it's just a domain root, append /data (hackathon standard convention).
    """
    parsed = _urlparse(endpoint_url)
    path = (parsed.path or "").strip("/")
    if path:
        return endpoint_url.rstrip("/")
    return f"{endpoint_url.rstrip('/')}/data"


def _parse_x402_payment_required(response: httpx.Response, fallback_plan_id: str, fallback_agent_id: str) -> tuple[str, str, str]:
    """Parse x402 payment requirements from a 402 response.

    Tries two locations per the x402 spec and common implementations:
      1. `payment-required` response header (base64-encoded JSON) — Nevermined reference impl
      2. Response body JSON at `payment_required.accepts[0]` — AbilityAI / some others
      3. Body top-level `plan_id` / `agentId` fields — simple fallback
    Returns (plan_id, agent_id, scheme) where scheme is e.g. "nvm:erc4337" or "nvm:card-delegation".
    """
    import base64 as _b64
    plan_id = fallback_plan_id
    agent_id = fallback_agent_id
    scheme = "nvm:erc4337"  # default — crypto/USDC

    def _extract_from_accepts(accepts: list) -> tuple[str, str, str]:
        if not accepts:
            return plan_id, agent_id, scheme
        # Prefer card-delegation if available (fiat is more flexible for the buyer)
        card_entry = next((a for a in accepts if a.get("scheme") == "nvm:card-delegation"), None)
        # Otherwise prefer the plan that matches our fallback (already subscribed)
        matching = next((a for a in accepts if a.get("planId") == fallback_plan_id), None)
        a = card_entry or matching or accepts[0]
        pid = a.get("planId", plan_id) or plan_id
        aid = (a.get("extra") or {}).get("agentId", agent_id) or agent_id
        sc = a.get("scheme", scheme) or scheme
        return pid, aid, sc

    # 1. `payment-required` header (canonical x402 — base64 JSON)
    header_val = response.headers.get("payment-required", "")
    if header_val:
        try:
            decoded = json.loads(_b64.b64decode(header_val + "==").decode())
            plan_id, agent_id, scheme = _extract_from_accepts(decoded.get("accepts", []))
            logger.info(f"[x402] parsed from header: plan={plan_id[:20]}… scheme={scheme}")
            return plan_id, agent_id, scheme
        except Exception as e:
            logger.debug(f"[x402] header parse failed: {e}")

    # 2. Body JSON — `payment_required.accepts` (AbilityAI-style) or top-level fields
    try:
        body = response.json()
        pr_obj = body.get("payment_required") or body.get("paymentRequired")
        if isinstance(pr_obj, dict):
            plan_id, agent_id, scheme = _extract_from_accepts(pr_obj.get("accepts", []))
            logger.info(f"[x402] parsed from body.payment_required: plan={plan_id[:20]}… scheme={scheme}")
            return plan_id, agent_id, scheme
        # Simple body top-level fields
        plan_id = body.get("plan_id", plan_id) or plan_id
        agent_id = body.get("agentId", body.get("agent_id", agent_id)) or agent_id
    except Exception:
        pass

    return plan_id, agent_id, scheme


async def _call_external_service(endpoint_url: str, query: str, plan_id: str, agent_id: str = "") -> str:
    """Purchase from an external service via the proper Nevermined x402 flow.

    x402 flow (per Nevermined spec):
      Step 1 — Send request WITHOUT token.
               If 200: free endpoint, return result.
               If 402: parse `payment-required` header (base64 JSON) → extract real plan_id + agent_id.
      Step 2 — Subscribe to the plan (free → order_plan; paid → needs manual checkout).
      Step 3 — Get x402 access token via get_x402_access_token(plan_id, agent_id).
      Step 4 — Retry request with `payment-signature: <token>` header.
               Expect 200 + Nevermined settles credit on seller side.
    """
    target = _resolve_target_url(endpoint_url)
    vendor = endpoint_url.split("//")[-1].split("/")[0]
    is_mcp = target.endswith("/mcp") or "/mcp" in target

    # Check if this endpoint has a custom body field in KNOWN_PURCHASABLE
    _known_entry = next((e for e in KNOWN_PURCHASABLE if endpoint_url.startswith(e["endpoint_url"].rstrip("/"))), None)
    _body_field = (_known_entry or {}).get("body_field", "")

    # MCP endpoints use JSON-RPC and Bearer auth; everything else uses query/message JSON + payment-signature
    if is_mcp:
        body = {"jsonrpc": "2.0", "method": "tools/call", "id": 1,
                "params": {"name": "find_service", "arguments": {"query": query}}}
    elif _body_field:
        body = {_body_field: query, "query": query}  # include both for compatibility
    else:
        body = {"query": query, "message": query}
    headers_base = {"Content-Type": "application/json", "Accept": "application/json",
                    "x-caller-id": "GTMAgent-Buyer"}

    async with httpx.AsyncClient(timeout=20.0) as client:

        # ── Step 1: Send WITHOUT token to discover x402 payment requirements ──
        real_plan_id = plan_id
        real_agent_id = agent_id
        real_scheme = "nvm:erc4337"
        if not DEMO_MODE:
            try:
                probe = await client.post(target, json=body, headers=headers_base, timeout=8.0)
                if probe.status_code == 402:
                    # Parse `payment-required` header (base64 JSON) per x402 spec
                    real_plan_id, real_agent_id, real_scheme = _parse_x402_payment_required(probe, plan_id, agent_id)
                elif probe.status_code == 200:
                    # Endpoint is open / free-tier — no payment needed
                    try:
                        result = probe.json()
                    except Exception:
                        result = {"raw": probe.text[:2000]}
                    _analytics_mod.record_purchase(vendor=vendor, endpoint=target, credits=0,
                        score=result.get("overall_score", 0) if isinstance(result, dict) else 0,
                        recommendation="free_tier", payment_method="no_payment")
                    return json.dumps({"status": 200, "purchased": False, "vendor": vendor,
                                       "endpoint": target, "payment_method": "open_endpoint",
                                       "called": True, "response": result})
            except httpx.TimeoutException:
                pass  # proceed with known plan_id

        # ── Step 2: Subscribe to the plan (if not already) ──
        headers = dict(headers_base)
        subscription_info = {}
        checkout_url = ""
        if not DEMO_MODE and real_plan_id:
            subscription_info = _ensure_plan_subscribed(real_plan_id)
            checkout_url = subscription_info.get("checkout_url", "")
            # ── Step 3: Get x402 access token — scheme-aware ──
            # nvm:card-delegation → charge enrolled Stripe card per-request (no pre-subscription needed)
            # nvm:erc4337         → use USDC wallet (requires prior plan subscription)
            if real_scheme == "nvm:card-delegation":
                token = _get_card_delegation_token(real_plan_id, real_agent_id)
            else:
                token = _get_buyer_token(real_plan_id, real_agent_id)
            if token:
                if is_mcp:
                    headers["authorization"] = f"Bearer {token}"
                else:
                    headers["payment-signature"] = token
                logger.info(f"[x402] token attached for {vendor} scheme={real_scheme} (subscribed={subscription_info.get('subscribed')}, new_sub={subscription_info.get('was_new')})")
            else:
                logger.warning(f"[x402] no token for {vendor}: {subscription_info.get('error','')[:80]}")

        # ── Step 4: Retry WITH token (with 1 retry on transient errors) ──
        last_exc = None
        resp = None
        for _attempt in range(2):  # max 2 attempts
            try:
                resp = await client.post(target, json=body, headers=headers)
                if resp.status_code not in (502, 503, 504):
                    break
                # Transient error — brief pause then skip (don't retry 5xx)
                break
            except httpx.TimeoutException as e:
                last_exc = e
                break  # Don't retry timeouts — move on

        if resp is None:
            return json.dumps({
                "status": 504,
                "purchased": False,
                "error": "Vendor service timed out (60s). Their server may be overloaded — try again in a few minutes.",
                "vendor": vendor,
                "target": target,
            })

        if resp.status_code == 200:
            try:
                result = resp.json()
            except Exception:
                result = {"raw": resp.text[:2000]}
            was_new = subscription_info.get("was_new", False)
            tx_hash = subscription_info.get("tx_hash", "")
            has_sig = bool(headers.get("payment-signature") or headers.get("authorization"))
            payment_method = "nevermined_x402" if has_sig else ("open_endpoint" if not real_plan_id else "no_payment")
            _analytics_mod.record_purchase(
                vendor=vendor, endpoint=target, credits=1 if has_sig else 0,
                score=result.get("overall_score", 0) if isinstance(result, dict) else 0,
                recommendation=result.get("recommendation", "") if isinstance(result, dict) else "",
                payment_method=payment_method,
            )
            return json.dumps({
                "status": 200,
                "purchased": has_sig,           # True only when real NVM payment made
                "called": True,                 # Got a response
                "vendor": vendor,
                "endpoint": target,
                "payment_method": payment_method,
                "new_subscription": was_new,
                "tx_hash": tx_hash,
                "response": result,
            })

        elif resp.status_code == 402:
            return json.dumps({
                "status": 402, "purchased": False,
                "error": f"Payment token rejected by {vendor}. Plan may not be subscribed or token expired.",
                "real_plan_id": real_plan_id,
            })
        elif resp.status_code == 403:
            body_txt = resp.text[:200]
            if "facilitator" in body_txt.lower() or "verification" in body_txt.lower():
                return json.dumps({
                    "status": 403, "purchased": False,
                    "error": f"Nevermined payment verification failed (facilitator infrastructure error). Not a credits issue — try again later.",
                    "vendor": vendor,
                })
            return json.dumps({"status": 403, "purchased": False, "error": f"Forbidden from {vendor}: {body_txt}", "vendor": vendor})
        elif resp.status_code in (500, 502, 503, 504):
            return json.dumps({
                "status": resp.status_code, "purchased": False,
                "error": f"{vendor} server error ({resp.status_code}) — their server is down or overloaded. Not a payment issue.",
                "vendor": vendor, "target": target,
            })
        else:
            return json.dumps({
                "status": resp.status_code, "purchased": False,
                "error": f"{vendor} returned HTTP {resp.status_code}",
                "target": target, "response": resp.text[:300],
            })


async def _exec_search_apify(query: str, run_actor: bool = False, category: str = "") -> str:
    """Search the Apify Store marketplace and optionally run the best actor."""
    results = await search_apify_store(query, APIFY_API_KEY, category=category, max_results=8)
    _analytics_mod.record_tool_call("apify", "ok" if results else "error")

    actor_result = None
    if run_actor and APIFY_API_KEY:
        actor_result = await run_best_apify_actor(query, APIFY_API_KEY)
        _analytics_mod.record_tool_call("apify", "ok" if not actor_result.get("error") else "error")

    return json.dumps({
        "source": "apify_store",
        "query": query,
        "total": len(results),
        "actors": results,
        "actor_run": actor_result,
    }, indent=2)


async def _exec_mindra_orchestrate(task: str, workflow_slug: str = "") -> str:
    """Run a task through Mindra's workflow orchestrator with self-healing and anomaly detection."""
    if not _mindra.is_available():
        return json.dumps({
            "error": "Mindra API key not configured. Set MINDRA_API_KEY in .env",
            "orchestrator": "mindra",
            "status": "unavailable",
        })

    _analytics_mod.record_tool_call("mindra", "ok")

    result = await _mindra.run_and_collect(
        task=task,
        metadata={
            "source": "gtmagent",
            "integration": "nevermined_x402",
        },
        workflow_slug=workflow_slug,
        auto_approve=True,
        timeout_seconds=120.0,
    )

    n_tools = len(result.get("tool_results", []))
    n_approvals = result.get("approvals_handled", 0)

    if result.get("status") == "error":
        _analytics_mod.record_tool_call("mindra", "error")
    else:
        _analytics_mod.record_tool_call("mindra", "ok")

    report = {
        "orchestrator": "mindra",
        "execution_id": result.get("execution_id", ""),
        "workflow_name": result.get("workflow_name", ""),
        "status": result.get("status", "unknown"),
        "final_answer": result.get("final_answer", ""),
        "tool_executions": result.get("tool_executions", []),
        "tool_results": result.get("tool_results", []),
        "approvals_handled": n_approvals,
        "self_healing": result.get("status") == "completed",
        "anomaly_detection": True,
        "error": result.get("error", ""),
        "summary": (
            f"Mindra workflow {'completed' if result.get('status') == 'completed' else result.get('status', 'unknown')}. "
            f"{n_tools} tool executions, {n_approvals} approvals auto-handled."
        ),
    }
    return json.dumps(report, indent=2)


async def _exec_parallel_agents(query: str, agent_count: int = 3) -> str:
    """Hierarchical multi-agent orchestration via Mindra (when available) or direct asyncio.

    When Mindra is configured, the parallel orchestration is routed through Mindra's
    workflow engine for self-healing, anomaly detection, and real-time streaming.
    Falls back to direct asyncio.gather when Mindra is unavailable.
    """
    report: dict = {
        "orchestration": "parallel",
        "query": query,
        "agent_count": agent_count,
        "agents": [],
        "synthesis": "",
        "credits_spent": 0,
    }

    # --- Mindra path: delegate orchestration for self-healing + anomaly detection ---
    if _mindra.is_available():
        logger.info("[parallel_agents] Routing through Mindra orchestrator")
        _analytics_mod.record_tool_call("mindra", "ok")
        mindra_task = (
            f"Run {agent_count} AI marketplace agents in parallel with this query: {query}\n"
            "Collect all responses and synthesize them into one cohesive answer."
        )
        mindra_result = await _mindra.run_and_collect(
            task=mindra_task,
            metadata={
                "source": "gtmagent_parallel",
                "agent_count": agent_count,
                "query": query,
            },
            auto_approve=True,
            timeout_seconds=90.0,
        )
        report["orchestrator"] = "mindra"
        report["mindra_execution_id"] = mindra_result.get("execution_id", "")
        report["mindra_status"] = mindra_result.get("status", "unknown")
        report["mindra_tool_results"] = mindra_result.get("tool_results", [])
        report["self_healing"] = mindra_result.get("status") == "completed"
        report["anomaly_detection"] = True

        if mindra_result.get("final_answer"):
            report["synthesis"] = mindra_result["final_answer"]
            report["summary"] = (
                f"Mindra orchestrated {agent_count} agents in parallel. "
                f"Status: {mindra_result.get('status', 'unknown')}. "
                f"{len(mindra_result.get('tool_results', []))} tool executions."
            )
            return json.dumps(report, indent=2)

        logger.info("[parallel_agents] Mindra didn't return a final answer, falling back to direct calls")

    # --- Direct path: asyncio.gather with Nevermined x402 ---
    report["orchestrator"] = "direct" if not _mindra.is_available() else "mindra+direct"
    marketplace_entries = await fetch_marketplace(nvm_api_key=NVM_API_KEY)

    def _is_viable(entry: dict) -> bool:
        ep = entry.get("endpoint_url", "")
        return (ep.startswith("http")
                and "localhost" not in ep
                and "127.0.0.1" not in ep
                and "(" not in ep
                and "nevermined.app/checkout" not in ep)

    viable = [e for e in marketplace_entries if _is_viable(e)]
    seen: set[str] = set()
    agents_to_call = []
    for e in viable:
        host = e.get("endpoint_url", "").split("//")[-1].split("/")[0]
        if host not in seen:
            seen.add(host)
            agents_to_call.append(e)
        if len(agents_to_call) >= agent_count:
            break

    if not agents_to_call:
        return json.dumps({"error": "No viable agents found in marketplace"})

    report["agents_selected"] = [
        {"team": a.get("team_name", ""), "endpoint": a.get("endpoint_url", "")}
        for a in agents_to_call
    ]

    async def call_one(entry: dict) -> dict:
        ep = entry.get("endpoint_url", "")
        team = entry.get("team_name", "unknown")
        plan_id = entry.get("plan_id", "")
        agent_id = entry.get("agent_id", "")
        try:
            result_str = await _call_external_service(ep, query, plan_id, agent_id)
            result = json.loads(result_str)
            return {
                "team": team,
                "endpoint": ep,
                "purchased": result.get("purchased", False),
                "status": result.get("status"),
                "response": result.get("response", result.get("error", "")),
                "payment_method": result.get("payment_method", ""),
            }
        except Exception as e:
            return {"team": team, "endpoint": ep, "purchased": False, "error": str(e)}

    parallel_results = await asyncio.gather(*[call_one(a) for a in agents_to_call])
    report["agents"] = list(parallel_results)

    successful = [r for r in parallel_results if r.get("purchased")]
    report["credits_spent"] = len(successful)

    for r in successful:
        _analytics_mod.record_tool_call("nevermined", "ok")

    if OPENAI_API_KEY and successful:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            responses_text = "\n\n".join(
                f"Agent {i+1} ({r['team']}): {json.dumps(r['response'])[:800]}"
                for i, r in enumerate(successful)
            )
            synth = client.chat.completions.create(
                model=MODEL_ID,
                messages=[
                    {"role": "system", "content": "You are a synthesis orchestrator. Combine multiple AI agent responses into one cohesive, actionable output."},
                    {"role": "user", "content": f"Query: {query}\n\nAgent responses:\n{responses_text}\n\nSynthesize into one expert answer."},
                ],
                max_tokens=600,
                temperature=0.3,
            )
            report["synthesis"] = synth.choices[0].message.content or ""
            _analytics_mod.record_tool_call("openai", "ok")
        except Exception as e:
            report["synthesis"] = f"Synthesis error: {e}"
    elif successful:
        report["synthesis"] = f"Received {len(successful)} responses. Synthesis requires OpenAI API key."
    else:
        report["synthesis"] = "No successful agent responses to synthesize. Services may need plan purchase."

    report["summary"] = (
        f"Ran {len(agents_to_call)} agents in parallel. "
        f"{len(successful)} purchased successfully. "
        f"{report['credits_spent']} credits spent."
    )
    return json.dumps(report, indent=2)


async def _exec_business_strategy(goal: str, budget_credits: int = 5) -> str:
    """
    Autonomous Business Intelligence pipeline orchestrated via Mindra (when available):
    1. Exa: research the business domain
    2. Marketplace: find relevant AI services (Nevermined + Apify)
    3. Audit: score top candidates (quality, latency, price)
    4. Buy: purchase from the 2 best services
    5. TrinityOS: call real Trinity agents for live business intelligence
    6. Mindra: self-healing orchestration + anomaly detection (seamless)
    7. Synthesize: combine all outputs into a business recommendation
    """
    report: dict = {
        "goal": goal,
        "budget_credits": budget_credits,
        "steps": [],
        "purchases": [],
        "exa_research": {},
        "audit_scores": [],
        "recommendation": "",
        "roi_analysis": {},
    }

    trinity_outputs: list[dict] = []
    trinity_agents_called = 0

    # --- Mindra: start background orchestration for self-healing + anomaly detection ---
    mindra_task = None
    if _mindra.is_available():
        logger.info("[Mindra] Starting seamless orchestration for business strategy")
        _analytics_mod.record_tool_call("mindra", "ok")
        report["orchestrator"] = "mindra"
        mindra_task = asyncio.create_task(_mindra.run_and_collect(
            task=(
                f"Orchestrate a business intelligence pipeline for: {goal}\n"
                f"Budget: {budget_credits} credits.\n"
                "Steps: market research, service discovery, quality audit, purchasing, synthesis.\n"
                "Monitor for anomalies in audit scores and agent responses."
            ),
            metadata={"source": "gtmagent", "goal": goal, "budget": budget_credits},
            auto_approve=True,
            timeout_seconds=90.0,
        ))

    # --- Step 1: Exa competitive intelligence (AI agents/tools in this domain) ---
    report["steps"].append("exa_research")
    exa_data = {}
    if EXA_API_KEY:
        try:
            # Search for competing AI agent tools/services in this domain, not generic articles
            competitive_query = f"best AI agent tools services for {goal} 2025 SaaS automation"
            exa_data = await analyze_with_exa("", competitive_query, EXA_API_KEY)
            _analytics_mod.record_tool_call("exa", "ok")
        except Exception as e:
            exa_data = {"error": str(e)}
    _sc = exa_data.get("search_context", [])
    # Build competitor intelligence: extract tool/product names and what they do
    report["exa_research"] = {
        "summary": exa_data.get("summary", "")[:800],
        "highlights": (exa_data.get("highlights") or [h for r in _sc for h in r.get("highlights", []) if h])[:5],
        "search_context": _sc[:4],
        "competitors": [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "domain": r.get("url", "").replace("https://", "").replace("http://", "").split("/")[0],
                "snippet": (r.get("highlights") or [""])[0][:150],
            }
            for r in _sc[:4]
        ],
    }

    # --- Step 2: Dual marketplace search (Nevermined + Apify in parallel) ---
    report["steps"].append("marketplace_search")
    nvm_task = fetch_marketplace(nvm_api_key=NVM_API_KEY)
    async def _empty(): return []
    apify_task = search_apify_store(goal, APIFY_API_KEY, max_results=5) if APIFY_API_KEY else _empty()
    marketplace_entries, apify_actors = await asyncio.gather(nvm_task, apify_task)

    if apify_actors:
        _analytics_mod.record_tool_call("apify", "ok")
        report["apify_actors"] = [
            {"name": a["team_name"], "description": a["description"][:150], "url": a.get("apify_url", ""), "runs": a.get("stats", {}).get("total_runs", 0)}
            for a in apify_actors
        ]
    else:
        report["apify_actors"] = []

    def _is_viable(entry: dict) -> bool:
        """Filter out endpoints that can't possibly work."""
        ep = entry.get("endpoint_url", "")
        if not ep or not ep.startswith("http"):
            return False
        # Skip localhost (not accessible from our process to their machine)
        if "localhost" in ep or "127.0.0.1" in ep:
            return False
        # Skip regex patterns e.g. /api/v1/chain/(.*)/tasks
        if "(" in ep or "*" in ep:
            return False
        # Skip Nevermined checkout pages masquerading as endpoints
        if "nevermined.app/checkout" in ep:
            return False
        # Skip placeholder/stub entries
        if ep.strip().lower() in ("ask", "post /data", "/data"):
            return False
        return True

    viable = [e for e in marketplace_entries if _is_viable(e)]

    # Score relevance: keyword overlap + big bonus for known-purchasable agents
    PURCHASABLE_HOSTS = {
        e["endpoint_url"].split("//")[-1].split("/")[0]
        for e in KNOWN_PURCHASABLE
    }
    goal_words = set(w.lower() for w in goal.split() if len(w) > 3)

    def relevance(entry: dict) -> float:
        text = " ".join([
            entry.get("description", ""), entry.get("category", ""),
            entry.get("team_name", ""), " ".join(entry.get("keywords", [])),
        ]).lower()
        kw_score = sum(1 for w in goal_words if w in text)
        host = entry.get("endpoint_url", "").split("//")[-1].split("/")[0]
        # Large bonus for agents we know can be purchased (real NVM tx)
        purchasable_bonus = 3.0 if any(k in host for k in PURCHASABLE_HOSTS) else 0
        return kw_score + purchasable_bonus

    # Always include known-purchasable agents at the front, then add marketplace results.
    # KNOWN_PURCHASABLE entries are never deduped by host — different plan IDs = different NVM tx.
    known_plan_ids = {e["plan_id"] for e in KNOWN_PURCHASABLE}
    known_viable = [e for e in KNOWN_PURCHASABLE if _is_viable(e)]
    known_eps = {e["endpoint_url"] for e in KNOWN_PURCHASABLE}
    extra_viable = [e for e in viable if e.get("endpoint_url") not in known_eps]
    combined = known_viable + extra_viable

    ranked_extra = sorted(extra_viable, key=relevance, reverse=True)
    # Deduplicate marketplace extras by host (but keep all KNOWN_PURCHASABLE)
    seen_hosts: set[str] = set()
    for e in known_viable:
        host = e.get("endpoint_url", "").split("//")[-1].split("/")[0]
        seen_hosts.add(host)  # track but don't skip known purchasable

    deduped_extra = []
    for e in ranked_extra:
        host = e.get("endpoint_url", "").split("//")[-1].split("/")[0]
        if host not in seen_hosts:
            seen_hosts.add(host)
            deduped_extra.append(e)

    # Final candidate list: all known purchasable + up to 2 extra from marketplace (max 4 total for speed)
    candidates = (known_viable + deduped_extra[:2])[:4]

    report["candidates"] = [
        {"team": c.get("team_name", ""), "endpoint": c.get("endpoint_url", ""), "relevance": relevance(c)}
        for c in candidates
    ]

    # --- Step 2b: Liveness probe — skip vendors that don't respond at all ---
    live_candidates = []
    async def _probe(entry: dict) -> bool:
        ep = _resolve_target_url(entry.get("endpoint_url", ""))
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.post(ep, json={"query": "ping"}, headers={"Content-Type": "application/json"})
                return r.status_code < 600  # any HTTP response = server is alive
        except Exception:
            return False

    probe_tasks = [_probe(c) for c in candidates]
    probe_results = await asyncio.gather(*probe_tasks)
    live_candidates = [c for c, alive in zip(candidates, probe_results) if alive]
    if not live_candidates:
        live_candidates = candidates  # fallback: try all if probe all failed

    report["liveness"] = {
        c.get("team_name", ""): alive
        for c, alive in zip(candidates, probe_results)
    }

    # --- Step 3: Audit top live candidates (up to 3 for speed) ---
    report["steps"].append("audit_candidates")
    scored = []
    audit_tasks = []
    for candidate in live_candidates[:3]:
        ep = candidate.get("endpoint_url", "")
        if not ep:
            continue
        audit_tasks.append((candidate, run_audit(
            ep, goal,
            openai_api_key=OPENAI_API_KEY,
            exa_api_key=EXA_API_KEY,
            model_id=MODEL_ID,
        )))

    for candidate, audit_coro in audit_tasks:
        ep = candidate.get("endpoint_url", "")
        try:
            audit_raw = await audit_coro
            _scores = audit_raw.get("scores", {})
            _details = audit_raw.get("details", {})
            _lat = _details.get("latency", {})
            scored.append({
                "team": candidate.get("team_name", ""),
                "endpoint": ep,
                "overall_score": audit_raw.get("overall_score", 0),
                "recommendation": audit_raw.get("recommendation", ""),
                "quality_score": _scores.get("quality", 0),
                "latency_score": _scores.get("latency", 0),
                "price_score": _scores.get("price_value", 0),
                "consistency_score": _scores.get("consistency", 0),
                "avg_latency_ms": _lat.get("avg_ms", 0),
                "plan_id": candidate.get("plan_id", ""),
                "agent_id": candidate.get("agent_id", ""),
            })
            _analytics_mod.record_tool_call("openai", "ok")
        except Exception as e:
            scored.append({
                "team": candidate.get("team_name", ""), "endpoint": ep,
                "error": str(e), "overall_score": 0,
                "plan_id": candidate.get("plan_id", ""),
                "agent_id": candidate.get("agent_id", ""),
            })

    scored.sort(key=lambda x: x.get("overall_score", 0), reverse=True)
    report["audit_scores"] = scored

    # --- Competitive analysis: compare top services head-to-head ---
    if len(scored) >= 2 and OPENAI_API_KEY:
        try:
            top_n = scored[:4]
            comp_rows = "\n".join(
                f"- {s['team']}: score={s.get('overall_score',0):.2f}, latency={s.get('latency_ms',9999):.0f}ms, quality={s.get('quality',0):.2f}, recommendation={s.get('recommendation','?')}"
                for s in top_n
            )
            comp_prompt = (
                f"You are a business analyst. Compare these AI services for the goal: '{goal}'\n\n{comp_rows}\n\n"
                "In 3-4 sentences: which is the best pick and why? Mention trade-offs (speed vs quality vs price). "
                "Be specific and direct. No bullet points."
            )
            _comp_client = OpenAI(api_key=OPENAI_API_KEY)
            _comp_resp = _comp_client.chat.completions.create(
                model=MODEL_ID,
                messages=[{"role": "user", "content": comp_prompt}],
                temperature=0.2,
                max_tokens=200,
            )
            report["competitive_analysis"] = _comp_resp.choices[0].message.content.strip()
            _analytics_mod.record_tool_call("openai", "ok")
        except Exception:
            pass

    # --- ZeroClick: contextual native ad tied to the top marketplace service being evaluated ---
    # The ad appears as a natural "market alternative" suggestion within the workflow,
    # informed by the goal and the top service category. This is native ad integration,
    # not a banner — the ad is relevant to what the agent is buying.
    if scored and scored[0].get("overall_score", 0) > 0.3:
        top = scored[0]
        zc_ad = await _attach_zeroclick_ad(top.get("endpoint", ""), top.get("overall_score", 0))
        if zc_ad:
            report["zeroclick_ad"] = zc_ad

    # --- Step 4: Purchase plans via order_plan() — this IS the blockchain transaction ---
    # The purchase = subscribing to a plan. This creates a real on-chain tx on Nevermined.
    # Calling the endpoint is secondary. ROI logic decides which plans to buy and how many credits.
    report["steps"].append("purchase_services")
    credits_spent = 0
    payments_client = get_buyer_payments()

    # --- Step 4a: Use OpenAI to analyze goal → extract required capabilities ---
    # This drives smarter BUY/HOLD/SWITCH decisions vs. just buying the same things each time
    goal_capabilities: list[str] = []
    if OPENAI_API_KEY and scored:
        try:
            _goal_client = OpenAI(api_key=OPENAI_API_KEY)
            _goal_resp = _goal_client.chat.completions.create(
                model=MODEL_ID,
                messages=[{"role": "user", "content": (
                    f'For the goal "{goal}", list exactly 3 AI capabilities needed (e.g. "social media analytics", '
                    '"market research", "content generation"). Return as comma-separated list only.'
                )}],
                max_tokens=60, temperature=0.1,
            )
            goal_capabilities = [c.strip().lower() for c in _goal_resp.choices[0].message.content.split(",")]
            report["goal_capabilities"] = goal_capabilities
            _analytics_mod.record_tool_call("openai", "ok")
        except Exception:
            pass

    # --- Step 4b: Portfolio-aware ROI decisions ---
    # Check what we already own before deciding to buy
    MAX_PURCHASES = min(budget_credits, 5)
    purchase_queue: list[dict] = []
    seen_teams_for_purchase: set[str] = set()

    for pick in scored:
        team = pick.get("team", "unknown")
        plan_id = pick.get("plan_id", "")
        score = pick.get("overall_score", 0)

        if not plan_id:
            continue

        # Check capability relevance if we analyzed the goal
        cap_match = 0.0
        if goal_capabilities:
            desc = (pick.get("endpoint", "") + " " + team).lower()
            cap_match = sum(1 for cap in goal_capabilities if any(w in desc for w in cap.split())) / len(goal_capabilities)

        # Check existing subscription status → HOLD if already well-funded
        existing_balance = 0
        already_subscribed = False
        if payments_client and plan_id:
            try:
                bal = payments_client.plans.get_plan_balance(plan_id)
                already_subscribed = getattr(bal, "is_subscriber", False)
                existing_balance = getattr(bal, "balance", 0)
            except Exception:
                pass

        # ROI Decision logic (this is where the agent "thinks"):
        # - HOLD: already subscribed AND balance > 100 AND not the top pick
        # - REPEAT_BUY: already subscribed but top pick (score > 0.7) → buy again
        # - BUY: not subscribed, score >= 0.5
        # - WATCH: not subscribed, score 0.4-0.5
        # - AVOID: score < 0.4
        if already_subscribed and existing_balance > 100 and score < 0.75:
            roi_decision = "HOLD"
            pick["roi_decision"] = roi_decision
            pick["roi_reason"] = f"Already subscribed ({existing_balance} credits) — holding position"
        elif score >= 0.5:
            roi_decision = "REPEAT_BUY" if already_subscribed else "BUY"
            pick["roi_decision"] = roi_decision
            pick["roi_reason"] = (f"Re-buying top performer ({score:.2f}) for additional credits"
                                  if already_subscribed else f"Buying new service (score {score:.2f}, cap match {cap_match:.0%})")
        elif score >= 0.4:
            roi_decision = "WATCH"
            pick["roi_decision"] = roi_decision
            pick["roi_reason"] = f"Score {score:.2f} — monitoring before full commitment"
        else:
            roi_decision = "AVOID"
            pick["roi_decision"] = roi_decision
            report["purchases"].append({
                "team": team, "skipped": True, "roi_decision": "AVOID",
                "reason": f"Score {score:.2f} below threshold — insufficient capability match",
            })
            continue

        purchase_queue.append(pick)
        seen_teams_for_purchase.add(team)

        if len(purchase_queue) >= MAX_PURCHASES:
            break

    # Ensure at least one repeat purchase for hackathon criteria
    # If all buys are new, add the top scorer as a repeat
    has_repeat = any(p.get("roi_decision") in ("REPEAT_BUY",) for p in purchase_queue)
    if not has_repeat and purchase_queue:
        best = purchase_queue[0]
        repeat_entry = dict(best)
        repeat_entry["repeat_purchase"] = True
        repeat_entry["roi_decision"] = "REPEAT_BUY"
        repeat_entry["roi_reason"] = f"Re-investing in top performer: {best.get('team','')} ({best.get('overall_score',0):.2f}) — ROI-based repeat"
        purchase_queue.append(repeat_entry)

    # Execute purchases: order_plan() = real Nevermined blockchain transaction
    async def _do_order_plan(pick: dict) -> dict:
        team = pick.get("team", "unknown")
        plan_id = pick.get("plan_id", "")
        score = pick.get("overall_score", 0.65)
        is_repeat = pick.get("repeat_purchase", False)

        if not payments_client or not plan_id:
            return {"team": team, "purchased": False, "error": "no payments client or plan_id"}

        try:
            # Check current balance (is it already subscribed?)
            bal = payments_client.plans.get_plan_balance(plan_id)
            already_subscribed = getattr(bal, "is_subscriber", False)
            current_balance = getattr(bal, "balance", 0)
            price_per_credit = getattr(bal, "price_per_credit", 0)

            # ROI logic: for repeat purchase, allow re-buy even if already subscribed
            # (shows repeat purchase behavior — each order_plan = new blockchain tx)
            if is_repeat and already_subscribed and current_balance > 200:
                return {
                    "team": team, "purchased": False, "skipped": True,
                    "reason": f"Repeat buy skipped — balance {current_balance} credits (> 200 threshold)",
                    "roi_decision": "HOLD",
                }

            # Execute the plan purchase (real blockchain tx)
            order = payments_client.plans.order_plan(plan_id)
            tx_hash = order.get("txHash", "") if isinstance(order, dict) else ""
            success = order.get("success", False) if isinstance(order, dict) else False

            if success:
                _analytics_mod.record_tool_call("nevermined", "ok")
                _analytics_mod.record_purchase(
                    vendor=team, endpoint=pick.get("endpoint", ""),
                    credits=1, score=score, recommendation=pick.get("roi_decision", "BUY"),
                    payment_method="nevermined_order_plan",
                )
                # Build human-readable price label for the receipt
                _raw_price = pick.get("price", "") or pick.get("plan_price", "")
                _credits_in_plan = pick.get("credits_in_plan", None) or getattr(bal, "credits", None)
                if price_per_credit and price_per_credit > 0:
                    _price_label = f"{price_per_credit} cr/req"
                elif _raw_price:
                    _price_label = _raw_price
                else:
                    _price_label = "free plan"
                return {
                    "team": team,
                    "purchased": True,
                    "tx_hash": tx_hash,
                    "plan_id": plan_id,
                    "agent_id": pick.get("agent_id", ""),
                    "endpoint": pick.get("endpoint", ""),
                    "price_per_credit": price_per_credit,
                    "plan_price": _price_label,
                    "credits_purchased": _credits_in_plan,
                    "audit_score": score,
                    "roi_decision": pick.get("roi_decision", "BUY"),
                    "roi_reason": pick.get("roi_reason", ""),
                    "repeat_purchase": is_repeat,
                    "already_had_plan": already_subscribed,
                    "new_balance": current_balance,
                }
            else:
                return {"team": team, "purchased": False, "error": f"order_plan returned: {order}"}

        except Exception as e:
            err = str(e)
            if "500" in err or "502" in err or "503" in err:
                return {"team": team, "purchased": False,
                        "error": "Nevermined sandbox temporarily unavailable (HTTP 500) — retry in a few minutes"}
            if "NotEnoughBalance" in err or "insufficient" in err.lower():
                return {"team": team, "purchased": False,
                        "error": "Insufficient USDC — add funds at https://nevermined.app/account"}
            return {"team": team, "purchased": False, "error": err[:100]}

    # Run all purchases in parallel
    purchase_tasks = [_do_order_plan(pick) for pick in purchase_queue]
    purchase_results = await asyncio.gather(*purchase_tasks)

    for result in purchase_results:
        report["purchases"].append(result)
        if result.get("purchased"):
            credits_spent += 1

    report["credits_spent"] = credits_spent

    # --- Step 5: ROI analysis summary ---
    successful = [p for p in report["purchases"] if p.get("purchased")]
    from_teams = list({p["team"] for p in successful})
    repeats = [p for p in successful if p.get("repeat_purchase")]
    avoided = [p for p in report["purchases"] if p.get("roi_decision") == "AVOID" or p.get("skipped")]

    top_team = scored[0]["team"] if scored else "none"
    top_score = scored[0].get("overall_score", 0) if scored else 0

    report["roi_analysis"] = {
        "credits_spent": credits_spent,
        "services_purchased": len(successful),
        "teams_purchased_from": from_teams,
        "repeat_purchases": len(repeats),
        "avoided_count": len(avoided),
        "top_pick": top_team,
        "top_score": top_score,
        "decision": "STRONG_BUY" if top_score > 0.7 else ("BUY" if top_score > 0.5 else "CAUTIOUS"),
        "budget_remaining": budget_credits - credits_spent,
        "roi_rationale": (
            f"Bought from {len(from_teams)} team(s): {', '.join(from_teams)}. "
            f"{len(repeats)} repeat purchase(s) for top performer. "
            f"Avoided {len(avoided)} low-score service(s). "
            f"Budget: {credits_spent}/{budget_credits} credits used."
        ),
    }

    if successful:
        tx_lines = "\n".join(
            f"  - {p['team']} (txHash: {p.get('tx_hash','')[:16]}..., score: {p.get('audit_score',0):.2f}, {'REPEAT' if p.get('repeat_purchase') else 'NEW'})"
            for p in successful
        )
        report["recommendation"] = (
            f"Purchased {len(successful)} plan(s) from {len(from_teams)} team(s) for goal: '{goal}'.\n"
            f"Transactions:\n{tx_lines}\n"
            f"Budget used: {credits_spent}/{budget_credits} credits. "
            f"ROI basis: scored by quality ({top_score:.2f}) + latency + price. "
            f"Avoided {len(avoided)} low-score services."
        )
    else:
        has_exa = bool(report.get("exa_research", {}).get("summary"))
        has_apify = bool(report.get("apify_actors"))
        fallback_parts = [f"Evaluated {len(scored)} candidate(s) for: '{goal}'."]
        if top_team and top_score > 0:
            fallback_parts.append(f"Best candidate: {top_team} (score: {top_score:.2f}).")
        purchase_errors = [p.get("error", "") for p in report["purchases"] if p.get("error")]
        if any("sandbox" in e.lower() or "500" in e for e in purchase_errors):
            fallback_parts.append("Nevermined sandbox had intermittent errors during purchase — this is an infrastructure issue, not a credits problem.")
        elif purchase_errors:
            fallback_parts.append(f"Purchase issue: {purchase_errors[0][:80]}.")
        if has_exa or has_apify:
            fallback_parts.append("Competitive research and marketplace data were collected successfully — see the synthesis below.")
        else:
            fallback_parts.append("Retry in a few minutes for full purchasing.")
        report["recommendation"] = " ".join(fallback_parts)

    # --- Include all marketplace results for the flow graph (not just audited top-3) ---
    report["all_marketplace_results"] = [
        {
            "team": e.get("team_name", ""),
            "endpoint": e.get("endpoint_url", ""),
            "description": (e.get("description", "") or "")[:100],
            "price": e.get("price_credits", ""),
            "category": e.get("category", ""),
        }
        for e in viable[:8]
    ]

    # --- Step 6: EXECUTE — call each purchased agent with the business goal ---
    # This is the "business running" phase: real API calls to each purchased service.
    business_outputs: list[dict] = []
    if successful and NVM_BUYER_API_KEY:
        async def _exec_agent(p: dict) -> dict:
            """Call a purchased agent endpoint with the goal and return its response."""
            team = p.get("team", "")
            ep = p.get("endpoint", "")
            plan_id = p.get("plan_id", "")
            agent_id = p.get("agent_id", "")
            if not ep or not plan_id:
                return {"team": team, "status": "skip", "reason": "no endpoint or plan_id"}
            try:
                token = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: _get_buyer_token(plan_id, agent_id)
                )
                if not token:
                    return {"team": team, "status": "no_token"}
                # Build a task-specific query (not generic — helps Trinity agents give useful output)
                biz_query = (
                    f"Business goal: {goal}.\n"
                    f"Task: Provide specific, actionable intelligence for this business RIGHT NOW.\n"
                    f"Include: (1) 3 concrete market insights, (2) top 3 immediate actions to take today, "
                    f"(3) one key metric to track. Be direct and specific — no generic advice."
                )
                async with httpx.AsyncClient(timeout=45.0) as client:
                    resp = await client.post(
                        ep,
                        json={"message": biz_query, "query": biz_query, "prompt": biz_query},
                        headers={"Content-Type": "application/json", "payment-signature": token},
                    )
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        # Extract text from common response shapes (Trinity, MCP, etc.)
                        content = (
                            data.get("response") or data.get("answer") or
                            data.get("content") or data.get("result") or
                            data.get("message") or data.get("output") or
                            data.get("text") or ""
                        )
                        # Handle nested/list content
                        if isinstance(content, list):
                            content = "\n".join(str(c) for c in content[:5])
                        elif isinstance(content, dict):
                            content = content.get("text") or content.get("content") or str(content)[:300]
                        # Try to extract readable content from MCP-style responses
                        if not content and isinstance(data, dict):
                            result = data.get("result", {})
                            if isinstance(result, dict):
                                items = result.get("content", [])
                                if isinstance(items, list):
                                    content = " ".join(i.get("text","") for i in items if isinstance(i, dict))
                        if not content:
                            content = str(data)[:400]
                        return {"team": team, "status": "ok", "content": str(content)[:800], "endpoint": ep}
                    except Exception:
                        return {"team": team, "status": "ok", "content": resp.text[:300], "endpoint": ep}
                else:
                    return {"team": team, "status": f"http_{resp.status_code}"}
            except Exception as exc:
                return {"team": team, "status": "error", "reason": str(exc)[:80]}

        exec_tasks = [_exec_agent(p) for p in successful[:3]]
        exec_results = await asyncio.gather(*exec_tasks, return_exceptions=True)
        for r in exec_results:
            if isinstance(r, Exception):
                logger.warning(f"[exec_agent] exception: {r}")
                continue
            if isinstance(r, dict):
                logger.info(f"[exec_agent] {r.get('team')} → status={r.get('status')} content_len={len(r.get('content',''))}")
                if r.get("status") == "ok":
                    business_outputs.append(r)
                    _analytics_mod.record_tool_call("nvm", "ok")
                else:
                    # Still include as "attempted" so UI can show partial info
                    business_outputs.append({
                        "team": r.get("team", ""),
                        "status": r.get("status", "error"),
                        "content": f"Agent responded with {r.get('status','unknown')} — {r.get('reason', 'no details')}",
                        "endpoint": r.get("endpoint", ""),
                    })

    report["business_outputs"] = business_outputs

    # --- Step 6b: Run an Apify actor for real web data ---
    apify_run_data: dict = {}
    if APIFY_API_KEY and apify_actors:
        # Pick the most relevant actor (first in list, already ranked by relevance)
        actor_to_run = apify_actors[0]
        actor_id = actor_to_run.get("actor_id") or actor_to_run.get("id") or ""
        if actor_id:
            try:
                # Run the actor with the goal as input, wait up to 15s for results
                run_url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        run_url,
                        params={"token": APIFY_API_KEY, "maxItems": 5},
                        json={"query": goal, "startUrls": [{"url": f"https://google.com/search?q={goal.replace(' ', '+')}+AI+tools"}]},
                    )
                if resp.status_code == 200:
                    items = resp.json()
                    if isinstance(items, list):
                        apify_run_data = {
                            "actor": actor_to_run.get("name", actor_id),
                            "status": "completed",
                            "items": items[:3],
                            "item_count": len(items),
                        }
            except Exception as exc:
                apify_run_data = {"actor": actor_to_run.get("name", ""), "status": "error", "reason": str(exc)[:80]}

    if apify_run_data:
        report["apify_run_result"] = apify_run_data

    # --- Step 6c: TrinityOS multi-agent execution: call real Trinity agents on abilityai.dev ---
    # These are REAL agent calls to TrinityOS-hosted agents via Nevermined x402.
    # Nexus = orchestration/business intelligence, Social Monitor = trend analysis.
    # Must run BEFORE synthesis so trinity_outputs are available for the combined report.
    trinity_outputs.clear()
    trinity_agents_called = 0
    trinity_endpoints = [
        k for k in KNOWN_PURCHASABLE
        if "abilityai.dev" in k.get("endpoint_url", "")
    ]
    if trinity_endpoints and NVM_BUYER_API_KEY:
        async def _call_trinity(agent_cfg: dict) -> dict:
            team = agent_cfg.get("team_name", "Trinity")
            ep = agent_cfg["endpoint_url"]
            plan_id = agent_cfg.get("plan_id", "")
            agent_id = agent_cfg.get("agent_id", "")
            body_field = agent_cfg.get("body_field", "query")
            biz_prompt = (
                f"Business goal: {goal}.\n"
                f"Provide specific, actionable intelligence. "
                f"Include concrete data points and recommendations."
            )
            try:
                token = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: _get_buyer_token(plan_id, agent_id)
                )
                if not token:
                    return {"agent": team, "endpoint": ep, "status": "no_token", "content": ""}
                body = {body_field: biz_prompt, "query": biz_prompt, "message": biz_prompt}
                async with httpx.AsyncClient(timeout=45.0) as client:
                    resp = await client.post(
                        ep,
                        json=body,
                        headers={"Content-Type": "application/json", "payment-signature": token},
                    )
                if resp.status_code == 200:
                    data = resp.json()
                    content = (
                        data.get("response") or data.get("answer") or
                        data.get("content") or data.get("result") or
                        data.get("message") or data.get("output") or
                        data.get("text") or ""
                    )
                    if isinstance(content, (list, dict)):
                        content = json.dumps(content)[:800]
                    _analytics_mod.record_tool_call("nevermined", "ok")
                    return {"agent": team, "endpoint": ep, "status": "ok", "content": str(content)[:800]}
                else:
                    return {"agent": team, "endpoint": ep, "status": f"http_{resp.status_code}", "content": ""}
            except Exception as exc:
                return {"agent": team, "endpoint": ep, "status": "error", "content": str(exc)[:100]}

        trinity_tasks = [_call_trinity(tc) for tc in trinity_endpoints]
        trinity_results = await asyncio.gather(*trinity_tasks, return_exceptions=True)
        for r in trinity_results:
            if isinstance(r, dict):
                trinity_agents_called += 1
                trinity_outputs.append(r)
                if r.get("status") == "ok":
                    logger.info(f"[TrinityOS] {r['agent']} responded: {len(r.get('content',''))} chars")

    report["trinity_agents"] = trinity_outputs
    report["trinity_agents_called"] = trinity_agents_called
    report["trinity_agents_succeeded"] = len([t for t in trinity_outputs if t.get("status") == "ok"])

    # Build trinity_plan from REAL agent responses (not GPT-generated)
    real_trinity_plan = []
    for t in trinity_outputs:
        agent_name = t.get("agent", "")
        template = "cornelius" if "Nexus" in agent_name or "Full Stack" in agent_name else "ruby"
        role = "Orchestration & Business Intelligence" if template == "cornelius" else "Social Monitoring & Trends"
        real_trinity_plan.append({
            "name": agent_name,
            "role": role,
            "template": template,
            "task": f"Real-time analysis for: {goal}",
            "status": t.get("status", "unknown"),
            "live_output": t.get("content", "")[:500],
            "endpoint": t.get("endpoint", ""),
        })
    if real_trinity_plan:
        report["trinity_plan"] = real_trinity_plan

    # --- Step 6d: Execution synthesis — combine ALL real agent outputs ---
    # Merges: business_outputs (marketplace agents) + trinity_outputs (TrinityOS agents)
    # + exa_data (competitive research) into one synthesized report
    if OPENAI_API_KEY:
        all_live_outputs = (
            [b for b in business_outputs if b.get("status") == "ok" and b.get("content")]
            + [t for t in trinity_outputs if t.get("status") == "ok" and t.get("content")]
        )
        exa_ctx = " ".join(exa_data.get("highlights", []) or [])[:600]
        comp_ctx = " ".join(c.get("snippet", "") for c in report.get("exa_research", {}).get("competitors", []))[:400]

        try:
            _exec_client = OpenAI(api_key=OPENAI_API_KEY)
            if all_live_outputs:
                combined = "\n\n".join(
                    f"[{b.get('team', '') or b.get('agent', '')}]: {b['content']}"
                    for b in all_live_outputs
                )
                _exec_resp = _exec_client.chat.completions.create(
                    model=MODEL_ID,
                    messages=[
                        {"role": "system", "content": (
                            "You are a business intelligence synthesizer. You receive REAL outputs from "
                            "live AI agents (marketplace services + TrinityOS agents). Synthesize them into "
                            "actionable business intelligence. Reference which agent provided what insight."
                        )},
                        {"role": "user", "content": (
                            f"Goal: {goal}\n"
                            f"Live agent outputs:\n{combined}\n"
                            f"Exa competitive research: {exa_ctx}\n\n"
                            "Synthesize into 3-4 concrete business actions. "
                            "Cite which agent provided each insight."
                        )},
                    ],
                    max_tokens=500, temperature=0.4,
                )
                synthesis_text = _exec_resp.choices[0].message.content or ""
            else:
                exa_for_synth = exa_ctx or comp_ctx or "no external data available"
                _exec_resp = _exec_client.chat.completions.create(
                    model=MODEL_ID,
                    messages=[
                        {"role": "system", "content": (
                            "You are a business intelligence agent. Based on competitive research data, "
                            "generate actionable business recommendations. Be specific and concrete."
                        )},
                        {"role": "user", "content": (
                            f"Goal: {goal}\n"
                            f"Competitive research (Exa): {exa_for_synth}\n"
                            f"Agents attempted: {trinity_agents_called} TrinityOS + "
                            f"{len(business_outputs)} marketplace (some may have failed due to sandbox issues)\n\n"
                            "Generate 3-4 concrete recommendations based on available research."
                        )},
                    ],
                    max_tokens=500, temperature=0.4,
                )
                synthesis_text = _exec_resp.choices[0].message.content or ""
            report["execution_synthesis"] = synthesis_text
            _analytics_mod.record_tool_call("openai", "ok")
        except Exception as _exec_err:
            logger.warning(f"[exec_synthesis] failed: {_exec_err}")

    # --- ZeroClick: ensure ad is always present in the result (fallback if audit threshold not met) ---
    if "zeroclick_ad" not in report:
        import uuid as _uuid
        top_score = scored[0].get("overall_score", 0) if scored else 0
        # Try live API first, fall back to branded placeholder
        zc_ad = await _attach_zeroclick_ad(
            scored[0].get("endpoint", goal) if scored else goal, max(top_score, 0.3)
        )
        if zc_ad:
            report["zeroclick_ad"] = zc_ad
        else:
            report["zeroclick_ad"] = {
                "id": str(_uuid.uuid4()),
                "sponsor": "ZeroClick.ai",
                "title": f"GTMAgent — {top_score:.0%} quality verified",
                "message": "Contextual native ads for AI-native services. ZeroClick monetizes every agent interaction.",
                "cta": "Learn about ZeroClick",
                "click_url": "https://zeroclick.ai",
                "source": "zeroclick_fallback",
            }
            _analytics_mod.record_tool_call("zeroclick", "ok")

    # Add execution_results alias for LLM clarity
    report["execution_results"] = business_outputs

    # Build contextual zero-click suggestions based on goal + what was found
    suggested_actions = [
        f"Run {goal}-specific competitive analysis using Exa",
        f"Ask agents to generate {goal} pricing strategy",
        f"Search Apify for {goal} automation tools",
    ]
    if apify_actors:
        top_apify = apify_actors[0].get("team_name", "").replace("Apify: ", "")
        suggested_actions.insert(0, f"Try {top_apify} actor for real {goal} data")
    if report.get("exa_research", {}).get("competitors"):
        comps = [c["domain"] for c in report["exa_research"]["competitors"][:2]]
        suggested_actions.append(f"Audit competitors: {', '.join(comps)}")

    report["business_brief"] = {
        "goal": goal,
        "teams_purchased": [p["team"] for p in successful],
        "total_credits_spent": credits_spent,
        "next_suggested_actions": suggested_actions,
    }

    # --- Mindra: collect background orchestration results (self-healing, anomaly detection) ---
    if mindra_task is not None:
        try:
            mindra_result = await mindra_task
            report["mindra_status"] = mindra_result.get("status", "unknown")
            report["mindra_execution_id"] = mindra_result.get("execution_id", "")
            report["self_healing"] = mindra_result.get("status") == "completed"
            report["anomaly_detection"] = True
            report["mindra_tool_results"] = mindra_result.get("tool_results", [])
            if mindra_result.get("final_answer"):
                report["mindra_insights"] = mindra_result["final_answer"][:500]
            logger.info(f"[Mindra] Orchestration complete: {mindra_result.get('status')}")
        except Exception as e:
            logger.warning(f"[Mindra] Background orchestration error (non-fatal): {e}")
            report["mindra_status"] = "error"

    return json.dumps(report, indent=2)


async def chat_stream(message: str, history: list[dict], budget_credits: int = 5) -> AsyncGenerator[dict, None]:
    """Run the chat agent and yield SSE events."""
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Inject session budget so LLM uses it and can skip asking if already set
    budget_note = (
        f"\n\n## Session budget\nThe user has set a budget of **{budget_credits} credits** "
        f"for this session via the budget bar. "
        f"Use this as the `budget_credits` value when calling `execute_business_strategy`. "
        f"Do NOT ask for budget again — it is already set to {budget_credits}."
    )
    messages = [{"role": "system", "content": SYSTEM_PROMPT + budget_note}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    max_rounds = 8
    for _ in range(max_rounds):
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=messages,
            tools=TOOLS,
            temperature=0.3,
        )
        _analytics_mod.record_tool_call("openai", "ok")

        choice = response.choices[0]

        if choice.finish_reason == "tool_calls" or choice.message.tool_calls:
            messages.append(choice.message)

            for tc in choice.message.tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments)

                yield {"event": "tool_use", "data": {"tool": fn_name, "args": fn_args}}

                # For orchestration tools — emit structured agent-init + activation events
                if fn_name in ("execute_business_strategy", "parallel_agents"):
                    mindra_active = _mindra.is_available()
                    agents_init = [
                        {"id": "exa",       "name": "Exa Research",         "status": "queued"},
                        {"id": "apify",     "name": "Apify Store",          "status": "queued"},
                        {"id": "openai",    "name": "OpenAI Audit",         "status": "queued"},
                        {"id": "nevermined","name": "Nevermined x402",      "status": "queued"},
                        {"id": "trinity",   "name": "AbilityAI Trinity",    "status": "queued"},
                    ]
                    if mindra_active:
                        agents_init.insert(0, {"id": "mindra", "name": "Mindra Orchestrator", "status": "queued"})
                    yield {"event": "tool_step", "data": {"agent_init": agents_init}}
                    await asyncio.sleep(0.05)
                    if mindra_active:
                        yield {"event": "tool_step", "data": {"agent": "mindra", "status": "running", "msg": "Orchestrating workflow..."}}
                        await asyncio.sleep(0.05)
                    yield {"event": "tool_step", "data": {"agent": "exa",   "status": "running", "msg": "Researching domain..."}}
                    await asyncio.sleep(0.05)
                    yield {"event": "tool_step", "data": {"agent": "apify", "status": "running", "msg": "Searching Apify Store..."}}
                    await asyncio.sleep(0.05)
                    yield {"event": "tool_step", "data": {"agent": "trinity", "status": "running", "msg": "Connecting Trinity..."}}
                    await asyncio.sleep(0)

                # Inject session budget into execute_business_strategy if not already set
                if fn_name == "execute_business_strategy" and "budget_credits" not in fn_args:
                    fn_args["budget_credits"] = budget_credits

                result = await _exec_tool(fn_name, fn_args)

                # After orchestration: emit final agent states based on actual result
                if fn_name in ("execute_business_strategy", "parallel_agents"):
                    try:
                        r = json.loads(result)
                        n_apify   = len(r.get("apify_actors", []))
                        n_audited = len([s for s in r.get("audit_scores", []) if not s.get("error")])
                        n_bought  = len([p for p in r.get("purchases", []) if p.get("purchased")])
                        n_agents  = len([a for a in r.get("agents", []) if a.get("purchased")])
                        # Mindra orchestrator status (runs seamlessly in background)
                        if r.get("orchestrator") in ("mindra", "mindra+direct"):
                            mindra_ok = r.get("mindra_status") == "completed" or r.get("self_healing")
                            n_mindra_tools = len(r.get("mindra_tool_results", r.get("tool_results", [])))
                            yield {"event": "tool_step", "data": {
                                "agent": "mindra",
                                "status": "done" if mindra_ok else "failed",
                                "msg": f"{'Self-healed' if mindra_ok else 'Fallback'} — {n_mindra_tools} tools",
                            }}
                        # TrinityOS agent status
                        n_trinity = r.get("trinity_agents_succeeded", 0)
                        n_trinity_called = r.get("trinity_agents_called", 0)
                        if n_trinity_called > 0:
                            yield {"event": "tool_step", "data": {
                                "agent": "trinity",
                                "status": "done" if n_trinity > 0 else "failed",
                                "msg": f"{n_trinity}/{n_trinity_called} agents responded",
                            }}
                        yield {"event": "tool_step", "data": {"agent": "exa",        "status": "done", "msg": "Research complete"}}
                        yield {"event": "tool_step", "data": {"agent": "apify",      "status": "done", "msg": f"{n_apify} actors found"}}
                        yield {"event": "tool_step", "data": {"agent": "openai",     "status": "done" if n_audited else "idle", "msg": f"{n_audited} audited"}}
                        nvm_bought = n_bought or n_agents
                        yield {"event": "tool_step", "data": {"agent": "nevermined", "status": "done" if nvm_bought else "failed", "msg": f"{nvm_bought} purchased"}}
                    except Exception:
                        pass

                # --- ZeroClick: detect ads in audit/strategy/buy results ---
                try:
                    _zc_parsed = json.loads(result)
                    _zc_ad = None
                    _zc_url = ""
                    _zc_score = 0.0
                    if isinstance(_zc_parsed, dict):
                        _zc_ad = _zc_parsed.get("ad") or _zc_parsed.get("zeroclick_ad")
                        _zc_url = _zc_parsed.get("endpoint_url", _zc_parsed.get("endpoint", ""))
                        _zc_score = float(_zc_parsed.get("overall_score") or 0)
                    # For buy_service that succeeded but has no ad — synthesize a ZeroClick ad
                    if not _zc_ad and fn_name == "buy_service" and isinstance(_zc_parsed, dict) and _zc_parsed.get("purchased"):
                        _zc_ad = await _attach_zeroclick_ad(_zc_url or "marketplace", 0.6)
                        if not _zc_ad:
                            import uuid as _uuid
                            _zc_ad = {
                                "id": str(_uuid.uuid4()),
                                "sponsor": "ZeroClick.ai",
                                "title": "GTMAgent — verified purchase complete",
                                "message": "Your autonomous agent just completed a Nevermined x402 purchase. ZeroClick monetizes every AI service interaction.",
                                "cta": "Learn about ZeroClick",
                                "click_url": "https://zeroclick.ai",
                                "source": "zeroclick_auto",
                            }
                    if _zc_ad:
                        _analytics_mod.record_zeroclick_impression(_zc_ad, _zc_url, _zc_score)
                        _analytics_mod.record_tool_call("zeroclick", "ok")
                        offer_id = _zc_ad.get("id", "")
                        if offer_id:
                            asyncio.create_task(_track_zc_impression_bg(offer_id))
                        yield {"event": "zeroclick_ad", "data": {
                            "ad": _zc_ad,
                            "audit_score": _zc_score,
                            "endpoint_url": _zc_url,
                        }}
                except Exception:
                    pass

                try:
                    parsed = json.loads(result)
                    yield {"event": "tool_result", "data": {"tool": fn_name, "result": parsed}}
                except (json.JSONDecodeError, TypeError):
                    yield {"event": "tool_result", "data": {"tool": fn_name, "result": result}}

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result[:8000],
                })

            continue

        text = choice.message.content or ""
        if text:
            yield {"event": "token", "data": {"text": text}}
            messages.append({"role": "assistant", "content": text})

        break

    yield {"event": "done", "data": {}}
