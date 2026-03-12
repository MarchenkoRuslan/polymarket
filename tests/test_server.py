"""Tests for server.py - init_db, pipeline status."""
from server import init_db


def test_init_db_does_not_crash():
    """init_db catches errors and does not raise."""
    init_db()
