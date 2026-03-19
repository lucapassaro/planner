"""SQLAlchemy ORM models for the IT Resource Planning tool."""

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class Piano(Base):
    """Represents a resource planning instance (plan).

    A plan groups activities and their allocations over a time period.
    """

    __tablename__ = "piani"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    anno: Mapped[int] = mapped_column(Integer, nullable=False, default=2026)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    attivita: Mapped[List["Attivita"]] = relationship(
        "Attivita", back_populates="piano", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Piano(id={self.id}, nome={self.nome!r}, anno={self.anno})"


class Attivita(Base):
    """Represents a work activity (task) within a plan.

    An activity belongs to exactly one plan, has a type (AM/EVO),
    a free-form group label, and a status.
    """

    __tablename__ = "attivita"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    piano_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("piani.id", ondelete="CASCADE"), nullable=False
    )
    gruppo: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    team: Mapped[str] = mapped_column(String(100), nullable=False)
    nome: Mapped[str] = mapped_column(String(500), nullable=False)
    stato: Mapped[str] = mapped_column(String(50), nullable=False, default="Da Confermare")
    effort_gg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    piano: Mapped["Piano"] = relationship("Piano", back_populates="attivita")
    allocazioni: Mapped[List["Allocazione"]] = relationship(
        "Allocazione", back_populates="attivita", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("tipo IN ('AM', 'EVO')", name="ck_attivita_tipo"),
        CheckConstraint(
            "stato IN ('Confermato', 'Da Confermare', 'Sospeso', 'Chiuso')",
            name="ck_attivita_stato",
        ),
    )

    def __repr__(self) -> str:
        return f"Attivita(id={self.id}, nome={self.nome!r}, tipo={self.tipo})"


class Risorsa(Base):
    """Represents a team member (resource/person).

    Resources are shared across all plans and can be allocated to activities.
    Soft deletion is supported via the 'attiva' flag.
    """

    __tablename__ = "risorse"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    team: Mapped[str] = mapped_column(String(100), nullable=False)
    attiva: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    allocazioni: Mapped[List["Allocazione"]] = relationship(
        "Allocazione", back_populates="risorsa"
    )

    def __repr__(self) -> str:
        return f"Risorsa(id={self.id}, nome={self.nome!r}, team={self.team})"


class Allocazione(Base):
    """Represents a time allocation of a resource to an activity for a month.

    The percentage field (0-100) indicates the fraction of the resource's
    working time dedicated to the activity in the given month.

    Backend constraint: the sum of all allocations for one resource in one
    month must not exceed 100%.
    """

    __tablename__ = "allocazioni"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attivita_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("attivita.id", ondelete="CASCADE"), nullable=False
    )
    risorsa_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("risorse.id", ondelete="RESTRICT"), nullable=False
    )
    mese: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    percentuale: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    attivita: Mapped["Attivita"] = relationship("Attivita", back_populates="allocazioni")
    risorsa: Mapped["Risorsa"] = relationship("Risorsa", back_populates="allocazioni")

    __table_args__ = (
        UniqueConstraint("attivita_id", "risorsa_id", "mese", name="uq_allocazione"),
        CheckConstraint(
            "percentuale >= 0 AND percentuale <= 100",
            name="ck_allocazione_percentuale",
        ),
        Index("ix_allocazione_risorsa_mese", "risorsa_id", "mese"),
    )

    def __repr__(self) -> str:
        return (
            f"Allocazione(id={self.id}, risorsa_id={self.risorsa_id}, "
            f"mese={self.mese}, percentuale={self.percentuale})"
        )


class FestivitaItaliana(Base):
    """Represents an Italian public holiday.

    Used for computing working days per month (8h/day, Mon-Fri, minus holidays).
    """

    __tablename__ = "festivita_italiane"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    data: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    descrizione: Mapped[str] = mapped_column(String(200), nullable=False)

    def __repr__(self) -> str:
        return f"FestivitaItaliana(data={self.data}, descrizione={self.descrizione!r})"
