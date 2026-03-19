"""Streamlit page: Overallocation analysis and reallocation suggestions."""

import streamlit as st
import pandas as pd

from db.engine import init_db
from services.ottimizzazione_service import (
    get_riepilogo_overallocation,
    get_suggerimenti,
)

init_db()

st.set_page_config(page_title="Ottimizzazione | IT Planner", layout="wide")
st.title("🔧 Ottimizzazione Allocazioni")

# ─── Guard ────────────────────────────────────────────────────────────────────
piano_id = st.session_state.get("piano_id")
piano_nome = st.session_state.get("piano_nome", "")

if not piano_id:
    st.warning("⚠️ Seleziona prima un piano dalla pagina **Piani**.")
    st.stop()

st.caption(f"Piano attivo: **{piano_nome}**")
st.info(
    "Questa pagina analizza il piano e suggerisce riallocazioni per risolvere "
    "le overallocation. I suggerimenti sono **indicativi** e non vengono applicati "
    "automaticamente — puoi applicarli manualmente dalla pagina **Allocazioni**."
)

# ─── Overallocation summary ───────────────────────────────────────────────────
st.subheader("📋 Riepilogo Overallocation")

overallocations = get_riepilogo_overallocation(piano_id)

if not overallocations:
    st.success("✅ Nessuna overallocation rilevata nel piano. Ottimo lavoro!")
    st.stop()

# Summary metrics
total_over = len(overallocations)
max_excess = max(o["eccesso"] for o in overallocations)
affected_resources = len({o["risorsa_nome"] for o in overallocations})

col1, col2, col3 = st.columns(3)
col1.metric("Overallocation totali", total_over, delta=f"+{total_over}", delta_color="inverse")
col2.metric("Risorse coinvolte", affected_resources)
col3.metric("Eccesso massimo", f"{max_excess:.1f}%")

# Table of overallocations
df_over = pd.DataFrame(overallocations).rename(
    columns={
        "risorsa_nome": "Risorsa",
        "mese": "Mese",
        "totale_percentuale": "% Totale",
        "eccesso": "Eccesso %",
    }
)

def _highlight_excess(val):
    """Highlight excess cells in red gradient."""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return ""
    if v < 10:
        return "background-color: #ffeb9c; color: #9c5700"
    elif v < 30:
        return "background-color: #ffc7ce; color: #9c0006"
    else:
        return "background-color: #c00000; color: white; font-weight: bold"

styled_over = df_over.style.applymap(
    _highlight_excess, subset=["Eccesso %"]
).format({"% Totale": "{:.1f}%", "Eccesso %": "+{:.1f}%"})

st.dataframe(styled_over, use_container_width=True, hide_index=True)

st.divider()

# ─── Reallocation suggestions ─────────────────────────────────────────────────
st.subheader("💡 Suggerimenti di Riallocazione")

with st.spinner("Analisi in corso..."):
    suggerimenti = get_suggerimenti(piano_id)

if not suggerimenti:
    st.warning("Nessun suggerimento automatico disponibile per questo piano.")
    st.stop()

st.caption(
    f"Trovati **{len(suggerimenti)}** suggerimenti. "
    "Priorità: attività 'Da Confermare' e di tipo EVO."
)

for i, s in enumerate(suggerimenti, 1):
    with st.container():
        # Header
        dest_label = s.mese_destinazione if s.mese_destinazione else "❌ nessun mese disponibile"
        icon = "🟡" if s.mese_destinazione else "🔴"

        col1, col2 = st.columns([1, 5])
        with col1:
            st.markdown(f"### {icon} #{i}")
        with col2:
            st.markdown(
                f"**{s.risorsa_nome}** — *{s.attivita_nome}*  \n"
                f"Sposta **{s.percentuale:.1f}%** da `{s.mese_origine}` → `{dest_label}`"
            )
            st.caption(s.motivo)

        st.divider()

# ─── Export suggestions ────────────────────────────────────────────────────────
with st.expander("📥 Esporta suggerimenti"):
    df_sugg = pd.DataFrame(
        [
            {
                "Risorsa": s.risorsa_nome,
                "Attività": s.attivita_nome,
                "Mese origine": s.mese_origine,
                "Mese destinazione": s.mese_destinazione or "N/D",
                "% da spostare": s.percentuale,
                "Motivo": s.motivo,
            }
            for s in suggerimenti
        ]
    )
    csv = df_sugg.to_csv(index=False, sep=";").encode("utf-8")
    st.download_button(
        "⬇️ Scarica CSV",
        data=csv,
        file_name=f"suggerimenti_{piano_nome.replace(' ', '_')}.csv",
        mime="text/csv",
    )
    st.dataframe(df_sugg, use_container_width=True, hide_index=True)
