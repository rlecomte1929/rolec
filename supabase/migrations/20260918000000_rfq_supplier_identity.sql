-- [AIQ-1520] Make an employee-led RFQ physically possible: give the catalog a real link to
-- suppliers, and let the RFQ tables actually hold a supplier id.
--
-- THE PROBLEM
-- -----------
-- POST /api/rfqs resolves recipients to a suppliers.id. The employee shortlists a
-- recommendation item_id, which is service_catalog_items.external_id. Those two only ever
-- lined up by STRING COINCIDENCE — the seed gave some suppliers the dataset id ('m-1'...).
--
-- That coincidence is gone. AIQ-1511 deduped the supplier registry and removed the 'm-N'
-- rows (they were genuine duplicates of the canonical uuid-keyed rows). Its guard checked
-- real FK references — but service_catalog_items.external_id is a SOFT, non-FK reference,
-- invisible to that guard. Result, measured in prod:
--
--     of the 11 HR-approved movers, ZERO resolve to a supplier.
--
-- Nothing live broke (suppliers and service_catalog_items are never joined in any live code
-- path — which is exactly why nothing 500'd), but an employee-led RFQ is impossible until the
-- two tables are linked for real. Restoring the 'm-N' rows would just re-create the
-- duplicates. So: build an explicit link.
--
-- WHAT THIS DOES
-- --------------
-- 1. service_catalog_items.supplier_id -> suppliers(id). Backfilled by lower(trim(name)),
--    which is DETERMINISTIC precisely because AIQ-1511 added uq_suppliers_name_ci. Measured:
--    80 of 82 items resolve, ZERO ambiguous. The 2 that don't stay NULL and must fail
--    honestly at the API — we never guess a supplier.
-- 2. rfq_recipients.vendor_id / quotes.vendor_id: uuid -> text. suppliers.id is varchar and
--    70 of 90 supplier ids are NOT uuid-shaped, so a uuid column physically cannot hold them.
--    Both tables are EMPTY (0 rows), so this is a free, zero-risk widening.
--
-- The column keeps the name `vendor_id` (it now holds a suppliers.id) because renaming it
-- would touch ~20 sites across the vendor portal that AIQ-1517 is about to delete. AIQ-1517
-- owns the rename. The COMMENT below exists so it does not become the next decoy.
--
-- No new table => the RLS/policy/REVOKE hard gate does not apply.

BEGIN;

-- ── 1. The explicit catalog -> supplier link ─────────────────────────────────
ALTER TABLE public.service_catalog_items
    ADD COLUMN IF NOT EXISTS supplier_id varchar REFERENCES public.suppliers(id);

COMMENT ON COLUMN public.service_catalog_items.supplier_id IS
    'The supplier this catalog item represents. Replaces the fragile external_id == suppliers.id '
    'string coincidence (broken by the AIQ-1511 dedupe). NULL = no supplier on record: the item '
    'cannot be sent an RFQ, and the API must say so rather than guess.';

-- Backfill by normalised name. Deterministic: uq_suppliers_name_ci (AIQ-1511) guarantees at
-- most one supplier per normalised name, so this cannot pick the wrong row.
UPDATE public.service_catalog_items sci
   SET supplier_id = s.id
  FROM public.suppliers s
 WHERE sci.supplier_id IS NULL
   AND lower(trim(s.name)) = lower(trim(sci.name));

CREATE INDEX IF NOT EXISTS idx_service_catalog_items_supplier_id
    ON public.service_catalog_items (supplier_id);

-- ── 2. Let the RFQ tables hold a suppliers.id ────────────────────────────────
-- suppliers.id is varchar; 70/90 ids are not uuid-shaped. Both tables are empty.
--
-- Postgres refuses to retype a column a policy depends on, so the two policies must be
-- dropped and recreated. Each had TWO arms:
--   (a) a VENDOR arm  — vendor_users vu ON vu.vendor_id = <table>.vendor_id
--   (b) a CASE arm    — rfqs -> case_assignments, employee_user_id / hr_user_id = auth.uid()
--
-- The vendor arm is dead: vendor_users has ZERO rows, no code has ever inserted one, and
-- AIQ-1517 deletes that portal outright (suppliers will answer by magic link, through the
-- service-role client, not via RLS). Recreating it would also force a uuid/text cast against
-- a table we are about to drop. So the vendor arm goes and the CASE arm — the real access
-- control, employee/HR on their own case — is preserved verbatim.
DROP POLICY IF EXISTS rfq_recipients_select ON public.rfq_recipients;
DROP POLICY IF EXISTS quotes_access         ON public.quotes;

ALTER TABLE public.rfq_recipients ALTER COLUMN vendor_id TYPE text USING vendor_id::text;
ALTER TABLE public.quotes          ALTER COLUMN vendor_id TYPE text USING vendor_id::text;

-- Recreate, case-scoped only. Same access as before for every principal that could actually
-- authenticate (i.e. everyone except the vendor, who never could).
CREATE POLICY rfq_recipients_select ON public.rfq_recipients
    FOR SELECT TO authenticated
    USING (EXISTS (
        SELECT 1 FROM public.rfqs r
        JOIN public.case_assignments ca ON ca.case_id = r.case_id
        WHERE r.id = rfq_recipients.rfq_id
          AND (ca.employee_user_id = (SELECT auth.uid())::text
            OR ca.hr_user_id       = (SELECT auth.uid())::text)
    ));

CREATE POLICY quotes_access ON public.quotes
    FOR ALL TO authenticated
    USING (EXISTS (
        SELECT 1 FROM public.rfqs r
        JOIN public.case_assignments ca ON ca.case_id = r.case_id
        WHERE r.id = quotes.rfq_id
          AND (ca.employee_user_id = (SELECT auth.uid())::text
            OR ca.hr_user_id       = (SELECT auth.uid())::text)
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM public.rfqs r
        JOIN public.case_assignments ca ON ca.case_id = r.case_id
        WHERE r.id = quotes.rfq_id
          AND (ca.employee_user_id = (SELECT auth.uid())::text
            OR ca.hr_user_id       = (SELECT auth.uid())::text)
    ));

COMMENT ON COLUMN public.rfq_recipients.vendor_id IS
    'Holds suppliers.id since AIQ-1520 (NOT vendors.id — that table is deprecated for writes). '
    'Name retained only because the vendor portal still reads it; AIQ-1517 deletes that portal '
    'and should rename this column to supplier_id.';
COMMENT ON COLUMN public.quotes.vendor_id IS
    'Holds suppliers.id since AIQ-1520 (NOT vendors.id). See rfq_recipients.vendor_id.';

COMMIT;
