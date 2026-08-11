/**
 * [S3] The admin editor must not delete template data it does not display.
 *
 * `form_templates.fields` has more than one writer. Seeded data sheets carry keys the
 * admin UI has no input for — `section`, `label_nb`/`label_de`/`label_fr`, `note`,
 * `portal_url`, `consult_professional`. `normalizeFields` rebuilt each field from the
 * modelled keys alone, so loading a data sheet into the editor and pressing Save wrote
 * those keys away. Silently: the editor never showed them, so it never showed them
 * going.
 *
 * The FR→NO sheet would have lost its Norwegian labels AND its section grouping in one
 * click — and the grouping loss is the worse half, because the PDF renderer falls back
 * to `fields[].section` when a template has no `sections`, so the sheet degrades to a
 * single flat block with no error anywhere.
 *
 * These assert on the ROUND TRIP (normalize → withComputedPositions, which is what the
 * save path actually sends) rather than on normalizeFields alone, because either step
 * dropping a key produces the same data loss.
 */
import { describe, it, expect } from 'vitest';
import { normalizeFields, withComputedPositions } from '../FieldDefinitionEditor';

/** A field as actually seeded by 20261015000000_seed_frno_data_sheet.sql. */
const SEEDED_DATA_SHEET_FIELD = {
  id: 'd_number_reason',
  label: 'Why you need a D-number',
  label_nb: 'Hvorfor du trenger et D-nummer',
  type: 'text',
  required: true,
  position: 3,
  section: 'd_number',
  note: 'Skatteetaten asks for the purpose of stay.',
  portal_url: 'https://www.skatteetaten.no/',
  consult_professional: false,
  prefill_source: 'case.purpose',
  requires_original: false,
};

/** The five keys the editor has no input for and used to destroy. */
const UNMODELLED_KEYS = [
  'label_nb',
  'section',
  'note',
  'portal_url',
  'consult_professional',
] as const;

describe('normalizeFields preserves unmodelled keys', () => {
  it('keeps every key the editor does not display', () => {
    const [out] = normalizeFields([{ ...SEEDED_DATA_SHEET_FIELD }]);
    for (const key of UNMODELLED_KEYS) {
      expect(out[key], `normalizeFields dropped "${key}"`).toEqual(
        SEEDED_DATA_SHEET_FIELD[key as keyof typeof SEEDED_DATA_SHEET_FIELD],
      );
    }
  });

  it('survives the full save round trip', () => {
    const roundTripped = withComputedPositions(
      normalizeFields([{ ...SEEDED_DATA_SHEET_FIELD }]),
    );
    expect(roundTripped[0].section).toBe('d_number');
    expect(roundTripped[0].label_nb).toBe('Hvorfor du trenger et D-nummer');
  });

  it('preserves a falsy unmodelled value rather than dropping it', () => {
    // `consult_professional: false` is the trap — a truthiness-based copy would lose it,
    // and "we did not tell you to consult a professional" is not the same claim as
    // "we have no opinion".
    const [out] = normalizeFields([{ ...SEEDED_DATA_SHEET_FIELD }]);
    expect(out).toHaveProperty('consult_professional');
    expect(out.consult_professional).toBe(false);
  });

  it('still normalizes the modelled keys it owns', () => {
    // Preservation must not become "pass everything through untouched" — the coercion
    // is why this function exists.
    const [out] = normalizeFields([
      { id: 42, label: null, type: undefined, required: 'yes', pdf_x: 'NaN' },
    ] as unknown as Array<Record<string, unknown>>);
    expect(out.id).toBe('');
    expect(out.label).toBe('');
    expect(out.type).toBe('text');
    expect(out.required).toBe(false);       // 'yes' is not `true`
    expect(out.pdf_x).toBeUndefined();      // 'NaN' is not a finite number
    expect(out.position).toBe(1);           // derived from index
  });

  it('does not let an unmodelled key shadow a modelled one', () => {
    // The spread comes FIRST precisely so the coerced values win.
    const [out] = normalizeFields([
      { id: 'x', label: 'X', type: 'text', required: true, position: 'not-a-number' },
    ] as unknown as Array<Record<string, unknown>>);
    expect(out.position).toBe(1);
  });
});
