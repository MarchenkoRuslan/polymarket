"""Application settings loaded from environment."""
import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Database
# Railway (and some other PaaS) may provide postgres:// which SQLAlchemy 2.0 rejects
_raw_db_url = os.getenv(
    "DATABASE_URL",
    "postgresql://polymarket:polymarket@localhost:5432/polymarket"
)
_db_url = _raw_db_url.replace("postgres://", "postgresql://", 1) if _raw_db_url else _raw_db_url

# SSL mode for PostgreSQL connections (require, verify-ca, verify-full, prefer, disable)
# Default: "prefer" — tries SSL, falls back to non-SSL if unavailable.
# Use "require" in production (Railway), "disable" for local dev without SSL.
DATABASE_SSLMODE = os.getenv("DATABASE_SSLMODE", "prefer")


def _apply_sslmode(url: str, sslmode: str) -> str:
    """Append sslmode to a PostgreSQL URL if not already present.

    All valid libpq sslmode values (disable, allow, prefer, require,
    verify-ca, verify-full) are forwarded.  The parameter is only
    skipped when *sslmode* is empty / None or when the URL already
    contains an explicit ``sslmode`` query parameter.
    """
    if not url or not url.startswith("postgresql"):
        return url
    if not sslmode:
        return url
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "sslmode" in qs:
        return url
    qs["sslmode"] = [sslmode]
    new_query = urlencode(qs, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


DATABASE_URL = _apply_sslmode(_db_url, DATABASE_SSLMODE)

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

# Max markets to collect detailed data (trades, orderbook) per cycle. 0 = all.
COLLECT_MARKETS_LIMIT = _parse_int("COLLECT_MARKETS_LIMIT", "0")
