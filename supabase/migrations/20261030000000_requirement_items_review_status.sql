-- Admin review gate for requirement_items.
--
-- WHY: there was no gate at all. A row written to `requirement_items` was readable the instant
-- COMMIT returned — by authenticated employees via requirements_builder, AND by anonymous
-- callers via GET /api/public/corridor-requirements, which takes no credentials and sets
-- Access-Control-Allow-Origin: *. `crud.list_requirements` filters on country_code + purpose
-- and nothing else. `verification_status` looked like a gate but is a display badge: no read
-- path has ever filtered on it, and the public endpoint strips it from the response entirely.
--
-- So when the Otto research pipeline promoted its first France requirements and the Norway
-- wedge was seeded, that content went straight to the public internet with no human in the
-- loop. The supplier half of the same Audos harvest does this correctly — candidates land at
-- platform_vetting_status='pending' and wait in /admin/vetting-queue for an admin to approve.
-- This gives requirement content the same treatment.
--
-- BACKFILL POLICY: default 'approved' so nothing currently live goes dark, then move the rows
-- written on 2026-08-12 to 'pending' — those are exactly the ones no human has reviewed:
--   * all NORWAY rows (the wedge seed rewrote every one of them, including re-scoping
--     "Valid passport (6+ months)" to THIRD_COUNTRY)
--   * the three FRANCE rows promoted from otto_staging (titled "EU/EEA/Swiss citizen – …")
--
-- review_status is set on INSERT and CARRIED on UPDATE by crud.create_requirement_item — the
-- same treatment verification_status already gets there. Without that, re-running any YAML
-- seed would silently un-approve live content.
--
-- Not a new table, so the RLS + policy + REVOKE gate in CLAUDE.md does not apply; the existing
-- requirement_items_public_select policy is unchanged. Version is above both the repo max and
-- the prod ledger max (both 20261029000000 at time of writing).

ALTER TABLE public.requirement_items
  ADD COLUMN IF NOT EXISTS review_status text NOT NULL DEFAULT 'approved',
  ADD COLUMN IF NOT EXISTS reviewed_by text,
  ADD COLUMN IF NOT EXISTS reviewed_at timestamptz;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'requirement_items_review_status_check'
  ) THEN
    ALTER TABLE public.requirement_items
      ADD CONSTRAINT requirement_items_review_status_check
      CHECK (review_status IN ('pending', 'approved', 'rejected'));
  END IF;
END $$;

COMMENT ON COLUMN public.requirement_items.review_status IS
  'Admin publication gate. Only ''approved'' rows are served to employees or the public '
  'endpoint (crud.list_requirements). Distinct from verification_status, which describes how '
  'well-sourced the content is and is a display badge, not a gate.';

-- Serving path filters on this on every request; the catalog is read by country + purpose.
CREATE INDEX IF NOT EXISTS requirement_items_country_purpose_review_idx
  ON public.requirement_items (country_code, purpose, review_status);

-- The 2026-08-12 content: Otto-promoted France rows + the whole Norway wedge seed.
UPDATE public.requirement_items
   SET review_status = 'pending'
 WHERE review_status = 'approved'
   AND (
        country_code = 'NORWAY'
     OR (country_code = 'FRANCE' AND title LIKE 'EU/EEA/Swiss citizen%')
   );
