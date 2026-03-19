"""CRUD operations for Piano (resource plans)."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from db.engine import get_session
from db.models import Piano


def get_all_piani() -> List[Piano]:
    """Return all plans ordered by most recently updated.

    Returns:
        List of Piano objects (detached from session).
    """
    with get_session() as session:
        piani = (
            session.query(Piano).order_by(Piano.updated_at.desc()).all()
        )
        session.expunge_all()
        return piani


def get_piano(piano_id: int) -> Optional[Piano]:
    """Return a single plan by its primary key.

    Args:
        piano_id: Primary key of the plan.

    Returns:
        Piano object or None if not found.
    """
    with get_session() as session:
        piano = session.get(Piano, piano_id)
        if piano:
            session.expunge(piano)
        return piano


def create_piano(nome: str, anno: int = 2026) -> Piano:
    """Create a new plan.

    Args:
        nome: Unique plan name.
        anno: Reference year for the plan (default 2026).

    Returns:
        The created Piano object.

    Raises:
        ValueError: If the name is blank or a plan with that name exists.
    """
    nome = nome.strip()
    if not nome:
        raise ValueError("Il nome del piano non può essere vuoto.")

    try:
        with get_session() as session:
            piano = Piano(nome=nome, anno=anno)
            session.add(piano)
            session.flush()
            session.expunge(piano)
            return piano
    except IntegrityError:
        raise ValueError(f"Esiste già un piano con nome '{nome}'.")


def update_piano(piano_id: int, nome: str, anno: int) -> Piano:
    """Update an existing plan's name and year.

    Args:
        piano_id: Primary key of the plan to update.
        nome: New plan name.
        anno: New reference year.

    Returns:
        The updated Piano object.

    Raises:
        ValueError: If the plan is not found, name is blank, or name is taken.
    """
    nome = nome.strip()
    if not nome:
        raise ValueError("Il nome del piano non può essere vuoto.")

    try:
        with get_session() as session:
            piano = session.get(Piano, piano_id)
            if not piano:
                raise ValueError(f"Piano {piano_id} non trovato.")
            piano.nome = nome
            piano.anno = anno
            piano.updated_at = datetime.now()
            session.flush()
            session.expunge(piano)
            return piano
    except IntegrityError:
        raise ValueError(f"Esiste già un piano con nome '{nome}'.")


def delete_piano(piano_id: int) -> None:
    """Delete a plan and all its activities/allocations (cascade).

    Args:
        piano_id: Primary key of the plan to delete.

    Raises:
        ValueError: If the plan is not found.
    """
    with get_session() as session:
        piano = session.get(Piano, piano_id)
        if not piano:
            raise ValueError(f"Piano {piano_id} non trovato.")
        session.delete(piano)


def touch_piano(piano_id: int) -> None:
    """Update the updated_at timestamp of a plan (call after modifying activities).

    Args:
        piano_id: Primary key of the plan.
    """
    with get_session() as session:
        piano = session.get(Piano, piano_id)
        if piano:
            piano.updated_at = datetime.now()
