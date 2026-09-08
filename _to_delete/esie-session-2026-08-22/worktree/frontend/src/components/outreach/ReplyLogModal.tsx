import React, { useState } from 'react';
import { Modal, Alert, Textarea } from '../antigravity';
import type { ReplyInsert, Sentiment } from '../../types/outreach';

interface ReplyLogModalProps {
  open: boolean;
  onClose: () => void;
  prospectId: string;
  messageId: string | null;
  onSave: (data: ReplyInsert) => Promise<void>;
}

const SENTIMENTS: { value: Sentiment; label: string; className: string }[] = [
  { value: 'positive',  label: 'Positive',  className: 'border-green-400 bg-green-50 text-green-700' },
  { value: 'neutral',   label: 'Neutral',   className: 'border-gray-300 bg-gray-50 text-gray-700' },
  { value: 'negative',  label: 'Negative',  className: 'border-red-300 bg-red-50 text-red-700' },
  { value: 'not_set',   label: 'Not sure',  className: 'border-gray-200 bg-white text-gray-500' },
];

const EMPTY = { reply_text: '', sentiment: 'not_set' as Sentiment, next_action: '', next_action_due: '' };

export function ReplyLogModal({ open, onClose, prospectId, messageId, onSave }: ReplyLogModalProps): React.ReactElement {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await onSave({
        prospect_id: prospectId,
        outreach_message_id: messageId,
        reply_text: form.reply_text.trim() || null,
        replied_at: new Date().toISOString(),
        sentiment: form.sentiment,
        next_action: form.next_action.trim() || null,
        next_action_due: form.next_action_due || null,
      });
      setForm(EMPTY);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to log reply.');
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
    <Modal open={open} onClose={handleClose} title="Log a reply" className="w-full max-w-lg p-6 max-h-[85vh] overflow-y-auto">
      <form onSubmit={handleSubmit} className="space-y-4 mt-2">
        {error && <Alert variant="error">{error}</Alert>}

        <div>
          <label htmlFor="rl-reply-text" className="block text-sm font-medium text-[#374151] mb-1">Reply text</label>
          <Textarea
            id="rl-reply-text"
            value={form.reply_text}
            onChange={(v) => setForm((p) => ({ ...p, reply_text: v }))}
            placeholder="Paste or type the prospect's reply…"
            rows={4}
          />
        </div>

        <div>
          <p className="block text-sm font-medium text-[#374151] mb-2">Sentiment</p>
          <div className="flex gap-2">
            {SENTIMENTS.map(({ value, label, className }) => (
              <button
                key={value}
                type="button"
                onClick={() => setForm((p) => ({ ...p, sentiment: value }))}
                className={`flex-1 py-1.5 text-xs font-medium rounded border transition-all ${
                  form.sentiment === value
                    ? className
                    : 'border-gray-200 bg-white text-gray-400 hover:border-gray-300'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label htmlFor="rl-next-action" className="block text-sm font-medium text-[#374151] mb-1">Next action</label>
          <input
            id="rl-next-action"
            type="text"
            value={form.next_action}
            onChange={(e) => setForm((p) => ({ ...p, next_action: e.target.value }))}
            placeholder="Book a discovery call, Send case study…"
            className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label htmlFor="rl-due-by" className="block text-sm font-medium text-[#374151] mb-1">Due by</label>
          <input
            id="rl-due-by"
            type="date"
            value={form.next_action_due}
            onChange={(e) => setForm((p) => ({ ...p, next_action_due: e.target.value }))}
            className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
          />
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
            {saving ? 'Saving…' : 'Log reply'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
