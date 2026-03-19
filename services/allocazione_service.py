"""CRUD and validation for Allocazione (resource-to-activity allocations)."""

from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from db.engine import get_session
from db.models import Allocazione, Attivita, Risorsa
from services.piano_service import touch_piano


class OverallocationError(Exception):
    """Raised when an allocation would exceed 100% for a resource in a month."""

    def __init__(self, risorsa_nome: str, mese: str, totale: float, nuova: float):
        self.risorsa_nome = risorsa_nome
        self.mese = mese
        self.totale = totale
        self.nuova = nuova
        super().__init__(
            f"Overallocation: {risorsa_nome} nel mese {mese} "
            f"raggiungerebbe {totale + nuova:.1f}% (max 100%)."
        )


def _check_overallocation(
    session,
    risorsa_id: int,
    mese: str,
    percentuale: float,
    exclude_id: Optional[int] = None,
) -> None:
    """Validate that adding an allocation won't exceed 100% for a resource/month.

    This is the backend enforcement of the overallocation business rule.
    Always called before creating or updating an allocation.

    Args:
        session: Active SQLAlchemy session.
        risorsa_id: Resource to check.
        mese: Month string in 'YYYY-MM' format.
        percentuale: Percentage to add.
        exclude_id: Allocation ID to exclude from the sum (for updates).

    Raises:
        OverallocationError: If the total would exceed 100%.
    """
    query = session.query(func.sum(Allocazione.percentuale)).filter(
        Allocazione.risorsa_id == risorsa_id,
        Allocazione.mese == mese,
    )
    if exclude_id is not None:
        query = query.filter(Allocazione.id != exclude_id)

    existing_total: float = query.scalar() or 0.0

    if existing_total + percentuale > 100.0 + 1e-9:
        risorsa = session.get(Risorsa, risorsa_id)
        nome = risorsa.nome if risorsa else str(risorsa_id)
        raise OverallocationError(nome, mese, existing_total, percentuale)


def get_allocazioni_by_attivita(attivita_id: int) -> List[Allocazione]:
    """Return all allocations for a given activity, ordered by mese then risorsa.

    Args:
        attivita_id: Primary key of the activity.

    Returns:
        List of Allocazione objects (detached).
    """
    with get_session() as session:
        allocs = (
            session.query(Allocazione)
            .filter(Allocazione.attivita_id == attivita_id)
            .order_by(Allocazione.mese, Allocazione.risorsa_id)
            .all()
        )
        session.expunge_all()
        return allocs


def get_allocazioni_by_piano(piano_id: int) -> List[Allocazione]:
    """Return all allocations for a plan (via its activities).

    Args:
        piano_id: Primary key of the plan.

    Returns:
        List of Allocazione objects (detached), with joined Attivita and Risorsa.
    """
    with get_session() as session:
        allocs = (
            session.query(Allocazione)
            .join(Attivita, Allocazione.attivita_id == Attivita.id)
            .filter(Attivita.piano_id == piano_id)
            .order_by(Allocazione.mese, Allocazione.risorsa_id)
            .all()
        )
        session.expunge_all()
        return allocs


def create_allocazione(
    attivita_id: int,
    risorsa_id: int,
    mese: str,
    percentuale: float,
    note: Optional[str] = None,
) -> Allocazione:
    """Create a new allocation with overallocation validation.

    Args:
        attivita_id: Primary key of the activity.
        risorsa_id: Primary key of the resource.
        mese: Month in 'YYYY-MM' format.
        percentuale: Allocation percentage (0-100).
        note: Optional notes.

    Returns:
        The created Allocazione object.

    Raises:
        OverallocationError: If total allocation would exceed 100%.
        ValueError: On invalid inputs or duplicate allocation.
    """
    _validate_percentuale(percentuale)
    _validate_mese(mese)

    try:
        with get_session() as session:
            # Backend overallocation check
            _check_overallocation(session, risorsa_id, mese, percentuale)

            alloc = Allocazione(
                attivita_id=attivita_id,
                risorsa_id=risorsa_id,
                mese=mese,
                percentuale=percentuale,
                note=note,
            )
            session.add(alloc)
            session.flush()

            # Retrieve piano_id for touch
            att = session.get(Attivita, attivita_id)
            piano_id = att.piano_id if att else None

            session.expunge(alloc)

        if piano_id:
            touch_piano(piano_id)
        return alloc

    except IntegrityError:
        raise ValueError(
            f"Esiste già un'allocazione per l'attività {attivita_id}, "
            f"risorsa {risorsa_id} nel mese {mese}."
        )


def update_allocazione(
    allocazione_id: int,
    percentuale: float,
    note: Optional[str] = None,
) -> Allocazione:
    """Update an existing allocation's percentage with overallocation validation.

    Args:
        allocazione_id: Primary key of the allocation.
        percentuale: New allocation percentage (0-100).
        note: Optional notes.

    Returns:
        The updated Allocazione object.

    Raises:
        OverallocationError: If total allocation would exceed 100%.
        ValueError: If the allocation is not found or percentage is invalid.
    """
    _validate_percentuale(percentuale)

    with get_session() as session:
        alloc = session.get(Allocazione, allocazione_id)
        if not alloc:
            raise ValueError(f"Allocazione {allocazione_id} non trovata.")

        # Backend overallocation check (excluding self)
        _check_overallocation(
            session, alloc.risorsa_id, alloc.mese, percentuale, exclude_id=allocazione_id
        )

        alloc.percentuale = percentuale
        alloc.note = note
        # Retrieve piano_id before expunge (while session is open)
        att = session.get(Attivita, alloc.attivita_id)
        piano_id = att.piano_id if att else None
        session.flush()
        session.expunge(alloc)

    if piano_id:
        touch_piano(piano_id)
    return alloc


def delete_allocazione(allocazione_id: int) -> None:
    """Delete an allocation.

    Args:
        allocazione_id: Primary key of the allocation.

    Raises:
        ValueError: If the allocation is not found.
    """
    with get_session() as session:
        alloc = session.get(Allocazione, allocazione_id)
        if not alloc:
            raise ValueError(f"Allocazione {allocazione_id} non trovata.")
        att = session.get(Attivita, alloc.attivita_id)
        piano_id = att.piano_id if att else None
        session.delete(alloc)

    if piano_id:
        touch_piano(piano_id)


def get_carico_per_risorsa_mese(piano_id: int) -> Dict[int, Dict[str, float]]:
    """Compute total allocation % per resource per month for a plan.

    Args:
        piano_id: Primary key of the plan.

    Returns:
        Nested dict: {risorsa_id: {mese: total_percentuale}}
        e.g. {1: {"2026-01": 80.0, "2026-02": 100.0}}
    """
    with get_session() as session:
        rows = (
            session.query(
                Allocazione.risorsa_id,
                Allocazione.mese,
                func.sum(Allocazione.percentuale).label("totale"),
            )
            .join(Attivita, Allocazione.attivita_id == Attivita.id)
            .filter(Attivita.piano_id == piano_id)
            .group_by(Allocazione.risorsa_id, Allocazione.mese)
            .all()
        )

    result: Dict[int, Dict[str, float]] = {}
    for risorsa_id, mese, totale in rows:
        result.setdefault(risorsa_id, {})[mese] = float(totale)
    return result


def get_overallocations(piano_id: int) -> List[Tuple[int, str, float]]:
    """Find all resource-month combinations exceeding 100% in a plan.

    Args:
        piano_id: Primary key of the plan.

    Returns:
        List of (risorsa_id, mese, total_percentuale) tuples where total > 100%.
    """
    carico = get_carico_per_risorsa_mese(piano_id)
    result = []
    for risorsa_id, mesi in carico.items():
        for mese, totale in mesi.items():
            if totale > 100.0 + 1e-9:
                result.append((risorsa_id, mese, totale))
    result.sort(key=lambda x: (x[1], x[0]))
    return result


def _validate_percentuale(percentuale: float) -> None:
    """Validate that percentuale is in [0, 100].

    Args:
        percentuale: Value to validate.

    Raises:
        ValueError: If out of range.
    """
    if not (0 <= percentuale <= 100):
        raise ValueError(f"Percentuale non valida: {percentuale}. Deve essere 0-100.")


def _validate_mese(mese: str) -> None:
    """Validate mese string format YYYY-MM.

    Args:
        mese: Month string to validate.

    Raises:
        ValueError: If format is wrong or month is out of range.
    """
    try:
        parts = mese.split("-")
        if len(parts) != 2:
            raise ValueError
        anno, m = int(parts[0]), int(parts[1])
        if not (1 <= m <= 12):
            raise ValueError
    except (ValueError, AttributeError):
        raise ValueError(f"Formato mese non valido: '{mese}'. Usare YYYY-MM.")
