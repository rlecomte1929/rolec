/**
 * AIQ-37-B · Policy Builder Wizard — Steps 1–3
 *
 * Container that orchestrates:
 *  - WizardStepIndicator (progress bar, 5 steps)
 *  - Step 1: StepTiers
 *  - Step 2: StepBudgets
 *  - Step 3: StepDocuments
 *  - Steps 4–5: placeholder panels (will be built in AIQ-37-C)
 *
 * State lives in usePolicyDraft.  HR can save a draft at any time using the
 * "Save draft" button; saving does NOT require navigating through all steps.
 */
import React, { useCallback } from 'react';
import { Input } from '../../components/antigravity/Input';
import { Card, Button } from '../../components/antigravity';
import { WizardStepIndicator } from './WizardStepIndicator';
import { StepTiers } from './StepTiers';
import { StepBudgets } from './StepBudgets';
import { StepDocuments } from './StepDocuments';
import { usePolicyDraft } from './usePolicyDraft';

const TOTAL_STEPS = 5;

// Simple placeholder for steps 4–5 (AIQ-37-C)
const PlaceholderStep: React.FC<{ title: string; onBack: () => void }> = ({
  title,
  onBack,
}) => (
  <div className="space-y-6">
    <div>
      <h2 className="text-lg font-semibold text-[#0b2b43]">{title}</h2>
      <p className="text-sm text-slate-500 mt-1">
        This step will be available soon (AIQ-37-C).
      </p>
    </div>
    <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-10 text-center text-slate-400 text-sm">
      Coming in the next release
    </div>
    <div className="flex justify-between pt-2">
      <Button variant="outline" onClick={onBack} type="button">
        ← Back
      </Button>
    </div>
  </div>
);

export const PolicyBuilderWizard: React.FC = () => {
  const [step, setStep] = React.useState(1);
  const draft = usePolicyDraft();

  const goNext = useCallback(() => setStep((s) => Math.min(s + 1, TOTAL_STEPS)), []);
  const goBack = useCallback(() => setStep((s) => Math.max(s - 1, 1)), []);

  const handleSaveDraft = async () => {
    await draft.saveDraft();
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6 pb-16">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#0b2b43]">Policy Builder</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Create or update your company&apos;s relocation policy in a few guided steps.
          </p>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          {draft.savedFlash && (
            <span
              className="text-sm text-emerald-600 font-medium"
              role="status"
              aria-live="polite"
            >
              ✓ Draft saved
            </span>
          )}
          {draft.saveError && (
            <span className="text-sm text-red-600">{draft.saveError}</span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={handleSaveDraft}
            disabled={draft.saving}
            type="button"
          >
            {draft.saving ? 'Saving…' : 'Save draft'}
          </Button>
        </div>
      </div>

      {/* Optional policy label */}
      <div className="flex items-center gap-2">
        <label htmlFor="pbw-policy-label" className="text-sm font-medium text-slate-600 whitespace-nowrap">
          Policy label:
        </label>
        <Input unstyled
          id="pbw-policy-label"
          type="text"
          value={draft.label}
          onChange={(v) => draft.setLabel(v)}
          placeholder='e.g. "2026-Q3 relocation policy"'
          className="flex-1 max-w-xs border border-slate-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#0b2b43] focus:ring-offset-1"
        />
        {draft.draftId && (
          <span className="text-xs text-slate-400">
            Draft saved · version will be assigned on activation
          </span>
        )}
      </div>

      {/* Progress indicator */}
      <WizardStepIndicator currentStep={step} />

      {/* Step content */}
      <Card padding="lg">
        {step === 1 && (
          <StepTiers
            tiers={draft.json.tiers}
            onChange={draft.setTiers}
            onNext={goNext}
          />
        )}
        {step === 2 && (
          <StepBudgets
            tiers={draft.json.tiers}
            budgets={draft.json.budgets}
            onChange={draft.setBudgets}
            onBack={goBack}
            onNext={goNext}
          />
        )}
        {step === 3 && (
          <StepDocuments
            documents={draft.json.documents}
            onChange={draft.setDocuments}
            onBack={goBack}
            onNext={goNext}
          />
        )}
        {step === 4 && (
          <PlaceholderStep
            title="Approved vendor categories"
            onBack={goBack}
          />
        )}
        {step === 5 && (
          <PlaceholderStep title="Review & activate policy" onBack={goBack} />
        )}
      </Card>

      {/* Bottom save hint */}
      <p className="text-xs text-slate-400 text-center">
        Your progress is saved as a draft — it won&apos;t go live until you activate it in Step 5.
      </p>
    </div>
  );
};
