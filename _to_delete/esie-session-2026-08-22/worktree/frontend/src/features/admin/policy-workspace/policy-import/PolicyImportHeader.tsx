import React from 'react';
import { ComingSoonBadge } from './ComingSoonBadge';

const SUBTITLE =
  'Soon you will be able to upload your internal mobility policy and let ReloPass prefill a structured draft.';

export const PolicyImportHeader: React.FC = () => (
  <div className="space-y-1">
    <div className="flex flex-wrap items-start justify-between gap-3 gap-y-2">
      <h2 id="policy-import-heading" className="text-sm font-semibold text-[#475569] pr-2">
        Policy import from internal documents
      </h2>
      <ComingSoonBadge />
    </div>
    <p className="text-xs text-[#94a3b8] max-w-2xl leading-snug">{SUBTITLE}</p>
  </div>
);
