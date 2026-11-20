"""Turbine-class reference table (`g36`, `g45`, `g62`).

Rows are created by migration `0003` with the values of `MODELS` in the frontend
(`frontend/AeolusAi.html`, design §6). They are reference data, not user data:
change them only with a new migration, never through the API.
"""

from sqlalchemy import CheckConstraint, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TurbineClass(Base):
    __tablename__ = "turbine_classes"
    __table_args__ = (
        CheckConstraint("v_in > 0 AND v_in < v_rated AND v_rated < v_out", name="speeds_ordered"),
        CheckConstraint("rotor_d_m > 0 AND hub_h_m > 0 AND rated_kw > 0", name="positive_size"),
        # `seeded` = filled by a migration. The test fixtures do not truncate these tables.
        {"info": {"seeded": True}},
    )

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # "g45"
    name: Mapped[str] = mapped_column(String(64))  # "4.5 MW class"
    rotor_d_m: Mapped[int] = mapped_column(Integer)  # rotor diameter D (m)
    hub_h_m: Mapped[int] = mapped_column(Integer)  # hub height H (m)
    rated_kw: Mapped[int] = mapped_column(Integer)  # rated power (kW)
    v_in: Mapped[float] = mapped_column(Float)  # cut-in speed (m/s)
    v_rated: Mapped[float] = mapped_column(Float)  # rated speed (m/s)
    v_out: Mapped[float] = mapped_column(Float)  # cut-out speed (m/s)
    rpm_min: Mapped[float] = mapped_column(Float)
    rpm_max: Mapped[float] = mapped_column(Float)
