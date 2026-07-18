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
import { companyPolicyAPI } from '../../api/client';
import { StarterPolicyOnboardingCard } from './StarterPolicyOnboardingCard';
import { type StarterTemplateKey } from './starterPolicyCopy';

export const PolicyBuilderStarterTab: React.FC<{ onOpenFullBuilder: () => void }> = ({
  onOpenFullBuilder,
}) => {
  const [busyTemplateKey, setBusyTemplateKey] = useState<StarterTemplateKey | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSelectTemplate = async (key: StarterTemplateKey) => {
    setError(null);
    setBusyTemplateKey(key);
    try {
      await companyPolicyAPI.initializeFromTemplate({
        template_key: key,
        comparison_ready_structure: true,
      });
      // The baseline is created as a draft; the full builder (now on the
      // Benefits summary tab) is where HR reviews and publishes it.
      onOpenFullBuilder();
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: unknown } } };
      const d = ax?.response?.data?.detail;
      const msg =
        d && typeof d === 'object' && d !== null && 'message' in d
          ? String((d as { message?: string }).message)
          : typeof d === 'string'
            ? d
            : 'Could not create baseline policy.';
      setError(msg);
    } finally {
      setBusyTemplateKey(null);
    }
  };

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
