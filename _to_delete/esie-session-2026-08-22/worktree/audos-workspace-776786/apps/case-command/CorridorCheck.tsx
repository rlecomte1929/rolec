/**
 * Corridor Check — the deterministic corridor case checker, gated by
 * CaseGate (Tier 0 free teaser → Tier 1 €800 full roadmap unlock).
 * Corridors: France → Norway (v0) and Norway → France (authoring draft).
 *
 * The user picks a corridor, an employee type and an anchor date.
 * The hardcoded rule engine (rule-engine.ts) produces the time-anchored
 * requirement sequence — identical inputs always produce identical output.
 * What renders is decided by the server-side access tier:
 *   free    → teaser (2–3 non-obvious requirements verbatim, rest blurred)
 *   roadmap → the full requirement roadmap
 *
 * Post-payment: Stripe redirects back with ?payment=success&caseId=N. This
 * component restores the case inputs from the server row, shows the unlock
 * banner, and renders the full roadmap once server-side verification (via
 * the case-access hook) confirms the payment.
 */

import { useState, useEffect, useMemo } from 'react';
import {
  Route, Calendar, User, Users, AlertTriangle, PlayCircle,
  CheckCircle2, Clock, XCircle, Link2, Loader2,
} from 'lucide-react';
import CaseGate, { type CaseAccessState, type PreviewRequirement } from '../../components/CaseGate';
import {
  runCaseCheck,
  localTodayIso,
  EMPLOYEE_TYPE_OPTIONS,
  NORWAY_FRANCE_EMPLOYEE_TYPE_OPTIONS,
  type CorridorId,
  type EmployeeType,
  type CaseCheckResult,
  type CaseRequirement,
  type Feasibility,
} from './rule-engine';

const SPACE_ID: string =
  (typeof window !== 'undefined' && ((window as any).__APP_ID__ || (window as any).__SPACE_ID__)) ||
  'workspace-776786';

const STORAGE_KEY = 'relopass_corridor_check_v1';

/** Corridors selectable in the check UI, with their per-corridor copy. */
type CheckCorridorId = Extract<CorridorId, 'france-norway' | 'norway-france'>;

const CORRIDOR_UI: Record<CheckCorridorId, {
  heading: string;
  sub: string;
  dateLabel: string;
  caseKeyPrefix: string;
  employeeTypeOptions: typeof EMPLOYEE_TYPE_OPTIONS;
  previewIds: string[];
  statusNote: string | null;
}> = {
  'france-norway': {
    heading: 'France → Norway corridor check',
    sub: 'Two inputs. A deterministic, time-anchored requirement sequence — same inputs, same answer, every time.',
    dateLabel: 'Target move date',
    caseKeyPrefix: 'frno',
    employeeTypeOptions: EMPLOYEE_TYPE_OPTIONS,
    previewIds: ['d-number', 'skattekort', 'police-registration'],
    statusNote: null,
  },
  'norway-france': {
    heading: 'Norway → France corridor check',
    sub: 'Anchored on your departure date from Norway — past or future. Already left? The check runs retrospectively and triages the windows that have closed.',
    dateLabel: 'Departure date from Norway',
    caseKeyPrefix: 'nofr',
    employeeTypeOptions: NORWAY_FRANCE_EMPLOYEE_TYPE_OPTIONS,
    previewIds: ['b2-urssaf-foreign-employer', 'a2-preserve-bankid', 'd1-household-goods-customs-relief'],
    statusNote: 'Authoring draft — sourced, informational content; not yet counsel-assured. Nothing here is legal or tax advice — items that need an individual determination route to a regulated professional.',
  },
};

const CORRIDOR_OPTIONS: { id: CheckCorridorId; label: string; description: string }[] = [
  { id: 'france-norway', label: 'France → Norway', description: 'Employer-supported move into Norway, anchored on the move date' },
  { id: 'norway-france', label: 'Norway → France', description: 'Leaving Norway for France — exit admin, cross-border employment, establishment, customs' },
];

interface StoredCheck {
  corridor: CheckCorridorId;
  employeeType: EmployeeType;
  moveDate: string;
  caseId: number | null;
}

function readStoredCheck(): StoredCheck | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if ((parsed?.employeeType === 'eea' || parsed?.employeeType === 'non-eea') && typeof parsed?.moveDate === 'string') {
      if (parsed.corridor !== 'france-norway' && parsed.corridor !== 'norway-france') {
        parsed.corridor = 'france-norway';
      }
      return parsed as StoredCheck;
    }
  } catch { /* ignore */ }
  return null;
}

function writeStoredCheck(check: StoredCheck) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(check)); } catch { /* ignore */ }
}

function sessionScope(): string {
  const sid = typeof window !== 'undefined' ? (window as any).__spaceSessionId : undefined;
  return typeof sid === 'string' && sid ? sid : 'anon';
}

// ── Full-roadmap rendering ───────────────────────────────────────────────────────

const FEASIBILITY_STYLE: Record<Feasibility, { border: string; dot: string; label: string; text: string }> = {
  green: { border: 'border-[var(--space-border-default)] bg-[var(--space-surface-card)]', dot: 'bg-[var(--space-semantic-success)]', label: 'On track', text: 'text-green-300' },
  amber: { border: 'border-amber-500/30 bg-amber-500/10', dot: 'bg-amber-400', label: 'Tight — under 7 days of buffer', text: 'text-amber-300' },
  red: { border: 'border-red-500/30 bg-red-500/10', dot: 'bg-red-500', label: 'Window passed', text: 'text-red-300' },
  confirmed: { border: 'border-[var(--space-border-strong)] bg-[var(--space-brand-highlight-50)]', dot: 'bg-[var(--space-text-accent)]', label: 'Confirmed — nothing to do', text: 'text-[var(--space-text-accent)]' },
};

const OWNER_ICON: Record<string, typeof User> = { HR: User, Employee: User, Both: Users };

function RequirementCard({ req }: { req: CaseRequirement }) {
  const style = FEASIBILITY_STYLE[req.feasibility];
  const OwnerIcon = OWNER_ICON[req.owner] || User;

  return (
    <div className={`p-3.5 rounded-xl border ${style.border}`}>
      <div className="flex items-start justify-between gap-2 mb-1">
        <div className="flex items-start gap-2 min-w-0">
          <span className={`w-2 h-2 rounded-full flex-shrink-0 mt-1.5 ${style.dot}`} />
          <h4 className="text-sm font-semibold text-[var(--space-text-primary)] leading-snug">{req.title}</h4>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {req.nonObvious && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/20 text-amber-200">Easy to miss</span>
          )}
          <span className={`text-[10px] font-semibold ${style.text}`}>{style.label}</span>
        </div>
      </div>
      <p className="text-xs text-[var(--space-text-secondary)] leading-relaxed ml-4 mb-1.5">{req.description}</p>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 ml-4 text-[10px] text-[var(--space-text-muted)]">
        <span className="flex items-center gap-1"><Calendar className="w-3 h-3" /> {req.feasibility === 'confirmed' ? `${req.offsetLabel} · no action needed` : `${req.offsetLabel} · act by ${req.actionByDate}`}</span>
        <span className="flex items-center gap-1"><OwnerIcon className="w-3 h-3" /> {req.owner}</span>
        {req.dependencyNote && (
          <span className="flex items-center gap-1"><Link2 className="w-3 h-3" /> {req.dependencyNote}</span>
        )}
      </div>
    </div>
  );
}

function FullRoadmap({ result }: { result: CaseCheckResult }) {
  return (
    <div>
      <div className={`grid ${result.counts.confirmed > 0 ? 'grid-cols-2 sm:grid-cols-4 max-w-xl' : 'grid-cols-3 max-w-md'} gap-3 mb-4`}>
        {[
          { label: 'On track', value: result.counts.green, color: 'text-green-300', Icon: CheckCircle2 },
          { label: 'Tight', value: result.counts.amber, color: 'text-amber-300', Icon: Clock },
          { label: 'Window passed', value: result.counts.red, color: 'text-red-300', Icon: XCircle },
          ...(result.counts.confirmed > 0
            ? [{ label: 'Confirmed clear', value: result.counts.confirmed, color: 'text-[var(--space-text-accent)]', Icon: CheckCircle2 }]
            : []),
        ].map(({ label, value, color, Icon }) => (
          <div key={label} className="px-3 py-2.5 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)] text-center">
            <p className={`text-lg font-bold ${color} flex items-center justify-center gap-1.5`}>
              <Icon className="w-4 h-4" /> {value}
            </p>
            <p className="text-[10px] text-[var(--space-text-secondary)]">{label}</p>
          </div>
        ))}
      </div>
      <div className="space-y-2.5">
        {result.requirements.map((req) => (
          <RequirementCard key={req.id} req={req} />
        ))}
      </div>
    </div>
  );
}

// ── Main view ────────────────────────────────────────────────────────────────────

export default function CorridorCheck() {
  const [corridor, setCorridor] = useState<CheckCorridorId>('france-norway');
  const [employeeType, setEmployeeType] = useState<EmployeeType>('eea');
  const [moveDate, setMoveDate] = useState('');
  const [submitted, setSubmitted] = useState<{ corridor: CheckCorridorId; employeeType: EmployeeType; moveDate: string } | null>(null);
  const [knownCaseId, setKnownCaseId] = useState<number | null>(null);
  const [paymentSuccess, setPaymentSuccess] = useState(false);
  const [restoring, setRestoring] = useState(true);

  // Restore state: post-payment URL params take priority, then the last
  // submitted check from localStorage.
  useEffect(() => {
    let cancelled = false;

    const restore = async () => {
      const params = new URLSearchParams(window.location.search);
      const isSuccess = params.get('payment') === 'success';
      const urlCaseId = parseInt(params.get('caseId') || '', 10) || null;

      if (isSuccess && urlCaseId) {
        setPaymentSuccess(true);
        setKnownCaseId(urlCaseId);
        // Consume the params so refreshes don't replay the banner.
        try {
          params.delete('payment');
          params.delete('caseId');
          const qs = params.toString();
          window.history.replaceState({}, '', window.location.pathname + (qs ? `?${qs}` : '') + window.location.hash);
        } catch { /* ignore */ }

        // Pull the case inputs back from the server row. The corridor is not
        // stored server-side — recover it from the last stored check.
        try {
          const res = await fetch(`/api/workspaces/${SPACE_ID}/hooks/case-access/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ caseId: urlCaseId }),
          });
          const data = await res.json();
          if (!cancelled && res.ok && (data?.employeeType === 'eea' || data?.employeeType === 'non-eea') && data?.moveDate) {
            const storedCorridor = readStoredCheck()?.corridor ?? 'france-norway';
            setCorridor(storedCorridor);
            setEmployeeType(data.employeeType);
            setMoveDate(data.moveDate);
            setSubmitted({ corridor: storedCorridor, employeeType: data.employeeType, moveDate: data.moveDate });
            writeStoredCheck({ corridor: storedCorridor, employeeType: data.employeeType, moveDate: data.moveDate, caseId: urlCaseId });
          }
        } catch { /* leave the form empty; the payment stays attached to the case row */ }
      } else {
        const stored = readStoredCheck();
        if (!cancelled && stored) {
          setCorridor(stored.corridor);
          setEmployeeType(stored.employeeType);
          setMoveDate(stored.moveDate);
          setKnownCaseId(stored.caseId);
          setSubmitted({ corridor: stored.corridor, employeeType: stored.employeeType, moveDate: stored.moveDate });
        }
      }
      if (!cancelled) setRestoring(false);
    };

    restore();
    return () => { cancelled = true; };
  }, []);

  const result = useMemo<CaseCheckResult | null>(() => {
    if (!submitted) return null;
    return runCaseCheck(submitted.employeeType, submitted.moveDate, localTodayIso(), submitted.corridor);
  }, [submitted]);

  const previewRequirements = useMemo<PreviewRequirement[]>(() => {
    if (!result || !submitted) return [];
    const nonObvious = result.requirements.filter((r) => r.nonObvious);
    const flagship = CORRIDOR_UI[submitted.corridor].previewIds
      .map((id) => nonObvious.find((r) => r.id === id))
      .filter((r): r is CaseRequirement => Boolean(r));
    const picked = flagship.length >= 2 ? flagship : nonObvious;
    return picked.slice(0, 3).map((r) => ({
      id: r.id,
      title: r.title,
      description: r.description,
      offsetLabel: r.offsetLabel,
      actionByDate: r.actionByDate,
      owner: r.owner,
    }));
  }, [result, submitted]);

  const caseKey = submitted
    ? `${CORRIDOR_UI[submitted.corridor].caseKeyPrefix}|${sessionScope()}|${submitted.employeeType}|${submitted.moveDate}`
    : '';

  const handleSubmit = () => {
    if (!moveDate) return;
    const isSameCase = submitted && submitted.corridor === corridor && submitted.employeeType === employeeType && submitted.moveDate === moveDate;
    const nextCaseId = isSameCase ? knownCaseId : null;
    setSubmitted({ corridor, employeeType, moveDate });
    setKnownCaseId(nextCaseId);
    setPaymentSuccess(false);
    writeStoredCheck({ corridor, employeeType, moveDate, caseId: nextCaseId });
  };

  const handleAccess = (access: CaseAccessState) => {
    setKnownCaseId(access.caseId);
    if (submitted) {
      writeStoredCheck({ corridor: submitted.corridor, employeeType: submitted.employeeType, moveDate: submitted.moveDate, caseId: access.caseId });
    }
  };

  if (restoring) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Loader2 className="w-6 h-6 animate-spin text-[var(--space-brand-primary)] mb-3" />
        <p className="text-sm text-[var(--space-text-secondary)]">Loading corridor check…</p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto w-full px-4 sm:px-6 py-5">
      {/* Input form */}
      <div className="p-4 sm:p-5 rounded-2xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)] mb-5">
        <div className="flex items-center gap-2 mb-3.5">
          <Route className="w-4 h-4 text-[var(--space-text-accent)]" />
          <h3 className="text-sm font-semibold text-[var(--space-text-primary)]">{CORRIDOR_UI[corridor].heading}</h3>
        </div>
        <p className="text-xs text-[var(--space-text-secondary)] mb-4">
          {CORRIDOR_UI[corridor].sub}
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 mb-3.5">
          {CORRIDOR_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              type="button"
              onClick={() => setCorridor(opt.id)}
              className={`text-left px-3.5 py-3 rounded-xl border transition-all ${
                corridor === opt.id
                  ? 'border-[var(--space-brand-highlight-600)] bg-[var(--space-brand-highlight-50)] ring-1 ring-[var(--space-brand-highlight-600)]'
                  : 'border-[var(--space-border-default)] bg-[var(--space-surface-muted)] hover:border-[var(--space-border-strong)]'
              }`}
            >
              <p className="text-sm font-semibold text-[var(--space-text-primary)] mb-0.5">{opt.label}</p>
              <p className="text-[11px] text-[var(--space-text-secondary)] leading-snug">{opt.description}</p>
            </button>
          ))}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 mb-3.5">
          {CORRIDOR_UI[corridor].employeeTypeOptions.map((opt) => (
            <button
              key={opt.id}
              type="button"
              onClick={() => setEmployeeType(opt.id)}
              className={`text-left px-3.5 py-3 rounded-xl border transition-all ${
                employeeType === opt.id
                  ? 'border-[var(--space-brand-primary)] bg-[var(--space-brand-primary-50)] ring-1 ring-[var(--space-brand-primary)]'
                  : 'border-[var(--space-border-default)] bg-[var(--space-surface-muted)] hover:border-[var(--space-border-strong)]'
              }`}
            >
              <p className="text-sm font-semibold text-[var(--space-text-primary)] mb-0.5">{opt.label}</p>
              <p className="text-[11px] text-[var(--space-text-secondary)] leading-snug">{opt.description}</p>
            </button>
          ))}
        </div>
        <div className="flex flex-col sm:flex-row gap-2.5">
          <label className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--space-surface-muted)] border border-[var(--space-border-default)] flex-1">
            <Calendar className="w-3.5 h-3.5 text-[var(--space-text-muted)] flex-shrink-0" />
            <span className="text-xs text-[var(--space-text-muted)] whitespace-nowrap">{CORRIDOR_UI[corridor].dateLabel}</span>
            <input
              type="date"
              value={moveDate}
              onChange={(e) => setMoveDate(e.target.value)}
              className="flex-1 text-sm bg-transparent border-none outline-none text-[var(--space-text-primary)]"
              aria-label={CORRIDOR_UI[corridor].dateLabel}
            />
          </label>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!moveDate}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-[var(--space-brand-primary)] text-[var(--space-text-on-primary)] text-sm font-semibold hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            <PlayCircle className="w-4 h-4" /> Run case check
          </button>
        </div>
      </div>

      {/* Results */}
      {result && submitted && (
        <div>
          {/* Free context: corridor summary + warnings (not part of the paid product) */}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mb-3 text-xs text-[var(--space-text-secondary)]">
            <span className="font-semibold text-[var(--space-text-primary)]">{result.corridorLabel}</span>
            <span>· {result.employeeTypeLabel}</span>
            <span>· {submitted.corridor === 'norway-france' ? 'departure date' : 'move date'} {result.moveDate}</span>
          </div>
          {CORRIDOR_UI[submitted.corridor].statusNote && (
            <div className="mb-3 px-4 py-2.5 rounded-xl border border-[var(--space-border-strong)] bg-[var(--space-surface-panel)]">
              <p className="text-xs text-[var(--space-text-secondary)]">{CORRIDOR_UI[submitted.corridor].statusNote}</p>
            </div>
          )}
          {result.criticalBanner && (
            <div className="mb-3 px-4 py-3 rounded-xl border border-red-500/30 bg-red-500/10 flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-red-200 font-medium">{result.criticalBanner}</p>
            </div>
          )}
          {result.moveDatePassedWarning && (
            <div className="mb-3 px-4 py-2.5 rounded-xl border border-amber-500/30 bg-amber-500/10">
              <p className="text-xs text-amber-200">{result.moveDatePassedWarning}</p>
            </div>
          )}
          {result.urgentSummary && (
            <div className="mb-3 px-4 py-2.5 rounded-xl border border-amber-500/30 bg-amber-500/10">
              <p className="text-xs text-amber-200 font-medium">{result.urgentSummary}</p>
            </div>
          )}

          <CaseGate
            caseKey={caseKey}
            createPayload={{ employeeType: submitted.employeeType, moveDate: submitted.moveDate, sessionId: sessionScope() }}
            initialCaseId={knownCaseId}
            paymentSuccess={paymentSuccess}
            totalRequirements={result.counts.total}
            nonObviousCount={result.requirements.filter((r) => r.nonObvious).length}
            previewRequirements={previewRequirements}
            onAccess={handleAccess}
          >
            <FullRoadmap result={result} />
          </CaseGate>
        </div>
      )}

      {!result && (
        <div className="text-center py-10">
          <Route className="w-8 h-8 text-[var(--space-text-muted)] mx-auto mb-2" />
          <p className="text-sm text-[var(--space-text-secondary)]">
            Pick a corridor, the employee type and the anchor date, then run the check to see what your move actually requires.
          </p>
        </div>
      )}
    </div>
  );
}
