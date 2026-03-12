"""Initialize SQLite database for local dev (no Docker)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text

DB_PATH = Path(__file__).resolve().parents[1] / "polymarket.db"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "db" / "schema_sqlite.sql"


def main():
    url = f"sqlite:///{DB_PATH}"
    engine = create_engine(url)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with engine.connect() as conn:
        for stmt in schema.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
        conn.commit()
    print(f"SQLite DB initialized: {DB_PATH}")


if __name__ == "__main__":
    main()
