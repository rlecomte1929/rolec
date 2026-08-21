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
  // Production stores `verified` for INTERNALLY reviewed rows. The backend passes
  // verification_status straight through — there is no translation layer — so this map
  // must honour the value the database actually holds, or the badge silently disappears.
  //
  // It must NOT, however, borrow the expert label. Measured 2026-08-20: all ten `verified`
  // rows are Norway, reviewed_by='romain', attestation_status=null, and `expert_verified`
  // is 0 across the entire catalog. disclaimers.py reserves "expert_verified" for content
  // "signed off by a licensed immigration lawyer" — no lawyer has seen these. Rendering
  // them as "Expert-verified" asserted a status we do not hold, to the reader least able
  // to check it. Missing provenance is a gap; a false provenance claim is a liability, and
  // it is the same mistake as the "EU AI Act Ready" badge (AIQ-1513).
  //
  // 'info', not 'success': the green rung stays reserved for genuine external sign-off, so
  // the first real counsel attestation is visibly distinct rather than lost among ten rows
  // already wearing the strongest badge we have.
  verified: { label: 'Reviewed', variant: 'info' },
};

const provenanceBadge = (status: RequirementItemDTO['verificationStatus']) => {
  const p = status ? PROVENANCE[status] : undefined;
  if (!p) return null;
  return <Badge variant={p.variant} size="sm">{p.label}</Badge>;
};

/**
 * Counsel attestation — a SEPARATE axis from provenance, deliberately not folded into
 * PROVENANCE above.
 *
 * That map is our own sourcing ladder (representative -> corpus_grounded -> verified).
 * This is external legal sign-off. models.py states the relationship: "Sellable means
 * BOTH". Merging them would let "Expert-verified" read as counsel-assured, which is a
 * claim we do not hold and must not imply.
 *
 * `requested` and null render NOTHING. An attestation that has been asked for is not an
 * attestation, and an absent one must never appear as reassurance — the same rule the
 * non-obvious badge follows, where only `true` earns a pill. Today every production row
 * is null, so this renders nothing at all; that is the honest state, and it is what makes
 * the first real attestation visible when it lands.
 */
const ATTESTATION: Record<string, { label: string; variant: 'neutral' | 'success' }> = {
  attested: { label: 'Counsel-attested', variant: 'success' },
  stale: { label: 'Attestation stale', variant: 'neutral' },
};

const attestationBadge = (
  status: RequirementItemDTO['attestationStatus'],
  by?: string | null,
) => {
  const a = status ? ATTESTATION[status] : undefined;
  if (!a) return null;
  const label = status === 'attested' && by ? `${a.label} · ${by}` : a.label;
  return (
    <Badge variant={a.variant} size="sm" data-testid="attestation-badge">
      {label}
    </Badge>
  );
};

/**
 * The whole point of the product: a requirement nobody warns you about, flagged
 * inline so a week-seven ambush is visible in week one.
 *
 * Only `true` renders. `null`/`undefined` means the item was synthesised by the rules
 * engine and has no catalog row to carry the flag — that is "not modeled", which is a
 * different claim from `false` ("modeled, and it is obvious"). Neither earns a badge,
 * but they must not be collapsed into one another.
 *
 * Amber matches the "Book early" pill in ImmigrationStatusPanel, which is the same idea
 * on the other requirement surface — the two should not diverge visually.
 */
const nonObviousBadge = (nonObvious: RequirementItemDTO['nonObvious']) =>
  nonObvious ? <Badge variant="warning" size="sm">Easy to miss</Badge> : null;

/** Free text, not a date — the source phrases deadlines against events we do not model. */
const timingLine = (timing: RequirementItemDTO['timing']) =>
  timing ? (
    <div data-testid="requirement-timing" className="text-xs text-[#7a5e2a] mt-1">
      Due: {timing}
    </div>
  ) : null;

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
        {(provenanceBadge(item.verificationStatus) ||
          attestationBadge(item.attestationStatus, item.attestedBy)) && (
          <div className="mt-3 flex flex-wrap gap-2">
            {provenanceBadge(item.verificationStatus)}
            {attestationBadge(item.attestationStatus, item.attestedBy)}
          </div>
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
                {timingLine(item.timing)}
                <div className="flex flex-wrap gap-2 mt-3">
                  <Badge variant={statusVariant(item.statusForCase)} size="sm">
                    {item.statusForCase}
                  </Badge>
                  <Badge variant={ownerVariant(item.owner)} size="sm">
                    {item.owner}
                  </Badge>
                  {nonObviousBadge(item.nonObvious)}
                  {provenanceBadge(item.verificationStatus)}
                  {attestationBadge(item.attestationStatus, item.attestedBy)}
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
