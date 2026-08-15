-- [Stage 9] legal_admin is sourced from BOTH ends of the corridor, not the destination only.
--
-- Addendum A §A.2 assigned `destination`, and Phase 1 shipped that while flagging it rather
-- than defaulting silently: `legal_admin` is the one category with
-- `compliance_critical = true`, and an origin-country immigration lawyer advising on an
-- outbound move is a real engagement, not an edge case.
--
-- WHY NOW, AND WHY IT IS SAFE. Measured 2026-08-13, every legal_admin supplier is based in
-- the country it serves — NO→NO 7 capabilities, FR→FR 4, DE→DE 2 — and only the three
-- Norwegian ones are approved. So for a FR→NO case this changes nothing an employee sees:
-- the catchment gains FR, and the four French lawyers in it are all `pending`, therefore
-- invisible either way.
--
-- Doing it later would not be free. Once a French lawyer is approved, the same edit becomes a
-- change to live slates. Today it costs nothing.
BEGIN;

UPDATE public.supplier_service_categories
   SET sourcing_side = 'both'
 WHERE code = 'legal_admin';

COMMIT;
