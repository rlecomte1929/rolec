import React from 'react';
import { Alert } from '../../../components/antigravity/Alert';
import type { RoadmapV2Advisory } from '../../../api/roadmapV2';

/**
 * [AIQ-1867 follow-up] The corridor's non-obvious traps, on the roadmap.
 *
 * These are the facts the whole corridor asset exists for — "a Spanish residence card gives
 * you no right to enter Ireland", "the employment permit is not immigration permission" —
 * and until now the backend computed them and no component read them.
 *
 * **The `asserted` flag decides the wording, and getting it wrong is the whole risk here.**
 * An advisory with `asserted: false` rests on an input the platform does not hold: the ES→IE
 * pathway declares `visa_required_nationality` as an `EXTERNAL_LOOKUP` against a table that
 * does not exist in this codebase. Telling someone "you are a visa-required national" on the
 * strength of a missing lookup would be inventing the fact that decides whether they can
 * board a plane. So an unasserted advisory is framed as something to confirm, and points at
 * the register that really holds the answer; only a resolved one is stated plainly.
 *
 * Provenance is shown, not hidden. The corridor files describe themselves as REPRESENTATIVE
 * and not SME-verified, and that caveat has to survive all the way to the reader — the same
 * reason `verified` renders as "Reviewed" and not "Expert-verified" elsewhere in the app.
 */

const CHECK_THIS = 'Worth checking';
const APPLIES = 'Applies to your move';

export const CorridorAdvisories: React.FC<{ advisories?: RoadmapV2Advisory[] }> = ({
  advisories,
}) => {
  const items = advisories ?? [];
  if (items.length === 0) return null;

  const representative = items.some(
    (a) => a.provenance?.verification === 'representative',
  );

  return (
    <section
      className="mb-4 space-y-3"
      data-testid="corridor-advisories"
      aria-label="Things people miss on this route"
    >
      <h2 className="text-sm font-semibold text-slate-900">
        Things people miss on this route
      </h2>

      {items.map((a) => (
        <Alert
          key={a.id}
          variant={a.asserted ? 'info' : 'warning'}
          title={a.asserted ? APPLIES : CHECK_THIS}
          className={a.asserted ? 'advisory-asserted' : 'advisory-conditional'}
        >
          <p data-testid={`advisory-${a.id}`}>{a.text}</p>
        </Alert>
      ))}

      {representative && (
        <p className="text-xs text-slate-500" data-testid="corridor-advisory-provenance">
          Based on published official sources for this route and reviewed internally. This is
          general information about the route, not legal advice about your case.
        </p>
      )}
    </section>
  );
};
