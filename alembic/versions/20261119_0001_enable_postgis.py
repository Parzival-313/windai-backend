"""enable postgis

Revision ID: 0001
Revises:
Create Date: 2026-11-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The postgis/postgis image usually creates this already; IF NOT EXISTS keeps the
    # migration correct on any plain PostgreSQL that has PostGIS available.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")


def downgrade() -> None:
    # Intentionally a no-op: other extensions (postgis_topology, tiger) depend on
    # postgis in the Docker image, and dropping it would destroy spatial_ref_sys.
    pass
