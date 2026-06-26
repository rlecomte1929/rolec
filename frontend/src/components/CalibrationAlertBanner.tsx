/**
 * CalibrationAlertBanner — P5-7: Policy gap detection & calibration alerts
 *
 * Fetches undismissed policy_calibration_alerts for the HR user's organisation
 * and renders a dismissable amber banner at the top of the HR dashboard.
 *
 * Each alert can be dismissed individually. When all are dismissed the banner
 * disappears.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { logger } from '../lib/logger';
import { hrAPI, type CalibrationAlert } from '../api/client';
import { Button } from './antigravity/Button';

// ---------------------------------------------------------------------------
// Icons (inline SVG — no extra dep)
// ---------------------------------------------------------------------------
const WarningIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg
    className={className}
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 20 20"
    fill="currentColor"
    aria-hidden="true"
  >
    <path
      fillRule="evenodd"
      d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z"
      clipRule="evenodd"
    />
  </svg>
);

const XMarkIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg
    className={className}
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 20 20"
    fill="currentColor"
    aria-hidden="true"
  >
    <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
  </svg>
);

// ---------------------------------------------------------------------------
// Single alert row
// ---------------------------------------------------------------------------
interface AlertRowProps {
  alert: CalibrationAlert;
  onDismiss: (id: string) => void;
  dismissingId: string | null;
}

const AlertRow: React.FC<AlertRowProps> = ({ alert, onDismiss, dismissingId }) => {
  const pct = Math.round(alert.avg_excess_pct * 100);
  const tierLabel = alert.tier_name ? ` · ${alert.tier_name}` : '';
  const isDismissing = dismissingId === alert.id;

  return (
    <div className="flex items-start justify-between gap-3 py-2 border-b border-amber-200 last:border-0">
      <div className="flex-1 min-w-0">
        <span className="font-medium text-amber-900 text-sm">
          {alert.category}{tierLabel}
        </span>
        <span className="text-amber-800 text-sm ml-2">
          — {alert.exception_count} exception{alert.exception_count !== 1 ? 's' : ''} in 30 days,{' '}
          avg {pct}% over cap. Consider revising this benefit's policy cap.
        </span>
      </div>
      <Button unstyled
        type="button"
        aria-label={`Dismiss alert for ${alert.category}`}
        disabled={isDismissing}
        onClick={() => onDismiss(alert.id)}
        className="flex-shrink-0 p-1 rounded hover:bg-amber-200 transition-colors disabled:opacity-40"
      >
        <XMarkIcon className="w-4 h-4 text-amber-700" />
      </Button>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main banner
// ---------------------------------------------------------------------------
export const CalibrationAlertBanner: React.FC = () => {
  const [alerts, setAlerts] = useState<CalibrationAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [dismissingId, setDismissingId] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  const fetchAlerts = useCallback(async () => {
    try {
      const data = await hrAPI.listCalibrationAlerts();
      setAlerts(data ?? []);
    } catch (err) {
      // Silently swallow — the banner is non-critical and shouldn't break the page
      logger.warn('CalibrationAlertBanner: failed to fetch alerts', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchAlerts();
  }, [fetchAlerts]);

  const handleDismiss = useCallback(async (alertId: string) => {
    setDismissingId(alertId);
    try {
      await hrAPI.dismissCalibrationAlert(alertId);
      setAlerts((prev) => prev.filter((a) => a.id !== alertId));
    } catch (err) {
      logger.error('CalibrationAlertBanner: dismiss failed', err);
    } finally {
      setDismissingId(null);
    }
  }, []);

  // Nothing to show while loading or when there are no undismissed alerts
  if (loading || alerts.length === 0) return null;

  return (
    <div
      role="region"
      aria-label="Policy calibration alerts"
      className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 shadow-sm"
    >
      {/* Header row */}
      <div className="flex items-center justify-between gap-2 mb-1">
        <div className="flex items-center gap-2">
          <WarningIcon className="w-5 h-5 text-amber-600 flex-shrink-0" />
          <span className="font-semibold text-amber-900 text-sm">
            Policy calibration {alerts.length === 1 ? 'alert' : `alerts (${alerts.length})`}
          </span>
          <span className="text-amber-700 text-sm hidden sm:inline">
            — Benefit caps that may need adjustment based on recent exception patterns
          </span>
        </div>
        <Button unstyled
          type="button"
          aria-expanded={!collapsed}
          aria-label={collapsed ? 'Expand calibration alerts' : 'Collapse calibration alerts'}
          onClick={() => setCollapsed((c) => !c)}
          className="text-xs text-amber-700 underline hover:text-amber-900 flex-shrink-0"
        >
          {collapsed ? 'Show' : 'Hide'}
        </Button>
      </div>

      {/* Alert rows */}
      {!collapsed && (
        <div className="mt-2">
          {alerts.map((alert) => (
            <AlertRow
              key={alert.id}
              alert={alert}
              onDismiss={handleDismiss}
              dismissingId={dismissingId}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default CalibrationAlertBanner;
