"""IT Resource Planning Tool — Streamlit entrypoint.

Navigate via the sidebar to manage plans, activities, resources, and allocations.
"""

import streamlit as st

from db.engine import init_db
from db.seed_holidays import seed_holidays_if_needed

st.set_page_config(
    page_title="IT Resource Planner",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def _init():
    init_db()
    seed_holidays_if_needed()
    return True


_init()

st.title("📋 IT Resource Planner")
st.markdown(
    """
Strumento web per la **pianificazione delle risorse** del team IT.

---

### Come iniziare

1. **[Piani e Schedulazioni](Piani_Schedulazioni)** — Gestisci piani, attività, allocazioni e controlla il carico
2. **[Risorse](Risorse)** — Gestisci le persone del team
3. **[Ottimizzazione](Ottimizzazione)** — Rileva e risolvi le overallocation

---
"""
)

piano_id = st.session_state.get("piano_id")
piano_nome = st.session_state.get("piano_nome", "")

if piano_id:
    st.success(f"Piano attivo: **{piano_nome}** (ID: {piano_id})")
else:
    st.warning("Nessun piano selezionato. Vai su **Piani e Schedulazioni** per selezionare o crearne uno.")

if piano_id:
    st.divider()
    st.subheader("Riepilogo rapido")
    try:
        from services.allocazione_service import get_overallocations
        from services.attivita_service import get_attivita_by_piano
        from services.risorsa_service import get_all_risorse

        attivita = get_attivita_by_piano(piano_id)
        risorse = get_all_risorse()
        overallocations = get_overallocations(piano_id)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Attività", len(attivita))
        col2.metric("Risorse attive", len(risorse))
        col3.metric(
            "Overallocation",
            len(overallocations),
            delta=f"+{len(overallocations)}" if overallocations else None,
            delta_color="inverse" if overallocations else "off",
        )
        evo_count = sum(1 for a in attivita if a.tipo == "EVO")
        am_count = sum(1 for a in attivita if a.tipo == "AM")
        col4.metric("EVO / AM", f"{evo_count} / {am_count}")

        if overallocations:
            st.error(
                f"⚠️ Rilevate **{len(overallocations)}** overallocation. "
                "Vai alla pagina [Ottimizzazione](Ottimizzazione) per i dettagli."
            )
    except Exception as exc:
        st.error(f"Errore nel caricamento del riepilogo: {exc}")
