"""Streamlit page: Resource (team member) management via inline data_editor."""

import pandas as pd
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

# ─── Active resources grid ─────────────────────────────────────────────────────
risorse_attive = get_all_risorse(only_active=True)

st.subheader(f"Risorse attive ({len(risorse_attive)})")

if risorse_attive:
    df_risorse = pd.DataFrame([
        {"_id": r.id, "Nome": r.nome, "Team": r.team}
        for r in risorse_attive
    ])
else:
    df_risorse = pd.DataFrame(columns=["_id", "Nome", "Team"])

st.data_editor(
    df_risorse,
    key="de_risorse",
    column_config={
        "_id": None,
        "Nome": st.column_config.TextColumn("Nome", required=True, width="large"),
        "Team": st.column_config.TextColumn("Team", required=True, width="medium"),
    },
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
)

col_save, col_info = st.columns([1, 3])
with col_save:
    save_risorse_btn = st.button("💾 Salva modifiche risorse", type="primary")
with col_info:
    st.caption("Modifica Nome e Team direttamente nella griglia. Usa ➕ per aggiungere, 🗑 per disattivare.")

if save_risorse_btn:
    delta_r = st.session_state.get("de_risorse", {})
    errors_r = []

    # Deleted rows → soft deactivate
    for row_idx in delta_r.get("deleted_rows", []):
        if row_idx < len(df_risorse):
            r_id = int(df_risorse.iloc[row_idx]["_id"])
            try:
                deactivate_risorsa(r_id)
            except Exception as exc:
                errors_r.append(f"Disattivazione: {exc}")

    # Edited rows → update
    for row_idx_str, changes in delta_r.get("edited_rows", {}).items():
        row_idx = int(row_idx_str)
        if row_idx < len(df_risorse):
            r_id = int(df_risorse.iloc[row_idx]["_id"])
            new_nome = changes.get("Nome", df_risorse.iloc[row_idx]["Nome"])
            new_team = changes.get("Team", df_risorse.iloc[row_idx]["Team"])
            try:
                update_risorsa(r_id, new_nome, new_team)
            except Exception as exc:
                errors_r.append(f"Modifica '{new_nome}': {exc}")

    # Added rows → create
    for row_data in delta_r.get("added_rows", []):
        new_nome = str(row_data.get("Nome", "")).strip()
        new_team = str(row_data.get("Team", "")).strip()
        if not new_nome:
            errors_r.append("Il nome della risorsa non può essere vuoto.")
            continue
        if not new_team:
            errors_r.append(f"Il team per '{new_nome}' non può essere vuoto.")
            continue
        try:
            create_risorsa(nome=new_nome, team=new_team)
        except Exception as exc:
            errors_r.append(f"Creazione '{new_nome}': {exc}")

    if errors_r:
        for e in errors_r:
            st.error(e)
    else:
        st.success("Modifiche risorse salvate.")
    st.rerun()

# ─── Inactive resources ────────────────────────────────────────────────────────
tutte = get_all_risorse(only_active=False)
risorse_inattive = [r for r in tutte if not r.attiva]

if risorse_inattive:
    st.divider()
    with st.expander(f"Risorse disattivate ({len(risorse_inattive)})"):
        df_inattive = pd.DataFrame([
            {"Nome": r.nome, "Team": r.team, "_id": r.id}
            for r in risorse_inattive
        ])
        st.dataframe(
            df_inattive[["Nome", "Team"]],
            use_container_width=True,
            hide_index=True,
        )
        ris_inattive_nomi = {r.nome: r.id for r in risorse_inattive}
        sel_react = st.selectbox("Risorsa da riattivare", list(ris_inattive_nomi.keys()), key="sel_react")
        if st.button("Riattiva risorsa selezionata"):
            try:
                reactivate_risorsa(ris_inattive_nomi[sel_react])
                st.success(f"'{sel_react}' riattivata.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
