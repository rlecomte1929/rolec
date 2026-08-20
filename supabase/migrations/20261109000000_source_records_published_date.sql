-- source_records.published_date — the date a SOURCE PAGE states about ITSELF.
--
-- WHY. Freshness has never been checkable. `retrieved_at` records when WE last opened a
-- page, which says nothing about whether the page is current: a scraper run this morning
-- makes a 2019 guidance note look fresh. The 2026-08-19 corridor provenance pass captured,
-- for each promoted fact, the revision date the page prints about itself — lovdata's
-- "Sist endret", service-public's « Vérifié le », gov.ie's "Last updated" — and there was
-- nowhere to put it. The longest-lived staleness threshold anywhere in this repo is 180
-- days and every one of them measures retrieval, not publication.
--
-- WHY HERE AND NOT ON requirement_items. The publication date is a property of the PAGE,
-- and one page legitimately backs several requirements: gov.ie's PPS page backs both the
-- PPS-number and the proof-of-address facts, impots.gouv.fr/resident-de-france backs both
-- the residence criteria and worldwide-income facts, and helsenorge's posted-workers page
-- backs both the A1 and S1 facts. On requirement_items the date would be duplicated per
-- row, and two rows could disagree about when one page was published. `retrieved_at`
-- already lives here; this is its sibling.
--
-- WHY `date` AND NOT `timestamptz`. The pages print a date. A timestamp would invent a
-- time of day and a time zone that no source states. Named `published_date` rather than
-- `published_at` for the same reason — `_at` reads as an instant.
--
-- NULLABLE, AND THAT IS NOT A LOOPHOLE. Some authorities genuinely publish no date
-- (udi.no, skatteetaten.no, politiet.no). NULL records that honestly instead of inferring
-- one. It is scripts/check_corridor_facts.py, not this column, that refuses to let a
-- customer-visible fact rest on an undated page — check (b) treats a null publication date
-- as a FAILURE rather than a skip, precisely because the gate this replaces skipped nulls
-- and therefore passed packs carrying no dates at all.
--
-- NO NEW TABLE, so the RLS + policy + REVOKE trio does not apply; source_records is
-- already covered by 20260605300000_rls_defense_in_depth_service_role.sql. Existing grants
-- are untouched.
--
-- TIMESTAMP. 20261109, not 20261108: repo max on origin/main and the prod ledger max are
-- both 20261107000000, but `20261108000000_candidate_beam_researched_source.sql` is already
-- claimed by two open branches (feat/beam-sourcing-api, feat/beam-sourcing-schema). Picking
-- from the ledger, or from origin/main alone, would have collided with a PR that has not
-- merged yet - which is exactly the #1716/#1717/#1718 three-way collision CLAUDE.md
-- describes, where each PR was individually valid.
--
-- SHIPS ALONE. scripts/check_column_read_before_apply.py fails a PR that adds a column and
-- reads it in application code, because migrations here apply OUT OF BAND — merging this
-- does not create the column. The reader (backend/app/models.py and the fact-pack loader)
-- follows in a separate PR, after an operator applies this and reconciles the ledger.

ALTER TABLE public.source_records
    ADD COLUMN IF NOT EXISTS published_date date;

COMMENT ON COLUMN public.source_records.published_date IS
    'The revision date the source page states about itself (lovdata "Sist endret", '
    'service-public "Verifie le", gov.ie "Last updated"). Distinct from retrieved_at, '
    'which is when we last opened it. NULL when the page publishes no date - recorded '
    'as a finding, never inferred. Freshness is measured against this column.';
