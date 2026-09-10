import React from 'react';
// Colocated (not index.css): marketing routes that never mount CountryFlag
// skip the ~flag-icons sprite sheet. Static import so HR/employee chunks
// load the stylesheet with this module — no post-paint dynamic import flash.
import 'flag-icons/css/flag-icons.min.css';
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
      {/* fix: BUG-260909-19B5 — keep a flag slot so missing glyphs do not shift the name */}
      {code ? (
        <span className={`fi fi-${code} inline-block h-[1em] w-[1.33em] shrink-0 rounded-sm`} aria-hidden="true" />
      ) : (
        <span
          className="inline-block h-[1em] w-[1.33em] shrink-0 rounded-sm bg-slate-100"
          aria-hidden="true"
          title="No flag for this country code"
        />
      )}
      {!hideLabel && <span className="truncate">{display}</span>}
    </span>
  );
};
