/**
 * [AIQ-1526] Does the "your roadmap needs review" email to HR actually work?
 *
 * A generated roadmap is held for HR approval — the employee can read their plan but not
 * start tasks. We email the case's HR owner the moment it's ready. This panel answers the
 * only questions that matter about that:
 *
 *   - Is anyone waiting?                     pending_review / oldest_pending_age_hours
 *   - Were they actually TOLD?               pending_unnotified
 *   - Is anyone waiting on NOBODY?           unreachable   <-- the one that must never hide
 *   - Did a send fail and never get retried? undelivered
 *
 * `unreachable` is the load-bearing number. 10 of the 47 cases with a roadmap resolve to
 * no HR contact at all (no case_assignments row, or an HR id with no email). For those, an
 * employee sits blocked and there is nobody to notify. A silent skip looks exactly like a
 * successful send — so we count it, name it, and show the case ids.
 *
 * Fails soft: on an error it renders nothing rather than breaking the ops page.
 */
import { useEffect, useState } from 'react';
import { apiGet } from '../../../api/client';

interface RoadmapReviewMetrics {
  pending_review: number;
  pending_and_notified: number;
  pending_unnotified: number;
  unreachable: number;
  unreachable_case_ids: string[];
  undelivered: number;
  no_key: number;
  sent: number;
  oldest_pending_age_hours: number | null;
}

function Stat({
  label, value, sub, tone = 'default',
}: {
  label: string;
  value: string | number;
  sub?: string;
  tone?: 'default' | 'warning' | 'danger' | 'success';
}) {
  const toneCls =
    tone === 'danger'
      ? 'border-rose-200 bg-rose-50 text-rose-900'
      : tone === 'warning'
        ? 'border-amber-200 bg-amber-50 text-amber-900'
        : tone === 'success'
          ? 'border-teal-200 bg-teal-50 text-teal-900'
          : 'border-slate-200 bg-white text-[#0b2b43]';
  return (
    <div className={`rounded-lg border px-4 py-3 ${toneCls}`}>
      <div className="text-[11px] font-semibold uppercase tracking-wide opacity-70">{label}</div>
      <div className="mt-1 text-2xl font-bold tabular-nums">{value}</div>
      {sub && <div className="mt-0.5 text-[11.5px] opacity-75">{sub}</div>}
    </div>
  );
}

export function RoadmapReviewMetricsPanel() {
  const [m, setM] = useState<RoadmapReviewMetrics | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    apiGet<RoadmapReviewMetrics>('/api/admin/roadmap-review/metrics')
      .then((res) => !cancelled && setM(res))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, []);

  if (failed || !m) return null;

  const age =
    typeof m.oldest_pending_age_hours === 'number'
      ? m.oldest_pending_age_hours >= 24
        ? `oldest ${Math.floor(m.oldest_pending_age_hours / 24)}d`
        : `oldest ${Math.round(m.oldest_pending_age_hours)}h`
      : undefined;

  return (
    <section className="mb-4">
      <h2 className="mb-2 text-sm font-semibold text-[#0b2b43]">Roadmap review queue</h2>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat
          label="Awaiting HR"
          value={m.pending_review}
          sub={age ?? 'nobody waiting'}
          tone={m.pending_review > 0 ? 'warning' : 'success'}
        />
        <Stat
          label="Waiting, not told"
          value={m.pending_unnotified}
          sub="HR has not been emailed"
          tone={m.pending_unnotified > 0 ? 'danger' : 'success'}
        />
        {/* The silent-failure counter. An employee blocked with nobody to notify. */}
        <Stat
          label="No HR contact"
          value={m.unreachable}
          sub={m.unreachable > 0 ? 'employee blocked, nobody to tell' : 'every case reachable'}
          tone={m.unreachable > 0 ? 'danger' : 'success'}
        />
        <Stat
          label="Emails sent"
          value={m.sent}
          sub={m.undelivered > 0 ? `${m.undelivered} failed (not retried)` : 'no failures'}
          tone={m.undelivered > 0 ? 'warning' : 'default'}
        />
      </div>

      {m.unreachable_case_ids.length > 0 && (
        <div className="mt-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-[12px] text-rose-900">
          <span className="font-semibold">No HR contact resolves for these cases</span> — the
          employee is waiting and nobody has been told. Link an HR owner to fix:{' '}
          <span className="font-mono">{m.unreachable_case_ids.slice(0, 5).join(', ')}</span>
          {m.unreachable_case_ids.length > 5 && ` +${m.unreachable_case_ids.length - 5} more`}
        </div>
      )}
    </section>
  );
}
