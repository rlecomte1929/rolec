// case-command-App-updated.tsx
// ReloPass — Stripe Integration v1.0
//
// Shows how the gate wires into Case Command (step 9 of the build sequence).
// The flow is unchanged up to case creation; the change is that the results
// panel now renders INSIDE <CaseGate>, which decides how much is visible.
//
// Diff summary vs. the pre-gate App:
//   + import CaseGate from './CaseGate'
//   + wrap the roadmap render in <CaseGate caseId={...} ...teaser props>
//   (no other behavioral changes)

import { useMemo, useState } from 'react';
import CaseGate from './CaseGate';
import { runRuleEngine, type RuleEngineResult } from './rule-engine';
import { RoadmapView } from './RoadmapView';

interface CaseRecord {
  id: string;
  employeeType: 'eea' | 'non_eea';
  moveDate: string; // ISO date
}

export default function CaseCommandApp() {
  const [activeCase, setActiveCase] = useState<CaseRecord | null>(null);
  const [employeeType, setEmployeeType] = useState<'eea' | 'non_eea'>('eea');
  const [moveDate, setMoveDate] = useState('');
  const [busy, setBusy] = useState(false);

  // The rule engine runs regardless of payment state — the gate only
  // controls how much of its output is VISIBLE.
  const engineResult: RuleEngineResult | null = useMemo(() => {
    if (!activeCase) return null;
    return runRuleEngine({
      corridor: 'france-norway',
      employeeType: activeCase.employeeType,
      moveDate: activeCase.moveDate,
    });
  }, [activeCase]);

  const createCase = async () => {
    if (!moveDate || busy) return;
    setBusy(true);
    try {
      const res = await fetch('/api/relopass/cases', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ employeeType, moveDate, corridor: 'france-norway' }),
      });
      if (!res.ok) throw new Error(`case creation failed: ${res.status}`);
      const data = await res.json();
      setActiveCase({ id: data.caseId, employeeType, moveDate });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="case-command">
      <header className="case-command__header">
        <h1>Case Command — France → Norway</h1>
      </header>

      {/* Step 1-2: the two-input intake (unchanged) */}
      {!activeCase && (
        <form
          className="case-command__intake"
          onSubmit={(e) => {
            e.preventDefault();
            createCase();
          }}
        >
          <label>
            Employee type
            <select
              value={employeeType}
              onChange={(e) => setEmployeeType(e.target.value as 'eea' | 'non_eea')}
            >
              <option value="eea">EEA national</option>
              <option value="non_eea">Non-EEA national</option>
            </select>
          </label>
          <label>
            Target move date
            <input
              type="date"
              value={moveDate}
              onChange={(e) => setMoveDate(e.target.value)}
              required
            />
          </label>
          <button type="submit" disabled={busy || !moveDate}>
            {busy ? 'Creating case…' : 'Check this move'}
          </button>
        </form>
      )}

      {/* Steps 4-8: results, gated. CaseGate renders the teaser while the
          case is at access_tier 'free' and the full roadmap once the €800
          unlock is confirmed server-side. */}
      {activeCase && engineResult && (
        <CaseGate
          caseId={activeCase.id}
          totalRequirements={engineResult.requirements.length}
          nonObviousCount={engineResult.nonObviousCount}
          feasibility={engineResult.feasibility}
          previewRequirements={engineResult.nonObviousPreview.slice(0, 3)}
        >
          <RoadmapView
            requirements={engineResult.requirements}
            feasibility={engineResult.feasibility}
            moveDate={activeCase.moveDate}
          />
        </CaseGate>
      )}
    </div>
  );
}
