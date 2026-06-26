/**
 * ProcessingTimeCard — fetches a case's processing-time estimate (P2-04) and
 * renders it as a labelled card. Renders nothing when there's no estimate (the
 * feature flag is off, the case is unknown, or no source is available), so it's
 * safe to drop onto any case page unconditionally.
 */
import React, { useEffect, useState } from 'react';
import { getProcessingTime } from '../../api/processingTime';
import { Card } from '../../components/antigravity';
import {
  ProcessingTimeBadge,
  type ProcessingTimeEstimate,
} from '../../components/ProcessingTimeBadge';

interface ProcessingTimeCardProps {
  caseId: string;
}

export const ProcessingTimeCard: React.FC<ProcessingTimeCardProps> = ({ caseId }) => {
  const [estimate, setEstimate] = useState<ProcessingTimeEstimate | null>(null);

  useEffect(() => {
    let active = true;
    getProcessingTime(caseId).then((result) => {
      if (active) setEstimate(result);
    });
    return () => {
      active = false;
    };
  }, [caseId]);

  if (!estimate) {
    return null;
  }

  return (
    <Card padding="lg" className="mt-6">
      <p className="text-sm font-semibold text-[#0b2b43] mb-2">Processing time</p>
      <ProcessingTimeBadge estimate={estimate} />
    </Card>
  );
};

export default ProcessingTimeCard;
