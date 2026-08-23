-- Evidence reconciliation scoreboard.
--
-- WHAT THIS ANSWERS: of the requirement_facts we are serving RIGHT NOW, how many carry a quote
-- that actually appears in the source text we archived for them?
--
-- WHICH COLUMN. `knowledge_docs` carries two source-text columns and they are not the same.
-- `content_excerpt` is the evidence column: it is what `admin_content_review` shows a reviewer,
-- what `backfill_fact_evidence.py` writes, and what `content_sha256` hashes (measured
-- 2026-08-23: of 267 documents with a hash, 254 match the excerpt and 23 match text_content).
-- `text_content` is the original ingest's column, since unmaintained — 638 of 758 documents hold
-- under 200 characters there. Checking a quote against `text_content` therefore reports a false
-- catastrophe; this report uses `content_excerpt` and falls back to `text_content`, the same
-- precedence `admin.py` and `official_ingest_service.py` already use.
--
-- NORMALISATION. Markup only, never words — and bullets BEFORE whitespace, because removing a
-- bullet after collapsing leaves a double space and a true quote reads as missing.
WITH src AS (
  SELECT f.id, f.fact_key, f.status, f.evidence_verified, f.evidence_quote,
         e.destination_country,
         coalesce(nullif(k.content_excerpt, ''), k.text_content) AS source_text
  FROM requirement_facts f
  JOIN requirement_entities e ON e.id = f.entity_id
  LEFT JOIN knowledge_docs k ON k.id = f.source_doc_id
  WHERE f.status = 'approved' AND COALESCE(f.evidence_verified, TRUE) = TRUE
), n AS (
  SELECT *,
    regexp_replace(regexp_replace(lower(coalesce(evidence_quote,'')), '[•·▪◦]',' ','g'),
                   '\s+',' ','g') AS q,
    regexp_replace(regexp_replace(lower(coalesce(source_text,'')),   '[•·▪◦]',' ','g'),
                   '\s+',' ','g') AS s
  FROM src
), verdict AS (
  SELECT destination_country,
    CASE
      WHEN coalesce(source_text,'') = ''            THEN 'no source archived'
      WHEN source_text LIKE 'Otto bridge capture%'  THEN 'placeholder source'
      WHEN length(source_text) < 200                THEN 'source under 200 chars'
      WHEN btrim(coalesce(evidence_quote,'')) = ''  THEN 'no quote to check'
      WHEN position(btrim(q) in s) > 0              THEN 'EVIDENCED'
      ELSE 'quote not in source'
    END AS verdict
  FROM n
)
SELECT verdict, count(*) AS served_facts,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct,
       string_agg(DISTINCT destination_country, ' ' ORDER BY destination_country) AS destinations
FROM verdict
GROUP BY verdict
ORDER BY served_facts DESC;
