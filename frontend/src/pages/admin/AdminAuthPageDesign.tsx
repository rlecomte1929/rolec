import React, { useState } from 'react';
import { Alert, Button, Card, Checkbox, Input } from '../../components/antigravity';
import { getAuthItem } from '../../utils/demo';
import { AdminLayout } from './AdminLayout';
import { GlobeNetwork, DEFAULT_GLOBE_NETWORK_CONFIG, type GlobeNetworkConfig } from '../../components/auth/GlobeNetwork';
import { updateAuthPageConfig } from '../../api/authPageConfig';
import { useAuthPageConfig } from '../../hooks/useAuthPageConfig';

// ── Field helpers ────────────────────────────────────────────────────────────

const RangeField: React.FC<{
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}> = ({ label, value, min, max, step, onChange }) => (
  <div className="mb-4">
    <div className="flex items-center justify-between mb-1.5">
      <label className="text-sm font-medium text-slate-700">{label}</label>
      <span className="text-xs font-mono text-slate-500">{value}</span>
    </div>
    <input
      type="range"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      className="w-full"
    />
  </div>
);

const ColorField: React.FC<{ label: string; value: string; onChange: (v: string) => void }> = ({
  label,
  value,
  onChange,
}) => (
  <div className="mb-4 flex items-center justify-between">
    <label className="text-sm font-medium text-slate-700">{label}</label>
    <div className="flex items-center gap-2">
      <input
        type="color"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-8 w-10 rounded border border-slate-200 cursor-pointer"
      />
      <Input unstyled
        value={value}
        onChange={onChange}
        className="w-24 rounded border border-slate-200 px-2 py-1 text-xs font-mono"
      />
    </div>
  </div>
);

const ToggleField: React.FC<{ label: string; checked: boolean; onChange: (v: boolean) => void }> = ({
  label,
  checked,
  onChange,
}) => (
  <label className="mb-3 flex items-center justify-between cursor-pointer">
    <span className="text-sm font-medium text-slate-700">{label}</span>
    <Checkbox checked={checked} onChange={(e) => onChange(e.target.checked)} />
  </label>
);

// ── Main page ─────────────────────────────────────────────────────────────────

export const AdminAuthPageDesign: React.FC = () => {
  const { config: remoteConfig, loading, refetch } = useAuthPageConfig();
  const [local, setLocal] = useState<GlobeNetworkConfig>(remoteConfig);
  const [hydrated, setHydrated] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveState, setSaveState] = useState<'idle' | 'success' | 'error'>('idle');
  const [saveError, setSaveError] = useState('');

  // Sync local editable state once the remote config finishes loading (don't
  // clobber in-progress edits on every refetch).
  if (!hydrated && !loading) {
    setLocal(remoteConfig);
    setHydrated(true);
  }

  const role = getAuthItem('relopass_role');
  if (role !== 'ADMIN') {
    return (
      <AdminLayout title="Auth Page Design" subtitle="Restricted">
        <div className="py-8 text-center text-slate-500">Admin only.</div>
      </AdminLayout>
    );
  }

  const set = <K extends keyof GlobeNetworkConfig>(key: K, value: GlobeNetworkConfig[K]) =>
    setLocal((prev) => ({ ...prev, [key]: value }));

  const handleSave = async () => {
    setSaving(true);
    setSaveState('idle');
    setSaveError('');
    try {
      await updateAuthPageConfig(local);
      setSaveState('success');
      void refetch();
    } catch (e) {
      setSaveState('error');
      setSaveError((e as Error)?.message ?? 'Failed to save config.');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setLocal(DEFAULT_GLOBE_NETWORK_CONFIG);
    setSaveState('idle');
  };

  return (
    <AdminLayout
      title="Auth Page Design"
      subtitle="Live-tune the GlobeNetwork visualization shown on the public /auth login page. Changes apply to all visitors once saved."
    >
      {saveState === 'success' && (
        <Alert variant="success" className="mb-5">
          Saved — the public /auth page now uses this config.
        </Alert>
      )}
      {saveState === 'error' && (
        <Alert variant="error" className="mb-5">
          {saveError}
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
        {/* ── Live preview ── */}
        <Card padding="none" className="overflow-hidden">
          <div className="h-[520px] bg-[#061424] relative">
            <GlobeNetwork config={local} />
          </div>
        </Card>

        {/* ── Tweaks panel ── */}
        <div className="space-y-6">
          <Card padding="lg">
            <h3 className="font-semibold mb-3 text-slate-900">Motion</h3>
            <RangeField label="Rotation speed" value={local.rotSpeed} min={0} max={10} step={0.1} onChange={(v) => set('rotSpeed', v)} />
            <RangeField label="Pulse speed (s)" value={local.pulseSpeed} min={0.5} max={10} step={0.1} onChange={(v) => set('pulseSpeed', v)} />
            <ToggleField
              label="Force reduced motion"
              checked={local.reducedMotion ?? false}
              onChange={(v) => set('reducedMotion', v)}
            />
          </Card>

          <Card padding="lg">
            <h3 className="font-semibold mb-3 text-slate-900">Continent dots</h3>
            <RangeField label="Dot count" value={local.dotCount} min={200} max={6000} step={100} onChange={(v) => set('dotCount', v)} />
            <RangeField label="Dot size" value={local.dotSize} min={0.3} max={4} step={0.1} onChange={(v) => set('dotSize', v)} />
            <RangeField label="Dot opacity" value={local.dotOpacity} min={0} max={1} step={0.05} onChange={(v) => set('dotOpacity', v)} />
          </Card>

          <Card padding="lg">
            <h3 className="font-semibold mb-3 text-slate-900">Coastline</h3>
            <ToggleField label="Show coastline" checked={local.showCoastline} onChange={(v) => set('showCoastline', v)} />
            <ColorField label="Coast color" value={local.coastColor} onChange={(v) => set('coastColor', v)} />
            <RangeField label="Coast width" value={local.coastWidth} min={0.2} max={4} step={0.1} onChange={(v) => set('coastWidth', v)} />
            <RangeField label="Coast opacity" value={local.coastOpacity} min={0} max={1} step={0.05} onChange={(v) => set('coastOpacity', v)} />
            <RangeField label="Coast glow" value={local.coastGlow} min={0} max={30} step={1} onChange={(v) => set('coastGlow', v)} />
          </Card>

          <Card padding="lg">
            <h3 className="font-semibold mb-3 text-slate-900">Network</h3>
            <ToggleField label="Show arcs" checked={local.showArcs} onChange={(v) => set('showArcs', v)} />
            <ColorField label="Arc color" value={local.arcColor} onChange={(v) => set('arcColor', v)} />
            <RangeField label="Arc width" value={local.arcWidth} min={0.3} max={6} step={0.1} onChange={(v) => set('arcWidth', v)} />
            <RangeField label="Arc glow" value={local.arcGlow} min={0} max={60} step={1} onChange={(v) => set('arcGlow', v)} />
            <RangeField label="Arc density" value={local.arcDensity} min={0} max={1} step={0.05} onChange={(v) => set('arcDensity', v)} />
            <ToggleField label="Show cities" checked={local.showCities} onChange={(v) => set('showCities', v)} />
            <RangeField label="City dot size" value={local.citySize} min={0.3} max={3} step={0.1} onChange={(v) => set('citySize', v)} />
            <ToggleField label="Show city labels" checked={local.showLabels} onChange={(v) => set('showLabels', v)} />
          </Card>

          <div className="flex gap-3">
            <Button variant="primary" onClick={() => void handleSave()} disabled={saving} className="flex-1">
              {saving ? 'Saving…' : 'Save'}
            </Button>
            <Button variant="secondary" onClick={handleReset} disabled={saving}>
              Reset to defaults
            </Button>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
};
