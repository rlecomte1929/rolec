import React from 'react';
import { Button, StatusPill } from '../../components/antigravity';
import type { JourneyStatus } from '../../components/antigravity';

/**
 * JourneySpine — the employee journey-home as a vertical timeline.
 *
 * Drop-in alternative to JourneyPhases (same props) that presents the
 * relocation as a connected spine of stations — Assignment claimed → Intake →
 * Services & policy → Roadmap — with the current actionable phase expanded
 * inline. Approved as design direction "A · Journey spine" (design-shotgun,
 * 2026-06-14); stays in the navy/teal antigravity "E" language. Strongest
 * "where am I on the journey" wayfinding; locked phases read as a clear path.
 *
 * Behavioural parity with JourneyPhases: the same three actions are always
 * available (intake CTA, Preview benefits, Roadmap), so swapping this in
 * changes layout only, not capability.
 */
interface JourneySpineProps {
  /** Current intake step (0 = not started). */
  intakeStep: number;
  /** Total intake steps (e.g. 5). */
  intakeTotalSteps: number;
  onContinueIntake: () => void;
  onPreviewBenefits: () => void;
  /** When omitted, the Roadmap phase stays locked until intake is done. */
  onViewRoadmap?: () => void;
}

type IntakeState = 'done' | 'in-progress' | 'not-started';

function intakeState(step: number, total: number): IntakeState {
  if (total > 0 && step >= total) return 'done';
  if (step > 0) return 'in-progress';
  return 'not-started';
}

const HomeIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M3 9.5 12 3l9 6.5" /><path d="M5 10v10h14V10" /><path d="M9 20v-6h6v6" />
  </svg>
);

type NodeKind = 'done' | 'active' | 'locked';

/** A single station: connector line + status node + content slot. */
const Station: React.FC<{
  kind: NodeKind;
  /** Glyph shown in the node (e.g. ✓ for done, a step number, or an icon). */
  glyph: React.ReactNode;
  last?: boolean;
  children: React.ReactNode;
}> = ({ kind, glyph, last = false, children }) => {
  const nodeClass =
    kind === 'done'
      ? 'bg-[#1f8e8b] border-[#1f8e8b] text-white'
      : kind === 'active'
        ? 'bg-[#0b2b43] border-[#0b2b43] text-white ring-4 ring-[#e6f4f3]'
        : 'bg-white border-[#e2e8f0] text-[#94a3b8]';
  return (
    <li className={`relative pl-12 ${last ? '' : 'pb-5'}`}>
      {/* connector line to the next station */}
      {!last ? (
        <span className="absolute left-[15px] top-7 bottom-0 w-0.5 bg-[#e2e8f0]" aria-hidden="true" />
      ) : null}
      <span
        className={`absolute left-0 top-0 grid h-8 w-8 place-items-center rounded-full border-2 text-xs font-bold ${nodeClass}`}
        aria-hidden="true"
      >
        {glyph}
      </span>
      {children}
    </li>
  );
};

export const JourneySpine: React.FC<JourneySpineProps> = ({
  intakeStep,
  intakeTotalSteps,
  onContinueIntake,
  onPreviewBenefits,
  onViewRoadmap,
}) => {
  const state = intakeState(intakeStep, intakeTotalSteps);
  const intakeDone = state === 'done';
  const intakeStarted = state === 'in-progress';
  const progressPct =
    intakeTotalSteps > 0 ? Math.min(100, Math.round((intakeStep / intakeTotalSteps) * 100)) : 0;

  const intakePill: { status: JourneyStatus; label: string } = intakeDone
    ? { status: 'done', label: 'Done' }
    : intakeStarted
      ? { status: 'in-progress', label: 'In progress' }
      : { status: 'upcoming', label: 'Not started' };
  const intakeCtaLabel = intakeDone ? 'Review intake' : intakeStarted ? 'Continue intake' : 'Start intake';

  // The active station is Intake until it's done, then Services & policy.
  const intakeActive = !intakeDone;
  const servicesActive = intakeDone;

  return (
    <ul className="relative m-0 list-none p-0">
      {/* Assignment claimed — you're linked to a case, so this is always done. */}
      <Station kind="done" glyph="✓">
        <div className="pt-0.5">
          <div className="font-semibold text-[#0b2b43] text-sm">Assignment claimed</div>
          <div className="text-xs text-[#64748b] mt-0.5">Linked to your company</div>
        </div>
      </Station>

      {/* Intake */}
      <Station kind={intakeActive ? 'active' : 'done'} glyph={intakeDone ? '✓' : <HomeIcon />}>
        <div className="flex flex-wrap items-center gap-2">
          <span className={`font-semibold text-sm ${intakeActive ? 'text-[#0b2b43]' : 'text-[#0b2b43]'}`}>Intake</span>
          <StatusPill status={intakePill.status}>{intakePill.label}</StatusPill>
        </div>
        {intakeActive ? (
          <div className="mt-2 rounded-xl border-2 border-[#1f8e8b] bg-white p-4">
            <p className="text-sm text-[#4b5563]">
              Tell us about your move and household so we can tailor your benefits and roadmap.
            </p>
            {intakeStarted ? (
              <div className="mt-3">
                <div className="flex items-center justify-between text-xs font-medium text-[#0b2b43] mb-1">
                  <span>Step {intakeStep} of {intakeTotalSteps}</span>
                  <span className="text-[#1f8e8b]">{progressPct}%</span>
                </div>
                <div className="h-2 w-full rounded-full bg-[#e2e8f0] overflow-hidden">
                  <div className="h-full rounded-full bg-[#1f8e8b]" style={{ width: `${progressPct}%` }} />
                </div>
              </div>
            ) : null}
            <Button variant="primary" size="sm" className="mt-4" onClick={onContinueIntake}>
              {intakeCtaLabel}
            </Button>
          </div>
        ) : (
          <div className="mt-1">
            <Button variant="ghost" size="sm" onClick={onContinueIntake}>{intakeCtaLabel}</Button>
          </div>
        )}
      </Station>

      {/* Services & policy */}
      <Station kind={servicesActive ? 'active' : 'locked'} glyph="2">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`font-semibold text-sm ${servicesActive ? 'text-[#0b2b43]' : 'text-[#94a3b8]'}`}>
            Services &amp; policy
          </span>
          <StatusPill status={servicesActive ? 'ready' : 'upcoming'}>
            {servicesActive ? 'Ready' : 'Up next'}
          </StatusPill>
        </div>
        {servicesActive ? (
          <div className="mt-2 rounded-xl border-2 border-[#1f8e8b] bg-white p-4">
            <p className="text-sm text-[#4b5563]">
              See the services and budget your policy covers for this move.
            </p>
            <Button variant="primary" size="sm" className="mt-4" onClick={onPreviewBenefits}>
              Preview benefits
            </Button>
          </div>
        ) : (
          <div className="mt-1">
            <div className="text-xs text-[#94a3b8]">Opens after intake</div>
            <Button variant="ghost" size="sm" className="mt-1" onClick={onPreviewBenefits}>
              Preview benefits
            </Button>
          </div>
        )}
      </Station>

      {/* Roadmap */}
      <Station kind={onViewRoadmap ? 'active' : 'locked'} glyph="3" last>
        <div className="flex flex-wrap items-center gap-2">
          <span className={`font-semibold text-sm ${onViewRoadmap ? 'text-[#0b2b43]' : 'text-[#94a3b8]'}`}>Roadmap</span>
          <StatusPill status={onViewRoadmap ? 'ready' : 'upcoming'}>
            {onViewRoadmap ? 'Ready' : 'Locked'}
          </StatusPill>
        </div>
        <div className="mt-1">
          <div className="text-xs text-[#94a3b8]">
            {onViewRoadmap ? 'Your step-by-step relocation roadmap is ready.' : 'Unlocks at the end, after intake.'}
          </div>
          {onViewRoadmap ? (
            <Button variant="primary" size="sm" className="mt-2" onClick={onViewRoadmap}>
              View roadmap
            </Button>
          ) : (
            <Button variant="primary" size="sm" className="mt-2" disabled>
              Locked until intake
            </Button>
          )}
        </div>
      </Station>
    </ul>
  );
};
