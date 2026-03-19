/**
 * Lightweight default view for HR Policy page. Renders immediately on entry.
 * No policy-related data fetching. Primary CTA opens the document workflow.
 */
import React from 'react';
import { Button, Card } from '../../components/antigravity';
import { trackPolicyStage } from '../../perf/pagePerf';

export interface HrPolicyOverviewProps {
  onOpenUpload: () => void;
}

export const HrPolicyOverview: React.FC<HrPolicyOverviewProps> = ({ onOpenUpload }) => {
  const handleOpen = () => {
    trackPolicyStage('upload_cta_click');
    onOpenUpload();
  };
  return (
  <Card padding="lg">
    <h2 className="text-lg font-semibold text-[#0b2b43] mb-2">Policy</h2>
    <p className="text-sm text-[#4b5563] mb-6">
      Upload a PDF or DOCX policy document to classify and extract benefit rules. Published policies enable automatic criteria filling for employee cases.
    </p>
    <Button onClick={handleOpen}>
      Upload company policy
    </Button>
  </Card>
  );
};
