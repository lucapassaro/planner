"""CRUD operations for Attivita (activities within a plan)."""

from typing import List, Optional

from sqlalchemy.exc import IntegrityError

from db.engine import get_session
from db.models import Attivita
from services.piano_service import touch_piano

TIPI_VALIDI = ("AM", "EVO")
STATI_VALIDI = ("Confermato", "Da Confermare", "Sospeso", "Chiuso")


def get_attivita_by_piano(piano_id: int) -> List[Attivita]:
    """Return all activities for a plan, ordered by gruppo and nome.

    Args:
        piano_id: Primary key of the parent plan.

    Returns:
        List of Attivita objects (detached).
    """
    with get_session() as session:
        attivita = (
            session.query(Attivita)
            .filter(Attivita.piano_id == piano_id)
            .order_by(Attivita.gruppo, Attivita.nome)
            .all()
        )
        session.expunge_all()
        return attivita


def get_attivita(attivita_id: int) -> Optional[Attivita]:
    """Return a single activity by its primary key.

    Args:
        attivita_id: Primary key of the activity.

    Returns:
        Attivita object or None.
    """
    with get_session() as session:
        att = session.get(Attivita, attivita_id)
        if att:
            session.expunge(att)
        return att


def create_attivita(
    piano_id: int,
    gruppo: str,
    tipo: str,
    team: str,
    nome: str,
    stato: str = "Da Confermare",
    note: Optional[str] = None,
) -> Attivita:
    """Create a new activity within a plan.

    Args:
        piano_id: Primary key of the parent plan.
        gruppo: Free-form group label (e.g., application or initiative name).
        tipo: Activity type — must be 'AM' or 'EVO'.
        team: Team responsible (e.g., 'FEQ', 'DATA').
        nome: Activity name/description.
        stato: Status — must be one of STATI_VALIDI.
        note: Optional free-text notes.

    Returns:
        The created Attivita object.

    Raises:
        ValueError: On invalid tipo, stato, or blank required fields.
    """
    _validate(gruppo, tipo, team, nome, stato)

    with get_session() as session:
        att = Attivita(
            piano_id=piano_id,
            gruppo=gruppo.strip(),
            tipo=tipo,
            team=team.strip(),
            nome=nome.strip(),
            stato=stato,
            note=note,
        )
        session.add(att)
        session.flush()
        session.expunge(att)

    touch_piano(piano_id)
    return att


def update_attivita(
    attivita_id: int,
    gruppo: str,
    tipo: str,
    team: str,
    nome: str,
    stato: str,
    note: Optional[str] = None,
) -> Attivita:
    """Update an existing activity.

    Args:
        attivita_id: Primary key of the activity.
        gruppo: New group label.
        tipo: New type ('AM' or 'EVO').
        team: New team.
        nome: New name.
        stato: New status.
        note: Optional notes.

    Returns:
        The updated Attivita object.

    Raises:
        ValueError: If the activity is not found or validation fails.
    """
    _validate(gruppo, tipo, team, nome, stato)

    with get_session() as session:
        att = session.get(Attivita, attivita_id)
        if not att:
            raise ValueError(f"Attività {attivita_id} non trovata.")
        piano_id = att.piano_id
        att.gruppo = gruppo.strip()
        att.tipo = tipo
        att.team = team.strip()
        att.nome = nome.strip()
        att.stato = stato
        att.note = note
        session.flush()
        session.expunge(att)

    touch_piano(piano_id)
    return att


def delete_attivita(attivita_id: int) -> None:
    """Delete an activity and all its allocations (cascade).

    Args:
        attivita_id: Primary key of the activity.

    Raises:
        ValueError: If the activity is not found.
    """
    with get_session() as session:
        att = session.get(Attivita, attivita_id)
        if not att:
            raise ValueError(f"Attività {attivita_id} non trovata.")
        piano_id = att.piano_id
        session.delete(att)

    touch_piano(piano_id)


def _validate(gruppo: str, tipo: str, team: str, nome: str, stato: str) -> None:
    """Validate activity fields.

    Args:
        gruppo: Group label.
        tipo: Type string.
        team: Team string.
        nome: Name string.
        stato: Status string.

    Raises:
        ValueError: If any field is invalid.
    """
    if not gruppo.strip():
        raise ValueError("Il campo 'Gruppo' non può essere vuoto.")
    if not nome.strip():
        raise ValueError("Il campo 'Nome' non può essere vuoto.")
    if not team.strip():
        raise ValueError("Il campo 'Team' non può essere vuoto.")
    if tipo not in TIPI_VALIDI:
        raise ValueError(f"Tipo non valido: '{tipo}'. Valori ammessi: {TIPI_VALIDI}")
    if stato not in STATI_VALIDI:
        raise ValueError(f"Stato non valido: '{stato}'. Valori ammessi: {STATI_VALIDI}")
