import React from 'react';
import type { CountryListDTO } from '../../types';

interface CountryTableProps {
  data: CountryListDTO;
  onSelect: (countryCode: string) => void;
}

export const CountryTable: React.FC<CountryTableProps> = ({ data, onSelect }) => {
  return (
    <div className="border border-[#e2e8f0] rounded-xl overflow-hidden">
      <div className="grid grid-cols-[1.2fr,1fr,1fr,1fr,1.2fr] gap-4 bg-[#f8fafc] px-4 py-3 text-[11px] uppercase tracking-wide text-[#6b7280]">
        <div>Country</div>
        <div>Last updated</div>
        <div>Requirements</div>
        <div>Confidence</div>
        <div>Top domains</div>
      </div>
      {data.countries.map((country) => (
        <button
          key={country.countryCode}
          onClick={() => onSelect(country.countryCode)}
          className="grid grid-cols-[1.2fr,1fr,1fr,1fr,1.2fr] gap-4 px-4 py-4 border-t border-[#e2e8f0] text-left hover:bg-[#f8fafc]"
        >
          <div className="text-sm font-semibold text-[#0b2b43]">{country.countryCode}</div>
          <div className="text-sm text-[#0b2b43]">
            {country.lastUpdatedAt ? new Date(country.lastUpdatedAt).toLocaleDateString('en-US') : '—'}
          </div>
          <div className="text-sm text-[#0b2b43]">{country.requirementsCount}</div>
          <div className="text-sm text-[#0b2b43]">{country.confidenceScore ?? '—'}</div>
          <div className="text-xs text-[#6b7280]">{country.topDomains.join(', ')}</div>
        </button>
      ))}
    </div>
  );
};
