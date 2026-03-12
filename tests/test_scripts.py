"""Tests for scripts - init_local, seed_demo, run_pipeline."""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_init_local_creates_db(tmp_path):
    """init_local creates SQLite DB with schema."""
    from sqlalchemy import create_engine, text

    project_root = Path(__file__).resolve().parents[1]
    schema_path = project_root / "db" / "schema_sqlite.sql"
    if not schema_path.exists():
        pytest.skip("schema_sqlite.sql not found")

    db_path = tmp_path / "polymarket.db"
    with patch("scripts.init_local.DB_PATH", db_path), patch(
        "scripts.init_local.SCHEMA_PATH", schema_path
    ):
        from scripts.init_local import main
        main()

    assert db_path.exists()
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        r = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='markets'"))
        assert r.fetchone() is not None


def test_seed_demo_uses_session_and_inserts():
    """seed_demo runs without error when DB is available."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    mock_session = MagicMock()
    with patch("scripts.seed_demo.SessionLocal", return_value=mock_session):
        from scripts.seed_demo import main
        main()
    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()


def test_run_pipeline_runs_features_and_ml():
    """run_pipeline invokes feature_store and ml_module mains."""
    with patch("scripts.run_pipeline.run_features", MagicMock()) as mock_f, patch(
        "scripts.run_pipeline.run_ml", MagicMock()
    ) as mock_m:
        from scripts.run_pipeline import main
        main()
        mock_f.assert_called_once()
        mock_m.assert_called_once()
