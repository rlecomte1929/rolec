-- [AIQ-1821] Evidence ledger for requirement facts + defuse the reviewer-id landmine.
--
-- WHY. 686 requirement facts sit pending across 12 destinations and only 51 of them have any
-- archived source text to check a claim against (avg 441 chars). A review queue built on that
-- shows an approve button with no evidence behind it — a rubber stamp. These columns let the
-- proof be computed once at ingest and rendered in the queue, so a reviewer sees the quote
-- inside its source context rather than taking the extractor's word for it.
--
-- No new tables: ALTERs only, so the RLS/policy/REVOKE gate for new public tables does not apply.
-- requirement_facts and requirement_reviews already carry service_role-only RLS from
-- 20260228025000_structured_requirements.sql.

-- ── 1. The evidence proof, computed per fact ────────────────────────────────────────────────
-- evidence_verified: was evidence_quote found verbatim in the archived source text.
--   NULL  = never checked (no archived text yet)
--   FALSE = checked and NOT found — either a paraphrase or an unsupported claim; needs a human
--   TRUE  = machine-provable against the snapshot the fact was extracted from
alter table public.requirement_facts
  add column if not exists evidence_verified boolean;

-- Character offset of the quote within knowledge_docs.content_excerpt, so the queue can render
-- surrounding context without re-searching the document on every page load.
alter table public.requirement_facts
  add column if not exists evidence_offset integer;

-- When the check last ran. Distinguishes "never checked" from "checked and failed", and lets a
-- future re-verification pass find facts whose source has changed since.
alter table public.requirement_facts
  add column if not exists evidence_checked_at timestamptz;

-- ── 2. Denormalised review stamps ───────────────────────────────────────────────────────────
-- requirement_reviews is the append-only history and stays the source of truth. These two make
-- the queue's list query cheap (no aggregate join just to show "approved by X on Y") and match
-- the shape requirement_fact_candidates already uses.
alter table public.requirement_facts
  add column if not exists reviewed_by text;

alter table public.requirement_facts
  add column if not exists reviewed_at timestamptz;

-- ── 3. THE LANDMINE: reviewer_user_id must be text, not uuid ────────────────────────────────
-- update_requirement_fact_status() runs the status UPDATE and this INSERT in ONE transaction.
-- reviewer_user_id is uuid NOT NULL, but ReloPass ids are frequently legacy text strings
-- ("seed-hr-testingapril"). Such a reviewer fails the uuid cast, which rolls back the INSERT —
-- AND the approval alongside it. The approval would appear to fail for no visible reason.
--
-- This is exactly bug #1543, which killed in-app notifications: notifications.user_id was uuid
-- while HR ids are text, so 424 rows were written and not one was ever readable. The sibling
-- tables already learned this — requirement_fact_candidates.reviewed_by and
-- specialist_review_events.reviewer_id are both text. Align.
--
-- Safe to convert: requirement_reviews has 0 rows in production (every historical approval
-- bypassed the audited path entirely), so there is nothing to migrate.
do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'requirement_reviews'
      and column_name = 'reviewer_user_id' and data_type = 'uuid'
  ) then
    alter table public.requirement_reviews
      alter column reviewer_user_id type text using reviewer_user_id::text;
  end if;
end $$;

-- ── 4. Inline edit needs somewhere to put the before/after ──────────────────────────────────
-- action='edit' has been permitted by the CHECK since 20260228025000 and nothing has ever
-- written it. A reviewer correcting an overstated fact ("you can get X if you provide Y" turned
-- into "you MUST provide Y") is the right verdict for a true-but-overstated claim — better than
-- rejecting accurate content over a modal verb. Storing both sides also gives the extractor the
-- clearest possible signal about how it was wrong.
alter table public.requirement_reviews
  add column if not exists previous_fact_text text;

alter table public.requirement_reviews
  add column if not exists new_fact_text text;

-- ── 5. Indexes the queue actually needs ─────────────────────────────────────────────────────
-- The list is always filtered by status and joined to requirement_entities for the destination.
create index if not exists idx_requirement_facts_status
  on public.requirement_facts (status);

create index if not exists idx_requirement_facts_entity
  on public.requirement_facts (entity_id);

-- Partial index for the default view: pending facts still awaiting an evidence check.
create index if not exists idx_requirement_facts_pending_unchecked
  on public.requirement_facts (status)
  where status = 'pending' and evidence_verified is null;

create index if not exists idx_requirement_reviews_fact
  on public.requirement_reviews (fact_id);
