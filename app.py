"""IT Resource Planning Tool — Streamlit entrypoint.

This file serves as the home page and initialises the database on startup.
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

# ─── One-time initialisation ──────────────────────────────────────────────────
@st.cache_resource
def _init():
    """Initialise DB schema and seed Italian holidays (runs once per session)."""
    init_db()
    seed_holidays_if_needed()
    return True

_init()

# ─── Home page ────────────────────────────────────────────────────────────────
st.title("📋 IT Resource Planner")
st.markdown(
    """
Strumento web per la **pianificazione delle risorse** del team IT.

---

### Come iniziare

1. **[Piani](Piani)** — Crea un nuovo piano o importa da file Excel
2. **[Attività](Attivita)** — Aggiungi le attività del piano (tipo AM/EVO, gruppo, stato)
3. **[Risorse](Risorse)** — Gestisci le persone del team
4. **[Allocazioni](Allocazioni)** — Assegna le risorse alle attività per mese (%)
5. **[Vista Tabellare](Vista_Tabellare)** — Visualizza il carico per persona per mese
6. **[Ottimizzazione](Ottimizzazione)** — Rileva e risolvi le overallocation

---
"""
)

# ─── Current plan indicator ───────────────────────────────────────────────────
piano_id = st.session_state.get("piano_id")
piano_nome = st.session_state.get("piano_nome", "")

if piano_id:
    st.success(f"Piano attivo: **{piano_nome}** (ID: {piano_id})")
else:
    st.warning("Nessun piano selezionato. Vai su **Piani** per selezionare o crearne uno.")

# ─── Quick summary (if plan selected) ────────────────────────────────────────
if piano_id:
    st.divider()
    st.subheader("Riepilogo rapido")

    try:
        from services.attivita_service import get_attivita_by_piano
        from services.allocazione_service import get_overallocations
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

        # EVO vs AM split
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

# ─── Colour legend ────────────────────────────────────────────────────────────
st.divider()
st.subheader("Legenda colori (vista tabellare)")
legend_cols = st.columns(4)
legend_cols[0].markdown(
    '<div style="background:#c6efce;padding:8px;border-radius:4px;text-align:center">'
    "<b>Verde</b><br>0–79%</div>",
    unsafe_allow_html=True,
)
legend_cols[1].markdown(
    '<div style="background:#ffeb9c;padding:8px;border-radius:4px;text-align:center">'
    "<b>Giallo</b><br>80–99%</div>",
    unsafe_allow_html=True,
)
legend_cols[2].markdown(
    '<div style="background:#92d050;padding:8px;border-radius:4px;text-align:center">'
    "<b>Verde pieno</b><br>100%</div>",
    unsafe_allow_html=True,
)
legend_cols[3].markdown(
    '<div style="background:#ffc7ce;padding:8px;border-radius:4px;text-align:center">'
    "<b>Rosso</b><br>&gt;100% (overalloc)</div>",
    unsafe_allow_html=True,
)
