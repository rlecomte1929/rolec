import React from 'react';
import { RefreshCw } from 'lucide-react';
import { Button } from './antigravity';

interface RefreshButtonProps {
  /** Manual re-fetch handler. */
  onClick: () => void;
  /** When true the icon spins and the control is disabled (re-fetch in flight). */
  loading?: boolean;
  /**
   * Optional visible text next to the icon. Omit for an icon-only toolbar
   * control; pass a short label (e.g. "Refresh assignment") in recovery/empty
   * states where the action needs to stay discoverable. An `aria-label` is
   * always set regardless, so the control is accessible either way.
   */
  label?: string;
  disabled?: boolean;
  className?: string;
}

/**
 * Standard, subordinate manual-refresh control (UIAUDIT / AIQ-918).
 *
 * Replaces the prominent primary/outline "Refresh" buttons that several pages
 * used as their main data-load action (which implied data was permanently
 * stale). This renders a small, low-emphasis `ghost` control with a refresh
 * icon — keeping manual refresh available but demoting its visual prominence so
 * it reads as a toolbar affordance, not the page's primary call to action.
 */
export const RefreshButton: React.FC<RefreshButtonProps> = ({
  onClick,
  loading = false,
  label,
  disabled = false,
  className = '',
}) => {
  const accessibleLabel = loading ? 'Refreshing' : label ?? 'Refresh';
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={onClick}
      disabled={disabled || loading}
      aria-label={accessibleLabel}
      title={accessibleLabel}
      className={`inline-flex items-center gap-1.5 ${className}`}
    >
      <RefreshCw size={16} className={loading ? 'animate-spin' : ''} aria-hidden="true" />
      {label ? <span>{loading ? 'Refreshing…' : label}</span> : null}
    </Button>
  );
};

RefreshButton.displayName = 'RefreshButton';
