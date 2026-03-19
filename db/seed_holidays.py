"""Seed Italian public holidays into the database for a range of years.

Uses a built-in implementation — no external 'holidays' package required.
Italian public holidays:
  Fixed : Capodanno (1/1), Epifania (6/1), Liberazione (25/4),
          Lavoratori (1/5), Repubblica (2/6), Ferragosto (15/8),
          Ognissanti (1/11), Immacolata (8/12), Natale (25/12),
          Santo Stefano (26/12)
  Variable: Pasqua (Easter Sunday), Pasquetta (Easter Monday)
"""

from datetime import date, timedelta
from typing import Dict

from db.engine import get_session, init_db
from db.models import FestivitaItaliana

SEED_YEARS = range(2024, 2032)

# Fixed holidays: (month, day) -> description
_FIXED_HOLIDAYS: Dict[tuple, str] = {
    (1, 1):   "Capodanno",
    (1, 6):   "Epifania",
    (4, 25):  "Festa della Liberazione",
    (5, 1):   "Festa dei Lavoratori",
    (6, 2):   "Festa della Repubblica",
    (8, 15):  "Ferragosto",
    (11, 1):  "Ognissanti",
    (12, 8):  "Immacolata Concezione",
    (12, 25): "Natale",
    (12, 26): "Santo Stefano",
}


def _easter(year: int) -> date:
    """Compute Easter Sunday for a given year (Anonymous Gregorian algorithm).

    Args:
        year: Four-digit year.

    Returns:
        Date of Easter Sunday.
    """
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    ll = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ll) // 451
    month = (h + ll - 7 * m + 114) // 31
    day = ((h + ll - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _italian_holidays(year: int) -> Dict[date, str]:
    """Return all Italian public holidays for a given year.

    Args:
        year: Four-digit year.

    Returns:
        Dictionary mapping each holiday date to its description.
    """
    result: Dict[date, str] = {}

    # Fixed holidays
    for (month, day), desc in _FIXED_HOLIDAYS.items():
        result[date(year, month, day)] = desc

    # Easter Sunday and Monday
    pasqua = _easter(year)
    result[pasqua] = "Pasqua"
    result[pasqua + timedelta(days=1)] = "Pasquetta (Lunedì dell'Angelo)"

    return result


def seed_holidays_if_needed() -> None:
    """Populate FestivitaItaliana table only if it is empty.

    Safe to call on every app startup — it is a no-op if data already exists.
    """
    with get_session() as session:
        count = session.query(FestivitaItaliana).count()
        if count > 0:
            return
        _do_seed(session)


def seed_holidays(years: range = SEED_YEARS) -> int:
    """Populate FestivitaItaliana for the given years, skipping duplicates.

    Args:
        years: Range of years to seed (default: 2024-2031).

    Returns:
        Number of new holiday records inserted.
    """
    with get_session() as session:
        return _do_seed(session, years)


def _do_seed(session, years: range = SEED_YEARS) -> int:
    """Internal helper that performs the actual insertion.

    Args:
        session: Active SQLAlchemy session.
        years: Range of years to process.

    Returns:
        Number of records inserted.
    """
    inserted = 0
    for year in years:
        for data, descrizione in sorted(_italian_holidays(year).items()):
            existing = session.query(FestivitaItaliana).filter_by(data=data).first()
            if not existing:
                session.add(FestivitaItaliana(data=data, descrizione=descrizione))
                inserted += 1
    return inserted


if __name__ == "__main__":
    init_db()
    n = seed_holidays()
    print(f"Seeded {n} holiday records.")
