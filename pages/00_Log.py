"""Streamlit page: Application log viewer.

Shows recent in-process log records (most recent first).
Useful for debugging Excel imports and other operations.
"""

import pandas as pd
import streamlit as st

from utils.app_logger import clear_records, get_records

st.set_page_config(page_title="Log | IT Planner", layout="wide")
st.title("📋 Log applicazione")
st.caption(
    "Registro degli eventi in-process (max 500 righe). "
    "I log vengono azzerati al riavvio del server."
)

# ─── Controls ─────────────────────────────────────────────────────────────────
col_filter, col_refresh, col_clear = st.columns([3, 1, 1])

with col_filter:
    LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]
    sel_levels = st.multiselect(
        "Filtra per livello",
        LEVELS,
        default=["INFO", "WARNING", "ERROR"],
        key="log_levels",
    )

with col_refresh:
    st.write("")  # spacer
    if st.button("🔄 Aggiorna", use_container_width=True):
        st.rerun()

with col_clear:
    st.write("")
    if st.button("🗑 Svuota log", use_container_width=True):
        clear_records()
        st.success("Log svuotato.")
        st.rerun()

# ─── Records ──────────────────────────────────────────────────────────────────
records = get_records()

if not records:
    st.info("Nessun record nel log. Esegui un'operazione (es. importa un file Excel) per vedere i log.")
    st.stop()

# Apply level filter
if sel_levels:
    records = [r for r in records if r["level"] in sel_levels]

if not records:
    st.info(f"Nessun record per i livelli selezionati: {', '.join(sel_levels)}.")
    st.stop()

st.caption(f"{len(records)} record{'i' if len(records) != 1 else ''} visualizzat{'i' if len(records) != 1 else 'o'}")

# ─── Styled dataframe ─────────────────────────────────────────────────────────
df = pd.DataFrame(records, columns=["ts", "level", "logger", "msg"])
df.columns = ["Ora", "Livello", "Logger", "Messaggio"]

_LEVEL_COLORS = {
    "DEBUG":   "background-color:#f0f0f0; color:#666666",
    "INFO":    "",
    "WARNING": "background-color:#fff3cd; color:#856404",
    "ERROR":   "background-color:#f8d7da; color:#842029",
}


def _style_row(row):
    css = _LEVEL_COLORS.get(row["Livello"], "")
    return [css] * len(row)


styled = df.style.apply(_style_row, axis=1)

st.dataframe(
    styled,
    use_container_width=True,
    hide_index=True,
    height=min(600, 40 + len(records) * 35),
    column_config={
        "Ora": st.column_config.TextColumn("Ora", width="small"),
        "Livello": st.column_config.TextColumn("Livello", width="small"),
        "Logger": st.column_config.TextColumn("Logger", width="small"),
        "Messaggio": st.column_config.TextColumn("Messaggio", width="large"),
    },
)

# ─── Copy all as plain text ───────────────────────────────────────────────────
with st.expander("📋 Copia tutto (testo)"):
    all_text = "\n".join(
        f"[{r['Ora']}] {r['Livello']:<8} {r['Logger']:<12} {r['Messaggio']}"
        for r in records
    )
    st.code(all_text, language=None)
