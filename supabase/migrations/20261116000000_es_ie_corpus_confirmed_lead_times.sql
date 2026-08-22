-- 20261116000000_es_ie_corpus_confirmed_lead_times.sql
-- [AIQ-1852] ES_IE corpus: replace the estimated lead times with what the official
-- sources actually publish, and retire the superseded chunks.
--
-- The seed (20261010000000) said so itself: "Lead times in the text are marked as
-- ESTIMATES pending confirmation against recent real cases (the beta tester's relocation
-- agent is the ground-truth check)." Three blocks carried that flag and all three are
-- live in retrieval — `immigration_corpus_chunks` holds 7 ES_IE chunks and 3 of them
-- contain "NOT yet verified", so the beta user is being served unverified numbers.
--
-- WHAT COULD BE CONFIRMED, AND WHAT COULD NOT
--
-- Checked against the official sources on 2026-08-22, not against the relocation agent
-- (who has still not reported — see the card's Dependencies):
--
--   * Employment permit  -- CONFIRMED. DETE publishes a live date-order queue.
--   * Burgh Quay IRP     -- NOT CONFIRMABLE. Immigration Service Delivery publishes no
--                           waiting time on its registration page; the only official
--                           number there is the 90-day deadline.
--   * Long-stay 'D' visa -- NOT CONFIRMABLE. The ISD long-stay employment visa page
--                           publishes no processing time.
--
-- Per the card's step 3, a number that cannot be confirmed stays flagged rather than
-- being promoted to fact. The two unconfirmable blocks are therefore re-worded to say
-- plainly that they are estimates AND to record that the official page carries no
-- figure — so the next person does not repeat the search to find the same nothing.
--
-- THE PERMIT NUMBER IS A QUEUE DEPTH, NOT A DECISION TIME
--
-- DETE publishes the RECEIPT DATE it is currently working on, in a date-order queue. On
-- 21 August 2026 that was 14 August 2026 for Critical Skills — about a week of backlog
-- to reach an application. It does NOT publish how long a decision then takes. Writing
-- "the permit takes about a week" would swap one unverified number for another, more
-- confident one, which is the exact failure this card exists to prevent. So the text
-- states the queue, dates it, and says the decision time is not published.
--
-- Note the corpus prose was also the outlier against our own pathway spec:
-- corridors/ES_IE/pathways/CSEP_2026/v1.yaml already models EMPLOYMENT_PERMIT_GRANTED at
-- expected_duration_days: 7, which agrees with the official queue. The YAML needs no
-- change; the prose was wrong, by roughly an order of magnitude.
--
-- WHY THIS ALSO DEACTIVATES CHUNKS
--
-- `immigration_chunk_indexer` is APPEND-ONLY: it skips chunks whose
-- (source_doc_id, content_hash) already exists and writes new ones, but never retires a
-- chunk whose source text has changed. Updating the document alone would therefore leave
-- the old "12 to 16 weeks" chunk `is_active = true` and still retrievable, and grow the
-- chunk count — the card's own "corpus chunk count stable" criterion would fail while
-- the wrong number stayed live. The retriever filters `is_active = true` on every path
-- (immigration_retriever.py:349, 376, 528, 573), so deactivating the superseded chunks
-- is what actually takes them out of retrieval. Same append-only-with-no-retirement
-- shape as AIQ-1866 in the forms engine.
--
-- Re-index AFTER applying this, so the replacement chunks are written:
--     .github/workflows/immigration-indexer.yml   (needs OPENAI_API_KEY)
--
-- Idempotent: the replacements are exact-substring and become no-ops once applied; the
-- hash is recomputed from the resulting text; the deactivation is keyed on the old
-- wording, which the new text does not contain.

begin;

-- ── 1. Employment permit — CONFIRMED against the published queue ────────────────
update public.crawled_immigration_documents
   set extracted_text = replace(
         extracted_text,
         'Timeline estimates — NOT yet verified against recent real cases; confirm with the relocation agent on the ground: the Critical Skills permit decision typically takes about 12 to 16 weeks, and the Burgh Quay IRP appointment about 6 to 8 weeks.',
         'Permit processing — CONFIRMED against the Department''s published queue (verified 2026-08-22). Employment permit applications are processed in date order of receipt, and DETE publishes the receipt date it is currently working on. As of 21 August 2026 it was processing Critical Skills Employment Permit applications received on 14 August 2026 — roughly one week of queue before an application is reached. DETE does NOT publish how long a decision takes once processing begins, so no total decision time should be quoted from this source. Check the current figure at https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/current-application-processing-dates/ rather than relying on this snapshot. The Burgh Quay IRP appointment lead time remains an unverified estimate — see the registration document.'
       )
 where corridor = 'ES_IE'
   and extracted_text like '%the Critical Skills permit decision typically takes about 12 to 16 weeks%';

-- ── 2. Burgh Quay IRP appointment — NOT confirmable, stays flagged ──────────────
update public.crawled_immigration_documents
   set extracted_text = replace(
         extracted_text,
         'Appointment lead-time estimate — NOT yet verified against recent real cases; confirm with the relocation agent on the ground: a first Burgh Quay appointment commonly takes on the order of 6 to 8 weeks to secure',
         'Appointment lead-time — STILL AN UNVERIFIED ESTIMATE. Immigration Service Delivery publishes no waiting time or appointment-availability figure on this page (checked 2026-08-22); the only official number it gives is the deadline, which is that you must register within 90 days of arrival. Treat the following as an estimate and not as guidance to plan against: a first Burgh Quay appointment commonly takes on the order of 6 to 8 weeks to secure'
       )
 where corridor = 'ES_IE'
   and extracted_text like '%Appointment lead-time estimate — NOT yet verified%';

-- ── 3. Long-stay 'D' visa — NOT confirmable, stays flagged ──────────────────────
update public.crawled_immigration_documents
   set extracted_text = replace(
         extracted_text,
         'Processing-time estimate — NOT yet verified against recent real cases; confirm with the relocation agent on the ground: the long-stay employment visa commonly takes on the order of 4 to 8 weeks',
         'Processing-time — STILL AN UNVERIFIED ESTIMATE. The Immigration Service Delivery long-stay employment visa page publishes no processing-time figure (checked 2026-08-22). Treat the following as an estimate and not as guidance to plan against: the long-stay employment visa commonly takes on the order of 4 to 8 weeks'
       )
 where corridor = 'ES_IE'
   and extracted_text like '%Processing-time estimate — NOT yet verified%';

-- ── 4. Re-derive the document hash from the new text ───────────────────────────
-- The seed's convention, verified against all three rows in prod:
--   content_hash = encode(sha256(extracted_text::bytea), 'hex')
-- Leaving it stale would make the crawl store claim a digest of text it no longer holds.
update public.crawled_immigration_documents
   set content_hash = encode(sha256(extracted_text::bytea), 'hex')
 where corridor = 'ES_IE'
   and content_hash <> encode(sha256(extracted_text::bytea), 'hex');

-- ── 5. Retire the superseded chunks ────────────────────────────────────────────
-- Keyed on the OLD wording, which none of the replacements above reproduce, so this
-- cannot catch a freshly written chunk. Deactivated rather than deleted: the embedding
-- and its citation/rejection counters are the audit trail of what was served.
update public.immigration_corpus_chunks
   set is_active = false
 where corridor = 'ES_IE'
   and is_active = true
   and chunk_text like '%NOT yet verified against recent real cases%';

commit;
