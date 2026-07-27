/**
 * [P1-6] Employee Roadmap page — /employee/case/:caseId/roadmap
 *
 * Renders the milestone-backed plan-view as the redesigned roadmap template
 * (dark hero + mini phase-timeline, "what you can do now", HR-handled banner,
 * collapsible phase sections). Header meta (cities / name / role / move date)
 * comes from the case-details endpoint; the plan + statuses from the plan-view.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { useTextSelection } from '../../hooks/useTextSelection';
import { ExplainTermPopover } from '../../features/explain/ExplainTermPopover';
import { PolicyAssistantFab } from '../../features/policy/PolicyAssistantFab';
import { PolicyAssistantDockedShell } from '../../features/policy/PolicyAssistantDockedShell';
import { EmployeePolicyAssistantPanel } from '../../features/policy/EmployeePolicyAssistantPanel';
import { RoadmapBeingBuilt } from '../../features/employee-journey/RoadmapBeingBuilt';
import { RoadmapPaywallGate } from '../../features/employee-journey/RoadmapPaywallGate';
import { fetchRoadmapUnlocked } from '../../utils/paymentStatus';
import { isRoadmapPaywallEnabled } from '../../featureFlags';
import { RuleUpdateBanner } from '../../features/platform-v2/roadmap/RuleUpdateBanner';
import { useEmployeeRelocationPlanPageData } from '../../features/relocation-plan-employee/useEmployeeRelocationPlanPageData';
import { useRelocationPlanCtaHandler } from '../../features/relocation-plan-employee/relocationPlanCtaNavigate';
import {
  RoadmapTemplate,
  type RoadmapHeaderMeta,
} from '../../features/relocation-plan-employee/roadmap-template/RoadmapTemplate';
import { getCaseDetailsByAssignmentId } from '../../api/caseDetails';
import { validateRoadmap } from '../../api/cases';
import { emitTestDriveStage } from '../../api/testDrive';
import { getCaseRoadmapV2 } from '../../api/roadmapV2';
import { buildConfidenceByTitle } from '../../features/relocation-plan-employee/roadmap-template/roadmapTemplateHelpers';
import type { ConfidenceByTitle } from '../../features/relocation-plan-employee/roadmap-template/RoadmapTemplate';
import { buildRoute, ROUTE_DEFS } from '../../navigation/routes';
import { useValidatedParams, caseParamsSchema } from '../../hooks/useValidatedParams';
import type { RelocationPlanPhaseTaskDTO } from '../../types/relocationPlanView';
import { track } from '../../analytics';
import { resolveRoadmapBuildVariant } from './roadmapBuildVariant';
import { isRoadmapHeldForHrReview } from './roadmapReleaseGate';

export const EmployeeCaseRoadmapPage: React.FC = () => {
  const caseId = useValidatedParams(caseParamsSchema, {
    redirectTo: ROUTE_DEFS.employeeDashboard.path,
  })?.caseId;
  const navigate = useNavigate();
  const selectionRef = useRef<HTMLDivElement>(null);
  const { selection, clear } = useTextSelection(selectionRef);
  // [AIQ-1259b] Policy Assistant ported from the retired /plan page so the
  // affordance survives the Plan→Roadmap consolidation.
  const [assistantOpen, setAssistantOpen] = useState(false);

  // H-08 (AIQ-1255): the page had no title — the browser tab + bookmarks were
  // unlabelled. Set a document title for the duration the page is mounted.
  useEffect(() => {
    const prev = document.title;
    document.title = 'Roadmap — ReloPass';
    return () => {
      document.title = prev;
    };
  }, []);

  // AIQ-1435: journey funnel — roadmap step reached (once per mount).
  useEffect(() => {
    track('journey_step_started', { step: 'roadmap', case_id: caseId, persona: 'employee' });
    // TD-FIX-4 (AIQ-1505): test-drive funnel — roadmap reached (no-op for real users).
    emitTestDriveStage('roadmap-reached');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { data, loading, error, refetch, ensureDefaultsAndReload } =
    useEmployeeRelocationPlanPageData(caseId);

  // AIQ-1435: journey funnel — roadmap completed once the plan data has loaded.
  const roadmapCompletedRef = useRef(false);
  useEffect(() => {
    if (data && !roadmapCompletedRef.current) {
      roadmapCompletedRef.current = true;
      track('journey_step_completed', { step: 'roadmap', case_id: caseId, persona: 'employee' });
    }
  }, [data, caseId]);
  const runCta = useRelocationPlanCtaHandler(caseId ?? '', { resourceCaseId: data?.case_id });
  const handleCta = (t: RelocationPlanPhaseTaskDTO) => {
    // [AIQ-1252] For document-upload tasks, pass the document key so the dossier
    // can deep-link to (auto-expand) the form whose required documents include it.
    const docKey = t.required_inputs?.find((ri) => ri.type === 'document')?.key;
    runCta(t.cta ?? null, docKey);
  };

  // Header meta (cities / employee / role / move date) — separate endpoint.
  const [header, setHeader] = useState<RoadmapHeaderMeta | null>(null);
  useEffect(() => {
    const aid = (data?.assignment_id || caseId || '').trim();
    if (!aid) return;
    let cancelled = false;
    getCaseDetailsByAssignmentId(aid)
      .then((res) => {
        if (cancelled || !res.data) return;
        const c = res.data.case;
        const a = res.data.assignment;
        setHeader({
          originCity: c.originCity,
          destCity: c.destCity,
          destCountry: c.destCountry,
          targetMoveDate: c.targetMoveDate,
          employeeName: a.employee_full_name ?? undefined,
          role: c.draft?.assignmentContext?.jobTitle ?? undefined,
        });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [data?.assignment_id, caseId]);

  // [AIQ-806] Confidence + source provenance for plan-view tasks, matched by title
  // from the parallel /roadmap/tracks projection (the form-backed path that carries
  // source_pages-derived confidence). Best-effort: failures leave tasks badge-less.
  const [confidenceByTitle, setConfidenceByTitle] = useState<ConfidenceByTitle>({});
  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    getCaseRoadmapV2(caseId)
      .then((res) => {
        if (!cancelled) setConfidenceByTitle(buildConfidenceByTitle(res));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  // Validate gate.
  const [localValidatedAt, setLocalValidatedAt] = useState<string | null>(null);
  const [validating, setValidating] = useState(false);
  const validated = !!data?.roadmap_validated || localValidatedAt !== null;
  const validatedAt = localValidatedAt ?? data?.roadmap_validated_at ?? null;
  const onValidate = async () => {
    if (!caseId || validating) return;
    setValidating(true);
    try {
      const res = await validateRoadmap(caseId);
      setLocalValidatedAt(res.roadmap_validated_at ?? new Date().toISOString());
    } finally {
      setValidating(false);
    }
  };

  // ── Roadmap generation state machine ────────────────────────────────────────
  // generating → ready | empty | failed. The plan builds asynchronously after
  // submit (~60–90s). AIQ-1377: a TRANSIENT error from the plan-view endpoint must
  // NOT dead-end the page. Within a bounded window an error OR an empty plan both
  // mean "not ready yet", so we keep polling/retrying. Only after the window elapses
  // do we resolve to a terminal state: a persistent error → failed, an empty → empty.
  const POLL_MS = 4000;
  const MAX_ATTEMPTS = 15; // ~60s of polling at the 4s cadence before we give up
  const [windowElapsed, setWindowElapsed] = useState(false);
  const [genStarted, setGenStarted] = useState(false);
  const attemptsRef = useRef(0);

  // ── Roadmap paywall (Phase 4a is the server-side enforcement; this is the UX) ──
  // Flag-gated (default off). We resolve the unlock from the SERVER (not localStorage)
  // and gate the render BEFORE the roadmap fetch below: the roadmap endpoints 402 when
  // locked, so a locked case must reach the paywall, not the "being built" fallback.
  const paywallOn = isRoadmapPaywallEnabled();
  const [roadmapUnlocked, setRoadmapUnlocked] = useState<boolean | null>(paywallOn ? null : true);
  // [AIQ-1723] Did the user arrive straight from Stripe checkout? Captured once, from the
  // URL at mount, because the grace-window poll below strips nothing and a re-render must
  // not change the answer. Drives the payment-aware copy in the two gates further down.
  const justPaidRef = useRef(
    new URLSearchParams(window.location.search).get('payment') === 'success',
  );
  // True once the just-paid grace window has elapsed WITHOUT entitlement landing. Terminal:
  // it stops the spinner and swaps the buy-CTA paywall for an honest "still confirming"
  // state. It never unlocks anything — the gate stays fail-CLOSED.
  const [paymentUnconfirmed, setPaymentUnconfirmed] = useState(false);
  useEffect(() => {
    if (!paywallOn || !caseId) {
      setRoadmapUnlocked(true);
      return;
    }
    let alive = true;
    setRoadmapUnlocked(null);
    setPaymentUnconfirmed(false);
    // Returning from Stripe checkout (?payment=success) the webhook that flips access_tier
    // can lag the browser redirect by a beat. Poll the server status briefly so a just-paid
    // user lands on their roadmap, not the paywall again. Normal loads check once.
    const justPaid = justPaidRef.current;
    const maxAttempts = justPaid ? 6 : 1; // ~6 × 2.5s ≈ 15s grace for the webhook
    let attempt = 0;
    const check = () => {
      void fetchRoadmapUnlocked(caseId).then((unlocked) => {
        if (!alive) return;
        attempt += 1;
        if (unlocked || attempt >= maxAttempts) {
          // [AIQ-1723] The webhook outlived the grace window. Remember that, so the render
          // below can say "we're still confirming your payment" instead of showing someone
          // who just paid the €800 buy button again — which reads as "my money vanished".
          if (!unlocked && justPaid) setPaymentUnconfirmed(true);
          setRoadmapUnlocked(unlocked);
        } else {
          window.setTimeout(check, 2500);
        }
      });
    };
    check();
    return () => {
      alive = false;
    };
  }, [paywallOn, caseId]);

  const planEmpty = !!data && data.summary.total_tasks === 0;
  const planReady = !!data && data.summary.total_tasks > 0 && data.phases.length > 0;
  // "not ready" = a transient error OR an empty plan still generating. Both retried.
  const notReady = !loading && !planReady && (error != null || planEmpty);

  useEffect(() => {
    if (planReady) {
      attemptsRef.current = 0;
      if (windowElapsed) setWindowElapsed(false);
      if (genStarted) setGenStarted(false);
      return;
    }
    if (loading || !notReady) return;
    if (!genStarted) setGenStarted(true);
    if (attemptsRef.current >= MAX_ATTEMPTS) {
      if (!windowElapsed) setWindowElapsed(true);
      return;
    }
    const t = window.setTimeout(() => {
      attemptsRef.current += 1;
      void refetch();
    }, POLL_MS);
    return () => window.clearTimeout(t);
  }, [loading, planReady, notReady, data, refetch, windowElapsed, genStarted]);

  const resetWindow = useCallback(() => {
    attemptsRef.current = 0;
    setWindowElapsed(false);
    setGenStarted(false);
  }, []);
  const retryGeneration = useCallback(() => {
    resetWindow();
    void ensureDefaultsAndReload();
  }, [resetWindow, ensureDefaultsAndReload]);
  const retryFetch = useCallback(() => {
    resetWindow();
    void refetch();
  }, [resetWindow, refetch]);

  // Paywall gate — runs BEFORE the loading/build-state returns so a locked case reaches
  // the paywall rather than the "being built" fallback (the roadmap fetch 402s when locked).
  if (paywallOn && roadmapUnlocked === null) {
    // [AIQ-1723] Same bounded wait either way, but say WHY we're waiting when the user
    // just came back from checkout. "Loading roadmap…" at the highest-anxiety moment in
    // the funnel reads as a hang; naming the payment makes the same seconds tolerable.
    return (
      <AppShell>
        <div style={{ padding: '24px', color: 'var(--text-muted)' }}>
          {justPaidRef.current ? 'Confirming your payment…' : 'Loading roadmap…'}
        </div>
      </AppShell>
    );
  }
  // [AIQ-1723] Paid, but the webhook hasn't landed within the grace window. Terminal and
  // fail-CLOSED — the roadmap stays locked — but showing the €800 buy CTA to someone who
  // has already paid is the worst copy in the product. Tell them the truth and give them
  // a way forward instead.
  if (paywallOn && roadmapUnlocked === false && paymentUnconfirmed) {
    return (
      <AppShell>
        <div className="mx-auto max-w-5xl px-6 py-6">
          <div className="rounded-lg border border-[#e2e8f0] bg-white p-6">
            <div className="text-base font-semibold text-navy-800">
              Payment received — we&apos;re still confirming it
            </div>
            <p className="mt-2 text-sm text-slate-600">
              Your payment went through. Our provider hasn&apos;t confirmed it back to us yet,
              which usually takes a few seconds. Your roadmap unlocks automatically as soon as
              it does — nothing else is needed from you.
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-4 rounded-md bg-navy-800 px-4 py-2 text-sm font-medium text-white"
            >
              Check again
            </button>
            <p className="mt-3 text-xs text-slate-500">
              Still waiting after a minute or two? Contact support and we&apos;ll sort it out —
              you will not be charged twice.
            </p>
          </div>
        </div>
      </AppShell>
    );
  }
  if (paywallOn && roadmapUnlocked === false) {
    return (
      <AppShell>
        <div className="mx-auto max-w-5xl px-6 py-6">
          <RoadmapPaywallGate
            assignmentId={data?.assignment_id || caseId || ''}
            destCity={header?.destCity}
            destCountry={header?.destCountry}
          />
        </div>
      </AppShell>
    );
  }

  if (loading && !data && !genStarted) {
    return (
      <AppShell>
        <div style={{ padding: '24px', color: 'var(--text-muted)' }}>Loading roadmap…</div>
      </AppShell>
    );
  }

  if (!planReady) {
    // Within the bounded window a transient error or empty plan both render as
    // "generating" (we keep retrying). Only after the window elapses do we show a
    // terminal state — persistent error → failed, empty plan → empty (AIQ-1377).
    // Pass the HTTP status: a 401/403 can never resolve into a roadmap, so it must
    // not sit in the "we're building it" state for 60s promising an email.
    const errorStatus =
      (error as { response?: { status?: number } } | null)?.response?.status ?? null;
    const variant = resolveRoadmapBuildVariant(windowElapsed, error != null, errorStatus);
    return (
      <AppShell>
        <div className="mx-auto max-w-5xl px-6 py-6">
          <RoadmapBeingBuilt
            variant={variant}
            onMessageTeam={() => navigate(buildRoute('messages'))}
            onRetry={variant === 'failed' ? retryFetch : variant === 'empty' ? retryGeneration : undefined}
          />
        </div>
      </AppShell>
    );
  }

  // ── HR review gate ──────────────────────────────────────────────────────────
  // The plan is BUILT but HR hasn't approved it yet. The employee EXPLORES it freely —
  // seeing the plan is reassuring and costs nothing. What waits for HR is ACTION: HR can
  // still send the plan back for regeneration, and work done against a plan that's about
  // to be replaced is wasted.
  //
  // So we render the whole roadmap and pass `pendingReview` down: banner on, task CTAs
  // disabled, "Validate & start tasks" hidden. The real enforcement is server-side
  // (assert_roadmap_released -> 409) — this is the UI telling the same truth.
  //
  // `=== false`, NOT `!released` — see roadmapReleaseGate.ts. The backend fails open and
  // the field is optional, so `undefined` means RELEASED.
  const pendingReview = isRoadmapHeldForHrReview(data);

  return (
    <AppShell>
      <PolicyAssistantDockedShell
        open={assistantOpen}
        onOpenChange={setAssistantOpen}
        title="Ask about your policy"
        subtitle="Bounded Q&A on your published policy."
        titleId="employee-roadmap-assistant-shell-title"
        assistant={() => (
          <EmployeePolicyAssistantPanel
            assignmentId={caseId ?? ''}
            assignmentLoading={false}
            variant="embedded"
          />
        )}
      >
        <div ref={selectionRef} className="mx-auto max-w-5xl px-6 py-6">
          {/* H-08 (AIQ-1255): page heading so the employee has orientation above the hero. */}
          <h1 className="text-2xl font-semibold text-slate-900 mb-4">My roadmap</h1>
          {/* [AIQ-693] P2-02e — surface approved rule-update notifications for this case. */}
          <RuleUpdateBanner caseId={caseId ?? ''} />
          <RoadmapTemplate
            data={data}
            header={header}
            caseId={caseId ?? ''}
            onCta={handleCta}
            validated={validated}
            validatedAt={validatedAt}
            validating={validating}
            onValidate={onValidate}
            confidenceByTitle={confidenceByTitle}
            pendingReview={pendingReview}
          />
        </div>
        {selection && (
          <ExplainTermPopover selection={selection} assignmentId={caseId ?? ''} onClose={clear} />
        )}
      </PolicyAssistantDockedShell>
      <PolicyAssistantFab
        label="Ask about your policy"
        isPanelOpen={assistantOpen}
        onClick={() => setAssistantOpen((v) => !v)}
      />
    </AppShell>
  );
};
