"""Run collector repeatedly to build price history for real markets."""
import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.collector.main import collect_from_api

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Warmup: run collect N times to build history")
    parser.add_argument("--runs", type=int, default=20, help="Number of collect runs")
    parser.add_argument("--interval", type=int, default=30, help="Seconds between runs")
    args = parser.parse_args()

    logger.info("Warmup: %d runs, %ds interval (~%d min total)", args.runs, args.interval, args.runs * args.interval // 60)
    for i in range(args.runs):
        logger.info("Collect run %d/%d", i + 1, args.runs)
        asyncio.run(collect_from_api())
        if i < args.runs - 1:
            logger.info("Sleeping %ds...", args.interval)
            time.sleep(args.interval)
    logger.info("Warmup done")


if __name__ == "__main__":
    main()
