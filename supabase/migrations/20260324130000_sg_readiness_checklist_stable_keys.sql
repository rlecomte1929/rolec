-- Backfill stable_key for Singapore employment checklist rows (provenance mapping).
-- Safe if already set (overwrites only when matching sort_order on SG employment template).

UPDATE public.readiness_template_checklist_items AS c
SET stable_key = v.sk
FROM public.readiness_templates AS t,
  (VALUES
    (1, 'sg_ep_contract'),
    (2, 'sg_passport_bio'),
    (3, 'sg_education_certs'),
    (4, 'sg_mom_photos'),
    (5, 'sg_company_ep_submit'),
    (6, 'sg_ipa'),
    (7, 'sg_medical'),
    (8, 'sg_issue_pass'),
    (9, 'sg_housing_school'),
    (10, 'sg_relocation_vendor')
  ) AS v(sort_o, sk)
WHERE c.template_id = t.id
  AND t.destination_key = 'SG'
  AND t.route_key = 'employment'
  AND c.sort_order = v.sort_o;
