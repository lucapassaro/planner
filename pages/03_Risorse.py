"""Streamlit page: Resource (team member) management."""

import streamlit as st

from db.engine import init_db
from services.risorsa_service import (
    create_risorsa,
    deactivate_risorsa,
    get_all_risorse,
    reactivate_risorsa,
    update_risorsa,
)

init_db()

st.set_page_config(page_title="Risorse | IT Planner", layout="wide")
st.title("👥 Risorse del Team")
st.caption("Le risorse sono condivise tra tutti i piani.")

# ─── List active resources ────────────────────────────────────────────────────
risorse = get_all_risorse(only_active=True)
risorse_inactive = get_all_risorse(only_active=False)
risorse_inactive = [r for r in risorse_inactive if not r.attiva]

if risorse:
    st.subheader(f"Risorse attive ({len(risorse)})")

    # Group by team
    teams: dict = {}
    for r in risorse:
        teams.setdefault(r.team, []).append(r)

    for team, members in sorted(teams.items()):
        with st.expander(f"🏷️ Team {team} ({len(members)})", expanded=True):
            for r in members:
                col1, col2, col3, col4 = st.columns([4, 2, 1, 1])
                with col1:
                    st.markdown(f"**{r.nome}**")
                with col2:
                    st.caption(r.team)
                with col3:
                    if st.button("✏️", key=f"edit_r_{r.id}", help="Modifica"):
                        st.session_state[f"editing_r_{r.id}"] = True
                with col4:
                    if st.button("🚫", key=f"deact_{r.id}", help="Disattiva"):
                        st.session_state[f"confirm_deact_{r.id}"] = True

                # Edit form
                if st.session_state.get(f"editing_r_{r.id}"):
                    with st.form(f"form_edit_r_{r.id}"):
                        new_nome_r = st.text_input("Nome", value=r.nome)
                        new_team_r = st.text_input("Team", value=r.team)
                        c_save, c_cancel = st.columns(2)
                        with c_save:
                            save_r = st.form_submit_button("Salva", type="primary")
                        with c_cancel:
                            cancel_r = st.form_submit_button("Annulla")

                    if save_r:
                        try:
                            update_risorsa(r.id, new_nome_r, new_team_r)
                            st.session_state.pop(f"editing_r_{r.id}", None)
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
                    if cancel_r:
                        st.session_state.pop(f"editing_r_{r.id}", None)
                        st.rerun()

                # Deactivate confirmation
                if st.session_state.get(f"confirm_deact_{r.id}"):
                    st.warning(
                        f"Disattivare **{r.nome}**? "
                        "Le allocazioni storiche rimarranno invariate."
                    )
                    c1, c2, _ = st.columns([1, 1, 4])
                    with c1:
                        if st.button("Sì", key=f"conf_deact_{r.id}", type="primary"):
                            deactivate_risorsa(r.id)
                            st.session_state.pop(f"confirm_deact_{r.id}", None)
                            st.rerun()
                    with c2:
                        if st.button("No", key=f"ann_deact_{r.id}"):
                            st.session_state.pop(f"confirm_deact_{r.id}", None)
                            st.rerun()
else:
    st.info("Nessuna risorsa attiva. Aggiungine una qui sotto.")

# ─── Inactive resources ────────────────────────────────────────────────────────
if risorse_inactive:
    with st.expander(f"Risorse disattivate ({len(risorse_inactive)})"):
        for r in risorse_inactive:
            col1, col2, col3 = st.columns([4, 2, 2])
            with col1:
                st.markdown(f"~~{r.nome}~~")
            with col2:
                st.caption(r.team)
            with col3:
                if st.button("Riattiva", key=f"react_{r.id}"):
                    reactivate_risorsa(r.id)
                    st.rerun()

st.divider()

# ─── Add new resource ──────────────────────────────────────────────────────────
_risorsa_form_v = st.session_state.get("form_risorsa_v", 0)

with st.expander("➕ Aggiungi risorsa", expanded=not risorse):
    with st.form(f"form_crea_risorsa_{_risorsa_form_v}"):
        col1, col2 = st.columns(2)
        with col1:
            nome_r = st.text_input("Nome *", placeholder="es. Mario Rossi")
        with col2:
            team_r = st.text_input("Team *", placeholder="es. FEQ, DATA")
        submitted_r = st.form_submit_button("Aggiungi Risorsa", type="primary")

    if submitted_r:
        try:
            create_risorsa(nome=nome_r, team=team_r)
            st.success(f"Risorsa '{nome_r}' aggiunta.")
            st.session_state["form_risorsa_v"] = _risorsa_form_v + 1
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

# ─── Bulk add ─────────────────────────────────────────────────────────────────
with st.expander("➕ Aggiungi più risorse (lista)"):
    st.caption("Inserisci una risorsa per riga nel formato: Nome, Team")
    bulk_text = st.text_area(
        "Lista risorse",
        placeholder="Mario Rossi, FEQ\nGiulia Bianchi, DATA\nLuca Verdi, FEQ",
        height=150,
    )
    team_default = st.text_input("Team di default (se non specificato)", value="")

    if st.button("Aggiungi tutte", type="primary"):
        added, errors = 0, []
        for line in bulk_text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            r_nome = parts[0] if parts else ""
            r_team = parts[1] if len(parts) > 1 else team_default
            if not r_nome:
                continue
            try:
                create_risorsa(nome=r_nome, team=r_team or "N/A")
                added += 1
            except ValueError as exc:
                errors.append(str(exc))

        if added:
            st.success(f"{added} risorse aggiunte.")
        for e in errors:
            st.warning(e)
        if added:
            st.rerun()
