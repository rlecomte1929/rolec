import React from 'react';
import { Check } from 'lucide-react';
import { Button, Badge } from '../antigravity';
import type { RequirementItemDTO } from '../../types';
import { Citations } from './Citations';

interface RequirementListProps {
  items: RequirementItemDTO[];
  onAction?: (action: string, item: RequirementItemDTO) => void;
}

const statusVariant = (status: RequirementItemDTO['statusForCase']) => {
  if (status === 'PROVIDED') return 'success';
  if (status === 'MISSING') return 'error';
  return 'warning';
};

const ownerVariant = (owner: RequirementItemDTO['owner']) => {
  if (owner === 'HR') return 'info';
  if (owner === 'Employee') return 'warning';
  return 'neutral';
};

// AIQ-1349: provenance badge — how trustworthy this requirement is.
const PROVENANCE: Record<string, { label: string; variant: 'neutral' | 'info' | 'success' }> = {
  representative: { label: 'Representative', variant: 'neutral' },
  corpus_grounded: { label: 'Source-grounded', variant: 'info' },
  expert_verified: { label: 'Expert-verified', variant: 'success' },
};

const provenanceBadge = (status: RequirementItemDTO['verificationStatus']) => {
  const p = status ? PROVENANCE[status] : undefined;
  if (!p) return null;
  return <Badge variant={p.variant} size="sm">{p.label}</Badge>;
};

/**
 * A `nothing_to_do` item is a POSITIVE ANSWER, not a pending task.
 *
 * "No visa or residence permit required" exists precisely so that a correct answer
 * of "none" gets stated rather than implied by an empty pillar — an empty pillar
 * reads as a broken screen, or as "we didn't check". Rendering it as an ordinary
 * row would undo that: it would carry a status badge and Upload / Answer / Ask HR /
 * Mark Reviewed buttons, asking the employee to act on a thing that asks nothing of
 * them. It is also a legal-adjacent statement, so its `reason` — the only
 * human-readable payload it has — must actually appear.
 */
const ConfirmationCard: React.FC<{ item: RequirementItemDTO }> = ({ item }) => (
  <div
    data-testid="requirement-confirmation"
    className="border border-[#bbf7d0] rounded-xl p-4 bg-[#f0fdf4]"
  >
    <div className="flex items-start gap-3">
      <Check className="w-4 h-4 mt-0.5 shrink-0 text-[#15803d]" aria-hidden="true" />
      <div>
        <div className="text-sm font-semibold text-[#14532d]">{item.title}</div>
        <div className="text-xs text-[#166534] mt-1">{item.reason || item.description}</div>
        {provenanceBadge(item.verificationStatus) && (
          <div className="mt-3">{provenanceBadge(item.verificationStatus)}</div>
        )}
      </div>
    </div>
    <Citations sources={item.citations} />
  </div>
);

export const RequirementList: React.FC<RequirementListProps> = ({ items, onAction }) => {
  return (
    <div className="space-y-4">
      {items.map((item) =>
        item.outcomeType === 'nothing_to_do' ? (
          <ConfirmationCard key={item.id} item={item} />
        ) : (
          <div key={item.id} className="border border-[#e2e8f0] rounded-xl p-4 bg-white">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-sm font-semibold text-[#0b2b43]">{item.title}</div>
                <div className="text-xs text-[#6b7280] mt-1">{item.description}</div>
                <div className="flex flex-wrap gap-2 mt-3">
                  <Badge variant={statusVariant(item.statusForCase)} size="sm">
                    {item.statusForCase}
                  </Badge>
                  <Badge variant={ownerVariant(item.owner)} size="sm">
                    {item.owner}
                  </Badge>
                  {provenanceBadge(item.verificationStatus)}
                </div>
              </div>
              {/* These four were rendered unconditionally, but no caller has ever
                  passed `onAction` — so they were dead no-ops on every screen. Now
                  they appear only when something is actually wired behind them; a
                  legally-consequential row must not offer an affordance that does
                  nothing. */}
              {onAction && (
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" onClick={() => onAction('Upload', item)}>
                    Upload
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => onAction('Answer', item)}>
                    Answer
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => onAction('Ask HR', item)}>
                    Ask HR
                  </Button>
                  <Button size="sm" onClick={() => onAction('Mark Reviewed', item)}>
                    Mark Reviewed
                  </Button>
                </div>
              )}
            </div>
            <Citations sources={item.citations} />
          </div>
        ),
      )}
    </div>
  );
};
