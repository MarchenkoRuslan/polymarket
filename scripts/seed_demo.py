"""Insert demo data for local testing (no API/PMXT needed)."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import SessionLocal
from services.collector.db_writer import upsert_market, insert_trade

def main():
    session = SessionLocal()
    base = datetime(2025, 1, 1, 12, 0, 0)
    upsert_market(session, {
        "id": "0x_demo_1",
        "question": "Demo market 1?",
        "event_id": "e1",
        "outcome_settled": False,
    })
    upsert_market(session, {
        "id": "0x_demo_2",
        "question": "Demo market 2?",
        "event_id": "e1",
        "outcome_settled": False,
    })
    for i in range(200):
        ts = base + timedelta(minutes=i)
        price = 0.5 + 0.002 * (i % 30) + 0.001 * (i // 50)
        insert_trade(session, "0x_demo_1", ts, min(0.99, max(0.01, price)), 10.0 + i, "buy")
    for i in range(150):
        ts = base + timedelta(minutes=i * 2)
        price = 0.4 + 0.003 * (i % 20)
        insert_trade(session, "0x_demo_2", ts, min(0.99, max(0.01, price)), 5.0, "buy")
    session.commit()
    session.close()
    print("Demo data: 2 markets, 350 trades")

if __name__ == "__main__":
    main()
