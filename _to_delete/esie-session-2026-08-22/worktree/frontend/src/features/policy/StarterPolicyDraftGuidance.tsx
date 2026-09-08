/**
 * After starter init: success + next step (publish vs review) for template-sourced drafts.
 */
import React from 'react';
import { Alert, Button, Card } from '../../components/antigravity';
import type { HrPolicyWorkspacePhase } from './hrPolicyWorkspaceState';
import { STARTER_TEMPLATE_OPTIONS, type StarterTemplateKey } from './starterPolicyCopy';

export type StarterPolicyDraftGuidanceProps = {
  templateKey: StarterTemplateKey | null;
  phase: HrPolicyWorkspacePhase;
  onReviewDraft: () => void;
  onPublishPolicy: () => void | Promise<void>;
  publishBusy: boolean;
  /** When false, publish entry points stay disabled (e.g. normalized/review still loading). */
  publishDataReady?: boolean;
};

function templateLabel(key: StarterTemplateKey | null): string {
  if (!key) return 'baseline';
  return STARTER_TEMPLATE_OPTIONS.find((o) => o.key === key)?.label || key;
}

export const StarterPolicyDraftGuidance: React.FC<StarterPolicyDraftGuidanceProps> = ({
  templateKey,
  phase,
  onReviewDraft,
  onPublishPolicy,
  publishBusy,
  publishDataReady = true,
}) => {
  const label = templateLabel(templateKey);

  return (
    <Card padding="lg" className="border-emerald-200 bg-emerald-50/60">
      <div className="text-sm font-semibold text-emerald-900">Baseline created</div>
      <p className="text-sm text-emerald-900/90 mt-2">
        Your <strong>{label}</strong> baseline is saved as a <strong>draft</strong>. Edit any rule in the table below.
        Employees do <strong>not</strong> see it until you publish.
      </p>

      {phase === 'ready_to_publish' && (
        <div className="mt-4 space-y-3">
          <p className="text-sm text-emerald-900">
            ReloPass checks show this draft is <strong>ready to go live</strong>. Publishing is what puts these
            benefits on employee assignments (within eligibility).
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              onClick={() => void onPublishPolicy()}
              disabled={publishBusy || !publishDataReady}
            >
              {publishBusy ? 'Publishing…' : 'Publish now'}
            </Button>
            <Button variant="outline" size="sm" onClick={onReviewDraft}>
              Review benefit table first
            </Button>
          </div>
        </div>
      )}

      {phase === 'draft_not_publishable' && (
        <div className="mt-4 space-y-3">
          <Alert variant="warning">
            <strong>Review before publish.</strong> Complete the items in the draft panel above (or adjust rules below)
            until the workspace shows <em>Ready to publish</em>. Then use <strong>Publish version</strong> in the
            publish controls.
          </Alert>
          <Button size="sm" variant="outline" onClick={onReviewDraft}>
            Jump to benefit table
          </Button>
        </div>
      )}

      {phase === 'published' && (
        <p className="text-sm text-emerald-800 mt-3">
          This baseline is live for employees. You can still edit values or upload a formal company policy later—new
          uploads stay as drafts until you publish them.
        </p>
      )}
    </Card>
  );
};
