/**
 * ImmigrationInterviewShell — IMM-08
 *
 * Multi-section interview wizard driven by the DAG-based backend engine.
 *
 * Layout:
 *   - Section tabs at the top (identity, travel_docs, address_history, family)
 *   - Progress bar beneath
 *   - Question card with the current question rendered by type
 *   - Pre-fill banner when the vault already has a value
 *   - Address-gap warning when the engine detects coverage gaps
 *   - "Save & continue later" exits without answering
 *   - Back navigates to the previous section (not individual questions; sessions
 *     are server-side, so back is best-effort)
 *
 * API calls:
 *   GET  /api/employee/cases/:caseId/interview/next
 *   POST /api/employee/cases/:caseId/interview/answer  { question_id, answer_value, skip? }
 *   GET  /api/employee/cases/:caseId/interview/status
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { CityPicker, CountryPicker } from '../../components/location';
import { Input } from '../../components/antigravity/Input';
import { Alert, Badge, Button, Card, LoadingButton } from '../../components/antigravity';
import api from '../../api/client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SectionProgress {
  section_id: string;
  total_applicable: number;
  answered: number;
  required_answered: number;
  required_total: number;
  is_complete: boolean;
}

interface NextQuestion {
  question_id: string;
  section: string;
  label: string;
  help_text: string;
  type: string;
  required: boolean;
  skippable: boolean;
  options: string[] | null;
  option_labels: Record<string, string> | null;
  upload_endpoint: string | null;
  pre_filled: boolean;
  existing_value: unknown;
}

interface AddressGap {
  from_address: Record<string, unknown>;
  to_address: Record<string, unknown>;
  gap_days: number;
}

interface InterviewNextResponse {
  next_question: NextQuestion | null;
  completion_pct: number;
  section_progress: Record<string, SectionProgress>;
  is_complete: boolean;
}

interface InterviewAnswerResponse {
  next_question: NextQuestion | null;
  vault_updated: boolean;
  gap_warnings: AddressGap[];
  completion_pct: number;
  is_complete: boolean;
  section_progress: Record<string, SectionProgress>;
}

// ---------------------------------------------------------------------------
// Section metadata
// ---------------------------------------------------------------------------

const SECTION_META: Record<string, { label: string; icon: string }> = {
  identity: { label: 'Identity', icon: '🪪' },
  travel_docs: { label: 'Travel docs', icon: '✈️' },
  address_history: { label: 'Addresses', icon: '🏠' },
  family: { label: 'Family', icon: '👨‍👩‍👧' },
};

const SECTION_ORDER = ['identity', 'travel_docs', 'address_history', 'family'];

// ---------------------------------------------------------------------------
// Address editor sub-component
// ---------------------------------------------------------------------------

interface AddressValue {
  line1?: string;
  line2?: string;
  city?: string;
  postcode?: string;
  country?: string;
  from_date?: string;
  to_date?: string;
}

interface AddressEditorProps {
  value: AddressValue;
  onChange: (v: AddressValue) => void;
  showDates?: boolean;
  label?: string;
}

const AddressEditor: React.FC<AddressEditorProps> = ({ value, onChange, showDates, label }) => {
  const upd = (key: keyof AddressValue, val: string) => onChange({ ...value, [key]: val });
  return (
    <div className="space-y-3 border border-[#e2e8f0] rounded-lg p-3 bg-[#fafbfc]">
      {label && <div className="text-xs font-medium text-[#64748b] uppercase tracking-wide">{label}</div>}
      <div>
        <label htmlFor="im-address-line-1" className="block text-xs font-medium text-[#374151] mb-1">Address line 1</label>
        <Input id="im-address-line-1" unstyled
          type="text"
          value={value.line1 || ''}
          onChange={(v) => upd('line1', v)}
          className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm text-[#0f172a] focus:outline-none focus:ring-2 focus:ring-[#0b2b43]/20 focus:border-[#0b2b43]"
          placeholder="Street address"
        />
      </div>
      <div>
        <label htmlFor="im-address-line-2" className="block text-xs font-medium text-[#374151] mb-1">Address line 2</label>
        <Input id="im-address-line-2" unstyled
          type="text"
          value={value.line2 || ''}
          onChange={(v) => upd('line2', v)}
          className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm text-[#0f172a] focus:outline-none focus:ring-2 focus:ring-[#0b2b43]/20 focus:border-[#0b2b43]"
          placeholder="Apartment, suite, etc. (optional)"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          {/* The old sibling <label htmlFor="im-city"> pointed at an id the picker does not
              render — an orphaned label announces nothing. The picker owns its label. */}
          <CityPicker
            label="City"
            value={value.city || ''}
            onChange={(v) => upd('city', v)}
            country={value.country || ''}
            testId="im-city"
          />
        </div>
        <div>
          <label htmlFor="im-postcode-zip" className="block text-xs font-medium text-[#374151] mb-1">Postcode / ZIP</label>
          <Input id="im-postcode-zip" unstyled
            type="text"
            value={value.postcode || ''}
            onChange={(v) => upd('postcode', v)}
            className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm text-[#0f172a] focus:outline-none focus:ring-2 focus:ring-[#0b2b43]/20 focus:border-[#0b2b43]"
            placeholder="Postcode"
          />
        </div>
      </div>
      <div>
        <CountryPicker
          label="Country"
          value={value.country || ''}
          onChange={(v) => upd('country', v)}
          testId="im-country"
        />
      </div>
      {showDates && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="im-lived-here-from" className="block text-xs font-medium text-[#374151] mb-1">Lived here from</label>
            <Input id="im-lived-here-from" unstyled
              type="date"
              value={value.from_date || ''}
              onChange={(v) => upd('from_date', v)}
              className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm text-[#0f172a] focus:outline-none focus:ring-2 focus:ring-[#0b2b43]/20 focus:border-[#0b2b43]"
            />
          </div>
          <div>
            <label htmlFor="im-to-leave-blank-if-current" className="block text-xs font-medium text-[#374151] mb-1">To (leave blank if current)</label>
            <Input id="im-to-leave-blank-if-current" unstyled
              type="date"
              value={value.to_date || ''}
              onChange={(v) => upd('to_date', v)}
              className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm text-[#0f172a] focus:outline-none focus:ring-2 focus:ring-[#0b2b43]/20 focus:border-[#0b2b43]"
            />
          </div>
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Address list editor
// ---------------------------------------------------------------------------

interface AddressListEditorProps {
  value: AddressValue[];
  onChange: (v: AddressValue[]) => void;
}

const AddressListEditor: React.FC<AddressListEditorProps> = ({ value, onChange }) => {
  const addEntry = () => onChange([...value, {}]);
  const removeEntry = (i: number) => onChange(value.filter((_, idx) => idx !== i));
  const updateEntry = (i: number, v: AddressValue) => {
    const next = [...value];
    next[i] = v;
    onChange(next);
  };

  return (
    <div className="space-y-3">
      {value.map((addr, i) => (
        <div key={i} className="relative">
          <AddressEditor
            value={addr}
            onChange={(v) => updateEntry(i, v)}
            showDates
            label={`Address ${i + 1}`}
          />
          {value.length > 1 && (
            <Button unstyled
              type="button"
              onClick={() => removeEntry(i)}
              className="absolute top-2 right-2 text-xs text-red-500 hover:text-red-700"
            >
              Remove
            </Button>
          )}
        </div>
      ))}
      <Button unstyled
        type="button"
        onClick={addEntry}
        className="text-sm font-medium text-[#0b2b43] hover:text-[#1a3f5e] flex items-center gap-1"
      >
        <span className="text-lg leading-none">+</span> Add another address
      </Button>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Dependent list editor
// ---------------------------------------------------------------------------

interface Dependent {
  full_name?: string;
  date_of_birth?: string;
  nationality?: string;
  relationship?: string;
}

interface DependentListEditorProps {
  value: Dependent[];
  onChange: (v: Dependent[]) => void;
}

const DependentListEditor: React.FC<DependentListEditorProps> = ({ value, onChange }) => {
  const upd = (i: number, key: keyof Dependent, val: string) => {
    const next = [...value];
    next[i] = { ...next[i], [key]: val };
    onChange(next);
  };
  const add = () => onChange([...value, {}]);
  const remove = (i: number) => onChange(value.filter((_, idx) => idx !== i));

  return (
    <div className="space-y-3">
      {value.map((dep, i) => (
        <div key={i} className="relative border border-[#e2e8f0] rounded-lg p-3 bg-[#fafbfc] space-y-3">
          <div className="text-xs font-medium text-[#64748b] uppercase tracking-wide">Dependent {i + 1}</div>
          {(['full_name', 'nationality'] as const).map((field) => (
            <div key={field}>
              <label className="block text-xs font-medium text-[#374151] mb-1">
                {field === 'full_name' ? 'Full legal name' : 'Nationality'}
              </label>
              <Input unstyled
                type="text"
                value={dep[field] || ''}
                onChange={(v) => upd(i, field, v)}
                className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm text-[#0f172a] focus:outline-none focus:ring-2 focus:ring-[#0b2b43]/20 focus:border-[#0b2b43]"
              />
            </div>
          ))}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="im-date-of-birth" className="block text-xs font-medium text-[#374151] mb-1">Date of birth</label>
              <Input id="im-date-of-birth" unstyled
                type="date"
                value={dep.date_of_birth || ''}
                onChange={(v) => upd(i, 'date_of_birth', v)}
                className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm text-[#0f172a] focus:outline-none focus:ring-2 focus:ring-[#0b2b43]/20 focus:border-[#0b2b43]"
              />
            </div>
            <div>
              <label htmlFor="im-relationship" className="block text-xs font-medium text-[#374151] mb-1">Relationship</label>
              <select id="im-relationship"
                value={dep.relationship || ''}
                onChange={(e) => upd(i, 'relationship', e.target.value)}
                className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm text-[#0f172a] focus:outline-none focus:ring-2 focus:ring-[#0b2b43]/20 focus:border-[#0b2b43]"
              >
                <option value="">Select…</option>
                <option value="child">Child</option>
                <option value="partner">Partner (not married)</option>
                <option value="parent">Parent</option>
                <option value="sibling">Sibling</option>
                <option value="other">Other dependent</option>
              </select>
            </div>
          </div>
          {value.length > 1 && (
            <Button unstyled type="button" onClick={() => remove(i)} className="text-xs text-red-500 hover:text-red-700">
              Remove
            </Button>
          )}
        </div>
      ))}
      <Button unstyled
        type="button"
        onClick={add}
        className="text-sm font-medium text-[#0b2b43] hover:text-[#1a3f5e] flex items-center gap-1"
      >
        <span className="text-lg leading-none">+</span> Add dependent
      </Button>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Question renderer
// ---------------------------------------------------------------------------

interface QuestionRendererProps {
  question: NextQuestion;
  value: unknown;
  onChange: (v: unknown) => void;
  caseId: string;
}

const QuestionRenderer: React.FC<QuestionRendererProps> = ({ question, value, onChange, caseId }) => {
  const baseInputClass =
    'w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm text-[#0f172a] ' +
    'focus:outline-none focus:ring-2 focus:ring-[#0b2b43]/20 focus:border-[#0b2b43]';

  switch (question.type) {
    case 'text':
      return (
        <Input unstyled
          type="text"
          value={(value as string) || ''}
          onChange={(v) => onChange(v)}
          className={baseInputClass}
          placeholder="Type your answer…"
        />
      );

    case 'date':
      return (
        <Input unstyled
          type="date"
          value={(value as string) || ''}
          onChange={(v) => onChange(v)}
          className={baseInputClass}
        />
      );

    case 'boolean':
      return (
        <div className="flex gap-3">
          {(['true', 'false'] as const).map((opt) => (
            <Button unstyled
              key={opt}
              type="button"
              onClick={() => onChange(opt)}
              className={`flex-1 rounded-lg border px-4 py-3 text-sm font-medium transition-colors ${
                value === opt
                  ? 'border-[#0b2b43] bg-[#0b2b43] text-white'
                  : 'border-[#e2e8f0] bg-white text-[#374151] hover:bg-[#f8fafc]'
              }`}
            >
              {opt === 'true' ? 'Yes' : 'No'}
            </Button>
          ))}
        </div>
      );

    case 'select': {
      const opts = question.options || [];
      const labels = question.option_labels || {};
      return (
        <div className="space-y-2">
          {opts.map((opt) => (
            <Button unstyled
              key={opt}
              type="button"
              onClick={() => onChange(opt)}
              className={`w-full text-left rounded-lg border px-4 py-3 text-sm transition-colors ${
                value === opt
                  ? 'border-[#0b2b43] bg-[#f0f4f8] text-[#0b2b43] font-medium'
                  : 'border-[#e2e8f0] bg-white text-[#374151] hover:bg-[#f8fafc]'
              }`}
            >
              <span className={`mr-2 inline-block h-3.5 w-3.5 rounded-full border ${
                value === opt ? 'border-[#0b2b43] bg-[#0b2b43]' : 'border-[#94a3b8] bg-white'
              }`} />
              {labels[opt] || opt}
            </Button>
          ))}
        </div>
      );
    }

    case 'address':
      return (
        <AddressEditor
          value={(value as AddressValue) || {}}
          onChange={onChange}
          showDates={false}
        />
      );

    case 'address_list':
      return (
        <AddressListEditor
          value={(value as AddressValue[]) || [{}]}
          onChange={onChange}
        />
      );

    case 'dependent_list':
      return (
        <DependentListEditor
          value={(value as Dependent[]) || [{}]}
          onChange={onChange}
        />
      );

    case 'upload': {
      const endpoint = question.upload_endpoint
        ? question.upload_endpoint.replace('{case_id}', caseId)
        : null;
      return (
        <div className="rounded-lg border-2 border-dashed border-[#cbd5e1] p-6 text-center bg-[#f8fafc]">
          <div className="text-sm text-[#475569]">
            {endpoint ? (
              <>
                Upload will go to <code className="text-xs bg-[#e2e8f0] px-1 rounded">{endpoint}</code>
                <br />
                <span className="text-xs text-slate-500 mt-1 inline-block">
                  Use the &quot;Upload passport&quot; step (before the interview) for a faster, auto-filled experience.
                </span>
              </>
            ) : (
              'File upload not available in this step.'
            )}
          </div>
          <Button unstyled
            type="button"
            onClick={() => onChange('__uploaded__')}
            className="mt-3 text-sm font-medium text-[#0b2b43] hover:underline"
          >
            Mark as uploaded
          </Button>
        </div>
      );
    }

    default:
      return (
        <Input unstyled
          type="text"
          value={(value as string) || ''}
          onChange={(v) => onChange(v)}
          className={baseInputClass}
          placeholder="Type your answer…"
        />
      );
  }
};

// ---------------------------------------------------------------------------
// Main shell
// ---------------------------------------------------------------------------

interface ImmigrationInterviewShellProps {
  caseId: string;
  onComplete: () => void;
  onSaveAndExit: () => void;
}

export const ImmigrationInterviewShell: React.FC<ImmigrationInterviewShellProps> = ({
  caseId,
  onComplete,
  onSaveAndExit,
}) => {
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState<NextQuestion | null>(null);
  const [completionPct, setCompletionPct] = useState(0);
  const [sectionProgress, setSectionProgress] = useState<Record<string, SectionProgress>>({});
  const [isComplete, setIsComplete] = useState(false);
  const [value, setValue] = useState<unknown>(null);
  const [gapWarnings, setGapWarnings] = useState<AddressGap[]>([]);
  const [prefillConfirmed, setPrefillConfirmed] = useState(false);
  const questionRef = useRef<HTMLDivElement>(null);

  const loadNext = useCallback(async () => {
    setLoading(true);
    setError(null);
    setGapWarnings([]);
    setPrefillConfirmed(false);
    try {
      const resp = await api.get<InterviewNextResponse>(
        `/api/employee/cases/${caseId}/interview/next`
      );
      const d = resp.data;
      setQuestion(d.next_question);
      setCompletionPct(d.completion_pct);
      setSectionProgress(d.section_progress || {});
      setIsComplete(d.is_complete);
      // Pre-seed value from existing_value if pre-filled
      setValue(d.next_question?.pre_filled ? d.next_question.existing_value : null);
      if (d.is_complete) onComplete();
    } catch {
      setError('Could not load the next question. Please refresh.');
    } finally {
      setLoading(false);
    }
  }, [caseId, onComplete]);

  useEffect(() => {
    void loadNext();
  }, [loadNext]);

  // Scroll to question card when question changes
  useEffect(() => {
    if (question && questionRef.current) {
      questionRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [question?.question_id]);

  const submitAnswer = async (skip = false) => {
    if (!question) return;
    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        question_id: question.question_id,
        answer_value: skip ? null : value,
        skip,
      };
      const resp = await api.post<InterviewAnswerResponse>(
        `/api/employee/cases/${caseId}/interview/answer`,
        payload
      );
      const d = resp.data;
      setQuestion(d.next_question);
      setCompletionPct(d.completion_pct);
      setSectionProgress(d.section_progress || {});
      setIsComplete(d.is_complete);
      setValue(d.next_question?.pre_filled ? d.next_question.existing_value : null);
      setPrefillConfirmed(false);
      if (d.gap_warnings?.length) setGapWarnings(d.gap_warnings);
      else setGapWarnings([]);
      if (d.is_complete) onComplete();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to submit answer. Please try again.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  // Determine active section for tab highlight
  const activeSection = question?.section || '';

  // Check if the current value is non-empty enough to submit
  const canSubmit = (() => {
    if (!question) return false;
    if (question.skippable) return true;
    if (value === null || value === undefined || value === '') return false;
    if (question.type === 'address') {
      const a = value as AddressValue;
      return !!(a.line1 && a.city && a.country);
    }
    if (question.type === 'address_list') {
      const list = value as AddressValue[];
      return list.length > 0 && list.every((a) => a.line1 && a.city && a.country && a.from_date);
    }
    if (question.type === 'dependent_list') {
      const list = value as Dependent[];
      return list.length > 0 && list.every((d) => d.full_name && d.date_of_birth);
    }
    return true;
  })();

  if (loading) {
    return (
      <div className="text-sm text-[#6b7280] py-8 text-center">Loading interview…</div>
    );
  }

  if (isComplete) {
    return (
      <Card padding="lg" className="text-center">
        <div className="text-4xl mb-3">✅</div>
        <h3 className="text-lg font-semibold text-[#0b2b43]">Interview complete</h3>
        <p className="text-sm text-[#475569] mt-2">
          All required information has been collected. Your immigration case manager will review your
          profile and be in touch.
        </p>
        <div className="mt-5">
          <Button variant="primary" onClick={onComplete}>Go to my case</Button>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Section tabs */}
      <div className="flex gap-1 overflow-x-auto pb-1">
        {SECTION_ORDER.map((sId) => {
          const meta = SECTION_META[sId] || { label: sId, icon: '•' };
          const sp = sectionProgress[sId];
          const isDone = sp?.is_complete;
          const isActive = sId === activeSection;
          return (
            <div
              key={sId}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium whitespace-nowrap transition-colors ${
                isActive
                  ? 'bg-[#0b2b43] text-white'
                  : isDone
                  ? 'bg-[#eaf5f4] text-[#105d5b]'
                  : 'bg-[#f1f5f9] text-[#64748b]'
              }`}
            >
              <span>{meta.icon}</span>
              <span>{meta.label}</span>
              {isDone && <span className="ml-0.5 text-[#1f8e8b]">✓</span>}
              {sp && !isDone && sp.required_total > 0 && (
                <span className={`opacity-70 ${isActive ? 'text-white' : ''}`}>
                  {sp.required_answered}/{sp.required_total}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Progress bar */}
      <div>
        <div className="flex justify-between items-center mb-1">
          <span className="text-xs text-[#6b7280]">Overall progress</span>
          <span className="text-xs font-semibold text-[#0b2b43]">{completionPct}%</span>
        </div>
        <div className="h-2 rounded-full bg-[#e2e8f0] overflow-hidden">
          <div
            className="h-full rounded-full bg-[#1f8e8b] transition-all duration-500"
            style={{ width: `${completionPct}%` }}
          />
        </div>
      </div>

      {/* Gap warnings */}
      {gapWarnings.length > 0 && (
        <Alert variant="warning">
          <div className="text-sm font-medium mb-1">Address history gap detected</div>
          {gapWarnings.map((g, i) => (
            <p key={i} className="text-sm">
              There is a gap of <strong>{g.gap_days} days</strong> in your address history. Immigration
              authorities require complete coverage — please review your address list.
            </p>
          ))}
        </Alert>
      )}

      {/* Error */}
      {error && <Alert variant="error">{error}</Alert>}

      {/* Question card */}
      {question && (
        <div ref={questionRef} className="scroll-mt-4">
          <Card padding="lg">
            {/* Pre-fill banner */}
            {question.pre_filled && !prefillConfirmed && (
              <div className="mb-4 rounded-lg border border-[#bfdbfe] bg-[#eff6ff] px-3 py-2.5 flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="text-xs font-semibold text-[#1e40af] uppercase tracking-wide">
                    Pre-filled from your profile
                  </div>
                  <div className="text-sm text-[#1e3a5f] mt-0.5">
                    We found an existing value: <strong>{String(question.existing_value)}</strong>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button unstyled
                    type="button"
                    onClick={() => { setPrefillConfirmed(true); setValue(question.existing_value); }}
                    className="text-xs font-medium bg-[#1d4ed8] text-white rounded-lg px-3 py-1.5 hover:bg-[#1e40af]"
                  >
                    Confirm
                  </Button>
                  <Button unstyled
                    type="button"
                    onClick={() => { setPrefillConfirmed(true); setValue(null); }}
                    className="text-xs font-medium bg-white border border-[#bfdbfe] text-[#1e40af] rounded-lg px-3 py-1.5 hover:bg-[#dbeafe]"
                  >
                    Edit
                  </Button>
                </div>
              </div>
            )}

            <div className="flex items-start justify-between gap-3 mb-1">
              <h3 className="text-base font-semibold text-[#0b2b43]">{question.label}</h3>
              <div className="flex gap-1 shrink-0">
                {question.required ? (
                  <Badge variant="neutral" size="sm">Required</Badge>
                ) : (
                  <Badge variant="neutral" size="sm">Optional</Badge>
                )}
              </div>
            </div>

            {question.help_text && (
              <p className="text-xs text-[#64748b] mb-4">{question.help_text}</p>
            )}

            <QuestionRenderer
              question={question}
              value={value}
              onChange={setValue}
              caseId={caseId}
            />

            <div className="mt-5 flex items-center justify-between gap-3 border-t border-[#e2e8f0] pt-4">
              <div className="flex gap-2">
                {question.skippable && (
                  <Button
                    variant="outline"
                    type="button"
                    onClick={() => submitAnswer(true)}
                    disabled={submitting}
                  >
                    Skip for now
                  </Button>
                )}
                <Button
                  variant="outline"
                  type="button"
                  onClick={onSaveAndExit}
                  disabled={submitting}
                >
                  Save & continue later
                </Button>
              </div>

              <LoadingButton
                variant="primary"
                loading={submitting}
                loadingLabel="Saving…"
                disabled={!canSubmit || submitting}
                onClick={() => submitAnswer(false)}
              >
                {question.pre_filled && !prefillConfirmed ? 'Confirm & continue' : 'Continue →'}
              </LoadingButton>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};
