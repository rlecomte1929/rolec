import React from 'react';

const NOTE =
  'The structured policy workspace remains the operational source of truth. Uploaded documents help prefill a draft, but the final published version is based on reviewed structured data.';

export const PolicyImportNote: React.FC = () => (
  <p className="rounded-md border border-[#eef2f7] bg-[#f8fafc] px-3 py-2 text-[11px] leading-relaxed text-[#94a3b8]">
    {NOTE}
  </p>
);
