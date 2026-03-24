import React from 'react';
import { Card } from '../../../../components/antigravity';
import { PolicyImportCTA } from './PolicyImportCTA';
import { PolicyImportNote } from './PolicyImportNote';
import { PolicyImportSteps } from './PolicyImportSteps';

const INTRO =
  'Use your existing policy document as a starting point. ReloPass will extract relevant policy information and place it into the structured policy workspace for review.';

export const PolicyImportCard: React.FC = () => (
  <Card padding="md" className="border-[#eef2f7] bg-[#fafbfc]/80 shadow-none">
    <div className="space-y-5">
      <p className="text-xs text-[#94a3b8] leading-relaxed max-w-3xl">{INTRO}</p>
      <PolicyImportSteps />
      <PolicyImportNote />
      <PolicyImportCTA />
    </div>
  </Card>
);
