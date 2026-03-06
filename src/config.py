import os
from dotenv import load_dotenv

load_dotenv()

# --- Seller (creates/verifies payments) ---
NVM_API_KEY = os.environ.get("NVM_API_KEY", "")
NVM_ENVIRONMENT = os.environ.get("NVM_ENVIRONMENT", "sandbox")
NVM_PLAN_ID = os.environ.get("NVM_PLAN_ID", "")
NVM_AGENT_ID = os.environ.get("NVM_AGENT_ID", "")

# --- Buyer (separate account that *purchases* from the plan, e.g. justin.07823@gmail.com) ---
# If not set, falls back to NVM_API_KEY (self-buy from same account — only works if
# the seller account also purchased its own plan).
NVM_BUYER_API_KEY = os.environ.get("NVM_BUYER_API_KEY", "") or NVM_API_KEY

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL_ID = os.environ.get("MODEL_ID", "gpt-4o-mini")

EXA_API_KEY = os.environ.get("EXA_API_KEY", "")
ZEROCLICK_API_KEY = os.environ.get("ZEROCLICK_API_KEY", "")
APIFY_API_KEY = os.environ.get("APIFY_API_KEY", "")

MARKETPLACE_CSV_URL = os.environ.get("MARKETPLACE_CSV_URL", "")

# Known purchasable agents — buyer wallet (0x390bd…) is confirmed subscribed to these plans.
# These produce REAL Nevermined x402 transactions when called.
KNOWN_PURCHASABLE = [
    {
        "team_name": "Full Stack Agents",
        "description": "AbilityAI Nexus hub — multi-agent orchestration, business strategy, and AI workflows",
        "endpoint_url": "https://us14.abilityai.dev/api/paid/nexus/chat",
        "plan_id": "62132339823439076950399695238634927378738244877172775303591114485168828025410",
        "agent_id": "38193170898726307123033205989462035601957241449542699022794362936331517059909",
        "price_credits": "free",
        "category": "AI,orchestration",
    },
    {
        # AbilityAI social monitor — same plan as nexus (62132339…), different agent_id
        "team_name": "TrinityAgents",
        "description": "AbilityAI social monitor — real-time social media trend analysis and monitoring",
        "endpoint_url": "https://us14.abilityai.dev/api/paid/social-monitor/chat",
        "plan_id": "62132339823439076950399695238634927378738244877172775303591114485168828025410",
        "agent_id": "102575793179870454885693749389321147500444253017787287080547662366660764018939",
        "body_field": "message",
        "price_credits": "free",
        "category": "social,monitoring,trends",
    },
    {
        # WAGMI / AgentBank — paid plan ($0.01/credit). Subscribe at checkout URL below.
        # Checkout: https://nevermined.app/checkout/22048418573188197583118225823590719469073032209055332683827376109982321424950
        "team_name": "WAGMI",
        "description": "AgentBank — autonomous DeFi deposit and yield optimization agent",
        "endpoint_url": "https://agentbank-nine.vercel.app/api/deposit",
        "plan_id": "22048418573188197583118225823590719469073032209055332683827376109982321424950",
        "agent_id": "103952894214985075133486264961407358632754398912965838438307744576640790529205",
        "price_credits": "$0.01",
        "category": "DeFi,finance,yield",
    },
]

MAX_DAILY_SPEND = int(os.environ.get("MAX_DAILY_SPEND", "100"))
MAX_PER_REQUEST = int(os.environ.get("MAX_PER_REQUEST", "10"))
MAX_VENDOR_PERCENT = float(os.environ.get("MAX_VENDOR_PERCENT", "0.4"))

SELLER_PORT = int(os.environ.get("SELLER_PORT", "3000"))
BUYER_PORT = int(os.environ.get("BUYER_PORT", "8000"))
AUDIT_SERVICE_URL = os.environ.get("AUDIT_SERVICE_URL", "http://localhost:3000")
AUDIT_INTERVAL_SECONDS = int(os.environ.get("AUDIT_INTERVAL_SECONDS", "900"))

_PLACEHOLDER_PREFIXES = ("your-", "sk-your", "sandbox:your")

DEMO_MODE = (
    not NVM_API_KEY
    or any(NVM_API_KEY.endswith(p) or NVM_API_KEY.startswith(p) for p in _PLACEHOLDER_PREFIXES)
    or not NVM_PLAN_ID
    or NVM_PLAN_ID.startswith("your-")
)


def get_payments():
    """Seller-side payments client (for verifying & settling incoming payments)."""
    if DEMO_MODE:
        return None
    from payments_py import Payments, PaymentOptions
    return Payments.get_instance(
        PaymentOptions(nvm_api_key=NVM_API_KEY, environment=NVM_ENVIRONMENT)
    )


def get_buyer_payments():
    """Buyer-side payments client (for generating access tokens to call other agents).
    
    Uses NVM_BUYER_API_KEY if set (the account that purchased the plan).
    Falls back to NVM_API_KEY if they are the same account.
    """
    if DEMO_MODE:
        return None
    from payments_py import Payments, PaymentOptions
    return Payments(
        PaymentOptions(nvm_api_key=NVM_BUYER_API_KEY, environment=NVM_ENVIRONMENT)
    )
