/**
 * InferredOnboardingPanel — AIQ-1223d
 *
 * First-run "Suggested setup" surface for a brand-new HR workspace. It is the
 * `variant` arm of the `hr_inference_onboarding` A/B test (the `control` arm is
 * the plain `CasesEmptyState`). Instead of asking HR a setup wall, it reads the
 * deterministic inference engine (AIQ-1223c, GET /api/hr/onboarding/inferred-config)
 * and renders the proposed workspace config as EDITABLE pre-fills.
 *
 * Everything here is additive: every value remains overrideable and the manual
 * surfaces (company profile + policy builder) stay one click away, so HR is
 * never locked into a suggestion.
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, Button, Input, Badge, Alert } from '../../components/antigravity';
import { hrAPI } from '../../api/client';
import { logger } from '../../lib/logger';
import type { InferredOnboardingConfig } from '../../types';

const CONFIDENCE_VARIANT: Record<string, 'success' | 'info' | 'neutral'> = {
  high: 'success',
  medium: 'info',
  low: 'neutral',
};

export function InferredOnboardingPanel({
  onCreateCase,
}: {
  onCreateCase: () => void;
}) {
  const [config, setConfig] = useState<InferredOnboardingConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [applying, setApplying] = useState(false);

  // Editable pre-fills (seeded from the inferred config).
  const [destination, setDestination] = useState('');
  const [workingLocation, setWorkingLocation] = useState('');

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const data = await hrAPI.getInferredOnboardingConfig();
        if (!active) return;
        setConfig(data);
        setDestination(data.proposed_config.default_destination_country ?? '');
        setWorkingLocation(data.proposed_config.default_working_location ?? '');
      } catch (e) {
        if (!active) return;
        logger.warn('InferredOnboardingPanel: failed to load inferred config', e);
        setError('Could not load suggestions.');
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  // Persist any edited pre-fills to the company profile, then open the first
  // case form. saveCompanyProfile requires the company name, so we read the
  // current profile first; if it is unavailable we skip the save and still let
  // HR proceed (the values stay editable on the company-profile page).
  const applyAndCreate = async () => {
    setApplying(true);
    try {
      const { company } = await hrAPI.getCompanyProfile();
      const name = (company?.name ?? '').trim();
      if (name) {
        await hrAPI.saveCompanyProfile({
          name,
          default_destination_country: destination.trim() || undefined,
          default_working_location: workingLocation.trim() || undefined,
        });
      }
    } catch (e) {
      logger.warn('InferredOnboardingPanel: apply failed (continuing to case form)', e);
    } finally {
      setApplying(false);
      onCreateCase();
    }
  };

  if (loading) {
    return (
      <div className="max-w-xl mx-auto py-16">
        <div className="h-40 rounded-lg bg-[#e2e8f0] animate-pulse" />
      </div>
    );
  }

  // On any error or missing config, degrade to the manual first-case path so the
  // variant is never worse than control.
  if (error || !config) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center max-w-md mx-auto">
        <h3 className="text-lg font-semibold text-[#0b2b43] mb-2">No relocation cases yet.</h3>
        <p className="text-sm text-[#4b5563] mb-6">
          A case is the record for one employee&rsquo;s move. It holds their timeline,
          documents, vendor assignments, and compliance status.
        </p>
        <Button onClick={onCreateCase}>Open your first case →</Button>
      </div>
    );
  }

  const { signals, proposed_config: cfg, confidence } = config;

  return (
    <div className="max-w-xl mx-auto py-10">
      <Card>
        <div className="flex items-start justify-between gap-3 mb-1">
          <h3 className="text-lg font-semibold text-[#0b2b43]">Suggested setup</h3>
          <Badge variant={CONFIDENCE_VARIANT[confidence] ?? 'neutral'} size="sm">
            {confidence} confidence
          </Badge>
        </div>
        <p className="text-sm text-[#4b5563] mb-5">
          We pre-filled your workspace from what we already know. Everything below
          is editable &mdash; adjust anything, then open your first case.
        </p>

        {/* Editable pre-fills */}
        <div className="grid gap-4 mb-5">
          <Input
            label="Default destination country"
            value={destination}
            onChange={setDestination}
            placeholder="e.g. Germany"
          />
          <Input
            label="Default working location"
            value={workingLocation}
            onChange={setWorkingLocation}
            placeholder="e.g. Berlin office"
          />
        </div>

        {/* Proposed policy tier scaffold (set up in the builder) */}
        <div className="mb-5">
          <div className="text-sm font-medium text-[#374151] mb-2">
            Proposed policy tiers
          </div>
          <div className="flex flex-wrap gap-2">
            {cfg.policy_tiers.map((tier) => (
              <Badge key={tier} variant="info" size="sm">
                {tier}
              </Badge>
            ))}
          </div>
          <p className="text-xs text-[#6b7280] mt-2">
            {cfg.tier_source === 'published'
              ? 'Reconciled from your published policy.'
              : 'Suggested from your company size — refine in the Policy Builder.'}
          </p>
        </div>

        {signals.size_band && (
          <Alert variant="info" className="mb-5">
            Based on company size {signals.size_band}
            {signals.case_count > 0 ? ` and ${signals.case_count} existing case(s)` : ''}.
          </Alert>
        )}

        <div className="flex flex-col gap-3">
          <Button onClick={applyAndCreate} disabled={applying}>
            {applying ? 'Applying…' : 'Apply & open first case →'}
          </Button>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
            <Link to="/hr/company-profile" className="text-[#1f8e8b] hover:underline">
              Edit company profile
            </Link>
            <Link to="/hr/policy?tab=builder" className="text-[#1f8e8b] hover:underline">
              Open Policy Builder
            </Link>
            <button
              type="button"
              onClick={onCreateCase}
              className="text-[#6b7280] hover:underline"
            >
              Skip suggestions
            </button>
          </div>
        </div>
      </Card>
    </div>
  );
}
