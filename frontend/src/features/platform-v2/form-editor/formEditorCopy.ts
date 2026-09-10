/**
 * Plain-English "what to do next" copy for the employee form editor
 * (BUG-260909-E7B1). Formats payload already on the form/template — does not
 * invent portals, deadlines, or legal claims.
 */
import type { FieldValueItem } from '../../../api/formEditor';
import type { CaseFormSummary } from '../../../api/dossier';

const MISSING_LIST_CAP = 8;

export function isFilled(value: string | null | undefined): boolean {
  return (value ?? '').trim() !== '';
}

export function officialSubmitUrl(
  form: CaseFormSummary | null,
  fields: FieldValueItem[],
): string | null {
  const fromTemplate = form?.template.source_url?.trim();
  if (fromTemplate) return fromTemplate;
  const fromSection = (form?.template.sections ?? [])
    .map((s) => s.portal_url?.trim())
    .find((u) => !!u);
  if (fromSection) return fromSection;
  const fromField = fields.map((f) => f.portal_url?.trim()).find((u) => !!u);
  return fromField ?? null;
}

export interface FormProceedBriefingModel {
  title: string;
  filledLine: string;
  youDoLine: string;
  missingLabels: string[];
  missingOverflow: number;
  submitLine: string;
  authorityName: string | null;
  hasFields: boolean;
}

export function buildFormProceedBriefing(
  form: CaseFormSummary | null,
  fields: FieldValueItem[],
  liveValues: Record<string, string>,
): FormProceedBriefingModel {
  const hasFields = fields.length > 0;
  const filled = fields.filter((f) => isFilled(liveValues[f.field_id] ?? f.value)).length;
  const missing = fields.filter(
    (f) =>
      f.required &&
      !f.consult_professional &&
      !isFilled(liveValues[f.field_id] ?? f.value),
  );
  const missingLabels = missing.map((f) => f.label).filter((l) => l.trim() !== '');
  const overflow = Math.max(0, missingLabels.length - MISSING_LIST_CAP);
  const authority = form?.template.authority_name?.trim() || null;
  const portal = officialSubmitUrl(form, fields);

  const filledLine =
    filled === 0
      ? 'ReloPass will pre-fill every field it already knows from your intake. Anything still blank is yours to add — we will not guess it.'
      : `ReloPass already filled ${filled} field${filled === 1 ? '' : 's'} from your intake and documents. Check those values; only change what is wrong.`;

  let youDoLine: string;
  if (!hasFields) {
    youDoLine =
      'There is nothing to type in ReloPass for this pack. Use the official site below to complete the registration.';
  } else if (missing.length === 0) {
    youDoLine =
      'Nothing else is required here. Mark the pack ready, then submit on the official site if this registration is filed there.';
  } else {
    youDoLine = `Add the remaining answer${missing.length === 1 ? '' : 's'} below — then mark the pack ready. ReloPass keeps this compiled for you; you do not have to rebuild the form.`;
  }

  const submitLine = portal
    ? `When the pack is ready, submit on the official site${authority ? ` (${authority})` : ''}. ReloPass does not file this for you.`
    : authority
      ? `When the pack is ready, file it with ${authority}. ReloPass does not file this for you.`
      : 'When the pack is ready, file it with the issuing authority. ReloPass does not file this for you.';

  return {
    title: 'How to finish this registration',
    filledLine,
    youDoLine,
    missingLabels: missingLabels.slice(0, MISSING_LIST_CAP),
    missingOverflow: overflow,
    submitLine,
    authorityName: authority,
    hasFields,
  };
}
