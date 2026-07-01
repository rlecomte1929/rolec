import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Badge, Button, Card } from '../../components/antigravity';
import {
  AiControl,
  AiControlSource,
  getAiControls,
  killAiFeature,
  setAiControl,
} from '../../api/aiControls';
import { AdminLayout } from './AdminLayout';

const SOURCE_BADGE: Record<AiControlSource, React.ReactNode> = {
  env: <Badge variant="info">env var</Badge>,
  db: <Badge variant="success">db override</Badge>,
  default: <Badge variant="warning">default</Badge>,
};

const LABEL: Record<string, string> = {
  policy_rag_groundedness_gate: 'Groundedness gate',
  policy_rag_groundedness_min_score: 'Groundedness min score',
  policy_rag_rerank: 'RAG rerank',
  supplier_learned_weights: 'Supplier learned weights',
};

interface ControlCardProps {
  control: AiControl;
  onUpdated: () => void;
}

const ControlCard: React.FC<ControlCardProps> = ({ control, onUpdated }) => {
  const [editing, setEditing] = useState(false);
  const [newValue, setNewValue] = useState(control.value);
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [killing, setKilling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    if (!reason.trim()) {
      setError('A reason is required to change a setting.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await setAiControl({ key: control.key, value: newValue, reason: reason.trim() });
      setEditing(false);
      setReason('');
      onUpdated();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save.');
    } finally {
      setSaving(false);
    }
  };

  const handleKill = async () => {
    if (!window.confirm(`Force "${LABEL[control.key] ?? control.key}" to OFF (value "0")?`)) return;
    setKilling(true);
    setError(null);
    try {
      await killAiFeature(control.key);
      onUpdated();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Kill-switch failed.');
    } finally {
      setKilling(false);
    }
  };

  const isEnvLocked = control.source === 'env';

  return (
    <Card className="mb-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium text-navy-900">
              {LABEL[control.key] ?? control.key}
            </span>
            {SOURCE_BADGE[control.source]}
          </div>
          <code className="text-sm text-navy-600 break-all">{control.value}</code>
          {isEnvLocked && (
            <p className="mt-1 text-xs text-navy-400">Set by env var — override via server config.</p>
          )}
        </div>
        {!isEnvLocked && (
          <div className="flex gap-2 shrink-0">
            <Button
              variant="outline"
              size="sm"
              onClick={() => { setEditing(e => !e); setNewValue(control.value); setError(null); }}
              disabled={saving || killing}
            >
              {editing ? 'Cancel' : 'Edit'}
            </Button>
            <Button
              variant="primary"
              size="sm"
              className="!bg-red-600 hover:!bg-red-700 !border-red-600"
              onClick={handleKill}
              disabled={saving || killing}
            >
              {killing ? 'Killing…' : 'Kill (force off)'}
            </Button>
          </div>
        )}
      </div>

      {error && (
        <Alert variant="error" className="mt-3">
          {error}
        </Alert>
      )}

      {editing && !isEnvLocked && (
        <div className="mt-4 space-y-3 border-t border-navy-100 pt-4">
          <div>
            <label htmlFor={`${control.key}-value`} className="block text-sm font-medium text-navy-700 mb-1">New value</label>
            <input
              id={`${control.key}-value`}
              className="w-full border border-navy-200 rounded px-3 py-2 text-sm"
              value={newValue}
              onChange={e => setNewValue(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor={`${control.key}-reason`} className="block text-sm font-medium text-navy-700 mb-1">
              Reason <span className="text-red-500">*</span>
            </label>
            <input
              id={`${control.key}-reason`}
              className="w-full border border-navy-200 rounded px-3 py-2 text-sm"
              placeholder="Why are you changing this setting?"
              value={reason}
              onChange={e => setReason(e.target.value)}
            />
          </div>
          <Button variant="primary" size="sm" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </Button>
        </div>
      )}
    </Card>
  );
};

export const AdminAiControlsPage: React.FC = () => {
  const [controls, setControls] = useState<AiControl[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const data = await getAiControls();
      setControls(data.controls);
    } catch (err) {
      setFetchError(err instanceof Error ? err.message : 'Failed to load controls.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  return (
    <AdminLayout
      title="AI governance"
      subtitle="Surface and gate AI behavior flags. Changes are audited."
    >
      {fetchError && (
        <Alert variant="error" className="mb-6">
          {fetchError}
        </Alert>
      )}
      {loading ? (
        <p className="text-navy-500 text-sm">Loading controls…</p>
      ) : (
        controls.map(c => (
          <ControlCard key={c.key} control={c} onUpdated={load} />
        ))
      )}
    </AdminLayout>
  );
};
