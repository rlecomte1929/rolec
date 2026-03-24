import React from 'react';
import { Card } from '../../components/antigravity';
import { HelpCircle } from 'lucide-react';
import { COMPENSATION_GLOSSARY } from './compensationGlossary';

type Props = {
  /** HR/Admin matrix vs employee read-only page */
  variant?: 'workspace' | 'employee';
};

export const PolicyGlossarySection: React.FC<Props> = ({ variant = 'workspace' }) => {
  const isEmployee = variant === 'employee';
  return (
    <Card padding="lg" className="border border-dashed border-[#cbd5e1] bg-[#f8fafc]">
      <details className="group">
        <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-semibold text-[#0b2b43] select-none [&::-webkit-details-marker]:hidden">
          <HelpCircle className="w-4 h-4 text-[#64748b] shrink-0" aria-hidden />
          <span>Key terms (glossary)</span>
          <span className="text-xs font-normal text-[#64748b] ml-1">
            {isEmployee ? 'Plain-language meanings' : 'Short definitions for editors'}
          </span>
        </summary>
        <p className="text-xs text-[#64748b] mt-3 mb-4 max-w-3xl">
          {isEmployee
            ? 'These descriptions explain words that often appear in mobility and allowance policies. They are for orientation only—not tax, legal, or payroll advice. Your employer’s formal documents and HR team stay authoritative.'
            : 'These descriptions explain common mobility-compensation language for day-to-day use. They are not tax or legal advice; your programme documents and payroll teams remain authoritative.'}
        </p>
        <dl className="space-y-3 text-sm border-t border-[#e2e8f0] pt-4">
          {COMPENSATION_GLOSSARY.map((e) => (
            <div key={e.id} className="grid grid-cols-1 md:grid-cols-[minmax(0,220px)_1fr] gap-1 md:gap-4">
              <dt className="font-medium text-[#0b2b43]">{e.term}</dt>
              <dd className="text-[#475569] leading-relaxed">{e.definition}</dd>
            </div>
          ))}
        </dl>
      </details>
    </Card>
  );
};
