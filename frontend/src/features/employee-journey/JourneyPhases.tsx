import React from 'react';
import { Card, Button, StatusPill } from '../../components/antigravity';
import type { JourneyStatus } from '../../components/antigravity';

interface JourneyPhasesProps {
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

const HomeIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M3 9.5 12 3l9 6.5" />
    <path d="M5 10v10h14V10" />
    <path d="M9 20v-6h6v6" />
  </svg>
);

const BriefcaseIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="3" y="7" width="18" height="13" rx="2" />
    <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    <path d="M3 12h18" />
  </svg>
);

const RouteIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="6" cy="19" r="2.5" />
    <circle cx="18" cy="5" r="2.5" />
    <path d="M8.5 19H15a3 3 0 0 0 0-6H9a3 3 0 0 1 0-6h6.5" />
  </svg>
);

function intakeState(step: number, total: number): IntakeState {
  if (total > 0 && step >= total) return 'done';
  if (step > 0) return 'in-progress';
  return 'not-started';
}

const PhaseCard: React.FC<{
  icon: React.ReactNode;
  title: string;
  pill: { status: JourneyStatus; label: string };
  active?: boolean;
  children: React.ReactNode;
}> = ({ icon, title, pill, active = false, children }) => (
  <Card
    padding="md"
    className={`flex-1 min-w-0 flex flex-col gap-3 ${
      active ? 'ring-2 ring-[#1f8e8b] border-[#1f8e8b]' : ''
    }`}
  >
    <div className="flex items-center justify-between gap-2">
      <div className="flex items-center gap-2 text-[#0b2b43]">
        <span className="text-[#1f8e8b]">{icon}</span>
        <span className="font-semibold">{title}</span>
      </div>
      <StatusPill status={pill.status}>{pill.label}</StatusPill>
    </div>
    <div className="flex flex-col gap-3 flex-1">{children}</div>
  </Card>
);

export const JourneyPhases: React.FC<JourneyPhasesProps> = ({
  intakeStep,
  intakeTotalSteps,
  onContinueIntake,
  onPreviewBenefits,
  onViewRoadmap,
}) => {
  const state = intakeState(intakeStep, intakeTotalSteps);
  const intakeStarted = state === 'in-progress';

  const intakePill: { status: JourneyStatus; label: string } =
    state === 'done'
      ? { status: 'done', label: 'Done' }
      : state === 'in-progress'
        ? { status: 'in-progress', label: 'In progress' }
        : { status: 'upcoming', label: 'Not started' };

  const intakeCtaLabel =
    state === 'done' ? 'Review intake' : state === 'in-progress' ? 'Continue intake' : 'Start intake';

  const progressPct =
    intakeTotalSteps > 0 ? Math.min(100, Math.round((intakeStep / intakeTotalSteps) * 100)) : 0;

  return (
    <div className="flex flex-col md:flex-row gap-4">
      {/* Phase 1 — Intake */}
      <PhaseCard
        icon={<HomeIcon />}
        title="Intake"
        pill={intakePill}
        active={state !== 'done'}
      >
        <p className="text-sm text-[#4b5563] flex-1">
          Tell us about your move so we can tailor your benefits and roadmap.
        </p>
        {intakeStarted ? (
          <div>
            <div className="text-xs font-medium text-[#0b2b43] mb-1">
              Step {intakeStep} of {intakeTotalSteps}
            </div>
            <div className="h-1.5 w-full rounded-full bg-[#e2e8f0] overflow-hidden">
              <div className="h-full rounded-full bg-[#1f8e8b]" style={{ width: `${progressPct}%` }} />
            </div>
          </div>
        ) : null}
        <Button variant="primary" size="sm" onClick={onContinueIntake}>
          {intakeCtaLabel}
        </Button>
      </PhaseCard>

      {/* Phase 2 — Services & policy */}
      <PhaseCard
        icon={<BriefcaseIcon />}
        title="Services & policy"
        pill={{ status: 'upcoming', label: 'Up next' }}
      >
        <p className="text-sm text-[#4b5563] flex-1">
          See the services and budget your policy covers for this move.
        </p>
        <Button variant="ghost" size="sm" onClick={onPreviewBenefits}>
          Preview benefits
        </Button>
      </PhaseCard>

      {/* Phase 3 — Roadmap */}
      <PhaseCard
        icon={<RouteIcon />}
        title="Roadmap"
        pill={
          onViewRoadmap
            ? { status: 'ready', label: 'Ready' }
            : { status: 'upcoming', label: 'Locked' }
        }
      >
        <p className="text-sm text-[#4b5563] flex-1">
          {onViewRoadmap
            ? 'Your step-by-step relocation roadmap is ready.'
            : 'Unlocks after intake.'}
        </p>
        {onViewRoadmap ? (
          <Button variant="primary" size="sm" onClick={onViewRoadmap}>
            View roadmap
          </Button>
        ) : (
          <Button variant="primary" size="sm" disabled>
            Locked until intake
          </Button>
        )}
      </PhaseCard>
    </div>
  );
};
