/**
 * Phase 3 — client-side CSV export of the Document Data Sheet.
 * Pure function over the DataSheet DTO; no rendering, no api client.
 */
import { describe, it, expect } from 'vitest';
import { buildDatasheetCsv, datasheetCsvFilename } from '../datasheetCsv';
import type { DataSheet, DataSheetField } from '../../../api/datasheet';

function field(o: Partial<DataSheetField> = {}): DataSheetField {
  return {
    fieldId: o.fieldId ?? 'f',
    factKey: o.factKey ?? null,
    label: o.label ?? 'Label',
    category: o.category ?? null,
    source: o.source ?? 'intake',
    value: o.value ?? null,
    confidence: o.confidence ?? null,
    hint: o.hint ?? null,
    guidance: o.guidance ?? null,
    requiresOriginal: o.requiresOriginal ?? false,
    employerActionNote: o.employerActionNote ?? null,
  };
}

const SHEET: DataSheet = {
  caseRef: 'c1', employeeName: 'Camille Moreau', corridor: 'FR_NO', corridorLabel: 'FR→NO',
  movementBasis: null, generatedAt: '2026-09-09T00:00:00Z', completionPct: 92, needsInputCount: 1,
  banners: [], consultProfessional: [], covered: true,
  sections: [
    {
      stepId: 'd_number', title: 'D Number', authority: 'Skatteetaten', sourceUrl: null,
      processNote: null, channels: [], order: 0, responsibleParty: null, slaNote: null,
      deadline: { date: '2026-09-01', isSuggested: false, isHard: true },
      fields: [
        field({ label: 'Full name', value: 'Camille Moreau', source: 'intake' }),
        field({ label: 'Address', value: 'Storgata 1, Oslo', source: 'needs_input',
                guidance: 'Bring, and confirm, the address' }),
      ],
    },
  ],
};

describe('buildDatasheetCsv', () => {
  it('emits the canonical header row', () => {
    const csv = buildDatasheetCsv(SHEET);
    expect(csv.split('\n')[0]).toBe(
      'Step,Authority,Field,Value,Source,Deadline,ResponsibleParty,NonObvious',
    );
  });

  it('maps a field to Step/Authority/Field/Value/Source/Deadline columns', () => {
    const line = buildDatasheetCsv(SHEET).split('\n')[1];
    // Full name row: value present, source label "Provided", deadline carried from the section.
    expect(line).toBe('D Number,Skatteetaten,Full name,Camille Moreau,Provided,2026-09-01,,');
  });

  it('RFC-4180-quotes a value containing a comma', () => {
    const line = buildDatasheetCsv(SHEET).split('\n')[2];
    expect(line).toContain('"Storgata 1, Oslo"'); // value quoted
    expect(line).toContain('Needs input');         // source label mapped
  });

  it('names the file relopass-{corridor}-datasheet-{date}.csv', () => {
    expect(datasheetCsvFilename(SHEET)).toMatch(/^relopass-fr-no-datasheet-\d{4}-\d{2}-\d{2}\.csv$/);
  });
});
