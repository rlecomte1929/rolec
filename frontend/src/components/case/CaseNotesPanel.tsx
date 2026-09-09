import { useEffect, useState } from 'react';
import { Card, Button, Alert } from '../antigravity';
import { loadErrorMessage } from '../LoadErrorBanner';
import { listCaseNotes, addCaseNote, type CaseNote } from '../../api/caseNotes';

/**
 * [AIQ-1136 / NAV-HR-2-FU] Internal notes on a case. HR can read + append notes
 * in context. Append-only (POST creates; the list is read-only) and company-scoped
 * server-side.
 */
function formatTs(iso?: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('en-GB', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function CaseNotesPanel({ caseId }: { caseId: string }) {
  const [notes, setNotes] = useState<CaseNote[] | null>(null);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setNotes(null);
    setError(null);
    listCaseNotes(caseId)
      .then((n) => {
        if (!cancelled) {
          setNotes(n);
          setError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setNotes([]);
          setError(loadErrorMessage(e, 'Could not load notes.'));
        }
      });
    return () => { cancelled = true; };
  }, [caseId]);

  const submit = async () => {
    const body = draft.trim();
    if (!body) return;
    setSaving(true);
    setError(null);
    try {
      const created = await addCaseNote(caseId, body);
      setNotes((prev) => [created, ...(prev ?? [])]);
      setDraft('');
    } catch {
      setError('Could not save the note. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card padding="lg" className="border border-[#e2e8f0]">
      <div className="mb-3">
        <h3 className="text-[15px] font-semibold text-[#0b2b43]">Internal notes</h3>
        <p className="text-xs text-slate-500">HR-only notes on this case. Visible to your company; append-only.</p>
      </div>

      <div className="mb-4">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={2}
          maxLength={4000}
          placeholder="Add a note for your team…"
          className="w-full rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43] focus:border-[#0b2b43] focus:outline-none focus:ring-1 focus:ring-[#0b2b43]"
          disabled={saving}
        />
        {error && (
          <div className="mt-2">
            <Alert variant="error">{error}</Alert>
          </div>
        )}
        <div className="mt-2 flex justify-end">
          <Button onClick={submit} disabled={saving || !draft.trim()}>
            {saving ? 'Saving…' : 'Add note'}
          </Button>
        </div>
      </div>

      {notes === null ? (
        <div className="text-sm text-slate-500">Loading notes…</div>
      ) : notes.length === 0 && !error ? (
        <div className="text-sm text-slate-500">No notes yet.</div>
      ) : notes.length > 0 ? (
        <ul className="space-y-3">
          {notes.map((n) => (
            <li key={n.id} className="rounded-lg border border-slate-100 bg-slate-50/60 px-3 py-2">
              <div className="whitespace-pre-wrap text-sm text-[#0b2b43]">{n.body}</div>
              <div className="mt-1 text-[11px] text-slate-500">
                {n.author_name || n.author_user_id} · {formatTs(n.created_at)}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}
