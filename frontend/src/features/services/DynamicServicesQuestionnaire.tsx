import React, { useMemo } from 'react';
import { Card, Input, Select } from '../../components/antigravity';

export type DynamicQuestionType = 'text' | 'number' | 'select' | 'multiselect' | 'checkbox' | 'date' | 'range';

export interface DynamicQuestion {
  question_key: string;
  label: string;
  type: DynamicQuestionType;
  service_category: string;
  required?: boolean;
  placeholder?: string | null;
  default?: unknown;
  options?: Array<{ value: string; label: string }>;
  applies_if?: Record<string, unknown> | null;
  criteria_key?: string;
}

function evalAppliesIf(appliesIf: Record<string, unknown> | null | undefined, answers: Record<string, unknown>): boolean {
  if (!appliesIf) return true;
  for (const [k, expected] of Object.entries(appliesIf)) {
    if (k === '!exists') {
      const key = String(expected || '');
      if (key && answers[key] === undefined) continue;
      return false;
    }
    if (answers[k] !== expected) return false;
  }
  return true;
}

function isEmpty(v: unknown): boolean {
  if (v == null) return true;
  if (typeof v === 'string') return v.trim().length === 0;
  if (Array.isArray(v)) return v.length === 0;
  return false;
}

export function validateDynamicAnswers(
  questions: DynamicQuestion[],
  answers: Record<string, unknown>
): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const q of questions) {
    if (!evalAppliesIf(q.applies_if ?? null, answers)) continue;
    if (!q.required) continue;
    const v = answers[q.question_key];
    if (isEmpty(v)) errors[q.question_key] = 'Required';
  }
  return errors;
}

export const DynamicServicesQuestionnaire: React.FC<{
  questions: DynamicQuestion[];
  answers: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
}> = ({ questions, answers, onChange }) => {
  const visibleQuestions = useMemo(
    () => questions.filter((q) => evalAppliesIf(q.applies_if ?? null, answers)),
    [questions, answers]
  );

  const grouped = useMemo(() => {
    const g = new Map<string, DynamicQuestion[]>();
    for (const q of visibleQuestions) {
      const key = q.service_category || 'other';
      if (!g.has(key)) g.set(key, []);
      g.get(key)!.push(q);
    }
    return Array.from(g.entries());
  }, [visibleQuestions]);

  const setValue = (key: string, value: unknown) => {
    onChange({ ...answers, [key]: value });
  };

  return (
    <div className="space-y-6">
      {grouped.map(([serviceKey, qs]) => (
        <Card key={serviceKey} padding="lg">
          <div className="text-sm text-[#6b7280] uppercase tracking-wide mb-2">{serviceKey}</div>
          <div className="space-y-4">
            {qs.map((q) => {
              const id = q.question_key;
              const val = answers[id] ?? q.default ?? (q.type === 'checkbox' ? false : '');

              return (
                <div key={id}>
                  <label className="block text-sm font-medium text-[#0b2b43] mb-1">
                    {q.label}{q.required ? ' *' : ''}
                  </label>

                  {q.type === 'text' && (
                    <Input
                      value={String(val)}
                      onChange={(v) => setValue(id, v)}
                      placeholder={q.placeholder || undefined}
                      fullWidth
                    />
                  )}

                  {q.type === 'number' && (
                    <Input
                      type="number"
                      value={String(val)}
                      onChange={(v) => {
                        const n = parseInt(v, 10);
                        setValue(id, Number.isNaN(n) ? '' : n);
                      }}
                      fullWidth
                    />
                  )}

                  {q.type === 'select' && (
                    <Select
                      value={String(val ?? '')}
                      onChange={(v) => setValue(id, v)}
                      options={q.options || []}
                      placeholder={q.placeholder || 'Select...'}
                      fullWidth
                    />
                  )}

                  {q.type === 'multiselect' && (
                    <select
                      multiple
                      value={Array.isArray(val) ? (val as string[]) : []}
                      onChange={(e) => {
                        const selected = Array.from(e.target.selectedOptions).map((o) => o.value);
                        setValue(id, selected);
                      }}
                      className="w-full px-4 py-2 border border-[#d1d5db] rounded-lg bg-white"
                    >
                      {(q.options || []).map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  )}

                  {q.type === 'checkbox' && (
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={Boolean(val)}
                        onChange={(e) => setValue(id, e.target.checked)}
                      />
                      <span className="text-sm text-[#4b5563]">Yes</span>
                    </label>
                  )}
                </div>
              );
            })}
          </div>
        </Card>
      ))}
    </div>
  );
};

