-- Pending-backlog conversion queue — reproducible verdict manifest (2026-09-11)
-- Read-only. Emits one row per pending requirement_items row across the four demo corridors,
-- with a verdict: APPROVE / COUNSEL / HOLD_DIRECTION / HOLD_DUPE_APPROVED / HOLD_DUPE_INTERNAL /
-- HOLD_REPRESENTATIVE. The COUNSEL predicate is identical to
-- backend/app/services/lawyer_review_gate.blocks_approval.
WITH p AS (
  SELECT id, country_code, pillar, verification_status, title,
    COALESCE(((citations_json ~ '"needs_lawyer_review"\s*:\s*true')
       OR (applies_to_nationality_classes_json ~ '"needs_lawyer_review"\s*:\s*true')), false)
     AND lower(coalesce(attestation_status,'')) <> 'attested' AS flagged
  FROM public.requirement_items
  WHERE review_status = 'pending'
    AND country_code IN ('IRELAND','FRANCE','NORWAY','SPAIN','SINGAPORE','ECUADOR','UNITED STATES')
),
dupe_appr AS (
  SELECT DISTINCT p.id
  FROM p JOIN public.requirement_items a
    ON a.country_code = p.country_code AND a.review_status = 'approved'
   AND lower(trim(a.title)) = lower(trim(p.title))
),
dupe_internal AS (
  SELECT id FROM (
    SELECT id, row_number() OVER (
      PARTITION BY country_code, pillar, lower(trim(title)) ORDER BY id) AS rn
    FROM p
  ) x WHERE rn > 1
)
SELECT
  CASE
    WHEN flagged THEN 'COUNSEL'
    WHEN country_code = 'SPAIN' THEN 'HOLD_DIRECTION'            -- ES:IE-ES:* = arrival, not Andrea's exit
    WHEN p.id IN (SELECT id FROM dupe_appr) THEN 'HOLD_DUPE_APPROVED'
    WHEN p.id IN (SELECT id FROM dupe_internal) THEN 'HOLD_DUPE_INTERNAL'
    WHEN country_code = 'UNITED STATES' THEN 'HOLD_REPRESENTATIVE'
    ELSE 'APPROVE'
  END AS verdict,
  country_code, pillar, verification_status, p.id, title
FROM p
ORDER BY verdict, country_code, pillar, title;
