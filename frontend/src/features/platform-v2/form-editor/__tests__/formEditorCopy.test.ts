import { describe, expect, it } from 'vitest';
import type { FieldValueItem } from '../../../../api/formEditor';
import type { CaseFormSummary } from '../../../../api/dossier';
import {
  buildFormProceedBriefing,
  officialSubmitUrl,
} from '../formEditorCopy';

function field(over: Partial<FieldValueItem>): FieldValueItem {
  return {
    field_id: 'f1',
    label: 'Full name',
    field_type: 'text',
    required: true,
    position: 0,
    prefill_source: 'profile.legal_full_name',
    requires_original: false,
    options: null,
    value: null,
    filled_by: null,
    ai_confidence: null,
    reviewed: false,
    overridden: false,
    section: null,
    ...over,
  };
}

function form(over: Partial<CaseFormSummary> = {}): CaseFormSummary {
  return {
    id: 'form-1',
    case_id: 'case-1',
    status: 'not_started',
    completion_pct: 0,
    deadline: null,
    deadline_trigger: null,
    blocker_form_id: null,
    blocker_form_code: null,
    original_file_url: null,
    draft_pdf_url: null,
    submitted_at: null,
    receipt_ref: null,
    rejection_reason: null,
    template: {
      id: 't1',
      code: 'EEA-REG',
      name: 'EEA registration',
      authority_code: 'politiet',
      authority_name: 'Politiet',
      country: 'NO',
      category: 'registration',
      version: '1',
      fields_total: 2,
      source_url: 'https://www.politiet.no/en/services/residence/',
      source_last_verified: null,
      required_documents: [],
      verification_status: 'representative',
    },
    person: { kind: 'employee', name: 'Ada', dependent_id: null, profile_id: null },
    fields_summary: {
      total: 2,
      filled_by_ai: 0,
      filled_by_human: 0,
      reviewed: 0,
      overridden: 0,
      missing_required: 2,
    },
    created_at: '',
    updated_at: '',
    ...over,
  };
}

describe('officialSubmitUrl', () => {
  it('prefers the template source_url', () => {
    expect(officialSubmitUrl(form(), [])).toBe(
      'https://www.politiet.no/en/services/residence/',
    );
  });

  it('falls back to a field portal when the template has none', () => {
    const summary = form({
      template: { ...form().template, source_url: null },
    });
    expect(
      officialSubmitUrl(summary, [
        field({ portal_url: 'https://www.skatteetaten.no/en/forms/d-number' }),
      ]),
    ).toBe('https://www.skatteetaten.no/en/forms/d-number');
  });
});

describe('buildFormProceedBriefing', () => {
  it('lists remaining required fields and says ReloPass already compiled known values', () => {
    const fields = [
      field({ field_id: 'n', label: 'Full name', value: 'Ada', filled_by: 'system' }),
      field({ field_id: 'addr', label: 'Norwegian address', value: null }),
    ];
    const model = buildFormProceedBriefing(form(), fields, {
      n: 'Ada',
      addr: '',
    });
    expect(model.title).toBe('How to finish this registration');
    expect(model.filledLine).toMatch(/already filled 1 field/);
    expect(model.missingLabels).toEqual(['Norwegian address']);
    expect(model.submitLine).toMatch(/Politiet/);
    expect(model.submitLine).toMatch(/does not file this for you/);
  });

  it('does not invent a portal when none is seeded', () => {
    const summary = form({
      template: { ...form().template, source_url: null, authority_name: null },
    });
    const model = buildFormProceedBriefing(summary, [], {});
    expect(model.hasFields).toBe(false);
    expect(model.youDoLine).toMatch(/nothing to type in ReloPass/i);
    expect(model.submitLine).toMatch(/issuing authority/);
  });
});
