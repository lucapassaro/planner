"""Seed Italian public holidays into the database for a range of years."""

import holidays
from sqlalchemy.exc import IntegrityError

from db.engine import get_session, init_db
from db.models import FestivitaItaliana

SEED_YEARS = range(2024, 2032)


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
        it_holidays = holidays.Italy(years=year)
        for data, descrizione in sorted(it_holidays.items()):
            existing = session.query(FestivitaItaliana).filter_by(data=data).first()
            if not existing:
                session.add(
                    FestivitaItaliana(data=data, descrizione=str(descrizione))
                )
                inserted += 1
    return inserted


if __name__ == "__main__":
    init_db()
    n = seed_holidays()
    print(f"Seeded {n} holiday records.")
