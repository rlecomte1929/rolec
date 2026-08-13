-- [Stage 9 · Phase 1] Which countries neighbour which, and whether that neighbour is
-- default-included in an origin-sourced catchment.
--
-- Addendum A §A.5.4. A neighbouring-country MOVER is plausible — a Strasbourg employee's
-- household goods are as easily packed by a Kehl agent 5 km away. A neighbouring-country BANK
-- or SCHOOL is not, which is why the caller applies this only to origin-sourced categories.
--
-- `default_included = false` is the escape valve for borders that are geographically real but
-- commercially or logistically not interchangeable:
--   * short_sea      — a crossing, not a drive (UK↔FR, IE↔UK, DK↔SE)
--   * cross-bloc     — a customs/regulatory edge that makes a household move a different job
--                      entirely (ES↔MA, PL↔UA, FI↔RU)
--
-- SYMMETRY IS GUARANTEED BY CONSTRUCTION, not by discipline: the seed lists each pair once and
-- inserts both directions from the same row, so the two can never disagree on
-- `default_included`. An asymmetry here would be a silent one-way border — vendors visible
-- FR→DE but not DE→FR — and a test asserts it holds.
--
-- Nothing reads this table yet; the reader ships separately once this is applied.
BEGIN;

CREATE TABLE IF NOT EXISTS public.country_adjacency (
  country_a        char(2)     NOT NULL,
  country_b        char(2)     NOT NULL,
  relation_type    text        NOT NULL,
  default_included boolean     NOT NULL DEFAULT true,
  notes            text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (country_a, country_b),
  CONSTRAINT country_adjacency_distinct CHECK (country_a <> country_b),
  CONSTRAINT country_adjacency_relation_check
    CHECK (relation_type IN ('land_border', 'short_sea'))
);

COMMENT ON TABLE public.country_adjacency IS
  'Reference data: neighbouring-country pairs, stored symmetrically. default_included=false '
  'marks a border that exists but should not widen a catchment automatically.';

-- Each pair appears ONCE here. Both directions are written below.
WITH pairs(a, b, relation_type, default_included, notes) AS (
  VALUES
    -- ── EEA + CH + LI internal land borders → default-included ──────────────
    ('AT','CH','land_border', true,  NULL),
    ('AT','CZ','land_border', true,  NULL),
    ('AT','DE','land_border', true,  NULL),
    ('AT','HU','land_border', true,  NULL),
    ('AT','IT','land_border', true,  NULL),
    ('AT','LI','land_border', true,  NULL),
    ('AT','SI','land_border', true,  NULL),
    ('AT','SK','land_border', true,  NULL),
    ('BE','DE','land_border', true,  NULL),
    ('BE','FR','land_border', true,  NULL),
    ('BE','LU','land_border', true,  NULL),
    ('BE','NL','land_border', true,  NULL),
    ('BG','GR','land_border', true,  NULL),
    ('BG','RO','land_border', true,  NULL),
    ('CH','DE','land_border', true,  NULL),
    ('CH','FR','land_border', true,  NULL),
    ('CH','IT','land_border', true,  NULL),
    ('CH','LI','land_border', true,  NULL),
    ('CZ','DE','land_border', true,  NULL),
    ('CZ','PL','land_border', true,  NULL),
    ('CZ','SK','land_border', true,  NULL),
    ('DE','DK','land_border', true,  NULL),
    ('DE','FR','land_border', true,  NULL),
    ('DE','LU','land_border', true,  NULL),
    ('DE','NL','land_border', true,  NULL),
    ('DE','PL','land_border', true,  NULL),
    ('EE','LV','land_border', true,  NULL),
    ('ES','FR','land_border', true,  NULL),
    ('ES','PT','land_border', true,  NULL),
    ('FI','NO','land_border', true,  NULL),
    ('FI','SE','land_border', true,  NULL),
    ('FR','IT','land_border', true,  NULL),
    ('FR','LU','land_border', true,  NULL),
    ('HR','HU','land_border', true,  NULL),
    ('HR','SI','land_border', true,  NULL),
    ('HU','RO','land_border', true,  NULL),
    ('HU','SI','land_border', true,  NULL),
    ('HU','SK','land_border', true,  NULL),
    ('IT','SI','land_border', true,  NULL),
    ('LT','LV','land_border', true,  NULL),
    ('LT','PL','land_border', true,  NULL),
    ('NO','SE','land_border', true,  NULL),
    ('PL','SK','land_border', true,  NULL),

    -- ── short sea → NOT default-included ────────────────────────────────────
    ('FR','GB','short_sea',   false, 'Channel crossing — not a drive-over move.'),
    ('GB','IE','short_sea',   false,
        'Classed short_sea per Addendum A §A.5.4. There IS a land border via Northern '
        'Ireland, but the commercial reality for a household move is a sea crossing.'),
    ('DK','SE','short_sea',   false, 'Øresund crossing.'),

    -- ── cross-bloc land borders → NOT default-included ──────────────────────
    ('ES','MA','land_border', false, 'Ceuta/Melilla. Customs edge; a different job entirely.'),
    ('PL','UA','land_border', false, 'EU external border.'),
    ('FI','RU','land_border', false, 'EU external border.')
)
INSERT INTO public.country_adjacency (country_a, country_b, relation_type, default_included, notes)
SELECT a, b, relation_type, default_included, notes FROM pairs
UNION ALL
SELECT b, a, relation_type, default_included, notes FROM pairs
ON CONFLICT (country_a, country_b) DO UPDATE
  SET relation_type    = EXCLUDED.relation_type,
      default_included = EXCLUDED.default_included,
      notes            = EXCLUDED.notes;

-- Reference data, no tenant scope — but the hard gate applies to every new public table:
-- RLS on, at least one policy, and anon revoked.
ALTER TABLE public.country_adjacency ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS country_adjacency_read_authenticated ON public.country_adjacency;
CREATE POLICY country_adjacency_read_authenticated
  ON public.country_adjacency
  FOR SELECT
  TO authenticated
  USING (true);

DROP POLICY IF EXISTS country_adjacency_service_role ON public.country_adjacency;
CREATE POLICY country_adjacency_service_role
  ON public.country_adjacency
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

GRANT SELECT ON public.country_adjacency TO authenticated;
REVOKE ALL ON public.country_adjacency FROM anon;

COMMIT;
