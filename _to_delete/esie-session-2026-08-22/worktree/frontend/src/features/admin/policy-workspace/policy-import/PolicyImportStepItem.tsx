import React from 'react';

type Props = {
  icon: React.ReactNode;
  title: string;
  description: string;
};

export const PolicyImportStepItem: React.FC<Props> = ({ icon, title, description }) => (
  <div className="flex gap-3 min-w-0">
    <div
      className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#f1f5f9] text-[#64748b]"
      aria-hidden
    >
      {icon}
    </div>
    <div className="min-w-0 space-y-0.5">
      <p className="text-xs font-medium text-[#64748b]">{title}</p>
      <p className="text-xs text-[#94a3b8] leading-snug">{description}</p>
    </div>
  </div>
);
