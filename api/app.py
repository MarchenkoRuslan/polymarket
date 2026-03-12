"""Re-export app from server module for backward compatibility."""
from server import app

__all__ = ["app"]
