/**
 * BL-Compliance.4 (AIQ-746) — HR command-center compliance alerts panel.
 *
 * Shows the company's open compliance alerts grouped by severity, with a
 * per-alert Resolve CTA and a "Re-check compliance" trigger that runs the
 * evaluator for the company's open cases.
 */
import React, { useCallback, useEffect, useState } from 'react';

import { Badge, Button, Card } from '../../components/antigravity';
import {
  AlertSeverity,
  ComplianceAlert,
  evaluateCompliance,
  listComplianceAlerts,
  resolveComplianceAlert,
} from '../../api/compliance';

const SEVERITY_ORDER: AlertSeverity[] = ['critical', 'high', 'medium', 'low'];

const SEVERITY_VARIANT: Record<AlertSeverity, 'error' | 'warning' | 'info' | 'neutral'> = {
  critical: 'error',
  high: 'warning',
  medium: 'info',
  low: 'neutral',
};

export const ComplianceAlertsPanel: React.FC = () => {
  const [alerts, setAlerts] = useState<ComplianceAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listComplianceAlerts();
      setAlerts(res.alerts);
    } catch {
      setError('Could not load compliance alerts.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const recheck = async () => {
    setBusy(true);
    setError(null);
    try {
      await evaluateCompliance();
      await load();
    } catch {
      setError('Re-check failed.');
    } finally {
      setBusy(false);
    }
  };

  const resolve = async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      await resolveComplianceAlert(id, 'resolved');
      setAlerts((prev) => prev.filter((a) => a.id !== id));
    } catch {
      setError('Could not resolve alert.');
    } finally {
      setBusy(false);
    }
  };

  const groups = SEVERITY_ORDER.map((sev) => ({
    sev,
    items: alerts.filter((a) => a.severity === sev),
  })).filter((g) => g.items.length > 0);

  return (
    <Card padding="lg">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-[#0b2b43]">Compliance alerts</h2>
          {!loading && (
            <Badge variant={alerts.length ? 'error' : 'success'} size="sm">
              {alerts.length} open
            </Badge>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={recheck} disabled={busy}>
          {busy ? 'Checking…' : 'Re-check compliance'}
        </Button>
      </div>

      {error && <p className="text-sm text-[#b91c1c] mb-3">{error}</p>}

      {loading ? (
        <div className="space-y-2 py-4">
          {[0, 1].map((i) => (
            <div key={i} className="h-12 rounded bg-[#e2e8f0] animate-pulse" />
          ))}
        </div>
      ) : alerts.length === 0 ? (
        <div className="py-8 text-center">
          <p className="text-sm font-medium text-[#0b2b43] mb-1">No open compliance alerts</p>
          <p className="text-sm text-[#6b7280]">
            Run a re-check to evaluate your cases against the active rules.
          </p>
        </div>
      ) : (
        <div className="space-y-5">
          {groups.map(({ sev, items }) => (
            <div key={sev}>
              <div className="flex items-center gap-2 mb-2">
                <Badge variant={SEVERITY_VARIANT[sev]} size="sm">
                  {sev.toUpperCase()}
                </Badge>
                <span className="text-xs text-[#6b7280]">{items.length}</span>
              </div>
              <ul className="space-y-2">
                {items.map((a) => (
                  <li
                    key={a.id}
                    className="flex items-start justify-between gap-3 rounded-lg border border-[#e2e8f0] p-3"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-[#0b2b43]">
                        {a.description || a.category}
                      </p>
                      <p className="text-xs text-[#6b7280] mt-0.5">
                        {a.category}
                        {a.home_country && a.host_country
                          ? ` · ${a.home_country} → ${a.host_country}`
                          : ''}
                        {a.fired_at ? ` · ${new Date(a.fired_at).toLocaleDateString()}` : ''}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => resolve(a.id)}
                      disabled={busy}
                    >
                      Resolve
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
};

export default ComplianceAlertsPanel;
