/**
 * Floating trigger button for the Setup & Help Assistant.
 *
 * Re-skin of PolicyAssistantFab: same props shape, same fixed bottom-right
 * position, same aria-expanded / hideOnPanelOpenLg behavior. Only the
 * icon + label differ.
 *
 * Mount site: AppShell (alongside FeedbackWidget), rendered only when
 * the authenticated role is HR.
 */
import React from 'react';
import { HelpCircle } from 'lucide-react';
import { Button } from '../../components/antigravity/Button';

export type SetupAssistantFabProps = {
  onClick: () => void;
  label?: string;
  isPanelOpen?: boolean;
  hideOnPanelOpenLg?: boolean;
};

export const SetupAssistantFab: React.FC<SetupAssistantFabProps> = ({
  onClick,
  label = 'Open setup assistant',
  isPanelOpen = false,
  hideOnPanelOpenLg = true,
}) => {
  const hideClass = isPanelOpen && hideOnPanelOpenLg ? 'lg:hidden' : '';

  return (
    <Button unstyled
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-expanded={isPanelOpen}
      title={label}
      // bottom-36: sits above the FeedbackWidget (bottom-6) and the
      // PolicyAssistantFab (bottom-24) — 16px clearance between each.
      className={`fixed bottom-36 right-6 z-40 h-14 w-14 rounded-full bg-[#0b2b43] text-white shadow-lg hover:bg-[#0f3a5a] focus:outline-none focus:ring-4 focus:ring-[#0b2b43]/30 flex items-center justify-center ${hideClass}`}
      data-testid="setup-assistant-fab"
    >
      <HelpCircle className="h-6 w-6" aria-hidden />
    </Button>
  );
};
