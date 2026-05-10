/**
 * Empty-state card: choose a platform starter baseline or upload a real policy later.
 */
import React, { useState } from 'react';
import { Alert, Button, Card } from '../../components/antigravity';
import {
  STARTER_POLICY_CARD_EXPLANATION,
  STARTER_POLICY_CARD_TITLE,
  STARTER_POLICY_DISCLOSURE_BULLETS,
  STARTER_TEMPLATE_OPTIONS,
  type StarterTemplateKey,
} from './starterPolicyCopy';

export type StarterPolicyOnboardingCardProps = {
  error: string | null;
  busyTemplateKey: StarterTemplateKey | null;
  onSelectTemplate: (key: StarterTemplateKey) => void | Promise<void>;
  onUploadDocument: () => void;
};

export const StarterPolicyOnboardingCard: React.FC<StarterPolicyOnboardingCardProps> = ({
  error,
  busyTemplateKey,
  onSelectTemplate,
  onUploadDocument,
}) => {
  const [selectedKey, setSelectedKey] = useState<StarterTemplateKey>('standard');

  return (
    <Card padding="lg" className="border-[#0b2b43]/15 bg-gradient-to-b from-[#f8fafc] to-white">
      <h2 className="text-lg font-semibold text-[#0b2b43]">{STARTER_POLICY_CARD_TITLE}</h2>
      <p className="text-sm text-[#4b5563] mt-2 max-w-3xl leading-relaxed">{STARTER_POLICY_CARD_EXPLANATION}</p>

      <ul className="mt-4 space-y-2 text-sm text-[#374151] list-disc list-inside max-w-3xl">
        {STARTER_POLICY_DISCLOSURE_BULLETS.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>

      {error && (
        <Alert variant="error" className="mt-4">
          {error}
        </Alert>
      )}

      <div className="mt-6">
        <div className="text-sm font-medium text-[#0b2b43] mb-3">Choose a baseline</div>
        <div className="grid gap-3 sm:grid-cols-3">
          {STARTER_TEMPLATE_OPTIONS.map((opt) => {
            const selected = selectedKey === opt.key;
            const busy = busyTemplateKey === opt.key;
            return (
              <button
                key={opt.key}
                type="button"
                onClick={() => setSelectedKey(opt.key)}
                disabled={busyTemplateKey !== null}
                className={`text-left rounded-lg border p-4 transition-colors ${
                  selected
                    ? 'border-[#0b2b43] bg-[#0b2b43]/5 ring-1 ring-[#0b2b43]/20'
                    : 'border-[#e5e7eb] bg-white hover:border-[#cbd5e1]'
                } ${busyTemplateKey !== null && !busy ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`h-4 w-4 rounded-full border-2 shrink-0 ${
                      selected ? 'border-[#0b2b43] bg-[#0b2b43]' : 'border-[#cbd5e1]'
                    }`}
                    aria-hidden
                  />
                  <span className="font-semibold text-[#0b2b43]">{opt.label}</span>
                </div>
                <p className="text-xs text-[#6b7280] mt-2 leading-snug">{opt.description}</p>
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex flex-wrap gap-3 mt-6">
        <Button
          onClick={() => void onSelectTemplate(selectedKey)}
          disabled={busyTemplateKey !== null}
        >
          {busyTemplateKey
            ? `Creating ${STARTER_TEMPLATE_OPTIONS.find((o) => o.key === busyTemplateKey)?.label ?? busyTemplateKey}…`
            : `Create ${STARTER_TEMPLATE_OPTIONS.find((o) => o.key === selectedKey)?.label ?? ''} baseline`}
        </Button>
        <Button variant="outline" onClick={onUploadDocument} disabled={busyTemplateKey !== null}>
          Upload company policy instead
        </Button>
      </div>

      <p className="text-xs text-[#6b7280] mt-4 max-w-2xl">
        After you create it, the baseline shows up as a <strong>draft</strong> below. Review the benefit table, then
        choose <strong>Publish version</strong> when this page shows <strong>Ready to go live</strong>.
      </p>
    </Card>
  );
};
