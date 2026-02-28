import React from 'react';

interface KPICardProps {
  title: string;
  value: number | string;
  subtitle?: string;
}

export const KPICard: React.FC<KPICardProps> = ({ title, value, subtitle }) => (
  <div className="rounded-xl border border-[#e2e8f0] bg-white p-4 shadow-sm">
    <div className="text-xs uppercase tracking-wide text-[#6b7280]">{title}</div>
    <div className="mt-1 text-2xl font-semibold text-[#0b2b43]">{value}</div>
    {subtitle && <div className="mt-0.5 text-xs text-[#94a3b8]">{subtitle}</div>}
  </div>
);
