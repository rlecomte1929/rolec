/**
 * Pure trigger button for the Policy Assistant.
 *
 * Sprint 2 reduces this from "FAB + modal sheet" to "FAB only" — the
 * actual panel chrome lives in PolicyAssistantDockedShell now, and the
 * page lifts open state to share between the trigger and the shell.
 *
 * Why FAB-as-trigger only: the previous component owned its own modal
 * overlay AND tried to render a sheet around the assistant. After
 * Sprint 2 the docked shell pushes content (no overlay, no dimming),
 * so the FAB's only job is to flip the page-level open flag. Less
 * duplicated focus-management code, no dead modal rendering, no risk
 * of two competing dismissal flows.
 *
 * Position is fixed bottom-right so the trigger stays reachable across
 * scroll. The page hides it via a `hideWhenOpen` prop (or by not
 * rendering it) when the docked shell is open on lg+ — see Sprint 2's
 * Task 2.3 for the recommended pattern.
 */
import React from 'react';
import { Button } from '../../components/antigravity/Button';
import { useFeedbackOpen } from '../../components/chromeDock';
export type PolicyAssistantFabProps = {
  /** Click handler — should toggle the docked shell's open state on
   *  the parent page. */
  onClick: () => void;
  /**
   * Accessible label for the trigger. Mount sites pass role-aware
   * wording: "Ask about your policy" / "Ask about this policy".
   */
  label?: string;
  /** True when the docked panel is open. Drives aria-expanded and
   *  optionally hides the FAB on lg+ to avoid overlap with the panel. */
  isPanelOpen?: boolean;
  /** When true (default), the FAB is hidden on lg+ while the panel is
   *  open — the panel's own close button is the dismissal affordance.
   *  Set to false if the page wants the FAB always visible. */
  hideOnPanelOpenLg?: boolean;
};

export const PolicyAssistantFab: React.FC<PolicyAssistantFabProps> = ({
  onClick,
  label = 'Open policy assistant',
  isPanelOpen = false,
  hideOnPanelOpenLg = true,
}) => {
  // On lg+ the docked panel takes the right column, so showing a FAB
  // in the same corner is visually awkward and would also overlap the
  // panel scroll area. Default behavior: hide on lg+ when open. On
  // mobile (<lg) we always keep the FAB visible because the bottom-
  // sheet covers the page; the FAB sits behind it but reappears on close.
  const hideClass = isPanelOpen && hideOnPanelOpenLg ? 'lg:hidden' : '';
  const feedbackOpen = useFeedbackOpen();
  if (feedbackOpen) return null;

  return (
    <Button unstyled
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-expanded={isPanelOpen}
      title={label}
      // Stacks above FeedbackWidget (bottom-6 right-6). Same right-6
      // column for visual alignment; bottom-24 leaves ~16px clearance
      // above the Feedback chip.
      className={`fixed bottom-24 right-6 z-40 h-14 w-14 rounded-full bg-[#0b2b43] text-white shadow-lg hover:bg-[#0f3a5a] focus:outline-none focus:ring-4 focus:ring-[#0b2b43]/30 flex items-center justify-center text-2xl ${hideClass}`}
      data-testid="policy-assistant-fab"
    >
      <span aria-hidden>💬</span>
    </Button>
  );
};
