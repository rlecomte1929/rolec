import React, { useState } from 'react';
import { Button } from '../antigravity/Button';
import { createResearchRequest } from '../../api/researchRequests';

/**
 * AIQ-1349 P2 — "Request research" CTA shown on an uncovered immigration corridor.
 * One click files a tracked research request (company resolved server-side); the
 * platform researches + curates it, then publishes verified guidance. This is the
 * customer-driven entry point for the on-demand research moat.
 */
export const RequestResearchButton: React.FC<{
  destCountry?: string | null;
  originCountry?: string | null;
  corridorLabel?: string | null;
}> = ({ destCountry, originCountry, corridorLabel }) => {
  const [state, setState] = useState<'idle' | 'sending' | 'done' | 'error'>('idle');

  if (!destCountry) return null;

  const onClick = async () => {
    setState('sending');
    try {
      await createResearchRequest({
        dest_country: destCountry,
        origin_country: originCountry || undefined,
        scope: corridorLabel ? `Requested via case for ${corridorLabel}` : undefined,
      });
      setState('done');
    } catch {
      setState('error');
    }
  };

  if (state === 'done') {
    return (
      <p className="text-xs font-medium text-[#1f8e8b]" role="status">
        ✓ Research requested — ReloPass will research and verify this corridor, then publish guidance here.
      </p>
    );
  }

  return (
    <div className="flex flex-col items-center gap-1">
      <Button size="sm" onClick={() => void onClick()} disabled={state === 'sending'}>
        {state === 'sending' ? 'Requesting…' : 'Request research for this corridor'}
      </Button>
      {state === 'error' && (
        <span className="text-xs text-[#b91c1c]">Couldn’t send the request — please try again.</span>
      )}
    </div>
  );
};
