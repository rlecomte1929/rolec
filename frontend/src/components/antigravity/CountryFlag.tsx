import React from 'react';
import { countryFlagCode } from '../../lib/countryFlagCode';

interface CountryFlagProps {
  /** Country name or demonym, e.g. "Germany" or "German". Doubles as the accessible label. */
  country: string;
  /** Override the resolved label (e.g. show "Germany" while the flag came from "German"). */
  label?: string;
  className?: string;
}

/** Flag glyph (decorative) + the country name as the accessible label. */
export const CountryFlag: React.FC<CountryFlagProps> = ({ country, label, className = '' }) => {
  const code = countryFlagCode(country);
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      {code && <span className={`fi fi-${code} rounded-sm`} aria-hidden="true" />}
      <span>{label ?? country}</span>
    </span>
  );
};
