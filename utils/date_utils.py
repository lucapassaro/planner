"""Date and month utility functions."""

from datetime import date
from typing import List, Tuple


MESI_IT = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]

MESI_SHORT = [
    "Gen", "Feb", "Mar", "Apr", "Mag", "Giu",
    "Lug", "Ago", "Set", "Ott", "Nov", "Dic",
]


def mese_str_to_label(mese: str, short: bool = False) -> str:
    """Convert 'YYYY-MM' to an Italian month label.

    Args:
        mese: Month string in 'YYYY-MM' format.
        short: If True, use abbreviated month name.

    Returns:
        Formatted label like 'Gennaio 2026' or 'Gen 26'.
    """
    parts = mese.split("-")
    anno, m = int(parts[0]), int(parts[1])
    if short:
        return f"{MESI_SHORT[m - 1]} {str(anno)[2:]}"
    return f"{MESI_IT[m - 1]} {anno}"


def mesi_in_anno(anno: int) -> List[str]:
    """Return all 12 month strings for a year in 'YYYY-MM' format.

    Args:
        anno: Four-digit year.

    Returns:
        List of 12 strings ['YYYY-01', 'YYYY-02', ..., 'YYYY-12'].
    """
    return [f"{anno}-{m:02d}" for m in range(1, 13)]


def parse_mese(mese: str) -> Tuple[int, int]:
    """Parse a 'YYYY-MM' string into (anno, mese) integers.

    Args:
        mese: Month string in 'YYYY-MM' format.

    Returns:
        Tuple of (anno, mese) integers.

    Raises:
        ValueError: If the format is invalid.
    """
    try:
        parts = mese.split("-")
        if len(parts) != 2:
            raise ValueError
        anno, m = int(parts[0]), int(parts[1])
        if not (1 <= m <= 12):
            raise ValueError
        return anno, m
    except (ValueError, AttributeError):
        raise ValueError(f"Formato mese non valido: '{mese}'. Usare YYYY-MM.")


def anni_disponibili(start: int = 2024, end: int = 2031) -> List[int]:
    """Return a list of years available for selection.

    Args:
        start: First year (inclusive).
        end: Last year (exclusive).

    Returns:
        List of integers.
    """
    return list(range(start, end))
