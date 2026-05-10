import React from 'react';
import { Badge } from '../../components/antigravity';
import type { PolicyCapCompareUiStatus } from './policyCapCompareTypes';

const LABELS: Record<PolicyCapCompareUiStatus, string> = {
  within: 'Within policy',
  exceeds: 'Exceeds policy',
  no_cap: 'No policy cap available',
};

export const PolicyCapComparisonBadge: React.FC<{ status: PolicyCapCompareUiStatus }> = ({ status }) => {
  const variant =
    status === 'within' ? 'success' : status === 'exceeds' ? 'error' : 'neutral';
  return <Badge variant={variant}>{LABELS[status]}</Badge>;
};
