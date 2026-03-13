"""Application settings loaded from environment."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Database
# Railway (and some other PaaS) may provide postgres:// which SQLAlchemy 2.0 rejects
_raw_db_url = os.getenv(
    "DATABASE_URL",
    "postgresql://polymarket:polymarket@localhost:5432/polymarket"
)
DATABASE_URL = _raw_db_url.replace("postgres://", "postgresql://", 1) if _raw_db_url else _raw_db_url

# Polymarket API
POLYMARKET_CLOB_API = os.getenv("POLYMARKET_CLOB_API", "https://clob.polymarket.com")
POLYMARKET_GAMMA_API = os.getenv("POLYMARKET_GAMMA_API", "https://gamma-api.polymarket.com")

# PMXT archive
PMXT_ARCHIVE_URL = os.getenv("PMXT_ARCHIVE_URL", "https://archive.pmxt.dev")

def _parse_int(name: str, default: str) -> int:
    val = os.getenv(name, default)
    try:
        return int(val)
    except (TypeError, ValueError):
        return int(default)


# Fee (basis points, 30 = 0.3%)
DEFAULT_FEE_BPS = _parse_int("DEFAULT_FEE_BPS", "30")

# Rate limits (requests per minute)
API_RATE_LIMIT = _parse_int("API_RATE_LIMIT", "100")
