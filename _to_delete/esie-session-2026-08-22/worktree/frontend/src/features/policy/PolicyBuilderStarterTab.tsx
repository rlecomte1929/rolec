/**
 * Policy builder tab (AIQ-1600).
 *
 * Per admin feedback BUG-260718-C624, the "Policy builder" tab now opens with
 * "Start with a standard baseline" as the first thing HR sees. The full
 * authoring UI (tier editor, document import, template picker, live preview)
 * moved to the "Benefits summary" tab — this tab links there for anyone who
 * wants the detailed builder.
 */
import React, { useState } from 'react';
import { Button, Card } from '../../components/antigravity';
import { StarterPolicyOnboardingCard } from './StarterPolicyOnboardingCard';
import { type StarterTemplateKey } from './starterPolicyCopy';
import { applyStarterBaseline, parseStarterBaselineError } from './applyStarterBaseline';
import { usePolicyPublished } from '../../hooks/usePolicyPublished';

export const PolicyBuilderStarterTab: React.FC<{ onOpenFullBuilder: () => void }> = ({
  onOpenFullBuilder,
}) => {
  const [busyTemplateKey, setBusyTemplateKey] = useState<StarterTemplateKey | null>(null);
  const [error, setError] = useState<string | null>(null);
  // AIQ-1644: this tab must not contradict the Published tab. Both read the SAME canonical
  // published-state signal (GET /api/hr/policy-config/published); when a policy already
  // exists, offer to edit / version it instead of inviting a from-scratch baseline. `null`
  // = unknown (still loading / check failed) → keep the baseline invite, exactly as before.
  const hasPublishedPolicy = usePolicyPublished();

  const handleSelectTemplate = async (key: StarterTemplateKey) => {
    setError(null);
    setBusyTemplateKey(key);
    try {
      // AIQ-1588: seed the config-matrix draft (canonical subsystem the full
      // builder edits). The baseline is a draft; the full builder (now on the
      // Benefits summary tab) is where HR reviews and publishes it.
      await applyStarterBaseline(key);
      onOpenFullBuilder();
    } catch (err: unknown) {
      const { code, message } = parseStarterBaselineError(err);
      setError(
        code === 'draft_has_rows'
          ? 'You already have a policy draft in progress. Open the full builder to apply a template there.'
          : message,
      );
    } finally {
      setBusyTemplateKey(null);
    }
  };

  // AIQ-1644: a policy is already published — reflect that instead of a blank-baseline
  // invitation, so the Policy builder tab agrees with the Published tab.
  if (hasPublishedPolicy === true) {
    return (
      <div className="space-y-6">
        <Card padding="lg">
          <h2 className="text-base font-semibold text-[#0b2b43]">
            A relocation policy is already set up for your company
          </h2>
          <p className="text-sm text-[#4b5563] mt-1 max-w-2xl">
            You don’t need to start from a baseline. Open the full policy builder to review the
            current benefits matrix, adjust the tier caps, or publish a new version.
          </p>
          <div className="mt-4">
            <Button variant="primary" onClick={onOpenFullBuilder}>
              Edit or version your policy →
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <StarterPolicyOnboardingCard
        error={error}
        busyTemplateKey={busyTemplateKey}
        onSelectTemplate={handleSelectTemplate}
        onUploadDocument={onOpenFullBuilder}
      />

      <Card padding="lg" className="border-dashed border-[#cbd5e1] bg-[#f8fafc]">
        <h2 className="text-sm font-semibold text-[#0b2b43]">Already have a policy in progress?</h2>
        <p className="text-sm text-[#4b5563] mt-1 max-w-2xl">
          The full policy builder — tier caps, document import, template picker and live preview —
          now lives on the <strong>Benefits summary</strong> tab.
        </p>
        <div className="mt-3">
          <Button variant="outline" onClick={onOpenFullBuilder}>
            Open the full policy builder →
          </Button>
        </div>
      </Card>
    </div>
  );
};
