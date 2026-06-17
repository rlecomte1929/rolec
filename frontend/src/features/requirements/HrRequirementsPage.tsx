import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Button, Card, Badge } from '../../components/antigravity';
import { ROUTE_DEFS, buildRoute } from '../../navigation/routes';
import { useSelectedCase } from '../../contexts/SelectedCaseContext';
import { ImmigrationStatusPanel } from '../../components/case/ImmigrationStatusPanel';
import { hrAPI } from '../../api/client';
import { listExceptionRequestsForCase, type ExceptionRequest } from '../../api/exceptions';

/**
 * [NAV-001 / AIQ-1113] HR Requirements tab — a categorized relocation-compliance
 * dashboard for the selected case.
 *
 * Categories are driven by what actually has per-case data. Today that is:
 *   • Immigration — document checklist, risk flags, milestones, intake progress
 *     (composes the existing ImmigrationStatusPanel; no duplication).
 *   • Policy warnings — exception requests where the case falls outside policy.
 *
 * Safety & Security and Housing & Logistics are deliberately NOT shown: there is
 * no structured per-case requirement data for them yet, so rendering empty panels
 * would be fabricated noise. Add a CategorySection here when that data lands.
 *
 * A top summary bar gives HR a one-line health check (document requirements, risk
 * flags, blocking items, open policy exceptions) without scrolling.
 */
const SUBTITLE =
  'Relocation compliance for the selected case, grouped by domain. Sourced from live data — sections appear only where real per-case requirements exist.';

type Health = 'green' | 'amber' | 'red';

function HealthDot({ level }: { level: Health }) {
  const cls = level === 'red' ? 'bg-rose-500' : level === 'amber' ? 'bg-amber-500' : 'bg-emerald-500';
  return <span className={`inline-block h-2 w-2 rounded-full ${cls}`} aria-hidden="true" />;
}

function Stat({ label, value, tone = 'default' }: { label: string; value: number; tone?: 'default' | 'amber' | 'red' }) {
  const color = tone === 'red' ? 'text-rose-700' : tone === 'amber' ? 'text-amber-700' : 'text-slate-900';
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">{label}</div>
      <div className={`mt-1 text-[26px] font-semibold leading-none tabular-nums ${color}`}>{value}</div>
    </div>
  );
}

function CategoryHeader({ icon, title, count, health, sub }: { icon: string; title: string; count: number; health: Health; sub: string }) {
  return (
    <div className="mb-2 flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span aria-hidden="true" className="text-base leading-none">{icon}</span>
          <h2 className="text-[15px] font-semibold text-[#0b2b43]">{title}</h2>
          <Badge variant="neutral" size="sm">{count}</Badge>
          <HealthDot level={health} />
        </div>
        <p className="mt-0.5 text-[12px] text-slate-500">{sub}</p>
      </div>
    </div>
  );
}

export function HrRequirementsPage() {
  const [searchParams] = useSearchParams();
  const { selectedCaseId } = useSelectedCase();
  const navigate = useNavigate();

  // Case-scoped: resolve from ?caseId= (deep links) then the HR selected-case
  // context — the same resolution other HR case-scoped pages use.
  const caseId = searchParams.get('caseId') || selectedCaseId || '';

  // Page-level fetch powers the summary bar + category health. The Immigration
  // panel still does its own detail fetch; this is a light counts-only read.
  const [imm, setImm] = useState<{ covered: boolean; requirements: unknown[]; risk_flags: { severity: string }[] } | null>(null);
  const [exceptions, setExceptions] = useState<ExceptionRequest[]>([]);

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    void Promise.allSettled([
      hrAPI.getImmigrationRequirements(caseId),
      listExceptionRequestsForCase(caseId),
    ]).then(([immRes, excRes]) => {
      if (cancelled) return;
      if (immRes.status === 'fulfilled') {
        const v = immRes.value;
        setImm({ covered: v.covered, requirements: v.requirements ?? [], risk_flags: v.risk_flags ?? [] });
      }
      if (excRes.status === 'fulfilled') setExceptions(excRes.value);
    });
    return () => { cancelled = true; };
  }, [caseId]);

  if (!caseId) {
    return (
      <AppShell section="HR Operations" title="Requirements" subtitle={SUBTITLE}>
        <Card padding="lg">
          <div className="flex flex-col items-center justify-center py-12 text-center max-w-md mx-auto">
            <h2 className="text-lg font-semibold text-[#0b2b43]">No case selected</h2>
            <p className="text-sm text-[#64748b] mt-1.5">
              Open a case from the Mobility command center to see its requirements grouped by
              domain — immigration checklist, risk flags, and policy warnings.
            </p>
            <div className="mt-5">
              <Button onClick={() => navigate(ROUTE_DEFS.hrCommandCenter.path)}>
                Go to Mobility command center →
              </Button>
            </div>
          </div>
        </Card>
      </AppShell>
    );
  }

  const reqCount = imm?.requirements.length ?? 0;
  const criticalFlags = imm?.risk_flags.filter((f) => f.severity === 'critical').length ?? 0;
  const warningFlags = imm?.risk_flags.filter((f) => f.severity === 'warning').length ?? 0;
  const openExceptions = exceptions.filter((e) => e.status === 'pending').length;
  const immHealth: Health = criticalFlags > 0 ? 'red' : warningFlags > 0 ? 'amber' : 'green';
  const polHealth: Health = openExceptions > 0 ? 'amber' : 'green';

  return (
    <AppShell section="HR Operations" title="Requirements" subtitle={SUBTITLE}>
      {/* Summary bar — one-line health check across the case's requirements. */}
      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Document requirements" value={reqCount} />
        <Stat label="Risk flags" value={criticalFlags + warningFlags} tone={criticalFlags ? 'red' : warningFlags ? 'amber' : 'default'} />
        <Stat label="Critical / blocking" value={criticalFlags} tone={criticalFlags ? 'red' : 'default'} />
        <Stat label="Open policy exceptions" value={openExceptions} tone={openExceptions ? 'amber' : 'default'} />
      </div>

      {/* Immigration category */}
      <section className="mb-6">
        <CategoryHeader
          icon="🛂"
          title="Immigration"
          count={reqCount}
          health={immHealth}
          sub="Document checklist, risk flags, milestones, and intake progress for this corridor."
        />
        <ImmigrationStatusPanel
          caseId={caseId}
          moveDate={null}
          onFindVendor={() => navigate(buildRoute('hrCommandCenterCase', { id: caseId }))}
          onViewProfile={() => navigate(buildRoute('hrAssignmentReview', { id: caseId }))}
        />
      </section>

      {/* Policy warnings category */}
      <section className="mb-6">
        <CategoryHeader
          icon="⚠️"
          title="Policy warnings"
          count={openExceptions}
          health={polHealth}
          sub="Exception requests where this case falls outside the standard policy."
        />
        <Card padding="none" className="overflow-hidden">
          {exceptions.length === 0 ? (
            <div className="px-4 py-4 text-sm text-slate-500">No policy exceptions on this case.</div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {exceptions.map((e) => (
                <li key={e.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-[#0b2b43]">
                      {(e.category || 'Exception').replace(/_/g, ' ')}
                    </div>
                    {e.reason && <div className="truncate text-xs text-slate-500">{e.reason}</div>}
                  </div>
                  <Badge
                    variant={e.status === 'approved' ? 'success' : e.status === 'rejected' ? 'error' : 'warning'}
                    size="sm"
                  >
                    {e.status}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>
    </AppShell>
  );
}
