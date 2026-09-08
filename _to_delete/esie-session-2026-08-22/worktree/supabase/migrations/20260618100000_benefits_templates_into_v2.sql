-- N12-followup-a / AIQ-889 — Port the out-of-band benefits_templates table
-- (42 rows = 14 spend categories x 3 generosity tiers) into the unified
-- policy_templates_v2 schema as a distinct CATEGORY-LEVEL BENCHMARK layer,
-- retiring the 4th legacy template system (benefits_templates).
--
-- WHY a distinct layer (not merged into LTA_*): benefits_templates is a
-- category-level benchmark *reference* (AIRINC/Mercer/ECA/KPMG/CIGNA-sourced
-- spend budgets per category), while N12's LTA/STA templates are granular
-- per-benefit operational defaults. There is no clean category->benefit_key
-- 1:1 mapping (one category spans many benefit keys), so merging would be lossy
-- and a guess. Approved design: port faithfully as policy_type='benchmark_reference'.
--
-- ADDITIVE ONLY: N12's LTA/STA 1.0.0 rows are untouched. Currency is EUR
-- (preserved, NOT coerced to the USD of the LTA/STA registry). Idempotent.
-- Mirrors backend/app/services/policy_template_service.py _BENCHMARK_CATEGORIES.
--
-- category_id -> benefit_key mapping (verified against prod policy_categories.code):
--   CAT-01 Housing & Accommodation   CAT-02 Transportation        CAT-03 International Schooling
--   CAT-04 Cost of Living Adjustment CAT-05 Healthcare & Wellbeing CAT-06 Tax & Social Security
--   CAT-07 Travel & Home Leave       CAT-08 Relocation Assistance  CAT-09 Settling-In & Orientation
--   CAT-10 Spouse & Family Support   CAT-11 Assignment Allowances  CAT-12 End of Assignment
--   CAT-13 Governance & Process      CAT-14 Legal & Compliance
-- benefit_key is kept as the category code (CAT-NN) — the category IS the unit here.

BEGIN;

-- 1. Widen the policy_type CHECK to admit the benchmark layer.
ALTER TABLE public.policy_templates_v2 DROP CONSTRAINT IF EXISTS policy_templates_v2_policy_type_check;
ALTER TABLE public.policy_templates_v2 ADD CONSTRAINT policy_templates_v2_policy_type_check
  CHECK (policy_type IN ('LTA', 'STA', 'commuter', 'benchmark_reference'));

-- 2. Provenance columns (benefits_templates carried these; v2 did not). Nullable —
--    existing LTA/STA rows stay NULL. No USD coercion: currency is stored per row.
ALTER TABLE public.policy_template_benefits ADD COLUMN IF NOT EXISTS currency text;
ALTER TABLE public.policy_template_benefits ADD COLUMN IF NOT EXISTS unit text;
ALTER TABLE public.policy_template_benefits ADD COLUMN IF NOT EXISTS benchmark_source text;

-- 3. Three benchmark-tier templates.
INSERT INTO public.policy_templates_v2 (template_id, version, policy_type, generosity_tier, status)
VALUES
  ('BENCHMARK_conservative', '1.0.0', 'benchmark_reference', 'conservative', 'active'),
  ('BENCHMARK_standard',     '1.0.0', 'benchmark_reference', 'standard',     'active'),
  ('BENCHMARK_premium',      '1.0.0', 'benchmark_reference', 'premium',      'active')
ON CONFLICT (template_id, version) DO NOTHING;

-- 4. The 42 category caps (14 categories x 3 tiers), keyed by category code.
WITH cat(code, display_name, unit, src, conservative, standard, premium) AS (VALUES
  ('CAT-01', 'Housing & Accommodation',   'month',    'AIRINC 2025 European upper quartile',                         1800, 2800, 4500),
  ('CAT-02', 'Transportation',            'month',    'ECA International 2024 median (car lease option)',             400,  750,  1400),
  ('CAT-03', 'International Schooling',    'month',    'AIRINC 2025 state school contribution, Europe',               800,  1800, 4000),
  ('CAT-04', 'Cost of Living Adjustment', 'month',    'Mercer 2024 COLA upper range, high-cost city',                400,  700,  1200),
  ('CAT-05', 'Healthcare & Wellbeing',    'month',    'CIGNA Global 2025 premium plan + dental + mental health',     250,  450,  800),
  ('CAT-06', 'Tax & Social Security',     'year',     'KPMG 2024 full tax equalisation advisory',                    2500, 4500, 9000),
  ('CAT-07', 'Travel & Home Leave',       'year',     'AIRINC 2025 two economy+ return flights per year',            900,  3000, 8000),
  ('CAT-08', 'Relocation Assistance',     'per_move', 'Mercer 2024 managed move + lump-sum, European executive',     8000, 15000, 28000),
  ('CAT-09', 'Settling-In & Orientation', 'per_move', 'ECA International 2024 standard DSP, 5 days + admin support',  1500, 3000, 6000),
  ('CAT-10', 'Spouse & Family Support',   'per_move', 'AIRINC 2025 full partner career coaching + integration',      1000, 3500, 8000),
  ('CAT-11', 'Assignment Allowances',     'month',    'ECA International 2024 standard foreign service premium',      300,  700,  1500),
  ('CAT-12', 'End of Assignment',         'per_move', 'Mercer 2024 repatriation median',                             5000, 10000, 20000),
  ('CAT-13', 'Governance & Process',      'year',     'ReloPass internal standard (policy management + HR support)', 500,  1000, 2000),
  ('CAT-14', 'Legal & Compliance',        'per_move', 'KPMG 2024 full immigration + compliance advisory',            2000, 4000, 8000)
),
tier(template_id, tier_name) AS (VALUES
  ('BENCHMARK_conservative', 'conservative'),
  ('BENCHMARK_standard',     'standard'),
  ('BENCHMARK_premium',      'premium')
)
INSERT INTO public.policy_template_benefits
  (template_pk, benefit_key, default_value, value_type, is_required, currency, unit, benchmark_source)
SELECT
  t2.id,
  cat.code,
  CASE tier.tier_name
    WHEN 'conservative' THEN cat.conservative
    WHEN 'standard'     THEN cat.standard
    ELSE                     cat.premium
  END,
  'amount', false, 'EUR', cat.unit, cat.src
FROM cat
CROSS JOIN tier
JOIN public.policy_templates_v2 t2
  ON t2.template_id = tier.template_id AND t2.version = '1.0.0'
ON CONFLICT (template_pk, benefit_key) DO NOTHING;

COMMIT;
