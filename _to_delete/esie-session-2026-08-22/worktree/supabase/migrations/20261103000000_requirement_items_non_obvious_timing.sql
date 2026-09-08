-- requirement_items: non_obvious + timing (additive, nullable/defaulted).
--
-- Two things a relocating person needs that the requirement row cannot express today:
--   * `non_obvious` — this step is a real obligation that nobody warns you about
--     (the IE emergency-tax bite, the NO skattekort, the police registration). The
--     honest answer to "what will bite me?" is a flag on the row, not prose.
--   * `timing`      — free text ("within 8 days of arrival", "before signing a lease").
--     Deliberately text, not an interval: the source rules are phrased relative to
--     events we do not model (arrival, first payslip, lease signature), and encoding
--     them as a duration would be inventing precision the citation does not carry.
--
-- Additive only. `non_obvious` defaults false so every existing row keeps its current
-- meaning; `timing` is nullable and stays NULL until data sets it. No backfill, no
-- row is rewritten, nothing is served differently until a fact populates a column.
--
-- guard: column-read-ok this migration is applied to production BEFORE the PR is opened
-- (psql -f + `supabase migration repair --status applied 20261103000000`), so the columns
-- exist ahead of the readers merging; both readers are also getattr/.get-defaulted and
-- degrade to false/NULL rather than raising.

ALTER TABLE public.requirement_items
    ADD COLUMN IF NOT EXISTS non_obvious boolean NOT NULL DEFAULT false;

ALTER TABLE public.requirement_items
    ADD COLUMN IF NOT EXISTS timing text;

COMMENT ON COLUMN public.requirement_items.non_obvious IS
    'True when this requirement is a real obligation a relocating person would not anticipate '
    '(e.g. emergency tax until a tax registration lands). Display/ranking hint only — it is not a gate.';
COMMENT ON COLUMN public.requirement_items.timing IS
    'Free-text deadline relative to an event we do not model, verbatim from the source '
    '(e.g. "within 8 days of arrival"). NULL when the source states no deadline.';
