import React, { useMemo, useState } from 'react';
import { Button, Card } from '../../components/antigravity';
import type { AssignmentDetail } from '../../types';
import { deriveCaseEssentials } from './caseEssentials';

type Props = {
  assignment: AssignmentDetail;
  embedInOperationalFlow?: boolean;
};

/**
 * Compact triage block: who, family shape, origin → destination.
 * Data comes from the same assignment detail payload (plus server-enriched hints).
 */
export const CaseEssentialsCard: React.FC<Props> = ({
  assignment,
  embedInOperationalFlow = false,
}) => {
  const e = useMemo(() => deriveCaseEssentials(assignment), [assignment]);
  const [assignmentIdCopied, setAssignmentIdCopied] = useState(false);

  const contactCells: { label: string; value: string }[] = [
    { label: 'Employee', value: e.fullName },
    { label: 'Email', value: e.email },
  ];

  const routeCells: { label: string; value: string }[] = [
    { label: 'Family', value: e.familyStatus },
    { label: 'Origin', value: e.origin },
    { label: 'Destination', value: e.destination },
  ];

  const copyAssignmentId = async () => {
    const id = assignment.id?.trim();
    if (!id) return;
    try {
      await navigator.clipboard.writeText(id);
      setAssignmentIdCopied(true);
      window.setTimeout(() => setAssignmentIdCopied(false), 2000);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <Card padding="md" className="border border-[#e2e8f0] shadow-sm">
      {!embedInOperationalFlow && (
        <div className="text-xs font-semibold uppercase tracking-wide text-[#64748b] mb-3">
          Case essentials
        </div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {contactCells.map((c) => (
          <div key={c.label} className="min-w-0">
            <div className="text-[11px] font-medium text-[#64748b] uppercase tracking-wide">
              {c.label}
            </div>
            <div className="text-sm font-semibold text-[#0b2b43] mt-1 break-words">{c.value}</div>
          </div>
        ))}
        <div className="min-w-0">
          <div className="text-[11px] font-medium text-[#64748b] uppercase tracking-wide">
            Assignment ID
          </div>
          <div className="flex flex-wrap items-center gap-2 mt-1">
            <span
              className="text-sm font-mono font-semibold text-[#0b2b43] break-all"
              title={assignment.id}
            >
              {assignment.id || '—'}
            </span>
            {assignment.id ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void copyAssignmentId()}
              >
                {assignmentIdCopied ? 'Copied!' : 'Copy'}
              </Button>
            ) : null}
          </div>
        </div>
        {routeCells.map((c) => (
          <div key={c.label} className="min-w-0">
            <div className="text-[11px] font-medium text-[#64748b] uppercase tracking-wide">
              {c.label}
            </div>
            <div className="text-sm font-semibold text-[#0b2b43] mt-1 break-words">{c.value}</div>
          </div>
        ))}
      </div>
      <p className="text-xs text-[#64748b] mt-4 border-t border-[#e2e8f0] pt-3 leading-relaxed">
        Gaps in route, household, or documents roll up to <strong className="text-[#475569]">Readiness &amp; actions</strong>{' '}
        (step 2) and map to concrete rows in the <strong className="text-[#475569]">relocation plan</strong> (step 3) with
        owner and due dates.
      </p>
    </Card>
  );
};
