import React, { useMemo, useState } from 'react';
import { trackReliefMomentCaptured } from '../../analyticsEvents';

export interface ReliefNonObviousItem {
  id: string;
  text: string;
}

export interface ReliefMomentCaptureProps {
  caseId: string;
  corridorId: string;
  items: ReliefNonObviousItem[];
}

const storageKey = (caseId: string) => `relopass.relief_moment.${caseId}`;

export const ReliefMomentCapture: React.FC<ReliefMomentCaptureProps> = ({
  caseId,
  corridorId,
  items,
}) => {
  const already = useMemo(() => {
    try {
      return window.localStorage.getItem(storageKey(caseId)) === '1';
    } catch {
      return false;
    }
  }, [caseId]);

  const [step, setStep] = useState<1 | 2 | 3 | 'done'>(already ? 'done' : 1);
  const [itemId, setItemId] = useState('');
  const [comment, setComment] = useState('');

  if (step === 'done') return null;

  const finish = (yes: boolean, surprisingId: string | null) => {
    const picked = items.find((i) => i.id === surprisingId) ?? null;
    trackReliefMomentCaptured({
      corridor_id: corridorId,
      case_id: caseId,
      response_yes_no: yes,
      surprising_item_id: surprisingId,
      surprising_item_text: picked?.text ?? null,
    });
    try {
      window.localStorage.setItem(storageKey(caseId), '1');
    } catch {
      /* ignore */
    }
    setStep('done');
  };

  return (
    <section
      className="mt-6 rounded-2xl border border-slate-200 bg-white p-5"
      data-testid="relief-moment-capture"
    >
      <h2 className="text-[15px] font-semibold text-navy-800">Was anything here new?</h2>
      {step === 1 && (
        <div className="mt-3 flex flex-wrap gap-2">
          <p className="w-full text-sm text-slate-600">
            Was there anything in this roadmap you didn&rsquo;t already know?
          </p>
          <button
            type="button"
            className="rounded-lg bg-navy-700 px-4 py-2 text-sm font-semibold text-white"
            onClick={() => (items.length > 0 ? setStep(2) : finish(true, null))}
          >
            Yes
          </button>
          <button
            type="button"
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-navy-800"
            onClick={() => finish(false, null)}
          >
            No
          </button>
        </div>
      )}
      {step === 2 && (
        <div className="mt-3 space-y-3">
          <label className="block text-sm text-slate-600" htmlFor="relief-item">
            Which item was most surprising?
          </label>
          <select
            id="relief-item"
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            value={itemId}
            onChange={(e) => setItemId(e.target.value)}
          >
            <option value="">Select one</option>
            {items.map((item) => (
              <option key={item.id} value={item.id}>
                {item.text}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="rounded-lg bg-navy-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            disabled={!itemId}
            onClick={() => setStep(3)}
          >
            Continue
          </button>
        </div>
      )}
      {step === 3 && (
        <div className="mt-3 space-y-3">
          <label className="block text-sm text-slate-600" htmlFor="relief-comment">
            Any comment on this flag? (optional, not sent to analytics)
          </label>
          <textarea
            id="relief-comment"
            maxLength={280}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            rows={3}
          />
          <button
            type="button"
            className="rounded-lg bg-navy-700 px-4 py-2 text-sm font-semibold text-white"
            onClick={() => finish(true, itemId)}
          >
            Submit
          </button>
        </div>
      )}
    </section>
  );
};
