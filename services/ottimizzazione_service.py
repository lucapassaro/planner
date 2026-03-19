"""Optimization service: suggest reallocations to resolve overallocation.

The algorithm:
1. Find all resource-months with total allocation > 100%.
2. For each overallocation, inspect the contributing allocations.
3. Prioritize shifting activities with stato='Da Confermare' to adjacent months
   where the resource has capacity.
4. Return a list of actionable suggestions without modifying any data.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from db.engine import get_session
from db.models import Allocazione, Attivita, Risorsa
from services.allocazione_service import get_carico_per_risorsa_mese, get_overallocations


@dataclass
class SuggerimentoRiallocazione:
    """A single reallocation suggestion.

    Attributes:
        risorsa_nome: Name of the overallocated resource.
        attivita_nome: Name of the activity to shift.
        allocazione_id: Primary key of the allocation to move.
        mese_origine: Month where the overallocation occurs (YYYY-MM).
        mese_destinazione: Suggested target month (YYYY-MM), or None if no slot found.
        percentuale: Percentage to move.
        motivo: Human-readable explanation.
    """

    risorsa_nome: str
    attivita_nome: str
    allocazione_id: int
    mese_origine: str
    mese_destinazione: Optional[str]
    percentuale: float
    motivo: str


def get_suggerimenti(piano_id: int) -> List[SuggerimentoRiallocazione]:
    """Generate reallocation suggestions for a plan to resolve overallocations.

    The function is read-only: it returns suggestions but does not apply them.
    Priority is given to activities with stato='Da Confermare'.

    Args:
        piano_id: Primary key of the plan.

    Returns:
        List of SuggerimentoRiallocazione objects, sorted by month then resource.
    """
    overallocations = get_overallocations(piano_id)
    if not overallocations:
        return []

    # Load carico for all resources in this plan
    carico = get_carico_per_risorsa_mese(piano_id)

    # Load resource names
    with get_session() as session:
        risorse: Dict[int, str] = {
            r.id: r.nome
            for r in session.query(Risorsa).all()
        }

        # Load all allocations for the plan with activity info
        allocs_raw = (
            session.query(Allocazione, Attivita)
            .join(Attivita, Allocazione.attivita_id == Attivita.id)
            .filter(Attivita.piano_id == piano_id)
            .all()
        )
        allocs_info = [
            {
                "id": a.id,
                "risorsa_id": a.risorsa_id,
                "mese": a.mese,
                "percentuale": a.percentuale,
                "attivita_id": a.attivita_id,
                "attivita_nome": att.nome,
                "stato": att.stato,
                "tipo": att.tipo,
            }
            for a, att in allocs_raw
        ]

    suggestions = []

    for risorsa_id, mese_orig, totale in overallocations:
        risorsa_nome = risorse.get(risorsa_id, str(risorsa_id))
        eccesso = totale - 100.0

        # Find allocations for this resource in this month, sorted by priority
        contrib = sorted(
            [a for a in allocs_info if a["risorsa_id"] == risorsa_id and a["mese"] == mese_orig],
            key=lambda a: (
                0 if a["stato"] == "Da Confermare" else 1,  # prefer Da Confermare
                0 if a["tipo"] == "EVO" else 1,             # prefer EVO over AM
                -a["percentuale"],                           # prefer larger allocations
            ),
        )

        remaining_excess = eccesso
        for alloc in contrib:
            if remaining_excess <= 1e-9:
                break

            perc_da_spostare = min(alloc["percentuale"], remaining_excess)
            mese_dest = _find_available_month(
                risorsa_id, mese_orig, perc_da_spostare, carico
            )

            motivo = (
                f"Overallocation di {totale:.1f}% nel mese {mese_orig}. "
                f"Sposta {perc_da_spostare:.1f}% "
                f"({'attività ' + alloc['stato'] if alloc['stato'] != 'Confermato' else 'attività confermata'})"
            )
            if mese_dest:
                motivo += f" al mese {mese_dest} (disponibilità: {100.0 - carico.get(risorsa_id, {}).get(mese_dest, 0.0):.1f}%)."
            else:
                motivo += " — nessun mese disponibile trovato nell'anno."

            suggestions.append(
                SuggerimentoRiallocazione(
                    risorsa_nome=risorsa_nome,
                    attivita_nome=alloc["attivita_nome"],
                    allocazione_id=alloc["id"],
                    mese_origine=mese_orig,
                    mese_destinazione=mese_dest,
                    percentuale=perc_da_spostare,
                    motivo=motivo,
                )
            )
            remaining_excess -= perc_da_spostare

    return suggestions


def _find_available_month(
    risorsa_id: int,
    mese_origine: str,
    percentuale: float,
    carico: Dict[int, Dict[str, float]],
) -> Optional[str]:
    """Find the nearest month where a resource has enough spare capacity.

    Searches adjacent months (alternating before/after) within the same year.

    Args:
        risorsa_id: Resource to check.
        mese_origine: Month causing overallocation (YYYY-MM).
        percentuale: Percentage to accommodate.
        carico: Current total allocation per resource per month.

    Returns:
        YYYY-MM string of the best target month, or None.
    """
    anno, m = int(mese_origine[:4]), int(mese_origine[5:])
    risorsa_carico = carico.get(risorsa_id, {})

    # Search adjacent months in expanding radius
    for delta in range(1, 12):
        for direction in (1, -1):
            candidate_m = m + direction * delta
            if not (1 <= candidate_m <= 12):
                continue
            candidate = f"{anno}-{candidate_m:02d}"
            used = risorsa_carico.get(candidate, 0.0)
            if used + percentuale <= 100.0 + 1e-9:
                return candidate

    return None


def get_riepilogo_overallocation(piano_id: int) -> List[Dict]:
    """Return a summary of all overallocations for display.

    Args:
        piano_id: Primary key of the plan.

    Returns:
        List of dicts with keys: risorsa_nome, mese, totale_percentuale, eccesso.
    """
    overallocations = get_overallocations(piano_id)
    if not overallocations:
        return []

    with get_session() as session:
        risorse: Dict[int, str] = {
            r.id: r.nome for r in session.query(Risorsa).all()
        }

    return [
        {
            "risorsa_nome": risorse.get(rid, str(rid)),
            "mese": mese,
            "totale_percentuale": round(totale, 1),
            "eccesso": round(totale - 100.0, 1),
        }
        for rid, mese, totale in overallocations
    ]
