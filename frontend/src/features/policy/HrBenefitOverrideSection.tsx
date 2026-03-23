/**
 * HR override editor: adjust effective entitlements without editing the underlying extracted rule rows.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Input } from '../../components/antigravity';
import { companyPolicyAPI } from '../../api/client';

type Meta = Record<string, unknown>;
function readMeta(r: any, key: string, def?: unknown): unknown {
  const m = (r?.metadata_json || r?.metadata) as Meta | undefined;
  if (!m || typeof m !== 'object') return def;
  const v = m[key];
  return v !== undefined && v !== null ? v : def;
}

function formatRuleLabel(r: any): string {
  return (readMeta(r, 'benefit_label') as string) || String(r?.benefit_key || 'Benefit');
}

function formatApiDetail(detail: unknown): string {
  if (detail && typeof detail === 'object' && !Array.isArray(detail) && 'message' in detail) {
    const o = detail as { message?: string; code?: string };
    const prefix = o.code ? `[${o.code}] ` : '';
    return `${prefix}${o.message || ''}`.trim() || 'Request failed';
  }
  if (typeof detail === 'string') return detail;
  if (detail == null) return '';
  return String(detail);
}

function amountLine(row: Record<string, unknown> | null | undefined): string {
  if (!row) return '—';
  if (row.included === false) return 'Not included';
  const v = row.amount_value;
  const c = row.currency;
  const u = row.amount_unit;
  const f = row.frequency;
  if (v == null || v === '') {
    if (c || u) return [c, u].filter(Boolean).join(' ') || '—';
    return '—';
  }
  return [c ? String(c) : '', String(v), u ? String(u) : '', f ? String(f) : ''].filter(Boolean).join(' · ') || '—';
}

type Vis = 'default' | 'force_included' | 'force_excluded';

function parseVis(ov: Record<string, unknown> | null | undefined): Vis {
  const s = String(ov?.service_visibility || '').toLowerCase();
  if (s === 'force_excluded') return 'force_excluded';
  if (s === 'force_included') return 'force_included';
  return 'default';
}

type Appr = 'default' | 'yes' | 'no';

function parseAppr(ov: Record<string, unknown> | null | undefined): Appr {
  const v = ov?.approval_required_override;
  if (v === true) return 'yes';
  if (v === false) return 'no';
  return 'default';
}

type HrBenefitOverrideRowProps = {
  policyId: string;
  versionId: string;
  rule: any;
  overrideRow: Record<string, unknown> | null | undefined;
  trace: Record<string, unknown> | null | undefined;
  onAfterMutation: () => void;
  onPreviewImpact: () => void;
  onClearMessage: () => void;
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
};

const HrBenefitOverrideRow: React.FC<HrBenefitOverrideRowProps> = ({
  policyId,
  versionId,
  rule,
  overrideRow,
  trace,
  onAfterMutation,
  onPreviewImpact,
  onClearMessage,
  onError,
  onSuccess,
}) => {
  const baseline = (trace?.baseline || null) as Record<string, unknown> | null;
  const effective = (trace?.effective || null) as Record<string, unknown> | null;

  const [vis, setVis] = useState<Vis>('default');
  const [amt, setAmt] = useState('');
  const [unit, setUnit] = useState('');
  const [cur, setCur] = useState('');
  const [durQty, setDurQty] = useState('');
  const [durUnit, setDurUnit] = useState('days');
  const [appr, setAppr] = useState<Appr>('default');
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);

  const syncFromOverride = useCallback(() => {
    setVis(parseVis(overrideRow));
    setAmt(overrideRow?.amount_value_override != null && overrideRow.amount_value_override !== '' ? String(overrideRow.amount_value_override) : '');
    setUnit(String(overrideRow?.amount_unit_override || ''));
    setCur(String(overrideRow?.currency_override || ''));
    const dq = overrideRow?.duration_quantity_json as Record<string, unknown> | null | undefined;
    if (dq && typeof dq === 'object') {
      setDurQty(dq.quantity != null ? String(dq.quantity) : '');
      setDurUnit(String(dq.unit || 'days'));
    } else {
      setDurQty('');
      setDurUnit('days');
    }
    setAppr(parseAppr(overrideRow));
    setNotes(String(overrideRow?.hr_notes || ''));
  }, [overrideRow]);

  useEffect(() => {
    syncFromOverride();
  }, [syncFromOverride]);

  const baselineLine = useMemo(() => {
    if (baseline && Object.keys(baseline).length) return amountLine(baseline);
    return amountLine({
      amount_value: rule?.amount_value,
      currency: rule?.currency,
      amount_unit: rule?.amount_unit,
      frequency: rule?.frequency,
      included: readMeta(rule, 'allowed', true) === false ? false : true,
    } as Record<string, unknown>);
  }, [baseline, rule]);

  const effectiveLine = useMemo(() => {
    if (effective && Object.keys(effective).length) return amountLine(effective);
    return baselineLine;
  }, [effective, baselineLine]);

  const adjustmentSummary = useMemo(() => {
    const parts: string[] = [];
    if (vis === 'force_excluded') parts.push('Force exclude');
    else if (vis === 'force_included') parts.push('Force include');
    if (amt.trim() !== '') parts.push(`Amount override: ${amt}`);
    if (cur.trim()) parts.push(`Currency: ${cur}`);
    if (unit.trim()) parts.push(`Unit: ${unit}`);
    if (durQty.trim()) parts.push(`Duration: ${durQty} ${durUnit}`);
    if (appr === 'yes') parts.push('Approval required');
    if (appr === 'no') parts.push('Approval not required');
    if (notes.trim()) parts.push(`Note: ${notes.trim().slice(0, 80)}${notes.length > 80 ? '…' : ''}`);
    return parts.length ? parts.join(' · ') : 'None — employees use extracted baseline';
  }, [vis, amt, cur, unit, durQty, durUnit, appr, notes]);

  const baselineAmount = rule?.amount_value;
  const hadNumericOverride = overrideRow?.amount_value_override != null && overrideRow.amount_value_override !== '';
  const clearingCap = hadNumericOverride && amt.trim() === '' && vis !== 'force_excluded';
  const lowerThanBaseline =
    amt.trim() !== '' &&
    typeof baselineAmount === 'number' &&
    baselineAmount > 0 &&
    !Number.isNaN(parseFloat(amt)) &&
    parseFloat(amt) < baselineAmount;

  const buildPatch = () => {
    const duration_quantity_json =
      durQty.trim() === ''
        ? null
        : (() => {
            const q = parseFloat(durQty);
            if (Number.isNaN(q)) return null;
            return { quantity: q, unit: durUnit.trim() || 'days' };
          })();

    return {
      service_visibility: vis === 'default' ? null : vis === 'force_included' ? ('force_included' as const) : ('force_excluded' as const),
      amount_value_override: amt.trim() === '' ? null : parseFloat(amt),
      amount_unit_override: unit.trim() === '' ? null : unit.trim(),
      currency_override: cur.trim() === '' ? null : cur.trim(),
      duration_quantity_json,
      approval_required_override: appr === 'default' ? null : appr === 'yes',
      hr_notes: notes.trim() === '' ? null : notes.trim(),
    };
  };

  const handleSave = async () => {
    const patch = buildPatch();
    if (patch.amount_value_override != null && Number.isNaN(patch.amount_value_override)) {
      onError('Enter a valid number for amount override, or leave blank to use the baseline.');
      return;
    }
    setBusy(true);
    onClearMessage();
    try {
      await companyPolicyAPI.patchHrBenefitOverride(policyId, versionId, String(rule.id), patch);
      onSuccess('HR adjustment saved. Effective preview updated.');
      onAfterMutation();
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: unknown } } };
      onError(formatApiDetail(ax?.response?.data?.detail) || 'Could not save HR adjustment');
    } finally {
      setBusy(false);
    }
  };

  const handleReset = async () => {
    if (!window.confirm('Remove all HR adjustments for this benefit? Extracted baseline values will apply again.')) return;
    setBusy(true);
    onClearMessage();
    try {
      await companyPolicyAPI.deleteHrBenefitOverride(policyId, versionId, String(rule.id));
      onSuccess('HR adjustment reset. Effective values follow the extracted baseline.');
      onAfterMutation();
    } catch (err: unknown) {
      const ax = err as { response?: { status?: number; data?: { detail?: unknown } } };
      if (ax.response?.status === 404) {
        onSuccess('No saved adjustment to remove.');
        onAfterMutation();
        return;
      }
      const msg = formatApiDetail(ax?.response?.data?.detail);
      onError(msg || 'Could not reset HR adjustment');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="border border-[#e2e8f0] rounded-lg p-4 bg-white space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="font-medium text-[#0b2b43]">{formatRuleLabel(rule)}</div>
          <p className="text-xs text-[#6b7280] mt-1 max-w-2xl">
            HR adjustments change <strong>effective policy</strong> for employees. They do <strong>not</strong> modify the
            uploaded document or the extracted baseline row — use <strong>Edit</strong> in the table below for that.
          </p>
        </div>
        <button
          type="button"
          className="text-xs text-[#059669] hover:underline shrink-0"
          onClick={onPreviewImpact}
        >
          Preview employee impact
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-3 text-sm">
        <div className="rounded-md bg-slate-50 border border-slate-200 p-3">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Extracted baseline</div>
          <div className="text-[#111827]">{baselineLine}</div>
        </div>
        <div className="rounded-md bg-indigo-50/60 border border-indigo-200 p-3">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-indigo-800 mb-1">HR adjustment</div>
          <div className="text-[#1e1b4b] text-xs leading-snug">{adjustmentSummary}</div>
        </div>
        <div className="rounded-md bg-emerald-50/70 border border-emerald-200 p-3">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-emerald-900 mb-1">Effective policy</div>
          <div className="text-[#065f46]">{effectiveLine}</div>
          <div className="text-[10px] text-emerald-800 mt-1">
            What employees would see if this version is the live published policy.
          </div>
        </div>
      </div>

      {vis === 'force_excluded' && (
        <Alert variant="warning">
          <strong>Force exclude:</strong> employees will not receive this benefit when this version is live (subject to
          eligibility rules elsewhere).
        </Alert>
      )}
      {clearingCap && (
        <Alert variant="warning">
          You cleared a custom cap — <strong>effective amounts</strong> will follow the <strong>extracted baseline</strong>{' '}
          again.
        </Alert>
      )}
      {lowerThanBaseline && vis !== 'force_excluded' && (
        <Alert variant="warning">
          Override cap is <strong>below</strong> the extracted baseline — confirm this is intentional.
        </Alert>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label className="text-xs text-[#374151] block">
          Visibility
          <select
            value={vis}
            onChange={(e) => setVis(e.target.value as Vis)}
            disabled={busy}
            className="mt-1 w-full border border-[#e2e8f0] rounded px-2 py-1.5 text-sm"
          >
            <option value="default">Policy default (from baseline)</option>
            <option value="force_included">Force include</option>
            <option value="force_excluded">Force exclude</option>
          </select>
        </label>
        <label className="text-xs text-[#374151] block">
          Override amount (optional)
          <Input value={amt} onChange={setAmt} placeholder="Leave blank for baseline" disabled={busy} />
        </label>
        <label className="text-xs text-[#374151] block">
          Override currency
          <Input value={cur} onChange={setCur} placeholder="e.g. USD" disabled={busy} />
        </label>
        <label className="text-xs text-[#374151] block">
          Override unit
          <Input value={unit} onChange={setUnit} placeholder="e.g. per_month, lump_sum" disabled={busy} />
        </label>
        <label className="text-xs text-[#374151] block">
          Duration / quantity
          <div className="flex gap-1 mt-1">
            <Input value={durQty} onChange={setDurQty} placeholder="Qty" disabled={busy} />
            <Input value={durUnit} onChange={setDurUnit} placeholder="Unit" disabled={busy} />
          </div>
          <span className="text-[10px] text-[#9ca3af]">Example: 30 days temporary housing</span>
        </label>
        <label className="text-xs text-[#374151] block">
          Approval required
          <select
            value={appr}
            onChange={(e) => setAppr(e.target.value as Appr)}
            disabled={busy}
            className="mt-1 w-full border border-[#e2e8f0] rounded px-2 py-1.5 text-sm"
          >
            <option value="default">Default (from baseline)</option>
            <option value="yes">Yes</option>
            <option value="no">No</option>
          </select>
        </label>
      </div>
      <label className="text-xs text-[#374151] block">
        HR notes (internal)
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          disabled={busy}
          rows={2}
          className="mt-1 w-full border border-[#e2e8f0] rounded px-2 py-1.5 text-sm"
          placeholder="Context for your team — not shown to employees as policy text"
        />
      </label>

      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={() => void handleSave()} disabled={busy}>
          {busy ? 'Saving…' : 'Save HR adjustment'}
        </Button>
        <Button variant="outline" size="sm" onClick={() => void handleReset()} disabled={busy}>
          Reset HR override
        </Button>
      </div>
    </div>
  );
};

export type HrBenefitOverrideSectionProps = {
  policyId: string | null;
  versionId: string | null;
  benefitRules: any[];
  hrOverrides: unknown;
  entitlementPreview: unknown;
  onDataRefresh: () => void;
};

export const HrBenefitOverrideSection: React.FC<HrBenefitOverrideSectionProps> = ({
  policyId,
  versionId,
  benefitRules,
  hrOverrides,
  entitlementPreview,
  onDataRefresh,
}) => {
  const [localMessage, setLocalMessage] = useState('');
  const [localVariant, setLocalVariant] = useState<'success' | 'error'>('error');

  const overrideByRule = useMemo(() => {
    const m = new Map<string, Record<string, unknown>>();
    if (!Array.isArray(hrOverrides)) return m;
    for (const o of hrOverrides) {
      if (o && typeof o === 'object' && 'benefit_rule_id' in o) {
        m.set(String((o as { benefit_rule_id: string }).benefit_rule_id), o as Record<string, unknown>);
      }
    }
    return m;
  }, [hrOverrides]);

  const traceByRule = useMemo(() => {
    const m = new Map<string, Record<string, unknown>>();
    if (!Array.isArray(entitlementPreview)) return m;
    for (const t of entitlementPreview) {
      if (t && typeof t === 'object' && 'benefit_rule_id' in t) {
        m.set(String((t as { benefit_rule_id: string }).benefit_rule_id), t as Record<string, unknown>);
      }
    }
    return m;
  }, [entitlementPreview]);

  const scrollPreview = () => {
    document.getElementById('hr-policy-employee-visibility-preview')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  if (!policyId || !versionId || !benefitRules.length) return null;

  return (
    <Card padding="lg" id="hr-policy-hr-overrides">
      <h3 className="text-sm font-semibold text-[#0b2b43] mb-1">HR adjustments (effective policy)</h3>
      <p className="text-xs text-[#6b7280] mb-4 max-w-3xl">
        Tune caps, visibility, and approval flags for what employees <strong>effectively</strong> receive—without
        changing the extracted baseline row. Save to refresh the employee preview above; reset drops your adjustment for
        that rule.
      </p>
      {localMessage && (
        <Alert variant={localVariant} className="mb-4">
          {localMessage}
        </Alert>
      )}
      <div className="space-y-4">
        {benefitRules.map((rule: any) => (
          <HrBenefitOverrideRow
            key={rule.id}
            policyId={policyId}
            versionId={versionId}
            rule={rule}
            overrideRow={overrideByRule.get(String(rule.id))}
            trace={traceByRule.get(String(rule.id))}
            onAfterMutation={onDataRefresh}
            onPreviewImpact={scrollPreview}
            onClearMessage={() => setLocalMessage('')}
            onError={(msg) => {
              setLocalVariant('error');
              setLocalMessage(msg);
            }}
            onSuccess={(msg) => {
              setLocalVariant('success');
              setLocalMessage(msg);
            }}
          />
        ))}
      </div>
    </Card>
  );
};
