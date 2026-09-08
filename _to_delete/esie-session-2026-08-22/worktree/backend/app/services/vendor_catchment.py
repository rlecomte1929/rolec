"""[Stage 9 · Phase 1] Which countries a vendor may be based in to serve a corridor.

Addendum A §A.2/§S2. Three primitives only — `resolve_catchment()` itself is Phase 2 and
depends on the `based_in_country` backfill landing first.

NOTHING CALLS THIS MODULE YET, AND THAT IS DELIBERATE
-----------------------------------------------------
The four migrations behind it (`sourcing_side`, `country_adjacency`,
`company_vendor_catchment_policy`, `suppliers.based_in_country`) are committed but applied
out-of-band, so the columns may not exist in production when this file merges. That is safe
only while no request path imports it — an absent column cannot 500 an endpoint that does not
call it. `test_vendor_catchment.py` asserts the zero-call-sites property so it stays true, and
Phase 2's wiring is the change that must wait for the apply.

WHY `conn` IS A PARAMETER
-------------------------
Same reason as `vendor_harvester.existing_dedupe_keys(conn, …)`: the caller owns the
transaction, and the whole decision surface stays testable against a throwaway SQLite engine
instead of needing the production schema.

THE TWO RULES WORTH READING BEFORE CHANGING ANYTHING
----------------------------------------------------
1. **A NULL `based_in_country` is NOT eligible.** It means "we never established where this
   supplier is", and 7 of 116 suppliers are in that state with no evidence available. Treating
   unknown as eligible-anywhere is how a Singapore mover ends up on a Paris→Oslo slate.
2. **`has_eligible_vendors` applies the FULL predicate** — based in the country AND able to
   reach the destination. §S7 omits a zero-vendor country from the UI entirely rather than
   greying it out, so a count that ignored reach would render a chip promising coverage that
   does not exist.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Set

from sqlalchemy import text

log = logging.getLogger(__name__)

#: Mirrors the CHECK in 20261101000000_supplier_sourcing_side.sql.
SIDE_ORIGIN = "origin"
SIDE_DESTINATION = "destination"
SIDE_BOTH = "both"
SIDE_EITHER = "either"
VALID_SIDES = frozenset({SIDE_ORIGIN, SIDE_DESTINATION, SIDE_BOTH, SIDE_EITHER})

#: The column's DEFAULT. Returned for a category nobody has classified, because
#: destination-sourcing is what the product did for every category before this work — an
#: unknown category behaves exactly as it does today rather than silently widening.
DEFAULT_SIDE = SIDE_DESTINATION

#: §S2 rule 3. A verified membership of one of these evidences that the vendor can reach an
#: arbitrary destination through the network, which is the whole point of belonging to one.
#: Substring match, because the stored bodies carry auditor suffixes
#: ("FIDI Global Alliance / FAIM Plus (auditor: EY)").
GLOBAL_NETWORK_BODIES = ("FIDI", "IAM", "OMNI")


def sourcing_side(conn: Any, category: str) -> str:
    """Which end of the corridor `category` is contracted from.

    Falls back to `destination` when the category is unknown — see DEFAULT_SIDE.
    """
    if not category:
        return DEFAULT_SIDE
    row = conn.execute(
        text(
            "SELECT sourcing_side FROM supplier_service_categories "
            "WHERE code = :code LIMIT 1"
        ),
        {"code": category},
    ).fetchone()
    if not row or not row[0]:
        return DEFAULT_SIDE
    side = str(row[0]).strip().lower()
    if side not in VALID_SIDES:
        # The DB CHECK should make this impossible. If it happens, the schema and this module
        # have drifted; degrading to the default beats propagating a value nothing handles.
        log.warning("vendor_catchment: unknown sourcing_side %r for %r", side, category)
        return DEFAULT_SIDE
    return side


def neighbours_of(
    conn: Any,
    country: Optional[str],
    *,
    default_included_only: bool = True,
) -> Set[str]:
    """Countries adjacent to `country`.

    `default_included_only=True` (the caller's normal case) drops the borders that exist
    geographically but are not commercially interchangeable — short-sea crossings and
    cross-bloc land borders. Pass False only to show HR the full list when they are choosing
    an extension deliberately.

    `country_adjacency` is stored symmetrically, so this reads one direction and needs no
    OR-swap. The seed writes both directions from a single row precisely so that holds.
    """
    if not country:
        return set()
    sql = (
        "SELECT country_b FROM country_adjacency WHERE country_a = :c"
        + (" AND default_included = TRUE" if default_included_only else "")
    )
    rows = conn.execute(text(sql), {"c": country.strip().upper()[:2]}).fetchall()
    return {str(r[0]).strip().upper() for r in rows if r and r[0]}


#: Based in `country`, offering `category`, and reaching `destination_country` by ANY of the
#: three §S2 routes: a globally-scoped capability, an explicit service-area row, or a verified
#: global-network accreditation.
#:
#: One query on purpose. §S7 calls this per candidate country per page load, and a per-country
#: round trip would be an N+1 across every chip in the catchment picker.
_ELIGIBLE_SQL = """
SELECT EXISTS (
  SELECT 1
  FROM suppliers s
  JOIN supplier_service_capabilities c ON c.supplier_id = s.id
  WHERE s.based_in_country = :country
    AND c.service_category = :category
    AND (
         c.coverage_scope_type = 'global'
      OR EXISTS (
           SELECT 1 FROM supplier_service_area_coverage a
           WHERE a.supplier_id = s.id
             AND a.service_category = c.service_category
             AND upper(a.area_id) = :dest
         )
      OR EXISTS (
           SELECT 1 FROM supplier_accreditations x
           WHERE x.supplier_id = s.id
             AND x.status = 'verified'
             AND ({network_clause})
         )
    )
)
"""


def has_eligible_vendors(
    conn: Any,
    country: Optional[str],
    category: str,
    destination_country: Optional[str],
) -> bool:
    """True when at least one vendor based in `country` can actually serve the destination.

    This is what makes default-on neighbours safe rather than noisy: a neighbouring country
    with nobody who can do the job is never added to a catchment and never rendered.
    """
    if not country or not category:
        return False

    network_clause = " OR ".join(
        f"upper(x.body) LIKE '%{body}%'" for body in GLOBAL_NETWORK_BODIES
    )
    row = conn.execute(
        text(_ELIGIBLE_SQL.format(network_clause=network_clause)),
        {
            "country": country.strip().upper()[:2],
            "category": category,
            "dest": (destination_country or "").strip().upper()[:2],
        },
    ).fetchone()
    return bool(row and row[0])
