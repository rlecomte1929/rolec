-- ---------------------------------------------------------------------------
-- ES EX-17 (TIE): fill the split date of birth — form-fill Build A follow-up.
--
-- The EX-17 asks for the date of birth in THREE separate AcroForm text fields
-- (Dia_Nacimiento / Mes_Nacimiento / Año_Nacimiento) rather than one. The fill
-- pipeline maps one vault value per row, so this seeds three rows that all read
-- the governed `date_of_birth` vault column and use the new date-part format
-- rules (apply_format_rule: date_day / date_month / date_year — day and month
-- zero-padded, year 4-digit) to write each box.
--
-- The Sexo and Estado Civil single-radio fields are filled by build_choice_fill
-- (CHOICE_GROUPS["ES_ex17_v2024"], code — not the mappings table), matching how
-- the FR CERFA radios are handled.
--
-- Idempotent: removes just these three form_field_ids before insert, leaving the
-- text rows from 20261136000000 untouched.
-- ---------------------------------------------------------------------------

BEGIN;

DELETE FROM public.form_field_mappings
 WHERE form_id = 'ES_ex17_v2024'
   AND form_field_id IN ('Dia_Nacimiento', 'Mes_Nacimiento', 'Año_Nacimiento');

INSERT INTO public.form_field_mappings
  (form_id, form_name, corridor_to, visa_type,
   form_field_id, form_field_label, vault_field_path, format_rule, exact_match_required)
VALUES
  ('ES_ex17_v2024', 'Spain — Foreigner ID card application (EX-17 / TIE, PAG F94803)', 'ES', 'residence',
     'Dia_Nacimiento', 'Día de nacimiento (day of birth)',   'date_of_birth', 'date_day',   FALSE),
  ('ES_ex17_v2024', 'Spain — Foreigner ID card application (EX-17 / TIE, PAG F94803)', 'ES', 'residence',
     'Mes_Nacimiento', 'Mes de nacimiento (month of birth)', 'date_of_birth', 'date_month', FALSE),
  ('ES_ex17_v2024', 'Spain — Foreigner ID card application (EX-17 / TIE, PAG F94803)', 'ES', 'residence',
     'Año_Nacimiento', 'Año de nacimiento (year of birth)',  'date_of_birth', 'date_year',  FALSE);

COMMIT;
