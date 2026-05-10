import React from 'react';
import { Card, Button } from '../../../components/antigravity';
import type { RelocationPlanNextActionDTO, RelocationPlanViewResponseDTO } from '../../../types/relocationPlanView';
import { ownerLabel } from '../../relocation-plan-employee/relocationPlanLabels';
import {
  relocationTaskCtaDefaultButtonLabel,
  resolveRelocationTaskCtaTarget,
  type RelocationPlanCtaNavigateContext,
} from '../task-card/relocationTaskCtaMap';
import { nextActionCardEmptyCopy } from './nextActionEmptyCopy';

function formatDue(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = iso.slice(0, 10);
  return d || null;
}

export interface NextActionCardProps {
  ctaContext: RelocationPlanCtaNavigateContext;
  /** Backend `next_action`; when null, a calm empty state is shown (no CTA). */
  nextAction: RelocationPlanNextActionDTO | null | undefined;
  /** Full plan view — used only to derive empty-state copy when `nextAction` is null. */
  planView: RelocationPlanViewResponseDTO;
  onCta: (cta: RelocationPlanNextActionDTO['cta']) => void;
}

/**
 * Compact sticky (desktop) highlight for the server-driven next step, or a single calm empty state.
 */
export const NextActionCard: React.FC<NextActionCardProps> = ({
  ctaContext,
  nextAction,
  planView,
  onCta,
}) => {
  const empty = nextActionCardEmptyCopy(planView);

  return (
    <div
      className="mb-4 lg:mb-5 lg:sticky lg:top-4 lg:z-[5] scroll-mt-4"
      style={{ paddingTop: 'env(safe-area-inset-top, 0px)' }}
    >
      {nextAction ? (
        <Card
          padding="md"
          className={`shadow-sm border-[#e2e8f0] bg-white/95 lg:backdrop-blur-sm ${
            nextAction.blocking ? 'border-l-[3px] border-l-amber-400' : ''
          }`}
        >
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#94a3b8] mb-2">Next action</p>
          <h2 className="text-base font-semibold text-[#0b2b43] leading-snug">{nextAction.title}</h2>
          <dl className="mt-2.5 flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-[#64748b]">
            <div className="flex items-baseline gap-1.5">
              <dt className="font-medium text-[#94a3b8] shrink-0">Owner</dt>
              <dd className="text-[#334155]">{ownerLabel(nextAction.owner)}</dd>
            </div>
            {formatDue(nextAction.due_date) ? (
              <div className="flex items-baseline gap-1.5">
                <dt className="font-medium text-[#94a3b8] shrink-0">Due</dt>
                <dd className="text-[#334155]">{formatDue(nextAction.due_date)}</dd>
              </div>
            ) : null}
          </dl>
          {nextAction.reason ? (
            <div className="mt-2.5 pt-2.5 border-t border-[#f1f5f9]">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[#94a3b8] mb-0.5">
                Why now
              </p>
              <p className="text-sm text-[#475569] leading-snug">{nextAction.reason}</p>
            </div>
          ) : null}
          <Button
            variant="primary"
            size="md"
            fullWidth
            className="mt-3 min-h-[44px] text-sm"
            aria-label={`Go to next step: ${nextAction.title}`}
            onClick={() => onCta(nextAction.cta)}
          >
            {relocationTaskCtaDefaultButtonLabel(
              nextAction.cta ?? undefined,
              resolveRelocationTaskCtaTarget(ctaContext, nextAction.cta)
            )}
          </Button>
        </Card>
      ) : (
        <div role="status" aria-live="polite">
          <Card
            padding="md"
            className="shadow-sm border-[#e8ecf0] bg-[#f8fafc] lg:bg-white/90 lg:backdrop-blur-sm"
          >
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[#94a3b8] mb-1.5">
              Next action
            </p>
            <p className="text-sm font-medium text-[#475569] leading-snug">{empty.headline}</p>
            {empty.detail ? (
              <p className="text-xs text-[#64748b] mt-1.5 leading-relaxed">{empty.detail}</p>
            ) : null}
          </Card>
        </div>
      )}
    </div>
  );
};
