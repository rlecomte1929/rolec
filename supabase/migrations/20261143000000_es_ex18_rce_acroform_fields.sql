-- ---------------------------------------------------------------------------
-- Seed form_field_mappings for the Spanish EX-18 (RCE / EU citizen registration)
-- AcroForm — form-fill Build A, the third real government form after FR CERFA and
-- ES EX-17.
--
-- Solicitud de inscripción en el Registro Central de Extranjeros — Residencia
-- ciudadano de la UE (RD 240/2007). Official editable PDF from the Ministerio de
-- Inclusión catalog (modelos generales), last-modified 2025-05-21:
--   https://www.inclusion.gob.es/documents/d/migraciones/ex18-formulario-inscripcion-en-el-rce-residencia-ciudadano-de-la-ue-editable
-- Verified as a genuine fillable AcroForm via pypdf.get_fields(): 105 named
-- fields (68 /Tx, 37 /Btn), PDF 1.7. The imprimible twin on the same catalog page
-- has 0 fields (flattened) and is rejected. Fixture:
--   docs/form-autofill/artifacts/es_ex18_rce_editable.pdf
--
-- Field names are Acrobat defaults (Texto1… / Casilla de verificaciónN) with no
-- /TU. Identity mappings were resolved from widget Rect vs the printed labels on
-- page 1 of that PDF — not invented:
--   Texto1  PASAPORTE
--   Texto5  1er Apellido
--   Texto7  Nombre
--   Texto8/9/10  Fecha de nacimiento (día / mes / año)
--   Texto11 Lugar
--   Texto13 Nacionalidad
--   Casilla 2/3  Sexo H / M  (checkbox_option, FR shape — not EX-17 single_radio)
--   Casilla 4–8  Estado civil S / C / V / D / Sp
-- Deferred (no governed vault path, or a value we cannot derive):
--   * 2º Apellido (Texto6) — Spanish two-surname convention; no vault field
--   * NIE split (Texto2/3/4)
--   * Sexo X/indefinido (Casilla 1) — legal status in origin country, not vault OTHER
--   * parent names, address, phone, email, representative, situation-in-Spain
--
-- visa_type = eea_registration (trigger_engine: EEA national → ES). Distinct from
-- ES_ex17_v2024 / residence (non-EU TIE). Idempotent: DELETE is scoped to this
-- form_id AND the field_kind values this file inserts — never an unscoped
-- WHERE form_id (that would wipe sibling rows of other kinds).
-- ---------------------------------------------------------------------------

BEGIN;

DELETE FROM public.form_field_mappings
 WHERE form_id = 'ES_ex18_v2024'
   AND field_kind IN ('text', 'checkbox_option');

INSERT INTO public.form_field_mappings
  (form_id, form_name, corridor_to, visa_type,
   form_field_id, form_field_label, vault_field_path,
   format_rule, exact_match_required, field_kind, transform_spec)
VALUES
  -- text (/Tx)
  ('ES_ex18_v2024', 'Spain — EU citizen registration (EX-18 / RCE)', 'ES', 'eea_registration',
     'Texto1',  'Pasaporte',                         'passport_number',  'passport_format', TRUE,  'text', NULL),
  ('ES_ex18_v2024', 'Spain — EU citizen registration (EX-18 / RCE)', 'ES', 'eea_registration',
     'Texto5',  'Primer apellido (first surname)',      'legal_last_name',  'name_normalise',  TRUE,  'text', NULL),
  ('ES_ex18_v2024', 'Spain — EU citizen registration (EX-18 / RCE)', 'ES', 'eea_registration',
     'Texto7',  'Nombre (given name)',                'legal_first_name', 'name_normalise',  TRUE,  'text', NULL),
  ('ES_ex18_v2024', 'Spain — EU citizen registration (EX-18 / RCE)', 'ES', 'eea_registration',
     'Texto8',  'Día de nacimiento (day of birth)',     'date_of_birth',     'date_day',        FALSE, 'text', NULL),
  ('ES_ex18_v2024', 'Spain — EU citizen registration (EX-18 / RCE)', 'ES', 'eea_registration',
     'Texto9',  'Mes de nacimiento (month of birth)',  'date_of_birth',     'date_month',      FALSE, 'text', NULL),
  ('ES_ex18_v2024', 'Spain — EU citizen registration (EX-18 / RCE)', 'ES', 'eea_registration',
     'Texto10', 'Año de nacimiento (year of birth)',    'date_of_birth',     'date_year',       FALSE, 'text', NULL),
  ('ES_ex18_v2024', 'Spain — EU citizen registration (EX-18 / RCE)', 'ES', 'eea_registration',
     'Texto11', 'Lugar de nacimiento (place of birth)', 'place_of_birth',    'name_normalise',  FALSE, 'text', NULL),
  ('ES_ex18_v2024', 'Spain — EU citizen registration (EX-18 / RCE)', 'ES', 'eea_registration',
     'Texto13', 'Nacionalidad',                       'nationality',      'uppercase',       FALSE, 'text', NULL),
  -- checkbox_option (/Btn) — one independent box per option (FR CERFA shape)
  ('ES_ex18_v2024', 'Spain — EU citizen registration (EX-18 / RCE)', 'ES', 'eea_registration',
     'Casilla de verificación2', 'Sexo (Hombre)',     'gender',         NULL, FALSE, 'checkbox_option', '{"code":"M"}'),
  ('ES_ex18_v2024', 'Spain — EU citizen registration (EX-18 / RCE)', 'ES', 'eea_registration',
     'Casilla de verificación3', 'Sexo (Mujer)',       'gender',         NULL, FALSE, 'checkbox_option', '{"code":"F"}'),
  ('ES_ex18_v2024', 'Spain — EU citizen registration (EX-18 / RCE)', 'ES', 'eea_registration',
     'Casilla de verificación4', 'Estado civil (Soltero)',   'marital_status', NULL, FALSE, 'checkbox_option', '{"code":"SINGLE"}'),
  ('ES_ex18_v2024', 'Spain — EU citizen registration (EX-18 / RCE)', 'ES', 'eea_registration',
     'Casilla de verificación5', 'Estado civil (Casado)',   'marital_status', NULL, FALSE, 'checkbox_option', '{"code":"MARRIED"}'),
  ('ES_ex18_v2024', 'Spain — EU citizen registration (EX-18 / RCE)', 'ES', 'eea_registration',
     'Casilla de verificación6', 'Estado civil (Viudo)',    'marital_status', NULL, FALSE, 'checkbox_option', '{"code":"WIDOWED"}'),
  ('ES_ex18_v2024', 'Spain — EU citizen registration (EX-18 / RCE)', 'ES', 'eea_registration',
     'Casilla de verificación7', 'Estado civil (Divorciado)','marital_status', NULL, FALSE, 'checkbox_option', '{"code":"DIVORCED"}'),
  ('ES_ex18_v2024', 'Spain — EU citizen registration (EX-18 / RCE)', 'ES', 'eea_registration',
     'Casilla de verificación8', 'Estado civil (Separado)',  'marital_status', NULL, FALSE, 'checkbox_option', '{"code":"SEPARATED"}');

COMMIT;
