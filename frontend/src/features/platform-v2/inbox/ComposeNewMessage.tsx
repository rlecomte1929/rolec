/**
 * ComposeNewMessage — modal for starting a brand-new HR↔employee message thread
 * from the inbox "New" button (AIQ-1326).
 *
 * A "thread" is one-per-assignment, so composing a new message = picking a
 * recipient (an assignment) and POSTing the first message to the EXISTING send
 * endpoints shipped by AIQ-1313 (hrAPI/employeeAPI.sendMessage(assignmentId, body)).
 * No new backend/thread model is involved — the send endpoint keys on assignment_id
 * and works even when the assignment has no prior messages.
 *
 * Recipients:
 *  - HR: the company's assignments (employees) via hrAPI.listAssignments() —
 *    includes employees with no existing thread (the whole point). Company-scoped
 *    server-side, and the send endpoint re-checks (403), so cross-company is impossible.
 *  - Employee: their linked assignment(s) → recipient is "HR".
 *
 * Accessibility (WCAG 2.1 AA) is handled by the shared antigravity <Modal>
 * (role="dialog", aria-modal, aria-labelledby, focus-in/trap, Esc-to-close,
 * focus restore on close).
 */
import { useCallback, useEffect, useState } from 'react';
import { Send } from 'lucide-react';
import { Modal } from '../../../components/antigravity/Modal';
import { Select } from '../../../components/antigravity/Select';
import { Button } from '../../../components/antigravity/Button';
import { hrAPI, employeeAPI } from '../../../api/client';
import type { AssignmentSummary } from '../../../types';

interface RecipientOption {
  value: string; // assignment_id
  label: string;
}

interface ComposeNewMessageProps {
  open: boolean;
  isHr: boolean;
  onClose: () => void;
  /** Fired after a successful send so the parent can refresh + select the thread. */
  onSent: (assignmentId: string) => void;
}

function hrRecipientLabel(a: AssignmentSummary): string {
  const name =
    [a.employeeFirstName, a.employeeLastName].filter(Boolean).join(' ').trim() ||
    a.employeeIdentifier ||
    'Employee';
  const route =
    a.case?.home_country && a.case?.host_country
      ? ` · ${a.case.home_country} → ${a.case.host_country}`
      : '';
  return `${name}${route}`;
}

export function ComposeNewMessage({ open, isHr, onClose, onSent }: ComposeNewMessageProps) {
  const [recipients, setRecipients] = useState<RecipientOption[]>([]);
  const [loadingRecipients, setLoadingRecipients] = useState(false);
  const [recipientError, setRecipientError] = useState<string | null>(null);
  const [selected, setSelected] = useState('');
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  // Load recipients each time the modal opens.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoadingRecipients(true);
    setRecipientError(null);
    setSendError(null);
    void (async () => {
      try {
        let opts: RecipientOption[] = [];
        if (isHr) {
          const res = await hrAPI.listAssignments({ limit: 100 });
          opts = (res.assignments || [])
            .map((a) => ({ value: a.id, label: hrRecipientLabel(a) }))
            .filter((o) => o.value);
        } else {
          const overview = await employeeAPI.getAssignmentsOverview();
          type LinkedRow = { assignment_id?: string; company?: { name?: string } };
          opts = ((overview.linked as LinkedRow[]) || [])
            .map((r) => ({
              value: r.assignment_id || '',
              label: `HR${r.company?.name ? ` · ${r.company.name}` : ''}`,
            }))
            .filter((o) => o.value);
        }
        if (cancelled) return;
        setRecipients(opts);
        // Auto-select when there is exactly one recipient (the common employee case).
        setSelected(opts.length === 1 ? opts[0]!.value : '');
      } catch {
        if (!cancelled) {
          setRecipientError(
            isHr ? 'Could not load your employees.' : 'Could not load your HR contact.'
          );
        }
      } finally {
        if (!cancelled) setLoadingRecipients(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, isHr]);

  // Reset transient fields when the modal closes.
  useEffect(() => {
    if (open) return;
    setBody('');
    setSelected('');
    setSendError(null);
  }, [open]);

  const canSend = !!selected && !!body.trim() && !sending;

  const handleSend = useCallback(async () => {
    const text = body.trim();
    if (!selected || !text) return;
    setSending(true);
    setSendError(null);
    try {
      const send = isHr ? hrAPI.sendMessage : employeeAPI.sendMessage;
      await send(selected, text);
      onSent(selected);
      onClose();
    } catch {
      setSendError("Couldn't send your message. Please try again.");
    } finally {
      setSending(false);
    }
  }, [selected, body, isHr, onSent, onClose]);

  const recipientLabel = isHr ? 'To (employee)' : 'To';

  return (
    <Modal open={open} onClose={onClose} title="New message">
      <div className="space-y-4">
        {recipientError ? (
          <p className="text-sm text-rose-600" role="alert">
            {recipientError}
          </p>
        ) : loadingRecipients ? (
          <p className="text-sm text-slate-400">Loading recipients…</p>
        ) : recipients.length === 0 ? (
          <p className="text-sm text-slate-500">
            {isHr
              ? 'No assigned employees to message yet. Create a case and assign an employee first.'
              : 'No HR contact is linked to your case yet.'}
          </p>
        ) : (
          <>
            {recipients.length === 1 ? (
              // Single recipient: show it read-only instead of a one-option dropdown.
              <div>
                <span className="mb-1 block text-sm font-medium text-slate-700">{recipientLabel}</span>
                <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800">
                  {recipients[0]!.label}
                </p>
              </div>
            ) : (
              <Select
                label={recipientLabel}
                value={selected}
                onChange={setSelected}
                options={recipients}
                placeholder="Select a recipient…"
              />
            )}

            <div>
              <label htmlFor="compose-new-body" className="mb-1 block text-sm font-medium text-slate-700">
                Message
              </label>
              <textarea
                id="compose-new-body"
                value={body}
                onChange={(e) => setBody(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                    e.preventDefault();
                    void handleSend();
                  }
                }}
                rows={5}
                placeholder="Write your message…"
                className="w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none"
              />
            </div>

            {sendError && (
              <p className="text-xs text-red-500" role="alert">
                {sendError}
              </p>
            )}

            <div className="flex items-center justify-end gap-2 pt-1">
              <Button
                unstyled
                type="button"
                onClick={onClose}
                className="inline-flex items-center rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </Button>
              <Button
                unstyled
                type="button"
                onClick={handleSend}
                disabled={!canSend}
                className="inline-flex items-center gap-1.5 rounded-lg bg-navy-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-navy-900 disabled:opacity-50"
              >
                <Send className="h-3.5 w-3.5" />
                {sending ? 'Sending…' : 'Send'}
              </Button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}

export default ComposeNewMessage;
