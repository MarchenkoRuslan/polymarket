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
# Default: "require" for PostgreSQL on Railway / production; ignored for SQLite
DATABASE_SSLMODE = os.getenv("DATABASE_SSLMODE", "require")


def _apply_sslmode(url: str, sslmode: str) -> str:
    """Append sslmode to a PostgreSQL URL if not already present."""
    if not url or not url.startswith("postgresql"):
        return url
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "sslmode" in qs:
        return url
    if sslmode and sslmode != "disable":
        qs["sslmode"] = [sslmode]
        new_query = urlencode(qs, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
    return url


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
