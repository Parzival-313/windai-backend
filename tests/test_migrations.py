"""Migrations and models must agree: after `alembic upgrade head` autogenerate finds nothing.

Catches "changed a model but forgot the migration" before it reaches a real database.
"""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

import app.models  # noqa: F401  - registers models
from app.db.base import Base
from app.db.migrations import include_name, include_object


def test_models_match_migrations(test_database):
    engine = create_engine(test_database)
    with engine.connect() as conn:
        ctx = MigrationContext.configure(
            conn,
            opts={
                "include_name": include_name,
                "include_object": include_object,
                "compare_type": True,
            },
        )
        diff = compare_metadata(ctx, Base.metadata)
    engine.dispose()
    assert diff == [], f"models differ from migrations: {diff}"
