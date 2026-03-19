"""Streamlit page: Tabular view of allocations (resources x months pivot).

Rows = people, Columns = months.
Values = total allocation % per person per month.
Color coding: green (ok), yellow (near full), red (overallocated).

Also shows person-days and hours per month, and a working-days reference row.
"""

import re

import pandas as pd
import streamlit as st

from db.engine import init_db
from services.allocazione_service import get_allocazioni_by_piano, get_carico_per_risorsa_mese
from services.calendario_service import get_giorni_lavorativi_anno, percentuale_to_giorni
from services.excel_service import export_to_excel
from services.risorsa_service import get_all_risorse
from utils.date_utils import MESI_SHORT, mesi_in_anno

init_db()

st.set_page_config(page_title="Vista Tabellare | IT Planner", layout="wide")
st.title("📊 Vista Tabellare")

# ─── Guard ────────────────────────────────────────────────────────────────────
piano_id = st.session_state.get("piano_id")
piano_nome = st.session_state.get("piano_nome", "")

if not piano_id:
    st.warning("⚠️ Seleziona prima un piano dalla pagina **Piani**.")
    st.stop()

st.caption(f"Piano attivo: **{piano_nome}**")

# ─── Determine year ───────────────────────────────────────────────────────────
anno_match = re.search(r"\b(202\d)\b", piano_nome)
anno = int(anno_match.group(1)) if anno_match else 2026
anno = st.number_input("Anno", min_value=2024, max_value=2031, value=anno, step=1)

mesi = mesi_in_anno(anno)
short_labels = [MESI_SHORT[int(m.split("-")[1]) - 1] for m in mesi]

# ─── Load data ────────────────────────────────────────────────────────────────
carico = get_carico_per_risorsa_mese(piano_id)
risorse = get_all_risorse(only_active=False)
gg_lav = get_giorni_lavorativi_anno(anno)

risorsa_map = {r.id: r for r in risorse}

if not carico:
    st.info("Nessuna allocazione presente nel piano.")
    st.stop()

# ─── Display mode toggle ──────────────────────────────────────────────────────
col_mode, col_dl, _ = st.columns([2, 2, 4])
with col_mode:
    display_mode = st.radio(
        "Unità",
        options=["Percentuale (%)", "Giorni lavorativi", "Ore"],
        horizontal=True,
    )
with col_dl:
    if st.button("📥 Esporta Excel", type="primary"):
        try:
            xlsx_bytes = export_to_excel(piano_id)
            st.download_button(
                label="⬇️ Scarica file",
                data=xlsx_bytes,
                file_name=f"{piano_nome.replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as exc:
            st.error(f"Errore export: {exc}")

st.divider()

# ─── Build pivot table ────────────────────────────────────────────────────────
rows_data = []
for r in risorse:
    r_carico = carico.get(r.id, {})
    any_data = any(r_carico.get(m, 0.0) > 0 for m in mesi)
    if not any_data:
        continue

    row = {"Risorsa": r.nome, "Team": r.team}
    for i, m in enumerate(mesi):
        perc = r_carico.get(m, 0.0)
        m_anno, m_num = int(m.split("-")[0]), int(m.split("-")[1])
        if display_mode == "Percentuale (%)":
            row[short_labels[i]] = round(perc, 1) if perc else None
        elif display_mode == "Giorni lavorativi":
            row[short_labels[i]] = (
                round(percentuale_to_giorni(perc, m_anno, m_num), 1) if perc else None
            )
        else:  # Ore
            row[short_labels[i]] = (
                round(percentuale_to_giorni(perc, m_anno, m_num) * 8, 1) if perc else None
            )
    rows_data.append(row)

if not rows_data:
    st.info("Nessun dato di allocazione per l'anno selezionato.")
    st.stop()

df = pd.DataFrame(rows_data)
month_cols = short_labels

# ─── Style helper ─────────────────────────────────────────────────────────────
def _cell_color(val, mode: str) -> str:
    """Return CSS style for a cell based on its value and display mode."""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return ""
    if v <= 0:
        return ""

    # Normalize to percentage for coloring
    if mode == "Percentuale (%)":
        pct = v
    elif mode == "Giorni lavorativi":
        # Rough normalization: 22 max working days
        pct = (v / 22) * 100
    else:  # Ore
        pct = (v / 176) * 100  # 22 days * 8h

    if pct < 80:
        return "background-color: #c6efce; color: #276221"
    elif pct < 100:
        return "background-color: #ffeb9c; color: #9c5700"
    elif pct <= 100:
        return "background-color: #92d050; color: #215732; font-weight: bold"
    else:
        return "background-color: #ffc7ce; color: #9c0006; font-weight: bold"


mode = display_mode
styled = df.style.applymap(
    lambda v: _cell_color(v, mode),
    subset=month_cols,
)

if display_mode == "Percentuale (%)":
    styled = styled.format("{:.1f}%", subset=month_cols, na_rep="—")
elif display_mode == "Giorni lavorativi":
    styled = styled.format("{:.1f}", subset=month_cols, na_rep="—")
else:
    styled = styled.format("{:.0f}h", subset=month_cols, na_rep="—")

# ─── Render table ─────────────────────────────────────────────────────────────
st.subheader(f"Carico per persona — {anno}")

# Overallocation summary
all_over = [
    (r.nome, m, carico[r.id][m])
    for r in risorse
    for m in mesi
    if carico.get(r.id, {}).get(m, 0.0) > 100.0 + 1e-9
]
if all_over:
    st.error(
        f"⚠️ **{len(all_over)} overallocation** rilevate — "
        "celle in rosso nella tabella. Usa la pagina **Ottimizzazione** per i suggerimenti."
    )

st.dataframe(styled, use_container_width=True, height=min(600, 80 + len(rows_data) * 38))

# ─── Working days reference row ───────────────────────────────────────────────
with st.expander("📅 Giorni lavorativi per mese"):
    gg_row = {
        "Info": "Giorni lavorativi",
        **{short_labels[i]: gg_lav[i + 1] for i in range(12)},
    }
    st.dataframe(pd.DataFrame([gg_row]), use_container_width=True, hide_index=True)

# ─── Detail by activity (per resource) ───────────────────────────────────────
with st.expander("🔍 Dettaglio allocazioni per risorsa"):
    allocs = get_allocazioni_by_piano(piano_id)
    if not allocs:
        st.info("Nessuna allocazione.")
    else:
        from services.attivita_service import get_attivita_by_piano

        attivita_map = {a.id: a for a in get_attivita_by_piano(piano_id)}

        detail_rows = []
        for alloc in allocs:
            att = attivita_map.get(alloc.attivita_id)
            r = risorsa_map.get(alloc.risorsa_id)
            m_anno, m_num = int(alloc.mese.split("-")[0]), int(alloc.mese.split("-")[1])
            if m_anno != anno:
                continue
            detail_rows.append(
                {
                    "Risorsa": r.nome if r else "N/A",
                    "Team": r.team if r else "N/A",
                    "Attività": att.nome if att else "N/A",
                    "Tipo": att.tipo if att else "N/A",
                    "Gruppo": att.gruppo if att else "N/A",
                    "Stato": att.stato if att else "N/A",
                    "Mese": alloc.mese,
                    "%": alloc.percentuale,
                    "GG": percentuale_to_giorni(alloc.percentuale, m_anno, m_num),
                }
            )

        if detail_rows:
            df_detail = pd.DataFrame(detail_rows).sort_values(["Risorsa", "Mese"])
            st.dataframe(df_detail, use_container_width=True, hide_index=True)
        else:
            st.info(f"Nessuna allocazione per l'anno {anno}.")
