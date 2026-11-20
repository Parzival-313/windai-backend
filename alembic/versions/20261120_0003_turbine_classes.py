"""turbine classes table, seeded with the frontend's MODELS

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-20 18:00:00

Values are copied from `MODELS` in frontend/AeolusAi.html (design §6). They are frozen
here on purpose: a migration must not import app code, so a later change to a class is a
new migration, not an edit to this one.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TURBINE_CLASSES = [
    {'id': 'g36', 'name': '3.6 MW class', 'rotor_d_m': 120, 'hub_h_m': 90, 'rated_kw': 3600,
     'v_in': 3.0, 'v_rated': 11.5, 'v_out': 25.0, 'rpm_min': 5.5, 'rpm_max': 14.9},
    {'id': 'g45', 'name': '4.5 MW class', 'rotor_d_m': 145, 'hub_h_m': 105, 'rated_kw': 4500,
     'v_in': 3.0, 'v_rated': 11.0, 'v_out': 25.0, 'rpm_min': 4.8, 'rpm_max': 12.3},
    {'id': 'g62', 'name': '6.2 MW class', 'rotor_d_m': 170, 'hub_h_m': 125, 'rated_kw': 6200,
     'v_in': 3.0, 'v_rated': 10.5, 'v_out': 25.0, 'rpm_min': 4.0, 'rpm_max': 10.6},
]


def upgrade() -> None:
    table = op.create_table('turbine_classes',
    sa.Column('id', sa.String(length=16), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('rotor_d_m', sa.Integer(), nullable=False),
    sa.Column('hub_h_m', sa.Integer(), nullable=False),
    sa.Column('rated_kw', sa.Integer(), nullable=False),
    sa.Column('v_in', sa.Float(), nullable=False),
    sa.Column('v_rated', sa.Float(), nullable=False),
    sa.Column('v_out', sa.Float(), nullable=False),
    sa.Column('rpm_min', sa.Float(), nullable=False),
    sa.Column('rpm_max', sa.Float(), nullable=False),
    sa.CheckConstraint('rotor_d_m > 0 AND hub_h_m > 0 AND rated_kw > 0', name=op.f('ck_turbine_classes_positive_size')),
    sa.CheckConstraint('v_in > 0 AND v_in < v_rated AND v_rated < v_out', name=op.f('ck_turbine_classes_speeds_ordered')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_turbine_classes'))
    )
    op.bulk_insert(table, TURBINE_CLASSES)


def downgrade() -> None:
    op.drop_table('turbine_classes')
