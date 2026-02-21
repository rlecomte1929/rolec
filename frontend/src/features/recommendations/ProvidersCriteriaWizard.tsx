import React, { useState, useEffect } from 'react';
import { Card, Button, Input, Alert } from '../../components/antigravity';
import { recommendationsEngineAPI } from './api';
import type { RecommendationResponse } from './types';

/** Map RelocationProfile (from employee journey) to wizard initial answers */
export function profileToWizardAnswers(profile: Record<string, unknown> | null): Record<string, unknown> {
  if (!profile) return {};
  const mp = (profile.movePlan as Record<string, unknown>) || {};
  const housing = (mp.housing as Record<string, unknown>) || {};
  const schooling = (mp.schooling as Record<string, unknown>) || {};
  const movers = (mp.movers as Record<string, unknown>) || {};
  const dest = String(mp.destination || 'Singapore').split(',')[0].trim();
  const origin = String(mp.origin || 'Oslo').split(',')[0].trim();

  const budgetStr = String(housing.budgetMonthlySGD || '2000-5000');
  const [budgetMin = 2000, budgetMax = 5000] = budgetStr
    .replace(/[^0-9-]/g, '')
    .split('-')
    .map((s) => parseInt(s.trim(), 10))
    .filter((n) => !isNaN(n));

  const schoolBudgetStr = String(schooling.budgetAnnualSGD || '0');
  const schoolBudgetNum = parseInt(schoolBudgetStr.replace(/[^0-9]/g, ''), 10) || 20000;
  const schoolBudgetLevel =
    schoolBudgetNum >= 35000 ? 'high' : schoolBudgetNum <= 20000 ? 'low' : 'medium';

  const currPref = String(schooling.curriculumPreference || '').toUpperCase();
  const curriculum =
    currPref && (currPref.includes('IB') || currPref.includes('UK') || currPref.includes('US'))
      ? 'international'
      : currPref === 'LOCAL'
        ? 'local'
        : 'either';

  const dependents = (profile.dependents as unknown[]) || [];
  const childAges = dependents
    .filter((d) => d && typeof d === 'object')
    .map((d) => {
      const dob = (d as Record<string, unknown>).dateOfBirth;
      if (typeof dob !== 'string') return null;
      const y = parseInt(dob.slice(0, 4), 10);
      return isNaN(y) ? null : new Date().getFullYear() - y;
    })
    .filter((a): a is number => a != null && a >= 0 && a <= 18);
  const childAgesStr = childAges.length > 0 ? childAges.join(', ') : '8';

  const inv = String(movers.inventoryRough || 'medium').toLowerCase();
  const accType = inv === 'small' ? 'studio' : inv === 'large' ? 'house' : 'apartment';

  return {
    dest_city: dest || 'Singapore',
    budget_min: budgetMin || 2000,
    budget_max: budgetMax || 5000,
    bedrooms: (housing.bedroomsMin as number) ?? 2,
    sqm_min: 65,
    commute_mins: 45,
    child_ages: childAgesStr,
    curriculum,
    school_budget: schoolBudgetLevel,
    origin_city: origin || 'Oslo',
    move_dest: dest || 'Singapore',
    move_type: 'international',
    acc_type: accType,
    acc_bedrooms: 2,
    people: Math.max(2, 1 + (profile.spouse ? 1 : 0) + dependents.length),
    packing: 'partial',
    bank_lang: 'en',
    bank_fees: 'medium',
    ins_coverage: 'health',
    ins_family: true,
    elec_green: true,
    elec_flex: 'medium',
  };
}

/** Map frontend tab IDs to backend category keys */
const CATEGORY_MAP: Record<string, string> = {
  housing: 'living_areas',
  schools: 'schools',
  movers: 'movers',
  banks: 'banks',
  insurances: 'insurance',
  electricity: 'electricity',
};

type TabKey = keyof typeof CATEGORY_MAP;

export interface WizardQuestion {
  id: string;
  label: string;
  type: 'text' | 'number' | 'select' | 'checkbox' | 'multiselect';
  key: string;
  category: TabKey;
  options?: { value: string; label: string }[];
  placeholder?: string;
  default?: unknown;
}

const WIZARD_QUESTIONS: WizardQuestion[] = [
  { id: 'dest_city', label: 'Destination city', type: 'text', key: 'destination_city', category: 'housing', default: 'Singapore' },
  { id: 'budget_min', label: 'Min monthly budget (SGD)', type: 'number', key: 'budget_min', category: 'housing', default: 2000 },
  { id: 'budget_max', label: 'Max monthly budget (SGD)', type: 'number', key: 'budget_max', category: 'housing', default: 5000 },
  { id: 'bedrooms', label: 'Number of bedrooms', type: 'number', key: 'bedrooms', category: 'housing', default: 2 },
  { id: 'sqm_min', label: 'Minimum sqm', type: 'number', key: 'sqm_min', category: 'housing', default: 65 },
  { id: 'commute_mins', label: 'Max commute to work (minutes)', type: 'number', key: 'commute_mins', category: 'housing', default: 45 },
  { id: 'office_address', label: 'Office/work address (optional, for map directions)', type: 'text', key: 'office_address', category: 'housing', placeholder: 'e.g. Raffles Place MRT, Singapore' },
  { id: 'child_ages', label: "Children's ages (comma-separated, e.g. 5,8)", type: 'text', key: 'child_ages', category: 'schools', default: '8' },
  { id: 'curriculum', label: 'Curriculum preference', type: 'select', key: 'curriculum', category: 'schools', options: [
    { value: 'international', label: 'International' },
    { value: 'local', label: 'Local' },
    { value: 'either', label: 'Either' },
  ], default: 'international' },
  { id: 'school_budget', label: 'School budget level', type: 'select', key: 'budget_level', category: 'schools', options: [
    { value: 'low', label: 'Low' },
    { value: 'medium', label: 'Medium' },
    { value: 'high', label: 'High' },
  ], default: 'medium' },
  { id: 'origin_city', label: 'Origin city', type: 'text', key: 'origin_city', category: 'movers', default: 'Oslo' },
  { id: 'move_dest', label: 'Destination city (move)', type: 'text', key: 'destination_city', category: 'movers', default: 'Singapore' },
  { id: 'move_type', label: 'Move type', type: 'select', key: 'move_type', category: 'movers', options: [
    { value: 'domestic', label: 'Domestic' },
    { value: 'international', label: 'International' },
  ], default: 'international' },
  { id: 'acc_type', label: 'Current accommodation type', type: 'select', key: 'acc_type', category: 'movers', options: [
    { value: 'studio', label: 'Studio' },
    { value: 'apartment', label: 'Apartment' },
    { value: 'house', label: 'House' },
  ], default: 'apartment' },
  { id: 'acc_bedrooms', label: 'Current bedrooms', type: 'number', key: 'acc_bedrooms', category: 'movers', default: 2 },
  { id: 'people', label: 'Number of people moving', type: 'number', key: 'people', category: 'movers', default: 2 },
  { id: 'packing', label: 'Packing service', type: 'select', key: 'packing_service', category: 'movers', options: [
    { value: 'self', label: 'Self' },
    { value: 'partial', label: 'Partial' },
    { value: 'full', label: 'Full' },
  ], default: 'partial' },
  { id: 'bank_lang', label: 'Preferred languages', type: 'text', key: 'preferred_languages', category: 'banks', placeholder: 'en, zh', default: 'en' },
  { id: 'bank_fees', label: 'Fee sensitivity', type: 'select', key: 'fee_sensitivity', category: 'banks', options: [
    { value: 'low', label: 'Low fees important' },
    { value: 'medium', label: 'Balanced' },
    { value: 'high', label: 'Premium acceptable' },
  ], default: 'medium' },
  { id: 'ins_coverage', label: 'Coverage types needed', type: 'text', key: 'coverage_types', category: 'insurances', placeholder: 'health, travel', default: 'health' },
  { id: 'ins_family', label: 'Family coverage needed', type: 'checkbox', key: 'family_coverage', category: 'insurances', default: true },
  { id: 'elec_green', label: 'Prefer green electricity', type: 'checkbox', key: 'green_preference', category: 'electricity', default: true },
  { id: 'elec_flex', label: 'Contract flexibility', type: 'select', key: 'contract_flexibility', category: 'electricity', options: [
    { value: 'high', label: 'High (short-term ok)' },
    { value: 'medium', label: 'Medium' },
    { value: 'low', label: 'Low (long-term preferred)' },
  ], default: 'medium' },
];

function getQuestionsForCategories(categories: TabKey[]): WizardQuestion[] {
  return WIZARD_QUESTIONS.filter((q) => categories.includes(q.category));
}

function buildCriteriaFromAnswers(
  answers: Record<string, unknown>,
  category: TabKey
): Record<string, unknown> {
  const questions = WIZARD_QUESTIONS.filter((q) => q.category === category);
  const criteria: Record<string, unknown> = {};

  for (const q of questions) {
    const val = answers[q.id];
    if (val === undefined) continue;
    criteria[q.key] = val;
  }

  if (category === 'housing') {
    criteria.destination_city = criteria.destination_city || 'Singapore';
    const minB = typeof criteria.budget_min === 'number' ? criteria.budget_min : 2000;
    const maxB = typeof criteria.budget_max === 'number' ? criteria.budget_max : 5000;
    criteria.budget_monthly = { min: minB, max: maxB };
    if (typeof criteria.commute_mins === 'number') {
      criteria.commute_work = { max_minutes: criteria.commute_mins, address: criteria.office_address || '', mode: 'transit' };
    }
    if (typeof criteria.office_address === 'string' && criteria.office_address.trim()) {
      criteria.office_address = criteria.office_address.trim();
    }
  }
  if (category === 'movers') {
    criteria.current_accommodation = {
      type: criteria.acc_type || 'apartment',
      bedrooms: typeof criteria.acc_bedrooms === 'number' ? criteria.acc_bedrooms : 2,
      sqm: 80,
    };
    delete criteria.acc_type;
    delete criteria.acc_bedrooms;
  }
  if (category === 'housing') {
    delete criteria.budget_min;
    delete criteria.budget_max;
    delete criteria.commute_mins;
  }
  if (category === 'schools') {
    criteria.destination_city = criteria.destination_city || answers.dest_city || 'Singapore';
  }
  if (category === 'schools' && typeof criteria.child_ages === 'string') {
    criteria.child_ages = (criteria.child_ages as string)
      .split(',')
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !isNaN(n));
    if ((criteria.child_ages as number[]).length === 0) criteria.child_ages = [8];
  }
  if (category === 'banks' && typeof criteria.preferred_languages === 'string') {
    criteria.preferred_languages = (criteria.preferred_languages as string)
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    if ((criteria.preferred_languages as string[]).length === 0) criteria.preferred_languages = ['en'];
  }
  if (category === 'insurances' && typeof criteria.coverage_types === 'string') {
    criteria.coverage_types = (criteria.coverage_types as string)
      .split(',')
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean);
    if ((criteria.coverage_types as string[]).length === 0) criteria.coverage_types = ['health'];
  }

  return criteria;
}

interface Props {
  selectedServices: Set<TabKey>;
  onComplete: (results: Record<string, RecommendationResponse>) => void;
  onBack: () => void;
  initialAnswers?: Record<string, unknown>;
}

export const ProvidersCriteriaWizard: React.FC<Props> = ({
  selectedServices,
  onComplete,
  onBack,
  initialAnswers,
}) => {
  const categories = Array.from(selectedServices) as TabKey[];
  const questions = getQuestionsForCategories(categories);

  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, unknown>>(() => {
    const a: Record<string, unknown> = {};
    for (const q of questions) {
      a[q.id] = initialAnswers?.[q.id] ?? q.default;
    }
    return a;
  });

  useEffect(() => {
    if (initialAnswers && Object.keys(initialAnswers).length > 0) {
      setAnswers((prev) => {
        const next = { ...prev };
        const questionIds = new Set(questions.map((q) => q.id));
        for (const [id, val] of Object.entries(initialAnswers)) {
          if (questionIds.has(id) && val !== undefined) next[id] = val;
        }
        return next;
      });
    }
  }, [initialAnswers]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  const STEPS_PER_PAGE = 4;
  const totalSteps = Math.ceil(questions.length / STEPS_PER_PAGE);
  const start = step * STEPS_PER_PAGE;
  const pageQuestions = questions.slice(start, start + STEPS_PER_PAGE);

  const setAnswer = (id: string, value: unknown) => {
    setAnswers((prev) => ({ ...prev, [id]: value }));
  };

  const handleSubmit = async () => {
    setError('');
    setIsSubmitting(true);
    try {
      const results: Record<string, RecommendationResponse> = {};
      for (const cat of categories) {
        const backendKey = CATEGORY_MAP[cat];
        const criteria = buildCriteriaFromAnswers(answers, cat);
        const res = await recommendationsEngineAPI.recommend(backendKey, criteria, 10);
        results[cat] = res;
      }
      onComplete(results);
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : (err as Error)?.message;
      setError(String(msg || 'Failed to load recommendations.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const isLastStep = step >= totalSteps - 1;

  return (
    <Card padding="lg">
      <div className="flex items-center justify-between mb-6">
        <button onClick={onBack} className="text-sm text-[#0b2b43] hover:underline">
          ← Change services
        </button>
        <span className="text-sm text-[#6b7280]">
          Step {step + 1} of {totalSteps}
        </span>
      </div>
      <h2 className="text-xl font-semibold text-[#0b2b43] mb-2">Tell us your preferences</h2>
      <p className="text-sm text-[#6b7280] mb-6">
        Answer a few questions so we can tailor recommendations for {categories.join(', ')}.
      </p>

      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      <div className="space-y-4">
        {pageQuestions.map((q) => (
          <div key={q.id}>
            <label className="block text-sm font-medium text-[#0b2b43] mb-1">{q.label}</label>
            {q.type === 'text' && (
              <Input
                value={String(answers[q.id] ?? q.default ?? '')}
                onChange={(val) => setAnswer(q.id, val)}
                placeholder={q.placeholder}
                fullWidth
              />
            )}
            {q.type === 'number' && (
              <Input
                type="number"
                value={String(answers[q.id] ?? q.default ?? '')}
                onChange={(val) => {
                  const n = parseInt(val, 10);
                  setAnswer(q.id, isNaN(n) ? 0 : n);
                }}
                fullWidth
              />
            )}
            {q.type === 'select' && (
              <select
                value={String(answers[q.id] ?? q.default ?? '')}
                onChange={(e) => setAnswer(q.id, e.target.value)}
                className="w-full px-4 py-2 border border-[#e2e8f0] rounded-lg"
              >
                {q.options?.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            )}
            {q.type === 'checkbox' && (
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={Boolean(answers[q.id] ?? q.default ?? false)}
                  onChange={(e) => setAnswer(q.id, e.target.checked)}
                />
                <span className="text-sm text-[#4b5563]">Yes</span>
              </label>
            )}
          </div>
        ))}
      </div>

      <div className="flex gap-3 mt-8">
        {step > 0 ? (
          <Button variant="outline" onClick={() => setStep((s) => s - 1)}>
            Back
          </Button>
        ) : (
          <Button variant="outline" onClick={onBack}>
            Back
          </Button>
        )}
        {!isLastStep ? (
          <Button onClick={() => setStep((s) => s + 1)}>Next</Button>
        ) : (
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? 'Loading recommendations...' : 'Get recommendations'}
          </Button>
        )}
      </div>
    </Card>
  );
};
