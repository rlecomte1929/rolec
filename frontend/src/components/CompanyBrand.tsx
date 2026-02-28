import React from 'react';
import { useCompany } from '../hooks/useCompany';

const MAX_NAME_LENGTH = 24;

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export const CompanyBrand: React.FC = () => {
  const { company, loading } = useCompany();

  if (loading || !company) {
    return null;
  }

  const displayName =
    company.name.length > MAX_NAME_LENGTH
      ? `${company.name.slice(0, MAX_NAME_LENGTH - 1)}…`
      : company.name;
  const initials = getInitials(company.name);

  return (
    <div className="flex items-center gap-2 shrink-0" title={company.name}>
      {company.logo_url ? (
        <img
          src={company.logo_url}
          alt=""
          className="h-7 w-7 rounded-full object-cover border border-[#e2e8f0]"
        />
      ) : (
        <div
          className="h-7 w-7 rounded-full flex items-center justify-center text-xs font-semibold bg-[#eef4f8] text-[#0b2b43] border border-[#e2e8f0]"
          aria-hidden
        >
          {initials}
        </div>
      )}
      <span className="text-sm font-medium text-[#0f172a] truncate max-w-[140px]">
        {displayName}
      </span>
      <span className="text-[#e2e8f0]" aria-hidden>|</span>
    </div>
  );
};
