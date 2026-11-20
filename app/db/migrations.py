"""Alembic autogenerate filters, shared by `alembic/env.py` and the migration test."""

from geoalchemy2 import alembic_helpers

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
