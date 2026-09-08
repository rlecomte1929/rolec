import React from 'react';
import { isKnownCountryCode } from '../../features/policy-config/countryList';
import { CountryFlag } from './CountryFlag';

/**
 * Turns a coverage string that still contains ISO codes
 * ("Global | NO, FR | Oslo (NO)") into flags + full names.
 */
export const CountryCoverageText: React.FC<{ summary?: string | null; className?: string }> = ({
  summary,
  className = '',
}) => {
  const raw = (summary ?? '').trim();
  if (!raw || raw === '—' || raw === '-') {
    return <span className={className}>-</span>;
  }
  const parts = raw.split(/(\b[A-Za-z]{2}\b)/);
  return (
    <span className={`inline-flex flex-wrap items-center gap-x-1 gap-y-1 ${className}`}>
      {parts.map((part, i) =>
        isKnownCountryCode(part) ? (
          <CountryFlag key={`${part}-${i}`} country={part} className="text-sm" />
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </span>
  );
};
