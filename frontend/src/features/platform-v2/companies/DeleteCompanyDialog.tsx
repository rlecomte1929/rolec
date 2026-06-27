import { useEffect, useRef, useState } from 'react';
import { Input } from '../../../components/antigravity/Input';
import { Button } from '../../../components/antigravity/Button';
import { adminAPI } from '../../../api/client';
import type { CompanyV2 } from './adapter';

interface DeleteCompanyDialogProps {
  company: CompanyV2;
  onClose: () => void;
  onDeleted: () => void;
}

/**
 * Hard-delete confirmation. Requires the operator to type the company
 * name verbatim to enable the destructive button — guards against
 * mis-clicks. The wording calls out that delete is irreversible AND
 * may orphan references in employees/hr_users/cases tables (the
 * backend's deleteCompany docstring explicitly warns about this).
 *
 * For "soft-delete-with-undo" semantics, prefer Archive instead — this
 * dialog is for the rare case where a row truly needs to be removed
 * from the companies table (e.g. typo, test data, GDPR erasure).
 */
export function DeleteCompanyDialog({ company, onClose, onDeleted }: DeleteCompanyDialogProps) {
  const [typed, setTyped] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Focus the confirm input on open so the operator can start typing
    // immediately instead of clicking through.
    const t = setTimeout(() => inputRef.current?.focus(), 50);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && !submitting) onClose();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, submitting]);

  const canConfirm = typed === company.name && !submitting;

  async function handleConfirm() {
    if (!canConfirm) return;
    setError(null);
    setSubmitting(true);
    try {
      await adminAPI.deleteCompany(company.id);
      onDeleted();
    } catch (e) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        (e as Error)?.message ??
        'Failed to delete company';
      setError(detail);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
      onClick={(e) => { if (e.target === e.currentTarget && !submitting) onClose(); }}
      onKeyDown={(e) => { if (e.key === 'Escape' && !submitting) onClose(); }}
      role="button"
      tabIndex={-1}
      aria-label="Close dialog"
    >
      <div
        className="w-full max-w-md rounded-xl bg-white shadow-2xl"
        role="dialog"
        aria-label={`Delete ${company.name}`}
      >
        <div className="border-b border-slate-200 px-6 py-4">
          <h2 className="text-base font-semibold text-rose-700">Delete company — irreversible</h2>
        </div>

        <div className="space-y-4 px-6 py-5 text-sm">
          <p className="text-slate-700">
            You're about to <strong>hard-delete</strong>{' '}
            <span className="font-mono text-slate-900">{company.name}</span>. This action is
            irreversible and may orphan references in employees / HR users / cases.
          </p>

          <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            Consider <strong>Archive</strong> instead — same outcome from the user's perspective,
            but reversible.
          </div>

          <label className="block">
            <div className="mb-1 text-[11px] font-semibold uppercase tracking-widest text-slate-500">
              Type <span className="font-mono text-slate-900">{company.name}</span> to confirm
            </div>
            <Input unstyled
              ref={inputRef}
              value={typed}
              onChange={(v) => setTyped(v)}
              placeholder={company.name}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500"
              autoComplete="off"
              spellCheck={false}
            />
          </label>

          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-slate-200 px-6 py-3">
          <Button unstyled
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Cancel
          </Button>
          <Button unstyled
            type="button"
            onClick={() => void handleConfirm()}
            disabled={!canConfirm}
            className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-50"
          >
            {submitting ? 'Deleting…' : 'Delete permanently'}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default DeleteCompanyDialog;
