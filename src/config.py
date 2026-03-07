import os
from pathlib import Path
from dotenv import load_dotenv

# Try .env in cwd first, then walk up to find it, then check known locations
_env_paths = [
    Path(".env"),
    Path(__file__).parent / ".env",
    Path(__file__).parent.parent / ".env",
    Path(__file__).parent.parent / "hackathons/agents/gtm-agent/.env",
]
for _p in _env_paths:
    if _p.exists():
        load_dotenv(_p, override=False)
        break
else:
    load_dotenv()  # fallback: search default locations

# --- Seller (creates/verifies payments) ---
NVM_API_KEY = os.environ.get("NVM_API_KEY", "")
NVM_ENVIRONMENT = os.environ.get("NVM_ENVIRONMENT", "sandbox")
NVM_PLAN_ID = os.environ.get("NVM_PLAN_ID", "")
NVM_AGENT_ID = os.environ.get("NVM_AGENT_ID", "")
# Additional accepted plan IDs (e.g. GTMAgentUSDC) — comma-separated
_extra = os.environ.get("NVM_EXTRA_PLAN_IDS", "")
NVM_EXTRA_PLAN_IDS: list[str] = [p.strip() for p in _extra.split(",") if p.strip()]
# All plan IDs this server accepts (primary + extras)
NVM_ACCEPTED_PLAN_IDS: list[str] = ([NVM_PLAN_ID] if NVM_PLAN_ID else []) + NVM_EXTRA_PLAN_IDS

# --- Buyer (separate account that *purchases* from the plan, e.g. justin.07823@gmail.com) ---
# If not set, falls back to NVM_API_KEY (self-buy from same account — only works if
# the seller account also purchased its own plan).
NVM_BUYER_API_KEY = os.environ.get("NVM_BUYER_API_KEY", "") or NVM_API_KEY

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL_ID = os.environ.get("MODEL_ID", "gpt-4o-mini")

EXA_API_KEY = os.environ.get("EXA_API_KEY", "")
ZEROCLICK_API_KEY = os.environ.get("ZEROCLICK_API_KEY", "")
APIFY_API_KEY = os.environ.get("APIFY_API_KEY", "")
MINDRA_API_KEY = os.environ.get("MINDRA_API_KEY", "")
MINDRA_WORKFLOW_SLUG = os.environ.get("MINDRA_WORKFLOW_SLUG", "gtmagent")

MARKETPLACE_CSV_URL = os.environ.get("MARKETPLACE_CSV_URL", "")

# Purchasable agents are discovered dynamically from the Nevermined marketplace.
# No hardcoded/preset agents — everything is fetched from the Discovery API.
KNOWN_PURCHASABLE: list[dict] = []

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
