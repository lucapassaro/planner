"""Pandas DataFrame styling helpers for the allocation table view."""

import pandas as pd


def style_allocation_cell(val) -> str:
    """Return CSS background color for an allocation percentage cell.

    Color scale:
    - 0%: white (no allocation)
    - 1-79%: light green (OK)
    - 80-99%: yellow (warning)
    - 100%: green (fully allocated)
    - >100%: red (overallocated)

    Args:
        val: Cell value (numeric or NaN).

    Returns:
        CSS style string.
    """
    try:
        v = float(val)
    except (TypeError, ValueError):
        return ""

    if v <= 0:
        return ""
    elif v < 80:
        return "background-color: #c6efce; color: #276221"
    elif v < 100:
        return "background-color: #ffeb9c; color: #9c5700"
    elif abs(v - 100) < 1e-9:
        return "background-color: #92d050; color: #215732; font-weight: bold"
    else:
        return "background-color: #ffc7ce; color: #9c0006; font-weight: bold"


def style_allocation_df(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Apply conditional styling to the allocation pivot DataFrame.

    Only numeric columns (month columns) get color-coded.
    Non-numeric columns (name, team, etc.) are left unstyled.

    Args:
        df: DataFrame with allocation data.

    Returns:
        Styled DataFrame.
    """
    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    styler = df.style.applymap(
        style_allocation_cell,
        subset=numeric_cols,
    ).format(
        "{:.1f}",
        subset=numeric_cols,
        na_rep="",
    )

    return styler


def build_pivot_table(
    allocazioni_data: list,
    risorse_map: dict,
    mesi: list,
    value: str = "percentuale",
) -> pd.DataFrame:
    """Build a pivot table: rows=risorse, columns=mesi.

    Args:
        allocazioni_data: List of dicts with keys:
            risorsa_id, risorsa_nome, team, mese, percentuale.
        risorse_map: Dict {risorsa_id: {'nome': str, 'team': str}}.
        mesi: List of 'YYYY-MM' strings (12 months).
        value: Which metric to aggregate ('percentuale').

    Returns:
        DataFrame with risorsa info as index columns and months as value columns.
    """
    if not allocazioni_data:
        return pd.DataFrame(
            columns=["Risorsa", "Team"] + mesi
        )

    df = pd.DataFrame(allocazioni_data)

    pivot = df.pivot_table(
        index=["risorsa_id", "risorsa_nome", "team"],
        columns="mese",
        values=value,
        aggfunc="sum",
        fill_value=0,
    ).reset_index()

    # Ensure all months present
    for m in mesi:
        if m not in pivot.columns:
            pivot[m] = 0.0

    # Rename index columns
    pivot = pivot.rename(columns={"risorsa_nome": "Risorsa", "team": "Team"})
    pivot = pivot.drop(columns=["risorsa_id"], errors="ignore")

    # Reorder columns
    meta_cols = ["Risorsa", "Team"]
    month_cols = [m for m in mesi if m in pivot.columns]
    pivot = pivot[meta_cols + month_cols]

    # Add total column
    pivot["Totale %"] = pivot[month_cols].sum(axis=1)

    return pivot
