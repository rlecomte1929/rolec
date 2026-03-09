import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Alert, Input, Select } from '../../../components/antigravity';
import { buildRoute } from '../../../navigation/routes';
import type {
  CaseDraftDTO,
  CaseRequirementsDTO,
  RequirementItemDTO,
  DossierQuestion,
  DossierSuggestion,
} from '../../../types';
import { buildRequirementsFromMissingFields, getRelocationCase } from '../../../api/relocation';
import { RequirementList } from '../../../components/requirements/RequirementList';
import { dossierAPI, requirementsAPI } from '../../../api/client';
import { GuidancePackPanel } from '../../../components/guidance/GuidancePackPanel';

interface StepProps {
  caseId: string;
  draft: CaseDraftDTO;
  requiredFields: string[];
  onSave: (draft: CaseDraftDTO) => Promise<void>;
  onNext: (draft: CaseDraftDTO) => Promise<void>;
  onBack: () => void;
  onGoToStep?: (stepNumber: number) => void;
}

const DYNAMIC_DOSSIER_ENABLED =
  import.meta.env.VITE_FEATURE_DYNAMIC_DOSSIER === 'true' ||
  import.meta.env.NEXT_PUBLIC_FEATURE_DYNAMIC_DOSSIER === 'true';

function SummarySection({
  title,
  stepNumber,
  onEdit,
  children,
}: {
  title: string;
  stepNumber: number;
  onEdit?: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-[#e2e8f0] bg-white p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-semibold text-[#0b2b43]">{title}</div>
        {onEdit && (
          <button
            type="button"
            onClick={onEdit}
            className="text-xs text-[#0b2b43] underline hover:no-underline"
          >
            Edit (Step {stepNumber})
          </button>
        )}
      </div>
      <div className="text-sm text-[#4b5563] space-y-1">{children}</div>
    </div>
  );
}

export const Step5ReviewCreate: React.FC<StepProps> = ({
  caseId,
  draft,
  onSave,
  onBack,
  onGoToStep,
}) => {
  const navigate = useNavigate();
  const [requirements, setRequirements] = useState<CaseRequirementsDTO | null>(null);
  const [missingFields, setMissingFields] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [dossierQuestions, setDossierQuestions] = useState<DossierQuestion[]>([]);
  const [dossierAnswers, setDossierAnswers] = useState<Record<string, any>>({});
  const [dossierComplete, setDossierComplete] = useState(true);
  const [dossierSources, setDossierSources] = useState<Array<{ title?: string; url: string; snippet?: string }>>([]);
  const [dossierLoading, setDossierLoading] = useState(false);
  const [dossierSaving, setDossierSaving] = useState(false);
  const [dossierError, setDossierError] = useState('');
  const [dossierSuggestions, setDossierSuggestions] = useState<DossierSuggestion[]>([]);
  const [suggestionSources, setSuggestionSources] = useState<Array<{ title?: string; url: string; snippet?: string }>>([]);
  const [suggestionLoading, setSuggestionLoading] = useState(false);
  const [approvedMissingFields, setApprovedMissingFields] = useState<string[]>([]);
  const errorRef = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (error && errorRef.current) {
      errorRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [error]);

  useEffect(() => {
    if (!caseId) return;
    getRelocationCase(caseId)
      .then((relocation) => {
        const missing = Array.isArray(relocation.missing_fields) ? relocation.missing_fields : [];
        setRequirements(buildRequirementsFromMissingFields(caseId, missing));
        setMissingFields(missing);
      })
      .catch(() => {
        setRequirements(null);
        setMissingFields([]);
      });
  }, [caseId]);

  useEffect(() => {
    if (!caseId) return;
    requirementsAPI.getSufficiency(caseId)
      .then((res) => {
        const missing = Array.isArray(res.missing_fields) ? res.missing_fields : [];
        setApprovedMissingFields(missing);
      })
      .catch(() => {
        setApprovedMissingFields([]);
      });
  }, [caseId]);

  useEffect(() => {
    if (!DYNAMIC_DOSSIER_ENABLED || !caseId) return;
    if (missingFields.length === 0 && approvedMissingFields.length === 0) {
      setDossierQuestions([]);
      setDossierAnswers({});
      setDossierComplete(true);
      setDossierSources([]);
      return;
    }
    setDossierLoading(true);
    setDossierError('');
    dossierAPI.getQuestions(caseId)
      .then((res) => {
        setDossierQuestions(res.questions || []);
        setDossierAnswers(res.answers || {});
        setDossierComplete(Boolean(res.is_step5_complete));
        setDossierSources(res.sources_used || []);
      })
      .catch(() => setDossierError('Unable to load dynamic dossier questions.'))
      .finally(() => setDossierLoading(false));
  }, [caseId, missingFields, approvedMissingFields]);

  useEffect(() => {
    if (!DYNAMIC_DOSSIER_ENABLED || !caseId || approvedMissingFields.length === 0) return;
    const questionMap: Record<string, string> = {
      visa_type: 'What is your visa / pass type (if known)?',
      passport_expiry_date: 'What is your passport expiry date?',
      nationality: 'What is your nationality?',
      employer_country: 'Which country is your employer based in?',
      employment_type: 'What is your employment type (e.g. employee, contractor)?',
      dependents: 'Will any dependents relocate with you?',
    };
    const existingTexts = new Set(dossierQuestions.map((q) => q.question_text));
    approvedMissingFields.forEach((field) => {
      const text = questionMap[field] || `Please provide: ${field.replace(/_/g, ' ')}`;
      if (existingTexts.has(text)) return;
      dossierAPI.addCaseQuestion({
        case_id: caseId,
        question_text: text,
        answer_type: 'text',
        is_mandatory: true,
      }).catch(() => undefined);
    });
  }, [approvedMissingFields, caseId, dossierQuestions]);

  const grouped = requirements?.requirements.reduce<Record<string, RequirementItemDTO[]>>((acc, item) => {
    acc[item.pillar] = acc[item.pillar] || [];
    acc[item.pillar].push(item);
    return acc;
  }, {}) || {};

  const isAnswered = (value: any) => {
    if (value === null || value === undefined) return false;
    if (typeof value === 'string') return value.trim().length > 0;
    if (Array.isArray(value)) return value.length > 0;
    return true;
  };

  const mandatoryRemaining = DYNAMIC_DOSSIER_ENABLED
    ? dossierQuestions.filter((q) => q.is_mandatory).filter((q) => !isAnswered(dossierAnswers[q.id])).length
    : 0;

  const handleSave = async (nextRoute?: string) => {
    setError('');
    setDossierError('');
    setIsSaving(true);
    try {
      if (DYNAMIC_DOSSIER_ENABLED && caseId && missingFields.length > 0) {
        if (mandatoryRemaining > 0) {
          setError('Please answer all mandatory dossier questions before continuing.');
          return;
        }
        setDossierSaving(true);
        const answersPayload = dossierQuestions
          .filter((q) => Object.prototype.hasOwnProperty.call(dossierAnswers, q.id))
          .map((q) => ({
            question_id: q.source === 'library' ? q.id : null,
            case_question_id: q.source === 'case' ? q.id : null,
            answer: dossierAnswers[q.id],
          }));
        await dossierAPI.saveAnswers({ case_id: caseId, answers: answersPayload });
        const refreshed = await dossierAPI.getQuestions(caseId);
        setDossierQuestions(refreshed.questions || []);
        setDossierAnswers(refreshed.answers || {});
        setDossierComplete(Boolean(refreshed.is_step5_complete));
        setDossierSources(refreshed.sources_used || []);
      }
      await onSave(draft);
      setSaved(true);
      if (nextRoute) {
        navigate(nextRoute);
      }
    } catch (err: any) {
      const resData = err?.response?.data;
      const detail = err?.detail ?? resData?.detail;
      if (detail && typeof detail === 'object' && detail.message) {
        const missing = Array.isArray(detail.missingFields) ? detail.missingFields : [];
        setError(missing.length
          ? `${detail.message}. Please complete Step 1 (Relocation Basics) required fields.`
          : detail.message);
      } else if (detail && typeof detail === 'string') {
        setError(detail);
      } else if (resData && typeof resData === 'object' && resData.message) {
        setError(resData.message);
      } else {
        setError('Unable to save. Please try again.');
      }
    } finally {
      setDossierSaving(false);
      setIsSaving(false);
    }
  };

  const handleSuggestionSearch = async () => {
    if (!caseId) return;
    setSuggestionLoading(true);
    try {
      const res = await dossierAPI.searchSuggestions(caseId);
      setDossierSuggestions(res.suggestions || []);
      setSuggestionSources(res.sources || []);
    } catch {
      setDossierError('Unable to fetch suggested questions at this time.');
    } finally {
      setSuggestionLoading(false);
    }
  };

  const handleAddSuggestion = async (suggestion: DossierSuggestion) => {
    if (!caseId) return;
    try {
      await dossierAPI.addCaseQuestion({
        case_id: caseId,
        question_text: suggestion.question_text,
        answer_type: suggestion.answer_type,
        sources: suggestion.sources,
      });
      const refreshed = await dossierAPI.getQuestions(caseId);
      setDossierQuestions(refreshed.questions || []);
      setDossierAnswers(refreshed.answers || {});
      setDossierComplete(Boolean(refreshed.is_step5_complete));
      setDossierSources(refreshed.sources_used || []);
      setDossierSuggestions((prev) => prev.filter((s) => s.question_text !== suggestion.question_text));
    } catch {
      setDossierError('Unable to add suggested question.');
    }
  };

  return (
    <Card padding="lg">
      <div className="text-lg font-semibold text-[#0b2b43]">Review & Save</div>
      {error && (
        <div ref={errorRef}>
          <Alert variant="error" className="mt-4">
            {error}
          </Alert>
        </div>
      )}
      {saved && (
        <div className="mt-4">
          <Alert variant="success" title="Saved">
            Your data has been saved successfully. You can continue editing or go to the dashboard.
          </Alert>
        </div>
      )}

      <div className="text-sm text-[#6b7280] mt-1">
        Review the requirements generated from destination research. Save to persist your data.
      </div>

      <div className="mt-6">
        <div className="text-sm font-semibold text-[#0b2b43] mb-3">Case overview — validate your responses</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <SummarySection
            title="Relocation Basics"
            stepNumber={1}
            onEdit={onGoToStep ? () => onGoToStep(1) : undefined}
          >
            <div>Origin: {[draft.relocationBasics?.originCity, draft.relocationBasics?.originCountry].filter(Boolean).join(', ') || '—'}</div>
            <div>Destination: {[draft.relocationBasics?.destCity, draft.relocationBasics?.destCountry].filter(Boolean).join(', ') || '—'}</div>
            <div>Purpose: {draft.relocationBasics?.purpose || '—'}</div>
            <div>Target move date: {draft.relocationBasics?.targetMoveDate || '—'}</div>
            <div>Duration: {draft.relocationBasics?.durationMonths != null ? `${draft.relocationBasics.durationMonths} months` : '—'}</div>
          </SummarySection>
          <SummarySection
            title="Employee Profile"
            stepNumber={2}
            onEdit={onGoToStep ? () => onGoToStep(2) : undefined}
          >
            <div>Name: {draft.employeeProfile?.fullName || '—'}</div>
            <div>Email: {draft.employeeProfile?.email || '—'}</div>
            <div>Nationality: {draft.employeeProfile?.nationality || '—'}</div>
            <div>Passport: {draft.employeeProfile?.passportCountry || '—'}</div>
            <div>Residence: {draft.employeeProfile?.residenceCountry || '—'}</div>
          </SummarySection>
          <SummarySection
            title="Family Members"
            stepNumber={3}
            onEdit={onGoToStep ? () => onGoToStep(3) : undefined}
          >
            <div>Spouse: {draft.familyMembers?.spouse?.fullName || '—'}</div>
            <div>Children: {draft.familyMembers?.children?.length ? `${draft.familyMembers.children.length} child(ren)` : '—'}</div>
          </SummarySection>
          <SummarySection
            title="Assignment / Context"
            stepNumber={4}
            onEdit={onGoToStep ? () => onGoToStep(4) : undefined}
          >
            <div>Employer: {draft.assignmentContext?.employerName || '—'}</div>
            <div>Job title: {draft.assignmentContext?.jobTitle || '—'}</div>
            <div>Contract start: {draft.assignmentContext?.contractStartDate || '—'}</div>
            <div>Contract type: {draft.assignmentContext?.contractType || '—'}</div>
          </SummarySection>
        </div>
      </div>

      {localStorage.getItem('demo_role') === 'admin' && (
        <button
          className="mt-3 text-xs text-[#0b2b43] underline"
          onClick={() => navigate('/admin/countries')}
        >
          View Country Requirements DB
        </button>
      )}

      <div className="mt-6 space-y-6">
        {Object.entries(grouped).map(([pillar, items]) => (
          <div key={pillar}>
            <div className="text-sm font-semibold text-[#0b2b43] mb-3">{pillar}</div>
            <RequirementList items={items} />
          </div>
        ))}
      </div>

      {DYNAMIC_DOSSIER_ENABLED && (
        <div className="mt-8 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-lg font-semibold text-[#0b2b43]">Additional questions to complete your dossier</div>
              <div className="text-sm text-[#6b7280]">
                These are suggested prompts based on official destination requirements. Please confirm your answers.
              </div>
            </div>
            <Button
              variant="outline"
              onClick={handleSuggestionSearch}
              disabled={suggestionLoading || dossierLoading || missingFields.length === 0}
            >
              {suggestionLoading ? 'Searching...' : 'Find suggested questions'}
            </Button>
          </div>

          {dossierError && (
            <div className="rounded-lg border border-[#fecaca] bg-[#fff5f5] px-4 py-3 text-sm text-[#7a2a2a]">
              {dossierError}
            </div>
          )}

          {missingFields.length === 0 ? (
            <div className="rounded-lg border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 text-sm text-[#4b5563]">
              All destination requirements are currently met based on official sources and the information you provided.
              If you think something is missing, use “Find suggested questions” to review optional prompts.
            </div>
          ) : dossierLoading ? (
            <div className="text-sm text-[#6b7280]">Loading dossier questions...</div>
          ) : (
            <div className="space-y-4">
              {dossierQuestions.length === 0 && (
                <div className="text-sm text-[#6b7280]">No additional questions for this destination.</div>
              )}
              {dossierQuestions.map((q) => (
                <div key={q.id} className="rounded-lg border border-[#e2e8f0] bg-white p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="text-sm font-medium text-[#0b2b43]">{q.question_text}</div>
                    {q.is_mandatory && (
                      <span className="text-[10px] uppercase tracking-wide text-[#7a2a2a]">Required</span>
                    )}
                  </div>
                  {q.answer_type === 'text' && (
                    <Input
                      value={dossierAnswers[q.id] ?? ''}
                      onChange={(value) => setDossierAnswers((prev) => ({ ...prev, [q.id]: value }))}
                      placeholder="Type your answer"
                      fullWidth
                    />
                  )}
                  {q.answer_type === 'date' && (
                    <Input
                      type="date"
                      value={dossierAnswers[q.id] ?? ''}
                      onChange={(value) => setDossierAnswers((prev) => ({ ...prev, [q.id]: value }))}
                      fullWidth
                    />
                  )}
                  {q.answer_type === 'boolean' && (
                    <Select
                      value={dossierAnswers[q.id] === true ? 'yes' : dossierAnswers[q.id] === false ? 'no' : ''}
                      onChange={(value) =>
                        setDossierAnswers((prev) => ({ ...prev, [q.id]: value === 'yes' }))
                      }
                      options={[
                        { value: 'yes', label: 'Yes' },
                        { value: 'no', label: 'No' },
                      ]}
                      placeholder="Select"
                      fullWidth
                    />
                  )}
                  {q.answer_type === 'select' && (
                    <Select
                      value={dossierAnswers[q.id] ?? ''}
                      onChange={(value) => setDossierAnswers((prev) => ({ ...prev, [q.id]: value }))}
                      options={(q.options || []).map((opt) => ({ value: opt, label: opt }))}
                      placeholder="Select"
                      fullWidth
                    />
                  )}
                  {q.answer_type === 'multiselect' && (
                    <div className="space-y-2">
                      {(q.options || []).map((opt) => {
                        const current = Array.isArray(dossierAnswers[q.id]) ? dossierAnswers[q.id] : [];
                        const checked = current.includes(opt);
                        return (
                          <label key={opt} className="flex items-center gap-2 text-sm text-[#4b5563]">
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={(event) => {
                                const next = event.target.checked
                                  ? [...current, opt]
                                  : current.filter((v: string) => v !== opt);
                                setDossierAnswers((prev) => ({ ...prev, [q.id]: next }));
                              }}
                            />
                            {opt}
                          </label>
                        );
                      })}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {dossierSuggestions.length > 0 && (
            <div className="rounded-lg border border-[#e2e8f0] bg-[#f8fafc] p-4">
              <div className="text-sm font-semibold text-[#0b2b43] mb-2">Suggested extra questions</div>
              <div className="space-y-3">
                {dossierSuggestions.map((s, idx) => (
                  <div key={`${s.question_text}-${idx}`} className="flex items-center justify-between gap-4">
                    <div className="text-sm text-[#4b5563]">{s.question_text}</div>
                    <Button variant="outline" onClick={() => handleAddSuggestion(s)}>
                      Add this question
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {(suggestionSources.length > 0 || dossierSources.length > 0) && (
            <details className="rounded-lg border border-[#e2e8f0] bg-white p-4">
              <summary className="text-sm font-semibold text-[#0b2b43] cursor-pointer">
                Sources used
              </summary>
              <ul className="mt-3 space-y-2 text-sm text-[#4b5563]">
                {(suggestionSources.length > 0 ? suggestionSources : dossierSources).map((src, idx) => (
                  <li key={`${src.url}-${idx}`}>
                    <a href={src.url} target="_blank" rel="noreferrer" className="text-[#1d4ed8] underline">
                      {src.title || src.url}
                    </a>
                    {src.snippet && <div className="text-xs text-[#6b7280] mt-1">{src.snippet}</div>}
                  </li>
                ))}
              </ul>
            </details>
          )}

          {dossierQuestions.length > 0 && (
            <div className="text-xs text-[#6b7280]">
              Mandatory remaining: {mandatoryRemaining} {mandatoryRemaining === 1 ? 'item' : 'items'}
            </div>
          )}
        </div>
      )}

      <div className="mt-8">
        <GuidancePackPanel caseId={caseId} isStep5Complete={dossierComplete} />
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <Button variant="outline" onClick={onBack}>Back</Button>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={() => handleSave(buildRoute('employeeDashboard'))}
            disabled={isSaving || dossierSaving}
          >
            {isSaving || dossierSaving ? 'Saving...' : 'Save & Exit'}
          </Button>
          <Button
            onClick={() => handleSave(buildRoute('services'))}
            disabled={isSaving || dossierSaving}
          >
            {isSaving || dossierSaving ? 'Saving...' : 'Save & go to Services'}
          </Button>
        </div>
      </div>
    </Card>
  );
};
