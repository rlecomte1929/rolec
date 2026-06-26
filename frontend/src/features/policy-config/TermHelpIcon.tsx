import React from 'react';
import { HelpCircle } from 'lucide-react';
import { Button } from '../../components/antigravity/Button';
import type { CompensationGlossaryId } from './compensationGlossary';
import { getCompensationGlossaryEntry } from './compensationGlossary';

type Props = {
  glossaryId: CompensationGlossaryId;
  className?: string;
};

/**
 * Small help control: native tooltip + screen-reader text. Keeps copy operational, not legal advice.
 */
export const TermHelpIcon: React.FC<Props> = ({ glossaryId, className }) => {
  const entry = getCompensationGlossaryEntry(glossaryId);
  const tip = `${entry.term}: ${entry.definition}`;
  return (
    <span
      className={`inline-flex items-center align-middle ${className ?? ''}`}
      title={tip}
    >
      <Button unstyled
        type="button"
        className="inline-flex rounded-full p-0.5 text-[#94a3b8] hover:text-[#0b2b43] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43] focus-visible:ring-offset-1"
        aria-label={`About ${entry.term}`}
      >
        <HelpCircle className="w-4 h-4" aria-hidden />
      </Button>
      <span className="sr-only">{tip}</span>
    </span>
  );
};
