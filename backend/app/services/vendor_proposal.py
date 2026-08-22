"""[AIQ-1903] ReloPass's default vendor proposal: seed a company's approved-list from the
destination catalog.

ONE query, TWO callers, deliberately different policies
-------------------------------------------------------
    test-drive provision   -> default_selected=True   (routers/test_drive.py)
    real case finalisation -> default_selected=False  (routers/cases_write.py)

The split is the point. A test-drive company exists to demo the product, so its marketplace must
be populated on arrival — that is what AIQ-1651 fixed. A real company must not have vendors
approved on its behalf: `hr_catalog.get_curation_view` defaults an untouched master row to
`selected=False` ("the employee can only pick from the list pre-selected and validated by HR"),
and `employee_recommendations_filter` renders an empty curation as "HR is finalizing providers".
Seeding real rows as selected=true would quietly overturn that authority model and put vendors in
front of employees that no HR user ever ticked. So we seed the PROPOSAL, not the approval: HR
opens a full pre-filled list and ticks, instead of facing an empty page.

WHY THIS LIVES IN ONE PLACE
---------------------------
Before AIQ-1903 the query existed once, in test_drive.py, and nothing seeded a real company at
all — measured 2026-08-17, 27 of 32 non-test companies had ZERO rows in
`company_vendor_selections`. `SLB_Denis` had 46 only because a human typed them. Adding a second
caller with its own copy of this WHERE clause is how the two drift apart, so both callers share
this function and the clause is written down once.

WHAT QUALIFIES AS A DESTINATION VENDOR
--------------------------------------
Two sources, and the country guard applies to BOTH:

  * a catalog row whose own ``country`` IS the destination, supplier-linked or not — this is the
    bulk of a real destination catalog (all 29 active Ireland rows have ``supplier_id IS NULL``);
  * a genuinely global row (``country IS NULL``) that ALSO reaches the destination through an
    approved supplier capability — this is what keeps SIRVA and Déménagements Delahaye working.

A row tagged for a DIFFERENT country never qualifies, even when its supplier capability is
``global``. Without that guard, ``Santa Fe Relocation`` (``country='AU'``, ``city='Sydney'``) is
seeded onto an Irish move while ``Santa Fe Relocation Dublin`` (``country='IE'``) is already in
the same list — a near-duplicate from the wrong hemisphere. The ``country IS NULL`` half must
also require the supplier link, or the active catalog rows literally named ``Supplier Test`` and
``testsupplier`` become vendor choices for real customers.

Measured against production, 2026-08-17:  IE -> 31 rows,  FR -> 48 rows.

The supplier registry stays the VETTING signal, not the EXISTENCE signal:
``employee_recommendations_filter`` remains the control that keeps unvetted suppliers out of what
an employee actually sees. This only populates the curation HR then decides on.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy import text

from ...database import db

logger = logging.getLogger(__name__)

#: Regulated professions. A solicitor is accredited by a law society, a tax adviser by a tax
#: institute; ReloPass runs no such check. Proposing one is a suggestion, pre-ticking one is an
#: implied endorsement, so these are never auto-approved unless a HUMAN marked them verified.
COMPLIANCE_CATEGORIES = ("legal_admin", "tax_finance")

#: `attributes_json.verified` is NOT sufficient on its own. Measured 2026-08-17, it is set by the
#: research scraper on essentially everything it writes:
#:
#:     otto_research_backfill  scraper  338/338 verified=true
#:     otto_research_thin      scraper  293/293 verified=true
#:     otto_research           scraper  245/245 verified=true
#:     cowork_curated          manual     9/29
#:     (seed)                  seed       0/53
#:
#: 876 of 877 scraper rows claim to be verified. Gating on the flag alone auto-approved 4 of 5
#: Irish solicitors and 5 of 5 Irish tax advisers — exactly the accreditation claim the guard
#: exists to prevent, made by an LLM pipeline about a regulated professional. So a row counts as
#: verified only when the flag is true AND a human wrote the row.
#:
#: Compared as TEXT, never cast to boolean: `(attributes_json ->> 'verified')::boolean` raises
#: `invalid input syntax for type boolean` on any non-boolean string, which would 500
#: provisioning on a single hand-edited "pending". Postgres `->>` yields 'true'; SQLite's JSON
#: operator yields 1 — accept both, or the SQLite tests assert the opposite of production.
_HUMAN_VERIFIED_SQL = """(
        COALESCE(CAST(sci.attributes_json ->> 'verified' AS TEXT), '') IN ('true', '1')
    AND COALESCE(sci.source, '') <> 'scraper'
)"""

_SEED_SQL = f"""
INSERT INTO company_vendor_selections
    (company_id, category, master_item_id, selected, display_order, country, created_by_user_id)
SELECT :company_id, sci.category, sci.id,
       CASE
         -- Never auto-approve a regulated professional we have not human-verified, regardless
         -- of the caller's default. A demo is not a reason to endorse a solicitor.
         WHEN sci.category IN ('legal_admin', 'tax_finance')
           THEN (:default_selected AND {_HUMAN_VERIFIED_SQL})
         ELSE :default_selected
       END,
       row_number() OVER (PARTITION BY sci.category ORDER BY sci.name) - 1,
       :dest_country, :created_by
FROM service_catalog_items sci
LEFT JOIN suppliers s
       ON s.id = sci.supplier_id
      AND s.status = 'active'
LEFT JOIN supplier_service_capabilities ssc
       ON ssc.supplier_id = sci.supplier_id
      AND ssc.service_category = sci.category
      AND ssc.platform_vetting_status = 'approved'
      AND (ssc.coverage_scope_type = 'global' OR ssc.country_code = :dest_country)
WHERE sci.active = true
  -- A row tagged for another country never qualifies, even via a global capability.
  AND (sci.country = :dest_country OR sci.country IS NULL)
  -- ...and an untagged row must earn its place through an approved supplier, which is what
  -- keeps the `Supplier Test` / `testsupplier` fixtures out.
  AND (
        sci.country = :dest_country
     OR (s.id IS NOT NULL AND ssc.supplier_id IS NOT NULL)
      )
  AND NOT EXISTS (
      SELECT 1 FROM company_vendor_selections cvs
      WHERE cvs.company_id = :company_id AND cvs.master_item_id = sci.id
  )
"""


def seed_destination_proposal(
    *,
    company_id: str,
    dest_country: Optional[str],
    created_by: Optional[str] = None,
    default_selected: bool = False,
) -> int:
    """Seed one `company_vendor_selections` row per catalog vendor serving `dest_country`.

    Idempotent (`NOT EXISTS` on `(company_id, master_item_id)`) and tenant-scoped — every row
    written carries the caller's `company_id`, and nothing reads another company's selections.

    Returns the number of rows inserted; 0 is legitimate on a re-run.

    Raises nothing to the caller by design is NOT the contract here — callers decide. Both
    current callers wrap this best-effort so a seed failure cannot break provisioning or case
    creation, but they log loudly: a silent swallow on this path caused a P0 before.
    """
    if not dest_country:
        logger.info(
            "vendor_proposal: skipped company=%s — no destination country yet", company_id
        )
        return 0

    params: Dict[str, Any] = {
        "company_id": str(company_id),
        "dest_country": dest_country,
        "created_by": created_by,
        # Bind a Python bool, not 1/0 — `selected` is a Postgres BOOLEAN and an int bind raises
        # psycopg2 DatatypeMismatch (SQLite coerces it, which would hide the bug in tests).
        "default_selected": bool(default_selected),
    }
    with db.engine.begin() as conn:
        result = conn.execute(text(_SEED_SQL), params)
        inserted = result.rowcount or 0

    logger.info(
        "vendor_proposal: seeded %s selection(s) company=%s country=%s default_selected=%s",
        inserted, company_id, dest_country, bool(default_selected),
    )
    return inserted
