/**
 * The one badge vocabulary for an exception request's status.
 *
 * Shared by every surface that shows an employee where their ask stands — the services
 * estimate page and the Benefit-comparison table. Extracted from PackageSummary so the two
 * cannot drift into describing the same row differently: an employee who files from one page
 * and checks the other must read the same words.
 */
import type { ExceptionRequest } from '../../api/exceptions';

export const EXCEPTION_BADGE: Record<
  ExceptionRequest['status'],
  { label: string; className: string }
> = {
  pending: {
    label: 'Exception pending HR review',
    className: 'bg-[#fef9c3] text-[#854d0e] border-[#fde68a]',
  },
  approved: {
    label: 'Exception approved by HR',
    className: 'bg-[#dcfce7] text-[#166534] border-[#bbf7d0]',
  },
  rejected: {
    label: 'Exception rejected',
    className: 'bg-[#fee2e2] text-[#991b1b] border-[#fecaca]',
  },
};
