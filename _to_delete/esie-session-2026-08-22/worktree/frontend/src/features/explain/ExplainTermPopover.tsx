/**
 * ExplainTermPopover (I-6) — anchored popover that explains a selected term by
 * calling the existing policy-assistant answer endpoint (company-scoped
 * server-side). The user selects text on the roadmap; this offers an "Explain"
 * action and renders the grounded answer.
 */
import { useState } from 'react';
import { Button } from '../../components/antigravity/Button';
import { employeeAPI } from '../../api/client';
import type { TextSelection } from '../../hooks/useTextSelection';

export interface ExplainTermPopoverProps {
  selection: TextSelection;
  /** Case/assignment id — echoed by the endpoint; answer scope is server-derived. */
  assignmentId: string;
  onClose: () => void;
}

type State =
  | { phase: 'idle' }
  | { phase: 'loading' }
  | { phase: 'answer'; text: string; citations: number }
  | { phase: 'error' };

export function ExplainTermPopover({ selection, assignmentId, onClose }: ExplainTermPopoverProps) {
  const [state, setState] = useState<State>({ phase: 'idle' });

  const explain = async () => {
    setState({ phase: 'loading' });
    try {
      const res = await employeeAPI.postPolicyAssistantQuery(
        assignmentId,
        `Explain the term "${selection.text}" in the context of my relocation, in one or two plain sentences.`,
      );
      const answer = res.answer;
      const text = answer?.refusal?.refusal_text || answer?.answer_text || 'No explanation available.';
      setState({ phase: 'answer', text, citations: answer?.cited_chunks?.length ?? 0 });
    } catch {
      setState({ phase: 'error' });
    }
  };

  // Anchor below the selection, clamped to the viewport.
  const width = 320;
  const left = Math.max(
    8,
    Math.min(selection.rect.left, (typeof window !== 'undefined' ? window.innerWidth : 1024) - width - 8),
  );
  const top = selection.rect.bottom + 8;

  return (
    <div
      role="dialog"
      aria-label={`Explain ${selection.text}`}
      style={{
        position: 'fixed',
        top,
        left,
        width,
        zIndex: 1000,
        background: 'var(--surface, #fff)',
        border: '1px solid var(--border-subtle, #e2e8f0)',
        borderRadius: 'var(--radius-lg, 12px)',
        boxShadow: 'var(--shadow-lg, 0 10px 30px rgba(0,0,0,0.15))',
        padding: '14px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: '8px' }}>
        <p style={{ margin: 0, fontSize: '13px', fontWeight: 600, color: 'var(--text, #0b2b43)' }}>
          “{selection.text}”
        </p>
        <Button unstyled type="button" aria-label="Close" onClick={onClose}
          style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--text-muted, #64748b)', fontSize: '16px', lineHeight: 1 }}>
          ×
        </Button>
      </div>

      {state.phase === 'idle' && (
        <div style={{ marginTop: '10px' }}>
          <Button variant="secondary" size="sm" onClick={explain}>✨ Explain this term</Button>
        </div>
      )}
      {state.phase === 'loading' && (
        <p style={{ margin: '10px 0 0', fontSize: '13px', color: 'var(--text-muted, #64748b)' }}>Explaining…</p>
      )}
      {state.phase === 'answer' && (
        <div style={{ marginTop: '10px' }}>
          <p style={{ margin: 0, fontSize: '13px', color: 'var(--text, #0b2b43)', lineHeight: 1.5 }}>{state.text}</p>
          {state.citations > 0 && (
            <p style={{ margin: '8px 0 0', fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
              Grounded in {state.citations} policy citation{state.citations === 1 ? '' : 's'}.
            </p>
          )}
        </div>
      )}
      {state.phase === 'error' && (
        <p role="alert" style={{ margin: '10px 0 0', fontSize: '13px', color: 'var(--danger, #e53e3e)' }}>
          Couldn’t explain that just now. Please try again.
        </p>
      )}
    </div>
  );
}

export default ExplainTermPopover;
