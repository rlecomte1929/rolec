-- ---------------------------------------------------------------------------
-- Seed form_field_mappings for the Spanish EX-17 (TIE) AcroForm — form-fill Build A,
-- the second real government form after the France-Visas CERFA (#2286).
--
-- Solicitud de Tarjeta de Identidad de Extranjero (TIE), the non-EU foreigner ID card
-- application, Punto de Acceso General form F94803 (título "Solicitud de Tarjeta de
-- Identidad de Extranjero (TIE)"). Verified as a genuine fillable AcroForm: 63 named
-- fields, PDF 1.7, committed as a fixture at docs/form-autofill/artifacts/es_ex17_F94803.pdf.
--
-- This seeds the CLEAN text (/Tx) fields that map to a vault column the Build B fact
-- dictionary governs. Deferred to a follow-up (they need pipeline extensions the fill
-- does not have yet):
--   * date of birth — split across THREE fields (Dia_Nacimiento / Mes_Nacimiento /
--     Año_Nacimiento); needs a one-value-to-three-fields date splitter;
--   * Sexo — a SINGLE /Btn radio with export values /Hombre|/Mujer (not the CERFA's
--     one-checkbox-per-option shape), so it needs a single-radio export-value layer;
--   * Estado Civil — likewise (/Soltero|/Casado|/Viudo|/Divorciado|/Separado);
--   * 2 Apellido (second surname) — Spanish two-surname convention; no vault field.
--
-- Applies to non-EU → ES (régimen general). Idempotent: ES_ex17 rows removed before insert.
-- ---------------------------------------------------------------------------

BEGIN;

DELETE FROM public.form_field_mappings
 WHERE form_id = 'ES_ex17_v2024';

INSERT INTO public.form_field_mappings
  (form_id, form_name, corridor_to, visa_type,
   form_field_id, form_field_label, vault_field_path, format_rule, exact_match_required)
VALUES
  ('ES_ex17_v2024', 'Spain — Foreigner ID card application (EX-17 / TIE, PAG F94803)', 'ES', 'residence',
     '1er Apellido',  'Primer apellido (first surname)',  'legal_last_name',  'name_normalise',  TRUE),
  ('ES_ex17_v2024', 'Spain — Foreigner ID card application (EX-17 / TIE, PAG F94803)', 'ES', 'residence',
     'Nombre',        'Nombre (given name)',              'legal_first_name', 'name_normalise',  TRUE),
  ('ES_ex17_v2024', 'Spain — Foreigner ID card application (EX-17 / TIE, PAG F94803)', 'ES', 'residence',
     'PASAPORTE',     'Número de pasaporte',              'passport_number',  'passport_format', TRUE),
  ('ES_ex17_v2024', 'Spain — Foreigner ID card application (EX-17 / TIE, PAG F94803)', 'ES', 'residence',
     'Nacionalidad',  'Nacionalidad',                     'nationality',      'uppercase',       FALSE),
  ('ES_ex17_v2024', 'Spain — Foreigner ID card application (EX-17 / TIE, PAG F94803)', 'ES', 'residence',
     'Lugar',         'Lugar de nacimiento (place of birth)', 'place_of_birth', 'name_normalise', FALSE);

COMMIT;
