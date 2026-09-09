/**
 * Client-side CSV export of the Document Data Sheet (Phase 3).
 *
 * Serialises the composed DataSheet DTO to a flat, one-row-per-field CSV the employee/HR can
 * open in a spreadsheet. No backend round-trip and no library — the RFC-4180 quoting + Blob
 * download trio mirrors features/ai-oversight/AIDecisionsAuditPage.tsx (the canonical precedent).
 *
 * Columns match the Multi-Country export schema: Step, Authority, Field, Value, Source,
 * Deadline, ResponsibleParty, NonObvious.
 */
import type { DataSheet, DataSheetSource } from '../../api/datasheet';

const SOURCE_LABEL: Record<DataSheetSource, string> = {
  intake: 'Provided',
  passport_ocr: 'From your passport',
  prior_form: 'From a previous form',
  needs_input: 'Needs input',
  consult_professional: 'Consult a professional',
  ai: 'AI suggestion — please check',
};

// RFC 4180 quoting: double-quote escape, wrap fields containing commas/quotes/newlines.
// Every cell built below is already a string, so the input is narrowed to string.
function csvEscape(value: string): string {
  if (/[",\n\r]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

const HEADER = [
  'Step', 'Authority', 'Field', 'Value', 'Source', 'Deadline', 'ResponsibleParty', 'NonObvious',
];

export function buildDatasheetCsv(sheet: DataSheet): string {
  const rows: string[][] = [];
  for (const section of sheet.sections) {
    const step = section.title ?? section.stepId;
    const authority = section.authority ?? '';
    const deadline = section.deadline?.date ?? '';
    const responsible = section.responsibleParty ?? '';
    for (const f of section.fields) {
      rows.push([
        step,
        authority,
        f.label,
        f.value ?? '',
        SOURCE_LABEL[f.source] ?? f.source,
        deadline,
        responsible,
        // Non-obvious / consult guidance for this field (section-level moat facts also render
        // as on-screen banners; per-country enrichment lands with the export-content data).
        f.guidance ?? f.hint ?? '',
      ]);
    }
  }
  return [HEADER.join(','), ...rows.map((r) => r.map(csvEscape).join(','))].join('\n');
}

export function downloadDatasheetCsv(csv: string, filename: string): void {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/** `relopass-{corridor}-datasheet-{YYYY-MM-DD}.csv` */
export function datasheetCsvFilename(sheet: DataSheet): string {
  const corridor = (sheet.corridor ?? 'datasheet').toLowerCase().replace(/[^a-z0-9]+/g, '-');
  const date = new Date().toISOString().slice(0, 10);
  return `relopass-${corridor}-datasheet-${date}.csv`;
}
