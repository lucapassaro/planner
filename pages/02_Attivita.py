"""Streamlit page: Activity management (CRUD within a selected plan)."""

import streamlit as st

from db.engine import init_db
from services.attivita_service import (
    STATI_VALIDI,
    TIPI_VALIDI,
    create_attivita,
    delete_attivita,
    get_attivita_by_piano,
    update_attivita,
)

init_db()

st.set_page_config(page_title="Attività | IT Planner", layout="wide")
st.title("📌 Attività")

# ─── Guard: plan must be selected ─────────────────────────────────────────────
piano_id = st.session_state.get("piano_id")
piano_nome = st.session_state.get("piano_nome", "")

if not piano_id:
    st.warning("⚠️ Seleziona prima un piano dalla pagina **Piani**.")
    st.stop()

st.caption(f"Piano attivo: **{piano_nome}**")

# ─── List activities ───────────────────────────────────────────────────────────
attivita_list = get_attivita_by_piano(piano_id)

if attivita_list:
    st.subheader(f"Attività ({len(attivita_list)})")

    # Group by gruppo
    gruppi: dict = {}
    for att in attivita_list:
        gruppi.setdefault(att.gruppo, []).append(att)

    for gruppo, atts in sorted(gruppi.items()):
        with st.expander(f"📁 {gruppo} ({len(atts)} attività)", expanded=True):
            for att in atts:
                col1, col2, col3, col4, col5, col6, col7 = st.columns([4, 2, 2, 2, 2, 1, 1])
                with col1:
                    st.markdown(f"**{att.nome}**")
                with col2:
                    badge = "🔵" if att.tipo == "EVO" else "🟠"
                    st.markdown(f"{badge} {att.tipo}")
                with col3:
                    st.caption(att.team)
                with col4:
                    color_map = {
                        "Confermato": "🟢",
                        "Da Confermare": "🟡",
                        "Sospeso": "⚫",
                        "Chiuso": "🔴",
                    }
                    st.caption(f"{color_map.get(att.stato, '')} {att.stato}")
                with col5:
                    if att.effort_gg:
                        st.caption(f"⏱ {att.effort_gg:.1f} gg/u")
                with col6:
                    if st.button("✏️", key=f"edit_{att.id}", help="Modifica"):
                        st.session_state[f"editing_{att.id}"] = True
                with col7:
                    if st.button("🗑️", key=f"del_{att.id}", help="Elimina"):
                        st.session_state[f"confirm_del_att_{att.id}"] = True

                # Edit form
                if st.session_state.get(f"editing_{att.id}"):
                    with st.form(f"form_edit_{att.id}"):
                        st.markdown("**Modifica attività**")
                        c1, c2 = st.columns(2)
                        with c1:
                            new_nome = st.text_input("Nome", value=att.nome)
                            new_gruppo = st.text_input("Gruppo", value=att.gruppo)
                            new_team = st.text_input("Team", value=att.team)
                            new_effort = st.number_input(
                                "Effort pianificato (gg/u)",
                                min_value=0.0,
                                step=0.5,
                                value=float(att.effort_gg) if att.effort_gg else 0.0,
                                help="Giorni-uomo totali pianificati per questa attività",
                            )
                        with c2:
                            new_tipo = st.selectbox(
                                "Tipo",
                                TIPI_VALIDI,
                                index=TIPI_VALIDI.index(att.tipo),
                            )
                            new_stato = st.selectbox(
                                "Stato",
                                STATI_VALIDI,
                                index=STATI_VALIDI.index(att.stato),
                            )
                            new_note = st.text_area("Note", value=att.note or "")

                        c_save, c_cancel = st.columns(2)
                        with c_save:
                            save = st.form_submit_button("Salva", type="primary")
                        with c_cancel:
                            cancel = st.form_submit_button("Annulla")

                    if save:
                        try:
                            update_attivita(
                                att.id, new_gruppo, new_tipo, new_team,
                                new_nome, new_stato,
                                effort_gg=new_effort if new_effort > 0 else None,
                                note=new_note or None,
                            )
                            st.session_state.pop(f"editing_{att.id}", None)
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
                    if cancel:
                        st.session_state.pop(f"editing_{att.id}", None)
                        st.rerun()

                # Delete confirmation
                if st.session_state.get(f"confirm_del_att_{att.id}"):
                    st.warning(
                        f"Eliminare **{att.nome}**? "
                        "Tutte le allocazioni collegate saranno rimosse."
                    )
                    c1, c2, _ = st.columns([1, 1, 4])
                    with c1:
                        if st.button("Sì, elimina", key=f"conf_del_{att.id}", type="primary"):
                            try:
                                delete_attivita(att.id)
                                st.session_state.pop(f"confirm_del_att_{att.id}", None)
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))
                    with c2:
                        if st.button("Annulla", key=f"ann_del_{att.id}"):
                            st.session_state.pop(f"confirm_del_att_{att.id}", None)
                            st.rerun()
else:
    st.info("Nessuna attività in questo piano. Aggiungine una qui sotto.")

st.divider()

# ─── Create new activity ──────────────────────────────────────────────────────
# Bug fix: versioned form key resets all widgets after a successful submission.
_form_v = st.session_state.get("form_att_v", 0)

with st.expander("➕ Aggiungi attività", expanded=not attivita_list):
    with st.form(f"form_crea_att_{_form_v}"):
        c1, c2 = st.columns(2)
        with c1:
            nome_input = st.text_input("Nome attività *", placeholder="es. Migrazione ETL")
            gruppo_input = st.text_input(
                "Gruppo *",
                placeholder="es. FEQ, Progetto Nobis, AM generale",
            )
            team_input = st.text_input("Team *", placeholder="es. FEQ, DATA")
            effort_input = st.number_input(
                "Effort pianificato (gg/u)",
                min_value=0.0,
                step=0.5,
                value=0.0,
                help="Giorni-uomo totali pianificati (facoltativo)",
            )
        with c2:
            tipo_input = st.selectbox("Tipo *", TIPI_VALIDI)
            stato_input = st.selectbox("Stato *", STATI_VALIDI, index=1)
            note_input = st.text_area("Note", placeholder="Facoltativo")

        submitted = st.form_submit_button("Aggiungi Attività", type="primary")

    if submitted:
        try:
            create_attivita(
                piano_id=piano_id,
                gruppo=gruppo_input,
                tipo=tipo_input,
                team=team_input,
                nome=nome_input,
                stato=stato_input,
                effort_gg=effort_input if effort_input > 0 else None,
                note=note_input or None,
            )
            st.success(f"Attività '{nome_input}' aggiunta.")
            # Increment version → form key changes → widgets reset on next render
            st.session_state["form_att_v"] = _form_v + 1
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
