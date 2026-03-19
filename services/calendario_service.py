"""Working-day calendar service using Italian public holidays."""

from datetime import date, timedelta
from typing import Dict, List, Tuple

from db.engine import get_session
from db.models import FestivitaItaliana


def _next_month(anno: int, mese: int) -> Tuple[int, int]:
    """Return the (anno, mese) tuple for the month following the given one."""
    if mese == 12:
        return anno + 1, 1
    return anno, mese + 1


def get_giorni_lavorativi(anno: int, mese: int) -> int:
    """Calculate the number of working days in a given month.

    Excludes Saturdays, Sundays, and Italian public holidays stored in the DB.

    Args:
        anno: Four-digit year.
        mese: Month number (1-12).

    Returns:
        Number of working days in the month.

    Raises:
        ValueError: If anno or mese are out of range.
    """
    if not (1 <= mese <= 12):
        raise ValueError(f"Invalid month: {mese}")
    if anno < 1:
        raise ValueError(f"Invalid year: {anno}")

    start = date(anno, mese, 1)
    anno_fine, mese_fine = _next_month(anno, mese)
    end = date(anno_fine, mese_fine, 1)

    with get_session() as session:
        festivita = {
            f.data
            for f in session.query(FestivitaItaliana)
            .filter(FestivitaItaliana.data >= start, FestivitaItaliana.data < end)
            .all()
        }

    count = 0
    current = start
    while current < end:
        if current.weekday() < 5 and current not in festivita:
            count += 1
        current += timedelta(days=1)
    return count


def get_ore_lavorative(anno: int, mese: int) -> float:
    """Calculate total working hours in a given month (8h per working day).

    Args:
        anno: Four-digit year.
        mese: Month number (1-12).

    Returns:
        Total working hours.
    """
    return get_giorni_lavorativi(anno, mese) * 8.0


def percentuale_to_giorni(percentuale: float, anno: int, mese: int) -> float:
    """Convert an allocation percentage to person-days for a given month.

    Args:
        percentuale: Allocation percentage (0-100).
        anno: Four-digit year.
        mese: Month number (1-12).

    Returns:
        Person-days (fractional).
    """
    giorni = get_giorni_lavorativi(anno, mese)
    return round((percentuale / 100.0) * giorni, 2)


def percentuale_to_ore(percentuale: float, anno: int, mese: int) -> float:
    """Convert an allocation percentage to hours for a given month.

    Args:
        percentuale: Allocation percentage (0-100).
        anno: Four-digit year.
        mese: Month number (1-12).

    Returns:
        Working hours.
    """
    return round(percentuale_to_giorni(percentuale, anno, mese) * 8.0, 2)


def get_giorni_lavorativi_anno(anno: int) -> Dict[int, int]:
    """Get working days for all 12 months of a year.

    Args:
        anno: Four-digit year.

    Returns:
        Dictionary mapping month number (1-12) to working days count.
    """
    return {m: get_giorni_lavorativi(anno, m) for m in range(1, 13)}


def get_festivita_mese(anno: int, mese: int) -> List[FestivitaItaliana]:
    """Return the list of Italian holidays falling in a given month.

    Args:
        anno: Four-digit year.
        mese: Month number (1-12).

    Returns:
        List of FestivitaItaliana objects.
    """
    start = date(anno, mese, 1)
    anno_fine, mese_fine = _next_month(anno, mese)
    end = date(anno_fine, mese_fine, 1)

    with get_session() as session:
        festivita = (
            session.query(FestivitaItaliana)
            .filter(FestivitaItaliana.data >= start, FestivitaItaliana.data < end)
            .order_by(FestivitaItaliana.data)
            .all()
        )
        # Detach from session before returning
        session.expunge_all()
        return festivita
