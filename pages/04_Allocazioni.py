"""Streamlit page: Allocation management (assign resources to activities by month)."""

import streamlit as st

from db.engine import init_db
from services.allocazione_service import (
    OverallocationError,
    create_allocazione,
    delete_allocazione,
    get_allocazioni_by_attivita,
    get_carico_per_risorsa_mese,
    update_allocazione,
)
from services.attivita_service import get_attivita_by_piano
from services.risorsa_service import get_all_risorse
from utils.date_utils import MESI_SHORT, mesi_in_anno

init_db()

st.set_page_config(page_title="Allocazioni | IT Planner", layout="wide")
st.title("📅 Allocazioni")

# ─── Guard ────────────────────────────────────────────────────────────────────
piano_id = st.session_state.get("piano_id")
piano_nome = st.session_state.get("piano_nome", "")

if not piano_id:
    st.warning("⚠️ Seleziona prima un piano dalla pagina **Piani**.")
    st.stop()

st.caption(f"Piano attivo: **{piano_nome}**")

# ─── Load data ────────────────────────────────────────────────────────────────
attivita_list = get_attivita_by_piano(piano_id)
risorse = get_all_risorse(only_active=True)

if not attivita_list:
    st.info("Nessuna attività nel piano. Creane una nella pagina **Attività**.")
    st.stop()

if not risorse:
    st.info("Nessuna risorsa disponibile. Aggiungila nella pagina **Risorse**.")
    st.stop()

# ─── Select activity ──────────────────────────────────────────────────────────
att_labels = {f"[{a.tipo}] {a.gruppo} / {a.nome}": a for a in attivita_list}
selected_label = st.selectbox("Seleziona attività", list(att_labels.keys()))
selected_att = att_labels[selected_label]

st.markdown(
    f"**Tipo:** {selected_att.tipo} | **Team:** {selected_att.team} | "
    f"**Stato:** {selected_att.stato}"
)

# ─── Show current carico for the selected year ────────────────────────────────
try:
    anno = int(piano_nome[-4:]) if piano_nome[-4:].isdigit() else 2026
except ValueError:
    anno = 2026

# Try to extract year from plan name, else default to current year
import re
anno_match = re.search(r"\b(202\d)\b", piano_nome)
if anno_match:
    anno = int(anno_match.group(1))

mesi = mesi_in_anno(anno)
carico = get_carico_per_risorsa_mese(piano_id)

# ─── Current allocations for this activity ────────────────────────────────────
allocs = get_allocazioni_by_attivita(selected_att.id)
risorsa_map = {r.id: r for r in risorse}

if allocs:
    st.subheader("Allocazioni correnti")
    for alloc in allocs:
        r = risorsa_map.get(alloc.risorsa_id)
        r_nome = r.nome if r else f"ID {alloc.risorsa_id}"

        # Check if this creates overallocation context
        totale_mese = carico.get(alloc.risorsa_id, {}).get(alloc.mese, 0.0)
        is_over = totale_mese > 100.0 + 1e-9
        icon = "🔴" if is_over else "🟢"

        col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 1, 1])
        with col1:
            st.markdown(f"{icon} **{r_nome}**")
        with col2:
            st.caption(alloc.mese)
        with col3:
            new_perc = st.number_input(
                "% allocazione",
                min_value=0.0,
                max_value=100.0,
                value=float(alloc.percentuale),
                step=5.0,
                key=f"perc_{alloc.id}",
                label_visibility="collapsed",
            )
        with col4:
            if st.button("💾", key=f"save_{alloc.id}", help="Salva modifica"):
                try:
                    update_allocazione(alloc.id, new_perc)
                    st.success("Aggiornato.")
                    st.rerun()
                except OverallocationError as exc:
                    st.error(str(exc))
                except ValueError as exc:
                    st.error(str(exc))
        with col5:
            if st.button("🗑️", key=f"del_alloc_{alloc.id}", help="Elimina"):
                try:
                    delete_allocazione(alloc.id)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

        if is_over:
            st.caption(
                f"⚠️ {r_nome} è overallocata in {alloc.mese}: {totale_mese:.1f}% totale"
            )
else:
    st.info("Nessuna allocazione per questa attività.")

st.divider()

# ─── Add new allocation ───────────────────────────────────────────────────────
with st.expander("➕ Aggiungi allocazione", expanded=True):
    with st.form("form_add_alloc"):
        col1, col2, col3 = st.columns(3)

        with col1:
            risorsa_options = {r.nome: r.id for r in risorse}
            risorsa_label = st.selectbox("Risorsa *", list(risorsa_options.keys()))
            risorsa_id_sel = risorsa_options[risorsa_label]

        with col2:
            mese_labels = {
                f"{MESI_SHORT[int(m.split('-')[1]) - 1]} {m.split('-')[0]}": m
                for m in mesi
            }
            mese_label = st.selectbox("Mese *", list(mese_labels.keys()))
            mese_sel = mese_labels[mese_label]

        with col3:
            perc_input = st.number_input(
                "Percentuale % *",
                min_value=0.0,
                max_value=100.0,
                value=100.0,
                step=5.0,
            )

        note_input = st.text_input("Note (facoltativo)")

        # Show current load for selected resource in selected month
        current_load = carico.get(risorsa_id_sel, {}).get(mese_sel, 0.0)
        remaining = max(0.0, 100.0 - current_load)
        st.caption(
            f"Carico attuale di **{risorsa_label}** in {mese_sel}: "
            f"{current_load:.1f}% | Disponibile: {remaining:.1f}%"
        )

        submitted = st.form_submit_button("Aggiungi allocazione", type="primary")

    if submitted:
        try:
            create_allocazione(
                attivita_id=selected_att.id,
                risorsa_id=risorsa_id_sel,
                mese=mese_sel,
                percentuale=perc_input,
                note=note_input or None,
            )
            st.success(
                f"Allocazione aggiunta: {risorsa_label} — {mese_sel} — {perc_input}%"
            )
            st.rerun()
        except OverallocationError as exc:
            st.error(str(exc))
        except ValueError as exc:
            st.error(str(exc))

# ─── Capacity overview for all resources (this month / year) ──────────────────
st.divider()
with st.expander("📊 Panoramica carico risorse"):
    if not carico:
        st.info("Nessuna allocazione presente nel piano.")
    else:
        import pandas as pd

        rows = []
        for r in risorse:
            r_carico = carico.get(r.id, {})
            row = {"Risorsa": r.nome, "Team": r.team}
            for m in mesi:
                row[m] = r_carico.get(m, 0.0)
            rows.append(row)

        df = pd.DataFrame(rows)

        # Rename month columns to short labels
        rename_map = {
            m: f"{MESI_SHORT[int(m.split('-')[1]) - 1]}" for m in mesi
        }
        df = df.rename(columns=rename_map)
        month_cols = list(rename_map.values())

        def _color(v):
            try:
                v = float(v)
            except (TypeError, ValueError):
                return ""
            if v <= 0:
                return ""
            elif v < 80:
                return "background-color: #c6efce"
            elif v < 100:
                return "background-color: #ffeb9c"
            elif abs(v - 100) < 1e-9:
                return "background-color: #92d050"
            else:
                return "background-color: #ffc7ce; font-weight: bold"

        styled = df.style.applymap(_color, subset=month_cols).format(
            "{:.0f}%", subset=month_cols, na_rep=""
        )
        st.dataframe(styled, use_container_width=True, height=400)
