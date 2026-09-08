import React from 'react';
import { countryFlagCode } from '../../lib/countryFlagCode';

interface CountryFlagProps {
  /** Country name, demonym, or ISO-2. Doubles as the accessible label unless `label` is set. */
  country: string;
  /** Override the resolved label (e.g. show "Germany" while the flag came from "DE"). */
  label?: string;
  className?: string;
  /** Flag glyph size. `lg` is for dense admin tables where the default sprite is easy to miss. */
  size?: 'sm' | 'md' | 'lg';
}

const FLAG_SIZE: Record<NonNullable<CountryFlagProps['size']>, string> = {
  sm: '!w-[1.15rem] !h-[0.85rem]',
  md: '!w-[1.5rem] !h-[1.125rem]',
  lg: '!w-[2.25rem] !h-[1.7rem]',
};

/** Flag glyph (decorative) + the country name as the accessible label. */
export const CountryFlag: React.FC<CountryFlagProps> = ({
  country,
  label,
  className = '',
  size = 'sm',
}) => {
  const code = countryFlagCode(country) ?? countryFlagCode(label);
  return (
    <span className={`inline-flex items-center gap-2.5 min-w-0 ${className}`}>
      {code && (
        <span
          className={`fi fi-${code} shrink-0 rounded-sm shadow-sm ring-1 ring-black/10 ${FLAG_SIZE[size]}`}
          aria-hidden="true"
        />
      )}
      <span className="truncate">{label ?? country}</span>
    </span>
  );
};
