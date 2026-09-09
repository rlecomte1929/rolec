-- [AIQ-1874] Four FR-NO legal accreditations claimed Den Norske Advokatforening
-- with evidence that only confirms company registration. Otto chose option (b):
-- drop the bar claim to Brønnøysund Enhetsregisteret (tier-2 entity confirmation).
--
-- UPDATE only. RLS already on supplier_accreditations / suppliers. Do not apply
-- to prod from this PR; operator apply is out of band.
--
-- Order is load-bearing: the fabricated Sulland organisation number is rewritten
-- before any body/status change.

BEGIN;

-- 1. Fabricated identifier must not survive a later rewrite.
UPDATE public.supplier_accreditations
SET membership_number = '918 627 995',
    updated_at = now()
WHERE replace(btrim(membership_number), ' ', '') = '914450133';

-- 2. Registered name, not the truncated harvest label.
UPDATE public.suppliers s
SET name = 'Humlen & Helle Advokater AS',
    legal_name = CASE
      WHEN s.legal_name IS NULL OR btrim(s.legal_name) = ''
        THEN 'HUMLEN & HELLE ADVOKATER AS'
      ELSE s.legal_name
    END
WHERE s.id IN (
    SELECT sa.supplier_id
    FROM public.supplier_accreditations sa
    WHERE replace(btrim(sa.membership_number), ' ', '') = '915363954'
)
AND s.name IS DISTINCT FROM 'Humlen & Helle Advokater AS';

-- 3. Bar claim dropped. membership_number remains the 9-digit organisation
-- number because that is what Enhetsregisteret identifies; it is not a bar number.
UPDATE public.supplier_accreditations sa
SET body = 'Brønnøysund Enhetsregisteret',
    evidence_url = 'https://virksomhet.brreg.no/nb/oppslag/enheter/'
                   || replace(btrim(sa.membership_number), ' ', ''),
    notes = '[AIQ-1874] Brønnøysund Enhetsregisteret confirms the registered company. '
            'membership_number is the organisation number, not a Den Norske Advokatforening '
            'membership number and not an advokatbevilling. Evidence is virksomhet.brreg.no '
            '(tier-2 entity confirmation). Bar membership left unclaimed.',
    status = 'claimed',
    verification_method = NULL,
    verified_at = NULL,
    verified_by = NULL,
    updated_at = now()
WHERE replace(btrim(sa.membership_number), ' ', '') IN (
    '918627995',
    '917334110',
    '915363954',
    '926162578'
)
AND (
    sa.body ILIKE '%Advokatforening%'
    OR sa.body ILIKE '%Brønnøysund%'
    OR sa.body ILIKE '%Enhetsregisteret%'
);

COMMIT;
