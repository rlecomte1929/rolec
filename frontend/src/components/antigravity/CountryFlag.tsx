import React from 'react';
import { countryName } from '../../features/policy-config/countryList';
import { countryFlagCode } from '../../lib/countryFlagCode';

interface CountryFlagProps {
  /** Country name, demonym, or ISO alpha-2. Doubles as the accessible label. */
  country: string;
  /** Override the resolved label (e.g. show "Germany" while the flag came from "German"). */
  label?: string;
  /** Render only the flag glyph (still expose the name via aria-label). */
  hideLabel?: boolean;
  className?: string;
}

/** Flag glyph (decorative) + the country name as the accessible label. */
export const CountryFlag: React.FC<CountryFlagProps> = ({
  country,
  label,
  hideLabel = false,
  className = '',
}) => {
  const code = countryFlagCode(country);
  const display = label ?? (code ? countryName(country) : country);
  return (
    <span
      className={`inline-flex items-center gap-2 min-w-0 ${className}`}
      aria-label={hideLabel ? display : undefined}
    >
      {code && <span className={`fi fi-${code} rounded-sm shrink-0`} aria-hidden="true" />}
      {!hideLabel && <span className="truncate">{display}</span>}
    </span>
  );
};
