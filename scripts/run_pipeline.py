"""Run features + ML pipeline (for cron)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.feature_store.main import main as run_features
from services.ml_module.main import main as run_ml


def main():
    run_features()
    run_ml()


if __name__ == "__main__":
    main()
