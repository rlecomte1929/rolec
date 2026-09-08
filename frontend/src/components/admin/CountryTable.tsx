import React from 'react';
import { Badge, CountryFlag } from '../antigravity';
import type { CountryListDTO } from '../../types';
import { getCountryName } from '../../utils/countries';

interface CountryTableProps {
  data: CountryListDTO;
  onSelect: (countryCode: string) => void;
}

function formatConfidence(score?: number | null): string {
  if (score == null || Number.isNaN(score)) return '—';
  if (score <= 1) return `${Math.round(score * 100)}%`;
  return String(score);
}

function formatDate(iso?: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

export const CountryTable: React.FC<CountryTableProps> = ({ data, onSelect }) => {
  if (data.countries.length === 0) {
    return (
      <div className="border border-[#e2e8f0] rounded-xl px-4 py-8 text-sm text-slate-500">
        No countries in the requirements catalog yet.
      </div>
    );
  }

  return (
    <div className="border border-[#e2e8f0] rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[52rem] border-collapse text-left">
          <thead>
            <tr className="bg-[#f8fafc] text-[11px] uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-4 py-3 font-medium">Country</th>
              <th scope="col" className="px-4 py-3 font-medium whitespace-nowrap">Published</th>
              <th scope="col" className="px-4 py-3 font-medium whitespace-nowrap">Pending</th>
              <th scope="col" className="px-4 py-3 font-medium whitespace-nowrap">Last updated</th>
              <th scope="col" className="px-4 py-3 font-medium whitespace-nowrap">Confidence</th>
              <th scope="col" className="px-4 py-3 font-medium">Top sources</th>
            </tr>
          </thead>
          <tbody>
            {data.countries.map((country) => {
              const name = country.countryName || getCountryName(country.countryCode);
              const pending = country.pendingCount ?? 0;
              const published = country.publishedCount ?? 0;
              return (
                <tr
                  key={country.countryCode}
                  className="border-t border-[#e2e8f0] cursor-pointer hover:bg-[#f8fafc] focus-within:bg-[#e6f2f4]"
                  onClick={() => onSelect(country.countryCode)}
                >
                  <td className="px-4 py-4 align-middle">
                    <div className="flex items-center gap-3 min-w-[18rem]">
                      <CountryFlag
                        country={country.isoCode || name}
                        label={name}
                        size="lg"
                        className="text-base font-semibold text-[#0b2b43]"
                      />
                      {country.isoCode && (
                        <span className="font-mono text-xs text-slate-500">{country.isoCode}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 align-top whitespace-nowrap text-sm text-[#0b2b43]">
                    {published}
                  </td>
                  <td className="px-4 py-3 align-top whitespace-nowrap">
                    {pending > 0 ? (
                      <Badge variant="warning" size="sm">
                        {pending} pending
                      </Badge>
                    ) : (
                      <span className="text-sm text-slate-500">0</span>
                    )}
                  </td>
                  <td className="px-4 py-3 align-top whitespace-nowrap text-sm text-[#0b2b43]">
                    {formatDate(country.lastUpdatedAt)}
                  </td>
                  <td className="px-4 py-3 align-top whitespace-nowrap text-sm text-[#0b2b43]">
                    {formatConfidence(country.confidenceScore)}
                  </td>
                  <td className="px-4 py-3 align-top text-sm text-slate-500 break-words max-w-[16rem]">
                    {country.topDomains.length > 0 ? country.topDomains.join(', ') : '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
