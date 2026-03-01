import React, { useMemo } from 'react';
import { Button, Input } from '../../components/antigravity';

const CATEGORY_LABELS: Record<string, string> = {
  housing: 'Housing',
  movers: 'Movers / Shipment',
  schools: 'Schools / Education',
  immigration: 'Immigration / Visa',
  travel: 'Travel',
  settling_in: 'Settling-in allowance',
  tax: 'Tax assistance',
  spouse: 'Spousal support',
  integration: 'Language / Cultural training',
  repatriation: 'Repatriation',
  home_sale: 'Home sale / purchase',
};

export interface PolicyBenefitRow {
  id?: string;
  service_category: string;
  benefit_key: string;
  benefit_label: string;
  eligibility?: Record<string, any> | null;
  limits?: Record<string, any> | null;
  notes?: string | null;
  source_quote?: string | null;
  source_section?: string | null;
  confidence?: number | null;
}

const formatLimits = (limits?: Record<string, any> | null) => {
  if (!limits) return '—';
  const parts: string[] = [];
  if (limits.days) parts.push(`${limits.days} days`);
  if (limits.percent) parts.push(`${limits.percent}%`);
  if (limits.monthly_cap) {
    const caps = Object.entries(limits.monthly_cap)
      .map(([cur, val]) => `${cur} ${val}`)
      .join(', ');
    parts.push(`Monthly cap: ${caps}`);
  }
  if (limits.cap && !limits.monthly_cap) {
    const caps = Object.entries(limits.cap)
      .map(([cur, val]) => `${cur} ${val}`)
      .join(', ');
    parts.push(`Cap: ${caps}`);
  }
  return parts.length ? parts.join(' • ') : '—';
};

const formatEligibility = (elig?: Record<string, any> | null) => {
  if (!elig) return '—';
  const parts: string[] = [];
  if (Array.isArray(elig.assignment_types)) {
    parts.push(`Assignment: ${elig.assignment_types.join(', ')}`);
  }
  if (Array.isArray(elig.bands)) {
    parts.push(`Bands: ${elig.bands.join(', ')}`);
  }
  return parts.length ? parts.join(' • ') : '—';
};

export const PolicyBenefitsTable: React.FC<{
  benefits: PolicyBenefitRow[];
  editable?: boolean;
  onChange?: (next: PolicyBenefitRow[]) => void;
  onSave?: () => void;
}> = ({ benefits, editable, onChange, onSave }) => {
  const grouped = useMemo(() => {
    const groups: Record<string, PolicyBenefitRow[]> = {};
    for (const b of benefits) {
      if (!groups[b.service_category]) groups[b.service_category] = [];
      groups[b.service_category].push(b);
    }
    return groups;
  }, [benefits]);

  const updateRow = (idx: number, key: keyof PolicyBenefitRow, value: any, category: string) => {
    if (!onChange) return;
    const next = benefits.map((b) => ({ ...b }));
    const group = grouped[category] || [];
    const row = group[idx];
    const realIdx = benefits.findIndex((b) => b.benefit_key === row.benefit_key);
    if (realIdx >= 0) {
      (next[realIdx] as any)[key] = value;
      onChange(next);
    }
  };

  return (
    <div className="space-y-6">
      {Object.entries(grouped).map(([category, rows]) => (
        <div key={category} className="border border-[#e2e8f0] rounded-xl">
          <div className="px-4 py-3 border-b border-[#e2e8f0] bg-[#f8fafc] font-semibold text-[#0b2b43]">
            {CATEGORY_LABELS[category] || category}
          </div>
          <div className="divide-y divide-[#eef2f7]">
            {rows.map((row, idx) => (
              <div key={row.benefit_key} className="px-4 py-3 grid grid-cols-1 md:grid-cols-4 gap-3">
                <div className="text-sm font-medium text-[#0b2b43]">{row.benefit_label}</div>
                <div className="text-sm text-[#4b5563]">
                  {editable ? (
                    <Input
                      value={JSON.stringify(row.eligibility || {})}
                      onChange={(val) => {
                        try {
                          updateRow(idx, 'eligibility', JSON.parse(val), category);
                        } catch {
                          updateRow(idx, 'eligibility', row.eligibility || {}, category);
                        }
                      }}
                      placeholder="Eligibility JSON"
                      fullWidth
                    />
                  ) : (
                    formatEligibility(row.eligibility)
                  )}
                </div>
                <div className="text-sm text-[#4b5563]">
                  {editable ? (
                    <Input
                      value={JSON.stringify(row.limits || {})}
                      onChange={(val) => {
                        try {
                          updateRow(idx, 'limits', JSON.parse(val), category);
                        } catch {
                          updateRow(idx, 'limits', row.limits || {}, category);
                        }
                      }}
                      placeholder="Limits JSON"
                      fullWidth
                    />
                  ) : (
                    formatLimits(row.limits)
                  )}
                </div>
                <div className="text-sm text-[#4b5563]">
                  {editable ? (
                    <Input
                      value={row.notes || ''}
                      onChange={(val) => updateRow(idx, 'notes', val, category)}
                      placeholder="Notes"
                      fullWidth
                    />
                  ) : (
                    row.notes || '—'
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
      {editable && onSave && (
        <div className="flex justify-end">
          <Button onClick={onSave}>Save changes</Button>
        </div>
      )}
    </div>
  );
};
