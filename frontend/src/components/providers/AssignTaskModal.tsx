/**
 * AssignTaskModal — create a new task for a specific provider.
 */
import React, { useState } from 'react';
import { createProviderTask } from '../../api/providers';
import type { ProviderItem, ProviderTaskItem } from '../../api/providers';
import { Input, Button } from '../antigravity';

interface AssignTaskModalProps {
  provider: ProviderItem;
  caseId: string;
  onCreated: (task: ProviderTaskItem) => void;
  onClose: () => void;
}

export const AssignTaskModal: React.FC<AssignTaskModalProps> = ({
  provider, caseId, onCreated, onClose,
}) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) { setError('Title is required.'); return; }
    setSaving(true);
    setError('');
    try {
      const task = await createProviderTask({
        case_id:     caseId,
        provider_id: provider.id,
        title:       title.trim(),
        description: description.trim() || undefined,
        due_date:    dueDate || undefined,
        notes:       notes.trim() || undefined,
      });
      onCreated(task);
    } catch {
      setError('Failed to create task. Please try again.');
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 p-6">
        <h2 className="text-base font-semibold text-[#0b2b43] mb-1">Assign task</h2>
        <p className="text-sm text-[#6b7280] mb-4">
          Provider: <span className="font-medium text-[#374151]">{provider.name}</span>
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Task title *"
            value={title}
            onChange={setTitle}
            placeholder="e.g. Prepare lease contract"
            fullWidth
            disabled={saving}
          />

          <div>
            <label className="block text-sm font-medium text-[#374151] mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              disabled={saving}
              placeholder="Optional details for the provider…"
              className="w-full text-sm rounded-lg border border-[#d1d5db] px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-[#0b2b43] disabled:bg-[#f3f4f6]"
            />
          </div>

          <Input
            label="Due date"
            type="date"
            value={dueDate}
            onChange={setDueDate}
            fullWidth
            disabled={saving}
          />

          <Input
            label="Internal notes"
            value={notes}
            onChange={setNotes}
            placeholder="Notes visible only to HR…"
            fullWidth
            disabled={saving}
          />

          {error && <p className="text-sm text-[#dc2626]">{error}</p>}

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outline" onClick={onClose} disabled={saving}>
              Cancel
            </Button>
            <Button unstyled
              type="submit"
              disabled={saving}
              className="px-4 py-2 rounded-lg bg-[#0b2b43] text-white text-sm font-semibold hover:bg-[#1a3d5c] disabled:opacity-50 transition-colors"
            >
              {saving ? 'Creating…' : 'Create task'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
