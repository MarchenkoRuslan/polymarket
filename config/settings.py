"""Application settings loaded from environment."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://polymarket:polymarket@localhost:5432/polymarket"
)

# Polymarket API
POLYMARKET_CLOB_API = os.getenv("POLYMARKET_CLOB_API", "https://clob.polymarket.com")
POLYMARKET_GAMMA_API = os.getenv("POLYMARKET_GAMMA_API", "https://gamma-api.polymarket.com")

# PMXT archive
PMXT_ARCHIVE_URL = os.getenv("PMXT_ARCHIVE_URL", "https://archive.pmxt.dev")

# Fee (basis points, 30 = 0.3%)
DEFAULT_FEE_BPS = int(os.getenv("DEFAULT_FEE_BPS", "30"))

# Rate limits (requests per minute)
API_RATE_LIMIT = int(os.getenv("API_RATE_LIMIT", "100"))
