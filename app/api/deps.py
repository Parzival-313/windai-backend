"""Shared FastAPI dependencies (`Depends(...)`). `get_current_user` arrives in Step 1."""

from app.db.session import get_db

__all__ = ["get_db"]
