"""Streamlit page: Main planning page with 4 inline-editable grids.

Grid 1 — Plan list (create, rename, delete inline)
Grid 2 — Activity scheduling in gg/u
Grid 3 — Resource allocations per activity in % (or gg/u)
Grid 4 — Allocation control pivot per person (read-only heatmap)
"""

import re

import pandas as pd
import streamlit as st

from db.engine import init_db
from db.seed_holidays import seed_holidays_if_needed
from services.allocazione_service import (
    OverallocationError,
    create_allocazione,
    delete_allocazione,
    get_allocazioni_by_piano,
    get_carico_per_risorsa_mese,
    update_allocazione,
)
from services.attivita_service import (
    STATI_VALIDI,
    TIPI_VALIDI,
    create_attivita,
    get_attivita_by_piano,
)
from services.calendario_service import get_giorni_lavorativi, percentuale_to_giorni
from services.excel_service import import_from_excel
from services.piano_service import (
    create_piano,
    delete_piano,
    get_all_piani,
    update_piano,
)
from services.pianificazione_service import (
    get_pianificazioni_by_piano,
    upsert_pianificazione,
)
from services.risorsa_service import get_all_risorse
from utils.date_utils import MESI_SHORT, anni_disponibili, mesi_in_anno
from utils.formatting import style_allocation_cell

init_db()
seed_holidays_if_needed()

st.set_page_config(page_title="Piani e Schedulazioni | IT Planner", layout="wide")
st.title("📋 Piani e Schedulazioni")


# ─── Grid 1: Plans ────────────────────────────────────────────────────────────
st.subheader("Piani")

piani = get_all_piani()

if piani:
    df_piani = pd.DataFrame([
        {
            "_id": p.id,
            "Nome piano": p.nome,
            "Anno": p.anno,
            "Creato": p.created_at.strftime("%d/%m/%Y %H:%M"),
            "Modificato": p.updated_at.strftime("%d/%m/%Y %H:%M"),
        }
        for p in piani
    ])
else:
    df_piani = pd.DataFrame(columns=["_id", "Nome piano", "Anno", "Creato", "Modificato"])

st.data_editor(
    df_piani,
    key="de_piani",
    column_config={
        "_id": None,
        "Nome piano": st.column_config.TextColumn("Nome piano", required=True, width="large"),
        "Anno": st.column_config.NumberColumn(
            "Anno", min_value=2024, max_value=2031, step=1, format="%d", width="small"
        ),
        "Creato": st.column_config.TextColumn("Creato", disabled=True, width="medium"),
        "Modificato": st.column_config.TextColumn("Modificato", disabled=True, width="medium"),
    },
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
)

col_save_p, col_sel_p = st.columns([1, 2])
with col_save_p:
    save_piani_btn = st.button("💾 Salva modifiche piani", type="primary", key="btn_save_piani")
with col_sel_p:
    if piani:
        piano_nomi = [p.nome for p in piani]
        current_nome = st.session_state.get("piano_nome", piano_nomi[0])
        default_idx = piano_nomi.index(current_nome) if current_nome in piano_nomi else 0
        sel_nome = st.selectbox("Piano attivo", piano_nomi, index=default_idx, key="sel_piano_nome",
                                label_visibility="visible")
        sel_id = next((p.id for p in piani if p.nome == sel_nome), None)
        if sel_id:
            st.session_state["piano_id"] = sel_id
            st.session_state["piano_nome"] = sel_nome

if save_piani_btn:
    delta_p = st.session_state.get("de_piani", {})
    errors_p = []

    for row_idx in delta_p.get("deleted_rows", []):
        if row_idx < len(df_piani):
            p_id = int(df_piani.iloc[row_idx]["_id"])
            try:
                delete_piano(p_id)
                if st.session_state.get("piano_id") == p_id:
                    st.session_state.pop("piano_id", None)
                    st.session_state.pop("piano_nome", None)
            except Exception as exc:
                errors_p.append(f"Eliminazione: {exc}")

    for row_idx_str, changes in delta_p.get("edited_rows", {}).items():
        row_idx = int(row_idx_str)
        if row_idx < len(df_piani):
            p_id = int(df_piani.iloc[row_idx]["_id"])
            new_nome = changes.get("Nome piano", df_piani.iloc[row_idx]["Nome piano"])
            new_anno = int(changes.get("Anno", df_piani.iloc[row_idx]["Anno"]))
            try:
                updated = update_piano(p_id, new_nome, new_anno)
                if st.session_state.get("piano_id") == p_id:
                    st.session_state["piano_nome"] = updated.nome
            except Exception as exc:
                errors_p.append(f"Modifica: {exc}")

    for row_data in delta_p.get("added_rows", []):
        new_nome = str(row_data.get("Nome piano", "")).strip()
        new_anno = int(row_data.get("Anno", 2026))
        if not new_nome:
            errors_p.append("Il nome del piano non può essere vuoto.")
            continue
        try:
            p = create_piano(nome=new_nome, anno=new_anno)
            st.session_state["piano_id"] = p.id
            st.session_state["piano_nome"] = p.nome
        except Exception as exc:
            errors_p.append(f"Creazione: {exc}")

    if errors_p:
        for e in errors_p:
            st.error(e)
    else:
        st.success("Modifiche piani salvate.")
    st.rerun()

# Import Excel
with st.expander("📥 Importa da file Excel"):
    st.info("Carica un file Excel nel formato esteso (Tipo | Gruppo | Team | Attività | Persona | Stato | Gen-Dic | Totale).")
    uploaded = st.file_uploader("Seleziona file Excel (.xlsx)", type=["xlsx"], key="import_excel")
    if uploaded:
        with st.form("form_import"):
            nome_import = st.text_input("Nome del nuovo piano", value=uploaded.name.replace(".xlsx", ""))
            anno_import = st.selectbox("Anno di riferimento", anni_disponibili(), index=2, key="anno_import")
            submit_import = st.form_submit_button("Importa", type="primary")
        if submit_import:
            try:
                result = import_from_excel(file_bytes=uploaded.read(), piano_nome=nome_import)
                st.session_state["piano_id"] = result["piano_id"]
                st.session_state["piano_nome"] = nome_import
                st.success(
                    f"Importazione completata: {result['attivita_count']} attività, "
                    f"{result['allocazioni_count']} allocazioni."
                )
                if result["warnings"]:
                    with st.expander(f"⚠️ {len(result['warnings'])} avvisi"):
                        for w in result["warnings"]:
                            st.warning(w)
                st.rerun()
            except Exception as exc:
                st.error(f"Errore importazione: {exc}")

st.divider()

# ─── Guard: plan must be selected ─────────────────────────────────────────────
piano_id = st.session_state.get("piano_id")
piano_nome = st.session_state.get("piano_nome", "")

if not piano_id:
    st.info("Seleziona o crea un piano qui sopra per visualizzare le griglie di pianificazione.")
    st.stop()

st.caption(f"Piano attivo: **{piano_nome}**")

# Derive year and month labels
_anno_match = re.search(r"\b(202\d)\b", piano_nome)
anno = int(_anno_match.group(1)) if _anno_match else 2026
mesi = mesi_in_anno(anno)
mesi_labels = [f"{MESI_SHORT[int(m.split('-')[1]) - 1]} {str(anno)[2:]}" for m in mesi]
label_to_mese = dict(zip(mesi_labels, mesi))

# Load data
attivita_list = get_attivita_by_piano(piano_id)
risorse = get_all_risorse(only_active=True)
pianificazioni = get_pianificazioni_by_piano(piano_id)  # {att_id: {mese: gg}}
allocs_raw = get_allocazioni_by_piano(piano_id)

att_map = {a.id: a for a in attivita_list}
ris_map = {r.id: r for r in risorse}
ris_by_nome = {r.nome: r.id for r in risorse}

# Build fast lookup dicts for allocations
alloc_perc: dict = {}   # (att_id, ris_id, mese) -> percentuale
alloc_id_lkp: dict = {}  # (att_id, ris_id, mese) -> alloc.id
for alloc in allocs_raw:
    k = (alloc.attivita_id, alloc.risorsa_id, alloc.mese)
    alloc_perc[k] = alloc.percentuale
    alloc_id_lkp[k] = alloc.id

# Compute gg/u per activity per month from existing allocations (fallback for Grid 2)
att_gg_alloc: dict = {}  # {att_id: {mese: total_gg}}
for _alloc in allocs_raw:
    _m = _alloc.mese
    _anno_m, _mese_m = int(_m.split("-")[0]), int(_m.split("-")[1])
    _gg = percentuale_to_giorni(_alloc.percentuale, _anno_m, _mese_m)
    att_gg_alloc.setdefault(_alloc.attivita_id, {})
    att_gg_alloc[_alloc.attivita_id][_m] = att_gg_alloc[_alloc.attivita_id].get(_m, 0.0) + _gg

# Activity label map for Griglia 3 added rows
att_label_to_id = {f"[{a.tipo}] {a.gruppo} / {a.nome}": a.id for a in attivita_list}

# ─── Grid 2: Scheduling gg/u ──────────────────────────────────────────────────
st.subheader("Schedulazione attività (gg/u)")

if attivita_list:
    rows_g2 = []
    for att in attivita_list:
        row: dict = {
            "_att_id": att.id,
            "Tipo": att.tipo,
            "Gruppo": att.gruppo,
            "Team": att.team,
            "Attività": att.nome,
            "Stato": att.stato,
        }
        att_piani = pianificazioni.get(att.id, {})
        totale = 0.0
        for m, lbl in zip(mesi, mesi_labels):
            gg = att_piani[m] if m in att_piani else att_gg_alloc.get(att.id, {}).get(m, 0.0)
            row[lbl] = gg
            totale += gg
        row["Totale gg"] = round(totale, 1)
        rows_g2.append(row)

    df_g2_orig = pd.DataFrame(rows_g2)

    col_cfg_g2: dict = {
        "_att_id": None,
        "Tipo": st.column_config.TextColumn("Tipo", disabled=True, width="small"),
        "Gruppo": st.column_config.TextColumn("Gruppo", disabled=True),
        "Team": st.column_config.TextColumn("Team", disabled=True, width="small"),
        "Attività": st.column_config.TextColumn("Attività", disabled=True, width="large"),
        "Stato": st.column_config.TextColumn("Stato", disabled=True),
        "Totale gg": st.column_config.NumberColumn("Totale gg", format="%.1f", disabled=True),
    }
    for lbl in mesi_labels:
        col_cfg_g2[lbl] = st.column_config.NumberColumn(lbl, min_value=0.0, step=0.5, format="%.1f")

    st.data_editor(
        df_g2_orig,
        key="de_g2",
        column_config=col_cfg_g2,
        num_rows="fixed",
        use_container_width=True,
        hide_index=True,
    )

    if st.button("💾 Salva schedulazione", key="btn_save_g2"):
        delta_g2 = st.session_state.get("de_g2", {})
        errs_g2 = []
        saved_g2 = 0
        for row_idx_str, changes in delta_g2.get("edited_rows", {}).items():
            row_idx = int(row_idx_str)
            if row_idx >= len(df_g2_orig):
                continue
            att_id = int(df_g2_orig.iloc[row_idx]["_att_id"])
            for lbl, new_val in changes.items():
                if lbl not in label_to_mese:
                    continue
                mese = label_to_mese[lbl]
                gg = float(new_val) if new_val is not None else 0.0
                try:
                    upsert_pianificazione(att_id, mese, gg)
                    saved_g2 += 1
                except Exception as exc:
                    errs_g2.append(str(exc))
        for e in errs_g2:
            st.error(e)
        if not errs_g2:
            st.success(f"Schedulazione aggiornata ({saved_g2} {'cella' if saved_g2 == 1 else 'celle'}).")
        st.rerun()
else:
    st.info("Nessuna attività nel piano.")

with st.expander("➕ Aggiungi attività"):
    _fa_v = st.session_state.get("form_att_ps_v", 0)
    with st.form(f"form_add_att_ps_{_fa_v}"):
        c1, c2 = st.columns(2)
        with c1:
            f_nome = st.text_input("Nome attività *", placeholder="es. Migrazione ETL")
            f_gruppo = st.text_input("Gruppo *", placeholder="es. FEQ, Progetto X")
            f_team = st.text_input("Team *", placeholder="es. FEQ, DATA")
            f_effort = st.number_input("Effort totale (gg/u)", min_value=0.0, step=0.5, value=0.0)
        with c2:
            f_tipo = st.selectbox("Tipo *", list(TIPI_VALIDI))
            f_stato = st.selectbox("Stato *", list(STATI_VALIDI), index=1)
            f_note = st.text_area("Note", placeholder="Facoltativo")
        sub_att = st.form_submit_button("Aggiungi attività", type="primary")
    if sub_att:
        try:
            create_attivita(
                piano_id=piano_id,
                gruppo=f_gruppo,
                tipo=f_tipo,
                team=f_team,
                nome=f_nome,
                stato=f_stato,
                effort_gg=f_effort if f_effort > 0 else None,
                note=f_note or None,
            )
            st.session_state["form_att_ps_v"] = _fa_v + 1
            st.success(f"Attività '{f_nome}' aggiunta.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

st.divider()

# ─── Grid 3: Allocations per person ──────────────────────────────────────────
st.subheader("Allocazione persone per attività")

show_gg = st.toggle("Mostra in gg/u (invece di %)", value=False, key="toggle_gg")

# Filters
with st.expander("🔍 Filtri", expanded=False):
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        f_tipo_g3 = st.multiselect("Tipo", list(TIPI_VALIDI), default=list(TIPI_VALIDI), key="f3_tipo")
    with fc2:
        gruppi_avail = sorted({a.gruppo for a in attivita_list}) if attivita_list else []
        f_gruppo_g3 = st.multiselect("Gruppo", gruppi_avail, default=gruppi_avail, key="f3_gruppo")
    with fc3:
        f_stato_g3 = st.multiselect("Stato", list(STATI_VALIDI), default=list(STATI_VALIDI), key="f3_stato")
    ris_nomi = [r.nome for r in risorse]
    f_persona_g3 = st.multiselect("Persona", ris_nomi, default=ris_nomi, key="f3_persona")

# Build Griglia 3 rows: one row per (att, ris) pair with allocations
rows_g3 = []
for att in attivita_list:
    if att.tipo not in f_tipo_g3:
        continue
    if att.gruppo not in f_gruppo_g3:
        continue
    if att.stato not in f_stato_g3:
        continue

    # Find resources allocated to this activity
    ris_ids_for_att = sorted({
        alloc.risorsa_id
        for alloc in allocs_raw
        if alloc.attivita_id == att.id and alloc.risorsa_id in ris_map
    })

    for ris_id in ris_ids_for_att:
        r = ris_map[ris_id]
        if r.nome not in f_persona_g3:
            continue
        row: dict = {
            "_att_id": att.id,
            "_ris_id": ris_id,
            "Tipo": att.tipo,
            "Gruppo": att.gruppo,
            "Team": att.team,
            "Attività": att.nome,
            "Stato": att.stato,
            "Persona": r.nome,
        }
        totale = 0.0
        for m, lbl in zip(mesi, mesi_labels):
            perc = alloc_perc.get((att.id, ris_id, m), 0.0)
            if show_gg:
                anno_m, mese_m = int(m.split("-")[0]), int(m.split("-")[1])
                val = percentuale_to_giorni(perc, anno_m, mese_m) if perc else 0.0
            else:
                val = perc
            row[lbl] = val
            totale += val
        row["Totale"] = round(totale, 1)
        rows_g3.append(row)

empty_cols = ["_att_id", "_ris_id", "Tipo", "Gruppo", "Team", "Attività", "Stato", "Persona"] + mesi_labels + ["Totale"]
df_g3_orig = pd.DataFrame(rows_g3) if rows_g3 else pd.DataFrame(columns=empty_cols)

unit_label = "gg" if show_gg else "%"
max_val = None if show_gg else 100.0
step_val = 0.5 if show_gg else 5.0

col_cfg_g3: dict = {
    "_att_id": None,
    "_ris_id": None,
    "Tipo": st.column_config.TextColumn("Tipo", disabled=True, width="small"),
    "Gruppo": st.column_config.TextColumn("Gruppo", disabled=True),
    "Team": st.column_config.TextColumn("Team", disabled=True, width="small"),
    "Attività": st.column_config.SelectboxColumn(
        "Attività", options=list(att_label_to_id.keys()), width="large"
    ),
    "Stato": st.column_config.TextColumn("Stato", disabled=True),
    "Persona": st.column_config.SelectboxColumn("Persona", options=ris_nomi),
    "Totale": st.column_config.NumberColumn(f"Totale {unit_label}", format="%.1f", disabled=True),
}
for lbl in mesi_labels:
    col_cfg_g3[lbl] = st.column_config.NumberColumn(
        lbl, min_value=0.0, max_value=max_val, step=step_val, format="%.1f"
    )

st.data_editor(
    df_g3_orig,
    key="de_g3",
    column_config=col_cfg_g3,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
)

if st.button("💾 Salva allocazioni", key="btn_save_g3", type="primary"):
    delta_g3 = st.session_state.get("de_g3", {})
    errs_g3 = []
    saved_g3 = 0

    # Helper: convert value to % based on current display mode
    def _to_perc(val: float, mese: str) -> float:
        if not show_gg:
            return val
        anno_m, mese_m = int(mese.split("-")[0]), int(mese.split("-")[1])
        gg_lav = get_giorni_lavorativi(anno_m, mese_m)
        return (val / gg_lav * 100) if gg_lav else 0.0

    # Edited rows: update or create/delete individual month allocations
    for row_idx_str, changes in delta_g3.get("edited_rows", {}).items():
        row_idx = int(row_idx_str)
        if row_idx >= len(df_g3_orig):
            continue
        att_id = int(df_g3_orig.iloc[row_idx]["_att_id"])
        ris_id = int(df_g3_orig.iloc[row_idx]["_ris_id"])
        for lbl, new_val in changes.items():
            if lbl not in label_to_mese:
                continue
            mese = label_to_mese[lbl]
            new_num = float(new_val) if new_val is not None else 0.0
            perc = _to_perc(new_num, mese)
            existing_id = alloc_id_lkp.get((att_id, ris_id, mese))
            if perc <= 0:
                if existing_id:
                    try:
                        delete_allocazione(existing_id)
                        saved_g3 += 1
                    except Exception as exc:
                        errs_g3.append(str(exc))
            elif existing_id:
                try:
                    update_allocazione(existing_id, perc)
                    saved_g3 += 1
                except OverallocationError as exc:
                    errs_g3.append(str(exc))
                except Exception as exc:
                    errs_g3.append(str(exc))
            else:
                try:
                    create_allocazione(att_id, ris_id, mese, perc)
                    saved_g3 += 1
                except OverallocationError as exc:
                    errs_g3.append(str(exc))
                except Exception as exc:
                    errs_g3.append(str(exc))

    # Added rows: create new allocations
    for row_data in delta_g3.get("added_rows", []):
        att_label = str(row_data.get("Attività", "")).strip()
        ris_nome = str(row_data.get("Persona", "")).strip()
        att_id = att_label_to_id.get(att_label)
        ris_id = ris_by_nome.get(ris_nome)
        if not att_id:
            errs_g3.append(f"Attività '{att_label}' non trovata — usa il formato [Tipo] Gruppo / Nome.")
            continue
        if not ris_id:
            errs_g3.append(f"Persona '{ris_nome}' non trovata.")
            continue
        for lbl, new_val in row_data.items():
            if lbl not in label_to_mese:
                continue
            new_num = float(new_val) if new_val is not None else 0.0
            if new_num <= 0:
                continue
            mese = label_to_mese[lbl]
            perc = _to_perc(new_num, mese)
            try:
                create_allocazione(att_id, ris_id, mese, perc)
                saved_g3 += 1
            except OverallocationError as exc:
                errs_g3.append(str(exc))
            except Exception as exc:
                errs_g3.append(str(exc))

    # Deleted rows: remove all allocations for that att×ris combo
    for row_idx in delta_g3.get("deleted_rows", []):
        if row_idx >= len(df_g3_orig):
            continue
        att_id = int(df_g3_orig.iloc[row_idx]["_att_id"])
        ris_id = int(df_g3_orig.iloc[row_idx]["_ris_id"])
        for m in mesi:
            existing_id = alloc_id_lkp.get((att_id, ris_id, m))
            if existing_id:
                try:
                    delete_allocazione(existing_id)
                    saved_g3 += 1
                except Exception as exc:
                    errs_g3.append(str(exc))

    for e in errs_g3:
        st.error(e)
    if not errs_g3 or saved_g3 > 0:
        if saved_g3 > 0:
            st.success(f"Allocazioni aggiornate ({saved_g3} operazioni).")
    st.rerun()

st.divider()

# ─── Grid 4: Allocation control pivot (read-only heatmap) ────────────────────
st.subheader("Controllo % allocazione per persona")

carico = get_carico_per_risorsa_mese(piano_id)
if carico:
    rows_g4 = []
    for r in risorse:
        r_carico = carico.get(r.id, {})
        if not any(r_carico.get(m, 0) > 0 for m in mesi):
            continue
        row: dict = {"Persona": r.nome, "Team": r.team}
        for m, lbl in zip(mesi, mesi_labels):
            row[lbl] = r_carico.get(m, 0.0)
        rows_g4.append(row)

    if rows_g4:
        df_g4 = pd.DataFrame(rows_g4)
        styled_g4 = df_g4.style.applymap(
            style_allocation_cell, subset=mesi_labels
        ).format("{:.0f}%", subset=mesi_labels, na_rep="")
        st.dataframe(styled_g4, use_container_width=True, hide_index=True, height=400)
    else:
        st.info("Nessuna allocazione presente nel piano.")
else:
    st.info("Nessuna allocazione presente nel piano.")
