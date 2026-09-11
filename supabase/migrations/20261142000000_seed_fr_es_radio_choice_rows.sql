-- Seed FR/ES radio choice rows as data (form-onboarding Phase 1b). 1:1 with CHOICE_GROUPS in code.
BEGIN;
DELETE FROM public.form_field_mappings
 WHERE form_id IN ('FR_cerfa_14571_v2024','ES_ex17_v2024')
   AND field_kind IN ('single_radio','checkbox_option');
INSERT INTO public.form_field_mappings
  (form_id, form_name, corridor_to, visa_type, form_field_id, form_field_label,
   vault_field_path, field_kind, transform_spec)
VALUES
  -- FR CERFA: one checkbox per option
  ('FR_cerfa_14571_v2024','France — Long-stay visa (CERFA 14571*05)','FR','long_stay',
     'applicantGenderM','Sexe (Male)','gender','checkbox_option','{"code":"M"}'),
  ('FR_cerfa_14571_v2024','France — Long-stay visa (CERFA 14571*05)','FR','long_stay',
     'applicantGenderF','Sexe (Female)','gender','checkbox_option','{"code":"F"}'),
  ('FR_cerfa_14571_v2024','France — Long-stay visa (CERFA 14571*05)','FR','long_stay',
     'applicantGenderOther','Sexe (Other)','gender','checkbox_option','{"code":"OTHER"}'),
  ('FR_cerfa_14571_v2024','France — Long-stay visa (CERFA 14571*05)','FR','long_stay',
     'applicantMaritalCEL','État civil (Single)','marital_status','checkbox_option','{"code":"SINGLE"}'),
  ('FR_cerfa_14571_v2024','France — Long-stay visa (CERFA 14571*05)','FR','long_stay',
     'applicantMaritalMAR','État civil (Married)','marital_status','checkbox_option','{"code":"MARRIED"}'),
  ('FR_cerfa_14571_v2024','France — Long-stay visa (CERFA 14571*05)','FR','long_stay',
     'applicantMaritalSEP','État civil (Separated)','marital_status','checkbox_option','{"code":"SEPARATED"}'),
  ('FR_cerfa_14571_v2024','France — Long-stay visa (CERFA 14571*05)','FR','long_stay',
     'applicantMaritalDIV','État civil (Divorced)','marital_status','checkbox_option','{"code":"DIVORCED"}'),
  ('FR_cerfa_14571_v2024','France — Long-stay visa (CERFA 14571*05)','FR','long_stay',
     'applicantMaritalVEU','État civil (Widowed)','marital_status','checkbox_option','{"code":"WIDOWED"}'),
  ('FR_cerfa_14571_v2024','France — Long-stay visa (CERFA 14571*05)','FR','long_stay',
     'applicantMaritalAUT','État civil (Other)','marital_status','checkbox_option','{"code":"OTHER"}'),
  -- ES EX-17: one radio field per group, Spanish export values
  ('ES_ex17_v2024','Spain — EX-17 (TIE)','ES','residence',
     'Sexo','Sexo','gender','single_radio','{"values":{"M":"/Hombre","F":"/Mujer"}}'),
  ('ES_ex17_v2024','Spain — EX-17 (TIE)','ES','residence',
     'Estado Civil','Estado civil','marital_status','single_radio',
     '{"values":{"SINGLE":"/Soltero","MARRIED":"/Casado","WIDOWED":"/Viudo","DIVORCED":"/Divorciado","SEPARATED":"/Separado"}}');
COMMIT;
