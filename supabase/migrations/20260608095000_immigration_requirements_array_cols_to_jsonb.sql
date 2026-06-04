-- AIQ-756 — immigration_requirements: 4 array columns text[] -> jsonb (fresh-replay parity)
--
-- 20260518120000_immigration_core_tables.sql creates apostille_countries,
-- translation_languages, success_tips and common_rejection_reasons as TEXT[].
-- On prod they were converted to jsonb out-of-band (never committed), so a fresh
-- `supabase db reset` / Supabase Preview diverges: the columns stay text[], and
-- the corridor-corpus ingests at 20260608100000 / 20260608110000 — which write
-- '[]'::jsonb / '["US"]'::jsonb — fail on a fresh DB with
--   42804: column "apostille_countries" is of type text[] but expression is of type jsonb.
--
-- Align a fresh DB to prod by converting the four columns to jsonb. Placed after
-- the CREATE (20260518120000) and before the first ingest (20260608100000).
--
-- GUARD: each column is converted only while it is still an array type, so on
-- prod (already jsonb) and on any re-run this is a clean no-op. to_jsonb() turns a
-- text[] like {US} into the jsonb array ["US"]; the table holds no rows at this
-- point on a fresh replay (it is seeded out-of-band), so the cast is trivial.

do $$
declare
  col text;
begin
  foreach col in array array[
    'apostille_countries',
    'translation_languages',
    'success_tips',
    'common_rejection_reasons'
  ]
  loop
    if (select data_type
          from information_schema.columns
         where table_schema = 'public'
           and table_name   = 'immigration_requirements'
           and column_name  = col) = 'ARRAY' then
      execute format(
        'alter table public.immigration_requirements alter column %I type jsonb using to_jsonb(%I)',
        col, col);
    end if;
  end loop;
end $$;
