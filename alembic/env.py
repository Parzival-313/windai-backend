"""Alembic migration environment.

Alembic is the schema-migration tool (like golang-migrate, but it can also
*autogenerate* a migration by diffing the SQLAlchemy models against the live DB):

    alembic revision --autogenerate -m "add sites"   # write a new migration file
    alembic upgrade head                              # apply all pending migrations
"""

from logging.config import fileConfig

from geoalchemy2 import alembic_helpers
from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401  - registers every model on Base.metadata
from alembic import context
from app.core.config import get_settings
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))

target_metadata = Base.metadata

# Tables owned by PostGIS (the postgis/postgis image also installs tiger/topology
# schemas). Autogenerate must never try to drop them.
POSTGIS_TABLES = {"spatial_ref_sys"}


def include_name(name: str | None, type_: str, parent_names: dict) -> bool:
    if type_ == "schema":
        return name in (None, "public")
    return True


def include_object(obj, name, type_, reflected, compare_to) -> bool:  # type: ignore[no-untyped-def]
    if type_ == "table" and name in POSTGIS_TABLES:
        return False
    return alembic_helpers.include_object(obj, name, type_, reflected, compare_to)


def _configure(**kwargs) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        target_metadata=target_metadata,
        include_name=include_name,
        include_object=include_object,
        process_revision_directives=alembic_helpers.writer,
        render_item=alembic_helpers.render_item,
        compare_type=True,
        **kwargs,
    )


def run_migrations_offline() -> None:
    _configure(url=config.get_main_option("sqlalchemy.url"), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
