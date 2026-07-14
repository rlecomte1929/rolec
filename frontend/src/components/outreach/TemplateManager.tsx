import React, { useState } from 'react';
import { Plus, Pencil, Trash2, Check, X } from 'lucide-react';
import { Modal, Alert, Textarea } from '../antigravity';
import { useTemplates } from '../../hooks/useTemplates';
import type { MessageTemplate, MessageType, TemplateInsert } from '../../types/outreach';

const MESSAGE_TYPES: { value: MessageType; label: string }[] = [
  { value: 'initial',        label: 'Initial outreach' },
  { value: 'follow_up',      label: 'Follow-up' },
  { value: 'reply_response', label: 'Reply response' },
];

const EMPTY_FORM = { name: '', message_type: 'initial' as MessageType, body_template: '', is_active: true };

interface TemplateFormState {
  name: string;
  message_type: MessageType;
  body_template: string;
  is_active: boolean;
}

interface TemplateManagerProps {
  open: boolean;
  onClose: () => void;
}

export function TemplateManager({ open, onClose }: TemplateManagerProps): React.ReactElement {
  const { templates, createTemplate, updateTemplate, deleteTemplate } = useTemplates();

  const [editing, setEditing] = useState<MessageTemplate | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<TemplateFormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setError(null);
    setCreating(true);
  };

  const openEdit = (t: MessageTemplate) => {
    setCreating(false);
    setError(null);
    setForm({ name: t.name, message_type: t.message_type, body_template: t.body_template, is_active: t.is_active });
    setEditing(t);
  };

  const cancelForm = () => {
    setCreating(false);
    setEditing(null);
    setForm(EMPTY_FORM);
    setError(null);
  };

  const handleSave = async () => {
    if (!form.name.trim()) { setError('Name is required.'); return; }
    if (!form.body_template.trim()) { setError('Template body is required.'); return; }
    setSaving(true);
    setError(null);
    try {
      if (creating) {
        const payload: TemplateInsert = {
          name: form.name.trim(),
          message_type: form.message_type,
          body_template: form.body_template.trim(),
          is_active: form.is_active,
        };
        await createTemplate(payload);
      } else if (editing) {
        await updateTemplate(editing.id, {
          name: form.name.trim(),
          message_type: form.message_type,
          body_template: form.body_template.trim(),
          is_active: form.is_active,
        });
      }
      cancelForm();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save template.');
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async (t: MessageTemplate) => {
    await updateTemplate(t.id, { is_active: !t.is_active });
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteTemplate(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete template.');
    } finally {
      setConfirmDelete(null);
    }
  };

  const isFormOpen = creating || editing !== null;

  return (
    <Modal open={open} onClose={onClose} title="Message templates" className="w-full max-w-2xl">
      <div className="mt-2 space-y-4">
        {error && <Alert variant="error">{error}</Alert>}

        {/* Template list */}
        {!isFormOpen && (
          <>
            {templates.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-6">No templates yet.</p>
            ) : (
              <div className="divide-y divide-gray-100 border border-gray-100 rounded-lg overflow-hidden">
                {templates.map((t) => (
                  <TemplateRow
                    key={t.id}
                    template={t}
                    onEdit={() => openEdit(t)}
                    onToggleActive={() => handleToggleActive(t)}
                    onDelete={() => setConfirmDelete(t.id)}
                    confirmingDelete={confirmDelete === t.id}
                    onConfirmDelete={() => handleDelete(t.id)}
                    onCancelDelete={() => setConfirmDelete(null)}
                  />
                ))}
              </div>
            )}

            <div className="flex justify-between items-center pt-2">
              <p className="text-xs text-gray-400">
                Tokens: <code className="bg-gray-100 px-1 rounded">{'{{full_name}}'}</code>{' '}
                <code className="bg-gray-100 px-1 rounded">{'{{company_name}}'}</code>{' '}
                <code className="bg-gray-100 px-1 rounded">{'{{job_title}}'}</code>{' '}
                <code className="bg-gray-100 px-1 rounded">{'{{corridor_relevance}}'}</code>
              </p>
              <button
                onClick={openCreate}
                className="flex items-center gap-1.5 px-3 py-2 bg-navy-700 text-white text-sm font-medium rounded-lg hover:bg-navy-800 transition-colors"
              >
                <Plus className="w-3.5 h-3.5" /> New template
              </button>
            </div>
          </>
        )}

        {/* Create / Edit form */}
        {isFormOpen && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-700">
              {creating ? 'New template' : `Edit — ${editing?.name}`}
            </h3>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label htmlFor="tm-name" className="block text-sm font-medium text-[#374151] mb-1">
                  Name <span className="text-red-500">*</span>
                </label>
                <input
                  id="tm-name"
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                  placeholder="FR→NO HR Generalist — Initial outreach"
                  className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
                />
              </div>

              <div>
                <label htmlFor="tm-type" className="block text-sm font-medium text-[#374151] mb-1">Type</label>
                <select
                  id="tm-type"
                  value={form.message_type}
                  onChange={(e) => setForm((p) => ({ ...p, message_type: e.target.value as MessageType }))}
                  className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm bg-white"
                >
                  {MESSAGE_TYPES.map(({ value, label }) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-2 self-end pb-1">
                <input
                  type="checkbox"
                  id="tpl-active"
                  checked={form.is_active}
                  onChange={(e) => setForm((p) => ({ ...p, is_active: e.target.checked }))}
                  className="w-4 h-4 accent-navy-700"
                />
                <label htmlFor="tpl-active" className="text-sm font-medium text-[#374151]">
                  Active (used for auto-draft)
                </label>
              </div>

              <div className="sm:col-span-2">
                <label htmlFor="tm-body" className="block text-sm font-medium text-[#374151] mb-1">
                  Body <span className="text-red-500">*</span>
                </label>
                <Textarea
                  id="tm-body"
                  value={form.body_template}
                  onChange={(v) => setForm((p) => ({ ...p, body_template: v }))}
                  placeholder={'Hi {{full_name}},\n\nI noticed your role at {{company_name}}…'}
                  rows={10}
                />
                <p className="text-xs text-gray-400 mt-1">
                  Use <code>{'{{full_name}}'}</code>, <code>{'{{company_name}}'}</code>, <code>{'{{job_title}}'}</code>, <code>{'{{corridor_relevance}}'}</code> as tokens.
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={cancelForm}
                disabled={saving}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 disabled:opacity-40"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-2 bg-navy-700 text-white text-sm font-medium rounded-lg hover:bg-navy-800 disabled:opacity-50 transition-colors"
              >
                {saving ? 'Saving…' : 'Save template'}
              </button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}

interface TemplateRowProps {
  template: MessageTemplate;
  onEdit: () => void;
  onToggleActive: () => void;
  onDelete: () => void;
  confirmingDelete: boolean;
  onConfirmDelete: () => void;
  onCancelDelete: () => void;
}

function TemplateRow({
  template: t,
  onEdit,
  onToggleActive,
  onDelete,
  confirmingDelete,
  onConfirmDelete,
  onCancelDelete,
}: TemplateRowProps): React.ReactElement {
  const typeLabel = MESSAGE_TYPES.find((m) => m.value === t.message_type)?.label ?? t.message_type;

  return (
    <div className="flex items-start gap-3 px-4 py-3 bg-white hover:bg-gray-50 transition-colors">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-sm font-medium text-gray-800 truncate">{t.name}</span>
          <span className="text-xs text-gray-400 flex-shrink-0">{typeLabel}</span>
        </div>
        <p className="text-xs text-gray-400 truncate">{t.body_template.slice(0, 80)}…</p>
      </div>

      <div className="flex items-center gap-1 flex-shrink-0">
        {/* Active toggle */}
        <button
          onClick={onToggleActive}
          title={t.is_active ? 'Active — click to deactivate' : 'Inactive — click to activate'}
          className={`text-xs px-2 py-1 rounded-full border font-medium transition-colors ${
            t.is_active
              ? 'bg-teal-50 text-teal-700 border-teal-200 hover:bg-teal-100'
              : 'bg-gray-50 text-gray-400 border-gray-200 hover:bg-gray-100'
          }`}
        >
          {t.is_active ? 'Active' : 'Inactive'}
        </button>

        <button
          onClick={onEdit}
          className="p-1.5 text-gray-400 hover:text-navy-700 rounded hover:bg-gray-100 transition-colors"
          title="Edit template"
        >
          <Pencil className="w-3.5 h-3.5" />
        </button>

        {confirmingDelete ? (
          <div className="flex items-center gap-1">
            <span className="text-xs text-red-600 font-medium">Delete?</span>
            <button
              onClick={onConfirmDelete}
              className="p-1 text-red-600 hover:text-red-800 rounded hover:bg-red-50 transition-colors"
              title="Confirm delete"
            >
              <Check className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={onCancelDelete}
              className="p-1 text-gray-400 hover:text-gray-600 rounded hover:bg-gray-100 transition-colors"
              title="Cancel"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <button
            onClick={onDelete}
            className="p-1.5 text-gray-400 hover:text-red-600 rounded hover:bg-red-50 transition-colors"
            title="Delete template"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}
