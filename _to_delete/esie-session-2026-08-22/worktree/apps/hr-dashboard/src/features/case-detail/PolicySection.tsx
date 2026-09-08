import { EmptyState } from '../../components/EmptyState';

// TODO [C2-06]: Replace this placeholder with the gap detector view —
// reads corridor.requirements and the case's known facts, surfaces
// missing documents / unmet eligibility criteria. The gap-detector
// data shape lives in backend/relopass/agents/gap_detector.py (TBD).

/**
 * Policy section — Cohort 2 (C2-06) gap detector ships here.
 *
 * C1-11c leaves the placeholder so the navigation surface is complete
 * and the C2-06 engineer has an explicit insertion point. The TODO
 * comment above is intentional: it grep's into the dependency planning
 * skill and the C2-06 brief's "Files to touch" list.
 */
export function PolicySection(): JSX.Element {
  return (
    <section aria-labelledby="section-title-Policy" className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h2 id="section-title-Policy" className="text-xl font-semibold text-foreground">
          Policy
        </h2>
        <p className="text-sm text-muted-foreground">
          Corridor entitlements + missing-evidence gaps. Lands with C2-06.
        </p>
      </header>
      <EmptyState
        title="Policy gap detector lands with C2-06"
        description="This section will surface the corridor's required documents that the case is missing, plus eligibility gaps detected by the requirement evaluator. Anchor reserved so the C2-06 PR can drop in without touching the layout."
      />
    </section>
  );
}
