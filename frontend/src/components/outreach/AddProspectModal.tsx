import React, { useState } from 'react';
import { Modal, Alert } from '../antigravity';
import type { ProspectInsert } from '../../types/outreach';

interface FormState {
  full_name: string;
  linkedin_url: string;
  profile_headline: string;
  company_name: string;
  company_size: string;
  job_title: string;
  corridor_relevance: string;
  notes: string;
}

const EMPTY: FormState = {
  full_name: '',
  linkedin_url: '',
  profile_headline: '',
  company_name: '',
  company_size: '',
  job_title: '',
  corridor_relevance: '',
  notes: '',
};

const CORRIDOR_OPTIONS = ['FR→NO', 'NO→FR', 'FR→DE', 'DE→FR', 'Unknown'];

interface AddProspectModalProps {
  open: boolean;
  onClose: () => void;
  onSave: (data: ProspectInsert) => Promise<void>;
}

export function AddProspectModal({ open, onClose, onSave }: AddProspectModalProps): React.ReactElement {
  const [form, setForm] = useState<FormState>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (field: keyof FormState) => (value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  const normaliseUrl = (url: string): string => {
    const trimmed = url.trim();
    if (!trimmed) return trimmed;
    return trimmed.startsWith('http') ? trimmed : `https://${trimmed}`;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const linkedin_url = normaliseUrl(form.linkedin_url);
    if (!linkedin_url) { setError('LinkedIn URL is required.'); return; }
    if (!linkedin_url.includes('linkedin.com')) { setError('Please enter a valid LinkedIn profile URL (linkedin.com/in/…).'); return; }
    if (!form.full_name.trim()) { setError('Full name is required.'); return; }
    if (!form.company_name.trim()) { setError('Company name is required.'); return; }
    if (!form.job_title.trim()) { setError('Job title is required.'); return; }

    setSaving(true);
    try {
      const payload: ProspectInsert = {
        full_name: form.full_name.trim(),
        linkedin_url,
        profile_headline: form.profile_headline.trim() || null,
        company_name: form.company_name.trim(),
        company_size: form.company_size.trim() || null,
        job_title: form.job_title.trim(),
        corridor_relevance: form.corridor_relevance || null,
        notes: form.notes.trim() || null,
        source: 'linkedin',
        status: 'flagged',
        message_sent_at: null,
        last_reply_at: null,
        follow_up_sent_at: null,
        converted_at: null,
      };
      await onSave(payload);
      setForm(EMPTY);
      onClose();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to save prospect.';
      setError(
        msg.includes('duplicate') || msg.includes('unique')
          ? 'This LinkedIn profile already exists in your prospect list.'
          : msg
      );
    } finally {
      setSaving(false);
    }
  };

  const handleClose = () => {
    if (saving) return;
    setForm(EMPTY);
    setError(null);
    onClose();
  };

  return (
    <Modal open={open} onClose={handleClose} title="Add prospect" className="w-full max-w-lg">
      <form onSubmit={handleSubmit} className="space-y-4 mt-2">
        {error && <Alert variant="error">{error}</Alert>}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label htmlFor="ap-full-name" className="block text-sm font-medium text-[#374151] mb-1">
              Full name <span className="text-red-500">*</span>
            </label>
            <input
              id="ap-full-name"
              type="text"
              value={form.full_name}
              onChange={(e) => set('full_name')(e.target.value)}
              placeholder="Marie Dupont"
              className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
              required
            />
          </div>

          <div className="sm:col-span-2">
            <label htmlFor="ap-linkedin-url" className="block text-sm font-medium text-[#374151] mb-1">
              LinkedIn URL <span className="text-red-500">*</span>
            </label>
            <input
              id="ap-linkedin-url"
              type="text"
              value={form.linkedin_url}
              onChange={(e) => set('linkedin_url')(e.target.value)}
              placeholder="https://linkedin.com/in/marie-dupont"
              className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
              required
            />
          </div>

          <div className="sm:col-span-2">
            <label htmlFor="ap-headline" className="block text-sm font-medium text-[#374151] mb-1">
              Profile headline
            </label>
            <input
              id="ap-headline"
              type="text"
              value={form.profile_headline}
              onChange={(e) => set('profile_headline')(e.target.value)}
              placeholder="HR Manager at Subsea7"
              className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label htmlFor="ap-company" className="block text-sm font-medium text-[#374151] mb-1">
              Company <span className="text-red-500">*</span>
            </label>
            <input
              id="ap-company"
              type="text"
              value={form.company_name}
              onChange={(e) => set('company_name')(e.target.value)}
              placeholder="Subsea7"
              className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
              required
            />
          </div>

          <div>
            <label htmlFor="ap-company-size" className="block text-sm font-medium text-[#374151] mb-1">
              Company size
            </label>
            <input
              id="ap-company-size"
              type="text"
              value={form.company_size}
              onChange={(e) => set('company_size')(e.target.value)}
              placeholder="50–200 employees"
              className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label htmlFor="ap-job-title" className="block text-sm font-medium text-[#374151] mb-1">
              Job title <span className="text-red-500">*</span>
            </label>
            <input
              id="ap-job-title"
              type="text"
              value={form.job_title}
              onChange={(e) => set('job_title')(e.target.value)}
              placeholder="HR Generalist"
              className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
              required
            />
          </div>

          <div>
            <label htmlFor="ap-corridor" className="block text-sm font-medium text-[#374151] mb-1">
              Corridor
            </label>
            <select
              id="ap-corridor"
              value={form.corridor_relevance}
              onChange={(e) => set('corridor_relevance')(e.target.value)}
              className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm bg-white"
            >
              <option value="">Unknown</option>
              {CORRIDOR_OPTIONS.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          <div className="sm:col-span-2">
            <label htmlFor="ap-notes" className="block text-sm font-medium text-[#374151] mb-1">
              Notes
            </label>
            <textarea
              id="ap-notes"
              value={form.notes}
              onChange={(e) => set('notes')(e.target.value)}
              placeholder="Why this person was flagged, any context…"
              rows={3}
              className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm resize-none"
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={handleClose}
            disabled={saving}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 disabled:opacity-40"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 bg-navy-700 text-white text-sm font-medium rounded-lg hover:bg-navy-800 disabled:opacity-50 transition-colors"
          >
            {saving ? 'Saving…' : 'Add prospect'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
