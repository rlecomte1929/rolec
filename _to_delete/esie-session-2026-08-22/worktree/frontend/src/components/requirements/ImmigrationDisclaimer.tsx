import React from 'react';
import { Alert } from '../antigravity';
import {
  IMMIGRATION_DISCLAIMER_TITLE,
  IMMIGRATION_DISCLAIMER_BODY,
} from '../../features/immigration/immigrationDisclaimerContent';

/**
 * AIQ-1349 — shared non-liability disclaimer rendered wherever immigration
 * requirements / roadmap guidance appears. ReloPass recommends, is not a legal
 * adviser, and accepts no liability; the user must validate with the authority
 * or a licensed immigration professional.
 */
export const ImmigrationDisclaimer: React.FC<{ className?: string }> = ({ className = '' }) => (
  <Alert variant="warning" title={IMMIGRATION_DISCLAIMER_TITLE} className={className}>
    {IMMIGRATION_DISCLAIMER_BODY}
  </Alert>
);
