"""CRUD operations for Risorsa (team members / resources)."""

from typing import List, Optional

from sqlalchemy.exc import IntegrityError

from db.engine import get_session
from db.models import Risorsa


def get_all_risorse(only_active: bool = True) -> List[Risorsa]:
    """Return all resources, optionally filtered to active only.

    Args:
        only_active: If True, exclude soft-deleted (inactive) resources.

    Returns:
        List of Risorsa objects (detached), ordered by nome.
    """
    with get_session() as session:
        query = session.query(Risorsa).order_by(Risorsa.nome)
        if only_active:
            query = query.filter(Risorsa.attiva == True)  # noqa: E712
        risorse = query.all()
        session.expunge_all()
        return risorse


def get_risorsa(risorsa_id: int) -> Optional[Risorsa]:
    """Return a single resource by its primary key.

    Args:
        risorsa_id: Primary key of the resource.

    Returns:
        Risorsa object or None if not found.
    """
    with get_session() as session:
        risorsa = session.get(Risorsa, risorsa_id)
        if risorsa:
            session.expunge(risorsa)
        return risorsa


def create_risorsa(nome: str, team: str) -> Risorsa:
    """Create a new resource (team member).

    Args:
        nome: Full name of the person (must be unique).
        team: Team the person belongs to.

    Returns:
        The created Risorsa object.

    Raises:
        ValueError: If name is blank or already exists.
    """
    nome = nome.strip()
    team = team.strip()
    if not nome:
        raise ValueError("Il nome della risorsa non può essere vuoto.")
    if not team:
        raise ValueError("Il team della risorsa non può essere vuoto.")

    try:
        with get_session() as session:
            risorsa = Risorsa(nome=nome, team=team, attiva=True)
            session.add(risorsa)
            session.flush()
            session.expunge(risorsa)
            return risorsa
    except IntegrityError:
        raise ValueError(f"Esiste già una risorsa con nome '{nome}'.")


def update_risorsa(risorsa_id: int, nome: str, team: str) -> Risorsa:
    """Update an existing resource's name and team.

    Args:
        risorsa_id: Primary key of the resource.
        nome: New full name.
        team: New team.

    Returns:
        The updated Risorsa object.

    Raises:
        ValueError: If not found, blank fields, or name collision.
    """
    nome = nome.strip()
    team = team.strip()
    if not nome:
        raise ValueError("Il nome della risorsa non può essere vuoto.")
    if not team:
        raise ValueError("Il team della risorsa non può essere vuoto.")

    try:
        with get_session() as session:
            risorsa = session.get(Risorsa, risorsa_id)
            if not risorsa:
                raise ValueError(f"Risorsa {risorsa_id} non trovata.")
            risorsa.nome = nome
            risorsa.team = team
            session.flush()
            session.expunge(risorsa)
            return risorsa
    except IntegrityError:
        raise ValueError(f"Esiste già una risorsa con nome '{nome}'.")


def deactivate_risorsa(risorsa_id: int) -> None:
    """Soft-delete a resource by setting attiva=False.

    The resource remains in the database and all historical allocations are
    preserved. It will no longer appear in active resource lists.

    Args:
        risorsa_id: Primary key of the resource.

    Raises:
        ValueError: If the resource is not found.
    """
    with get_session() as session:
        risorsa = session.get(Risorsa, risorsa_id)
        if not risorsa:
            raise ValueError(f"Risorsa {risorsa_id} non trovata.")
        risorsa.attiva = False


def reactivate_risorsa(risorsa_id: int) -> None:
    """Re-activate a previously deactivated resource.

    Args:
        risorsa_id: Primary key of the resource.

    Raises:
        ValueError: If the resource is not found.
    """
    with get_session() as session:
        risorsa = session.get(Risorsa, risorsa_id)
        if not risorsa:
            raise ValueError(f"Risorsa {risorsa_id} non trovata.")
        risorsa.attiva = True
