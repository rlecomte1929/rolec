import React from 'react';
import { Card } from '../../../components/antigravity';
import type { WorkspaceAggregate } from './policyWorkspaceModel';

type Props = {
  aggregate: WorkspaceAggregate | null;
  sourceMode: string;
  unpublishedLabel: string;
};

function Tile({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <Card padding="md" className="border-[#e2e8f0] bg-[#fafbfc]">
      <div className="text-xs font-medium uppercase tracking-wide text-[#64748b]">{label}</div>
      <div className="text-2xl font-semibold text-[#0b2b43] mt-1">{value}</div>
      {sub ? <div className="text-xs text-[#94a3b8] mt-0.5">{sub}</div> : null}
    </Card>
  );
}

export const PolicyWorkspaceSummaryTiles: React.FC<Props> = ({ aggregate, sourceMode, unpublishedLabel }) => {
  const a = aggregate;
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
      <Tile label="Included" value={a?.included ?? '—'} />
      <Tile label="Excluded" value={a?.excluded ?? '—'} />
      <Tile label="Conditional" value={a?.conditional ?? '—'} />
      <Tile label="Categories configured" value={a?.categoriesConfigured ?? '—'} />
      <Tile label="Draft changes" value={unpublishedLabel} />
      <Tile label="Source mode" value={sourceMode} />
    </div>
  );
};
