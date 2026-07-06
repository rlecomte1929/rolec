import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Card } from '../../components/antigravity/Card';
import { MessageInput } from '../messages/MessageInput';
import { coordinatorAPI, type CoordinatorTurn } from '../../api/coordinator';

/**
 * AIQ-1414 Phase 4 — per-case Mobility Coordinator chat panel, shared by HR and the
 * assigned employee. Loads the persisted session (GET) and sends turns (POST). The
 * backend `recent_turns` are stored as {user, assistant} pairs, flattened here into one
 * bubble each. Self-hides when the feature is unavailable (API 404). Reuses the Messages
 * `MessageInput` composer; bubbles are rendered locally to avoid coupling to the
 * messaging `Conversation` type.
 */

type ChatMsg = { role: 'user' | 'assistant'; content: string };

export function flattenTurns(turns: CoordinatorTurn[] | undefined): ChatMsg[] {
  const out: ChatMsg[] = [];
  for (const t of turns || []) {
    if (t?.user) out.push({ role: 'user', content: t.user });
    if (t?.assistant) out.push({ role: 'assistant', content: t.assistant });
  }
  return out;
}

interface Props {
  caseId: string;
}

export const CoordinatorChatPanel: React.FC<Props> = ({ caseId }) => {
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [summary, setSummary] = useState('');
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    coordinatorAPI
      .getSession(caseId)
      .then((s) => {
        if (!alive) return;
        setMsgs(flattenTurns(s.recent_turns));
        setSummary(s.rolling_summary || '');
      })
      .catch((e: { status?: number }) => {
        if (!alive) return;
        if (e?.status === 404) setUnavailable(true);
        else setError('Could not load the coordinator.');
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [caseId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth' });
  }, [msgs, sending]);

  const handleSend = useCallback(
    (text: string) => {
      setError(null);
      setMsgs((m) => [...m, { role: 'user', content: text }]);
      setSending(true);
      coordinatorAPI
        .respond(caseId, text)
        .then((r) => setMsgs((m) => [...m, { role: 'assistant', content: r.answer }]))
        .catch((e: { status?: number }) => {
          if (e?.status === 429) setError('You’re sending messages too quickly — give it a moment.');
          else setError('The coordinator could not respond. Try again.');
        })
        .finally(() => setSending(false));
    },
    [caseId],
  );

  if (unavailable) return null;

  return (
    <Card padding="lg" className="border border-[#e2e8f0]">
      <div className="mb-3 flex items-center gap-2">
        <span className="text-lg" aria-hidden>
          🤖
        </span>
        <h3 className="text-[15px] font-semibold text-[#0b2b43]">Mobility Coordinator</h3>
      </div>

      {summary && (
        <p className="mb-3 rounded-lg bg-[#f8fafc] p-3 text-[13px] text-[#475569]">{summary}</p>
      )}

      <div className="max-h-80 space-y-2 overflow-y-auto pr-1" aria-live="polite">
        {loading && <p className="text-[13px] text-[#94a3b8]">Loading…</p>}
        {!loading && msgs.length === 0 && (
          <p className="text-[13px] text-[#94a3b8]">
            Ask the coordinator about this relocation — visa steps, housing, timelines, or the next best action.
          </p>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
            <div
              className={
                'max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-[14px] ' +
                (m.role === 'user' ? 'bg-[#0b2b43] text-white' : 'bg-[#f1f5f9] text-[#1A1A1A]')
              }
            >
              {m.content}
            </div>
          </div>
        ))}
        {sending && <p className="text-[13px] text-[#94a3b8]">Coordinator is thinking…</p>}
        <div ref={bottomRef} />
      </div>

      {error && <p className="mt-2 text-[13px] text-[#b91c1c]">{error}</p>}

      <div className="mt-2">
        <MessageInput onSend={handleSend} disabled={sending} placeholder="Ask the coordinator…" />
      </div>
    </Card>
  );
};

export default CoordinatorChatPanel;
