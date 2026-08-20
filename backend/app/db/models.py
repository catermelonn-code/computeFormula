from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    histories: Mapped[list[History]] = relationship(back_populates="user")


class History(Base):
    __tablename__ = "histories"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)
    coal_gangue: Mapped[float | None] = mapped_column(Float, nullable=True)
    fly_ash: Mapped[float | None] = mapped_column(Float, nullable=True)
    limestone: Mapped[float | None] = mapped_column(Float, nullable=True)
    gypsum: Mapped[float | None] = mapped_column(Float, nullable=True)
    carbide_slag: Mapped[float | None] = mapped_column(Float, nullable=True)
    al_so3_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    ca_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    xy_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    user: Mapped[User] = relationship(back_populates="histories")


class ProcessParamRow(Base):
    __tablename__ = "process_params"

    id: Mapped[int] = mapped_column(primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
