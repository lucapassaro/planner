"""Streamlit page: Plan management (list, create, import, rename, delete)."""

import streamlit as st

from db.engine import init_db
from db.seed_holidays import seed_holidays_if_needed
from services.excel_service import import_from_excel
from services.piano_service import (
    create_piano,
    delete_piano,
    get_all_piani,
    update_piano,
)
from utils.date_utils import anni_disponibili

# Ensure DB is initialised on every page
init_db()
seed_holidays_if_needed()

st.set_page_config(page_title="Piani | IT Planner", layout="wide")
st.title("📋 Piani di Pianificazione")


def _select_piano(piano_id: int, nome: str) -> None:
    """Store the selected plan in session state."""
    st.session_state["piano_id"] = piano_id
    st.session_state["piano_nome"] = nome


# ─── List existing plans ───────────────────────────────────────────────────────
piani = get_all_piani()

if piani:
    st.subheader("Piani esistenti")
    for p in piani:
        col1, col2, col3, col4, col5 = st.columns([4, 2, 2, 1, 1])
        with col1:
            st.markdown(f"**{p.nome}** (anno {p.anno})")
        with col2:
            st.caption(f"Creato: {p.created_at.strftime('%d/%m/%Y %H:%M')}")
        with col3:
            st.caption(f"Modificato: {p.updated_at.strftime('%d/%m/%Y %H:%M')}")
        with col4:
            if st.button("Seleziona", key=f"sel_{p.id}", use_container_width=True):
                _select_piano(p.id, p.nome)
                st.success(f"Piano '{p.nome}' selezionato.")
        with col5:
            if st.button("🗑️", key=f"del_{p.id}", help="Elimina piano"):
                st.session_state[f"confirm_delete_{p.id}"] = True

        # Confirm deletion dialog
        if st.session_state.get(f"confirm_delete_{p.id}"):
            st.warning(
                f"⚠️ Eliminare il piano **{p.nome}**? Questa azione è irreversibile."
            )
            c1, c2, _ = st.columns([1, 1, 4])
            with c1:
                if st.button("Conferma", key=f"conf_{p.id}", type="primary"):
                    try:
                        delete_piano(p.id)
                        st.session_state.pop(f"confirm_delete_{p.id}", None)
                        if st.session_state.get("piano_id") == p.id:
                            st.session_state.pop("piano_id", None)
                            st.session_state.pop("piano_nome", None)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Errore: {exc}")
            with c2:
                if st.button("Annulla", key=f"ann_{p.id}"):
                    st.session_state.pop(f"confirm_delete_{p.id}", None)
                    st.rerun()

    st.divider()
else:
    st.info("Nessun piano trovato. Crea il primo piano qui sotto.")

# ─── Current selection indicator ──────────────────────────────────────────────
if st.session_state.get("piano_id"):
    st.success(
        f"Piano attivo: **{st.session_state.get('piano_nome', '')}** "
        f"(ID: {st.session_state['piano_id']})"
    )

# ─── Create new plan ──────────────────────────────────────────────────────────
with st.expander("➕ Crea nuovo piano", expanded=not piani):
    with st.form("form_crea_piano"):
        nome_input = st.text_input("Nome piano", placeholder="es. Piano 2026 Q1")
        anno_input = st.selectbox("Anno di riferimento", anni_disponibili(), index=2)
        submitted = st.form_submit_button("Crea Piano", type="primary")

    if submitted:
        try:
            p = create_piano(nome=nome_input, anno=anno_input)
            _select_piano(p.id, p.nome)
            st.success(f"Piano '{p.nome}' creato e selezionato.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

# ─── Import from Excel ────────────────────────────────────────────────────────
with st.expander("📥 Importa da file Excel"):
    st.info(
        "Carica un file Excel nel formato esteso (con colonna Persona) "
        "oppure nel formato originale (solo attività, senza allocazioni individuali)."
    )
    uploaded = st.file_uploader(
        "Seleziona file Excel (.xlsx)",
        type=["xlsx"],
        key="import_excel",
    )
    if uploaded:
        with st.form("form_import"):
            nome_import = st.text_input(
                "Nome del nuovo piano",
                value=uploaded.name.replace(".xlsx", ""),
            )
            anno_import = st.selectbox(
                "Anno di riferimento",
                anni_disponibili(),
                index=2,
                key="anno_import",
            )
            submit_import = st.form_submit_button("Importa", type="primary")

        if submit_import:
            try:
                result = import_from_excel(
                    file_bytes=uploaded.read(),
                    piano_nome=nome_import,
                )
                _select_piano(result["piano_id"], nome_import)
                st.success(
                    f"Importazione completata: {result['attivita_count']} attività, "
                    f"{result['allocazioni_count']} allocazioni."
                )
                if result["warnings"]:
                    with st.expander(f"⚠️ {len(result['warnings'])} avvisi"):
                        for w in result["warnings"]:
                            st.warning(w)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Errore durante l'importazione: {exc}")

# ─── Rename plan ──────────────────────────────────────────────────────────────
if piani:
    with st.expander("✏️ Rinomina piano"):
        piano_options = {f"{p.nome} ({p.anno})": p for p in piani}
        selected_label = st.selectbox("Piano da rinominare", list(piano_options.keys()))
        piano_to_edit = piano_options[selected_label]

        with st.form("form_rinomina"):
            nuovo_nome = st.text_input("Nuovo nome", value=piano_to_edit.nome)
            nuovo_anno = st.selectbox(
                "Anno",
                anni_disponibili(),
                index=anni_disponibili().index(piano_to_edit.anno)
                if piano_to_edit.anno in anni_disponibili()
                else 2,
                key="anno_rinomina",
            )
            submit_rename = st.form_submit_button("Salva modifiche")

        if submit_rename:
            try:
                updated = update_piano(piano_to_edit.id, nuovo_nome, nuovo_anno)
                if st.session_state.get("piano_id") == piano_to_edit.id:
                    st.session_state["piano_nome"] = updated.nome
                st.success(f"Piano rinominato in '{updated.nome}'.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
