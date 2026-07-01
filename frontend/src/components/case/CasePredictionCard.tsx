import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Badge } from '../antigravity';
import { hrAPI } from '../../api/client';

// [Parker-A] Predicted time-to-completion for an HR case.
//
// The backend endpoint (GET /api/cases/:id/predicted-duration) is dark-shipped:
// it 404s when the PREDICTIONS_ENABLED canary is off, when no model has been
// trained into public.ml_models, or when the caller can't access the case. In
// every one of those cases we render NOTHING so the surrounding stat grid is
// unaffected — the card only appears once a prediction is genuinely available.
export const CasePredictionCard: React.FC<{ caseId: string }> = ({ caseId }) => {
  const query = useQuery({
    queryKey: ['hr', 'case-predicted-duration', caseId],
    enabled: !!caseId,
    retry: false, // a 404 is an expected "no prediction" state, not a transient error
    queryFn: () => hrAPI.getCasePredictedDuration(caseId),
  });

  const data = query.data;
  if (!data) return null;

  const median = Math.round(data.median_days);
  const low = Math.round(data.p20_days);
  const high = Math.round(data.p80_days);
  const n = data.n_training_cases;

  return (
    <Card padding="lg">
      <div className="text-sm font-semibold text-[#0b2b43] mb-3">Predicted time to completion</div>
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="text-3xl font-semibold text-[#0b2b43]">~{median} days</span>
        <Badge variant="info">{low}–{high} day range</Badge>
      </div>
      <div className="mt-2 text-sm text-[#6b7280]">
        Estimated remaining, based on {n.toLocaleString()} comparable case{n === 1 ? '' : 's'}.
      </div>
    </Card>
  );
};
