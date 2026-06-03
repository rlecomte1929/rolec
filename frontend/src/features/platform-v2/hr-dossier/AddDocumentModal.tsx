/**
 * [P4-3] AddDocumentModal — attach an ad-hoc document to a case.
 *
 * Opens from the HR Dossier panel's "+ Add document" button. Creates a
 * template-less CaseForm (is_adhoc=true) via adhocFormsAPI.create.
 *
 * Fields: name [required], authority, for-person select, deadline date,
 *         optional PDF upload, notes textarea.
 */
import React, { useState } from 'react';
import { Button } from '../../../components/antigravity';
import { adhocFormsAPI } from '../../../api/dossier';

export interface AddDocumentPersonOption {
  /** person_id sent to the backend (profile_id for employee/HR rows) */
  id: string;
  label: string;
}

export interface AddDocumentModalProps {
  caseId: string;
  /** Optional list of people to scope the document to (employee + dependents). */
  people?: AddDocumentPersonOption[];
  onClose: () => void;
  /** Called after a successful create so the parent can refresh the list. */
  onCreated: () => void;
}

export const AddDocumentModal: React.FC<AddDocumentModalProps> = ({
  caseId,
  people = [],
  onClose,
  onCreated,
}) => {
  const [name, setName] = useState('');
  const [authority, setAuthority] = useState('');
  const [personId, setPersonId] = useState('');
  const [deadline, setDeadline] = useState('');
  const [notes, setNotes] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError('Document name is required.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await adhocFormsAPI.create(caseId, {
        name: name.trim(),
        authority: authority.trim() || null,
        personId: personId || null,
        deadline: deadline || null,
        notes: notes.trim() || null,
        file,
      });
      onCreated();
      onClose();
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setError(err.response?.data?.detail || err.message || 'Failed to add document.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6 space-y-4">
        <div>
          <h2 className="text-base font-semibold text-slate-900">Add document</h2>
          <p className="text-sm text-slate-500 mt-1">
            Attach a custom document that isn't part of the standard form set.
          </p>
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Document name <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Apostilled birth certificate"
              autoFocus
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0b2b43]"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Issuing authority</label>
            <input
              type="text"
              value={authority}
              onChange={(e) => setAuthority(e.target.value)}
              placeholder="e.g. Town hall"
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0b2b43]"
            />
          </div>

          {people.length > 0 && (
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">For person</label>
              <select
                value={personId}
                onChange={(e) => setPersonId(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#0b2b43]"
              >
                <option value="">— Not specified —</option>
                {people.map((p) => (
                  <option key={p.id} value={p.id}>{p.label}</option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Deadline</label>
            <input
              type="date"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0b2b43]"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">PDF (optional)</label>
            <input
              type="file"
              accept="application/pdf"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="w-full text-sm text-slate-600 file:mr-3 file:rounded file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-slate-700 hover:file:bg-slate-200"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Internal notes for this document…"
              rows={3}
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-[#0b2b43]"
            />
          </div>
        </div>

        {error && <p className="text-xs text-rose-600">{error}</p>}

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button variant="primary" onClick={() => void handleSubmit()} disabled={submitting || !name.trim()}>
            {submitting ? 'Adding…' : 'Add document'}
          </Button>
        </div>
      </div>
    </div>
  );
};
