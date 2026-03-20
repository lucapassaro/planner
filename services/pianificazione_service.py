"""Service layer for PianificazioneMensile (activity-level monthly gg/u planning)."""

from typing import Dict

from db.engine import get_session
from db.models import Attivita, PianificazioneMensile


def upsert_pianificazione(attivita_id: int, mese: str, gg_pianificati: float) -> None:
    """Create or update a monthly planning entry.

    If gg_pianificati is 0, the record is deleted (no-op if absent).

    Args:
        attivita_id: Activity primary key.
        mese: Month string in YYYY-MM format.
        gg_pianificati: Planned person-days (must be >= 0).

    Raises:
        ValueError: If gg_pianificati is negative or mese format is invalid.
    """
    if gg_pianificati < 0:
        raise ValueError("I giorni pianificati non possono essere negativi.")
    if len(mese) != 7 or mese[4] != "-":
        raise ValueError(f"Formato mese non valido: {mese!r} (atteso YYYY-MM).")

    with get_session() as session:
        existing = (
            session.query(PianificazioneMensile)
            .filter_by(attivita_id=attivita_id, mese=mese)
            .first()
        )
        if gg_pianificati == 0:
            if existing:
                session.delete(existing)
        elif existing:
            existing.gg_pianificati = gg_pianificati
        else:
            session.add(PianificazioneMensile(
                attivita_id=attivita_id,
                mese=mese,
                gg_pianificati=gg_pianificati,
            ))


def get_pianificazioni_by_piano(piano_id: int) -> Dict[int, Dict[str, float]]:
    """Return a nested dict of planned gg/u keyed by activity and month.

    Args:
        piano_id: Plan primary key.

    Returns:
        {attivita_id: {mese: gg_pianificati}}
    """
    with get_session() as session:
        rows = (
            session.query(PianificazioneMensile)
            .join(Attivita, Attivita.id == PianificazioneMensile.attivita_id)
            .filter(Attivita.piano_id == piano_id)
            .all()
        )
        result: Dict[int, Dict[str, float]] = {}
        for row in rows:
            result.setdefault(row.attivita_id, {})[row.mese] = row.gg_pianificati
        return result
