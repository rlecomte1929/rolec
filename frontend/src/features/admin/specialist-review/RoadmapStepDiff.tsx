import { Badge, Button } from '../../../components/antigravity';
import {
  REASON_CODE_OPTIONS,
  ReasonCode,
  ReviewDecision,
  confidenceLabel,
  confidenceVariant,
} from './reasonCodes';

export interface AiStep {
  step_id: string;
  title: string;
  description?: string;
  source_url?: string;
  confidence?: number;
  [k: string]: unknown;
}

export interface StepReviewValue {
  decision: ReviewDecision;
  edited?: AiStep;
  reason_code?: ReasonCode;
}

interface Props {
  step: AiStep;
  value: StepReviewValue;
  onChange: (next: StepReviewValue) => void;
}

function changed(original: unknown, override: unknown): boolean {
  return override !== undefined && original !== override;
}

export function RoadmapStepDiff({ step, value, onChange }: Props) {
  const edited = value.edited ?? step;
  const showReason = value.decision === 'edit' || value.decision === 'reject';
  const reasonSelectId = `reason-code-${step.step_id}`;

  const set = (patch: Partial<StepReviewValue>) => onChange({ ...value, ...patch });
  const setEdited = (patch: Partial<AiStep>) =>
    set({ decision: 'edit', edited: { ...edited, ...patch } });

  const titleChanged = changed(step.title, value.edited?.title);

  return (
    <div className="rounded-lg border border-white/10 p-4">
      {/* Header row: confidence badge + source link */}
      <div className="mb-3 flex items-center justify-between gap-2">
        <Badge variant={confidenceVariant(step.confidence)}>
          {confidenceLabel(step.confidence)}
        </Badge>
        {step.source_url && (
          <a
            className="text-sm underline opacity-80 hover:opacity-100"
            href={step.source_url}
            target="_blank"
            rel="noreferrer"
          >
            Source
          </a>
        )}
      </div>

      {/* Side-by-side diff grid */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {/* AI-generated column */}
        <div>
          <p className="mb-1 text-xs uppercase tracking-wide opacity-60">AI generated</p>
          <h4 className="font-semibold">{step.title}</h4>
          {step.description && (
            <p className="mt-1 text-sm opacity-80">{step.description}</p>
          )}
        </div>

        {/* Specialist edit column */}
        <div>
          <p className="mb-1 text-xs uppercase tracking-wide opacity-60">Specialist edit</p>
          <h4
            data-testid="diff-title"
            data-changed={titleChanged}
            className={
              titleChanged
                ? 'rounded bg-amber-500/20 px-1 font-semibold'
                : 'font-semibold'
            }
          >
            <input
              aria-label="Edited title"
              className="w-full bg-transparent outline-none"
              value={edited.title}
              onChange={(e) => setEdited({ title: e.target.value })}
            />
          </h4>
          <textarea
            aria-label="Edited description"
            className="mt-1 w-full bg-transparent text-sm opacity-90 outline-none"
            value={edited.description ?? ''}
            onChange={(e) => setEdited({ description: e.target.value })}
          />
        </div>
      </div>

      {/* Action row */}
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <Button
          variant={value.decision === 'approve' ? 'primary' : 'outline'}
          size="sm"
          onClick={() =>
            set({ decision: 'approve', edited: undefined, reason_code: undefined })
          }
        >
          Approve
        </Button>
        <Button
          variant={value.decision === 'reject' ? 'primary' : 'outline'}
          size="sm"
          onClick={() => set({ decision: 'reject' })}
        >
          Reject
        </Button>

        {/* Reason code selector — rendered as plain label+select so getByLabelText works */}
        {showReason && (
          <div>
            <label
              htmlFor={reasonSelectId}
              className="block text-sm font-medium text-[#374151] mb-1"
            >
              Reason code
            </label>
            <select
              id={reasonSelectId}
              value={value.reason_code ?? ''}
              onChange={(e) => set({ reason_code: e.target.value as ReasonCode })}
              className="px-4 py-2 border border-[#d1d5db] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0b2b43] transition-all bg-white"
            >
              <option value="">Select reason…</option>
              {REASON_CODE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
    </div>
  );
}
