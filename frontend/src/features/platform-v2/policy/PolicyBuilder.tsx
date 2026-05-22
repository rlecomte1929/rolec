/**
 * PolicyBuilder.tsx — T10 Policy Builder (S5b) /admin/policy
 * HR-facing. Create/edit policy tiers and their benefits.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { PolicyTier, PolicyBenefit, BenefitValueType } from '../../../types/relopass-api-contracts';
import { EmptyState } from '../shared';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface PolicyBuilderProps {
  tiers: PolicyTier[];
  benefits: PolicyBenefit[];
  onSaveTier: (tier: PolicyTier) => Promise<void>;
  onCreateTier: () => Promise<PolicyTier>;
  onSaveBenefit: (benefit: PolicyBenefit) => Promise<void>;
  onAddBenefit: (tierId: string) => Promise<PolicyBenefit>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Toast
// ─────────────────────────────────────────────────────────────────────────────

function useToast() {
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = useCallback(() => {
    setVisible(true);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setVisible(false), 2000);
  }, []);

  return { visible, show };
}

// ─────────────────────────────────────────────────────────────────────────────
// Benefit Row (editable)
// ─────────────────────────────────────────────────────────────────────────────

interface BenefitRowProps {
  benefit: PolicyBenefit;
  onSave: (b: PolicyBenefit) => Promise<void>;
  onSaved: () => void;
}

function BenefitRow({ benefit, onSave, onSaved }: BenefitRowProps) {
  const [local, setLocal] = useState({ ...benefit });
  const dirty = useRef(false);

  function update<K extends keyof PolicyBenefit>(key: K, value: PolicyBenefit[K]) {
    setLocal(prev => ({ ...prev, [key]: value }));
    dirty.current = true;
  }

  async function handleBlur() {
    if (!dirty.current) return;
    dirty.current = false;
    await onSave(local);
    onSaved();
  }

  const cellInput: React.CSSProperties = {
    background: 'none',
    border: 'none',
    borderBottom: '1px solid transparent',
    padding: '4px 2px',
    fontSize: '14px',
    color: 'var(--text)',
    width: '100%',
    outline: 'none',
    transition: 'border-color 0.15s',
  };

  return (
    <tr style={{ borderBottom: '1px solid var(--border)' }}>
      {/* Icon placeholder */}
      <td style={{ padding: '10px 12px', width: '36px' }}>
        <div style={{ width: '28px', height: '28px', borderRadius: '6px', background: 'var(--surface-hover)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
      </td>

      {/* Name */}
      <td style={{ padding: '10px 8px' }}>
        <input
          type="text"
          value={local.name}
          onChange={e => update('name', e.target.value)}
          onBlur={handleBlur}
          style={cellInput}
          onFocus={e => (e.target.style.borderBottomColor = 'var(--accent)')}
          aria-label="Benefit name"
        />
      </td>

      {/* Value type */}
      <td style={{ padding: '10px 8px', width: '140px' }}>
        <select
          value={local.value_type}
          onChange={e => update('value_type', e.target.value as BenefitValueType)}
          onBlur={handleBlur}
          style={{ ...cellInput, cursor: 'pointer' }}
          aria-label="Value type"
        >
          <option value="currency">Currency</option>
          <option value="days">Days</option>
          <option value="boolean">Yes / No</option>
          <option value="text">Text</option>
        </select>
      </td>

      {/* Value */}
      <td style={{ padding: '10px 8px', width: '140px' }}>
        {local.value_type === 'boolean' ? (
          <select
            value={local.benefit_value}
            onChange={e => update('benefit_value', e.target.value)}
            onBlur={handleBlur}
            style={{ ...cellInput, cursor: 'pointer' }}
            aria-label="Benefit value"
          >
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        ) : (
          <input
            type={local.value_type === 'days' ? 'number' : 'text'}
            value={local.benefit_value}
            onChange={e => update('benefit_value', e.target.value)}
            onBlur={handleBlur}
            style={cellInput}
            onFocus={e => (e.target.style.borderBottomColor = 'var(--accent)')}
            aria-label="Benefit value"
          />
        )}
      </td>

      {/* Mandatory toggle */}
      <td style={{ padding: '10px 12px', textAlign: 'center', width: '90px' }}>
        <button
          role="switch"
          aria-checked={false}
          onClick={handleBlur}
          style={{
            width: '36px', height: '20px', borderRadius: '10px',
            background: 'var(--surface-hover)',
            border: 'none', cursor: 'pointer', position: 'relative', display: 'inline-block',
          }}
          title="Toggle mandatory"
        >
          <span style={{ position: 'absolute', top: '2px', left: '2px', width: '16px', height: '16px', borderRadius: '50%', background: 'var(--text-muted)', transition: 'transform 0.2s' }} />
        </button>
      </td>
    </tr>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function PolicyBuilder({ tiers, benefits, onSaveTier: _onSaveTier, onCreateTier, onSaveBenefit, onAddBenefit }: PolicyBuilderProps) {
  const [selectedTierId, setSelectedTierId] = useState<string | null>(tiers[0]?.id ?? null);
  const [creatingTier, setCreatingTier] = useState(false);
  const [addingBenefit, setAddingBenefit] = useState(false);
  const toast = useToast();

  const selectedTier = tiers.find(t => t.id === selectedTierId) ?? null;
  const tierBenefits = benefits.filter(b => b.policy_tier_id === selectedTierId);

  // Keep selected tier in sync if tiers list changes
  useEffect(() => {
    if (!selectedTierId && tiers.length > 0) {
      setSelectedTierId(tiers[0].id);
    }
  }, [tiers, selectedTierId]);

  async function handleCreateTier() {
    setCreatingTier(true);
    try {
      const newTier = await onCreateTier();
      setSelectedTierId(newTier.id);
    } finally {
      setCreatingTier(false);
    }
  }

  async function handleAddBenefit() {
    if (!selectedTierId) return;
    setAddingBenefit(true);
    try {
      await onAddBenefit(selectedTierId);
    } finally {
      setAddingBenefit(false);
    }
  }

  return (
    <div style={{ padding: '24px', maxWidth: '1100px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '24px', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ margin: '0 0 4px', fontSize: '22px', fontWeight: 700, color: 'var(--text)' }}>
            Policy Builder
          </h1>
          <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-muted)' }}>
            Manage relocation policy tiers and their benefit entitlements.
          </p>
        </div>
      </div>

      {/* Toast */}
      {toast.visible && (
        <div style={{
          position: 'fixed', top: '20px', right: '20px', zIndex: 500,
          background: 'var(--success)', color: '#fff',
          padding: '10px 18px', borderRadius: 'var(--radius-md, 8px)',
          fontSize: '13px', fontWeight: 600, boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          transition: 'opacity 0.3s',
        }}>
          Saved
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 3fr', gap: '20px', alignItems: 'start' }}>
        {/* Left: tier list */}
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg, 12px)', overflow: 'hidden' }}>
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontWeight: 700, fontSize: '14px', color: 'var(--text)' }}>Tiers</span>
            <button
              onClick={handleCreateTier}
              disabled={creatingTier}
              style={{ padding: '5px 10px', borderRadius: 'var(--radius-md, 8px)', background: 'var(--accent)', color: '#fff', fontWeight: 600, fontSize: '12px', border: 'none', cursor: creatingTier ? 'not-allowed' : 'pointer', opacity: creatingTier ? 0.7 : 1 }}
            >
              {creatingTier ? '…' : '+ New tier'}
            </button>
          </div>

          {tiers.length === 0 ? (
            <div style={{ padding: '24px' }}>
              <EmptyState
                icon="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
                title="No tiers"
                description="Create a tier to get started."
              />
            </div>
          ) : (
            <ul role="listbox" aria-label="Policy tiers" style={{ margin: 0, padding: 0, listStyle: 'none' }}>
              {tiers
                .slice()
                .sort((a, b) => a.rank - b.rank)
                .map(tier => {
                  const isSelected = tier.id === selectedTierId;
                  return (
                    <li
                      key={tier.id}
                      role="option"
                      aria-selected={isSelected}
                      onClick={() => setSelectedTierId(tier.id)}
                      style={{
                        padding: '12px 16px',
                        cursor: 'pointer',
                        background: isSelected ? 'var(--accent-soft)' : 'transparent',
                        borderLeft: `3px solid ${isSelected ? 'var(--accent)' : 'transparent'}`,
                        borderBottom: '1px solid var(--border)',
                        transition: 'background 0.15s',
                      }}
                    >
                      <p style={{ margin: '0 0 2px', fontWeight: 600, fontSize: '14px', color: isSelected ? 'var(--accent-text)' : 'var(--text)' }}>
                        {tier.name}
                      </p>
                      <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-muted)' }}>
                        Rank {tier.rank}
                        {tier.description ? ` · ${tier.description.slice(0, 40)}…` : ''}
                      </p>
                    </li>
                  );
                })}
            </ul>
          )}
        </div>

        {/* Right: benefits editor */}
        <div>
          {!selectedTier ? (
            <EmptyState
              icon="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5"
              title="Select a tier"
              description="Click a tier on the left to edit its benefits."
            />
          ) : (
            <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg, 12px)', overflow: 'hidden' }}>
              <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <h2 style={{ margin: '0 0 2px', fontSize: '16px', fontWeight: 700, color: 'var(--text)' }}>
                    {selectedTier.name}
                  </h2>
                  {selectedTier.description && (
                    <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-muted)' }}>{selectedTier.description}</p>
                  )}
                </div>
                <button
                  onClick={handleAddBenefit}
                  disabled={addingBenefit}
                  style={{ padding: '7px 14px', borderRadius: 'var(--radius-md, 8px)', background: 'var(--surface-hover)', color: 'var(--text-secondary)', fontWeight: 600, fontSize: '13px', border: '1px solid var(--border)', cursor: addingBenefit ? 'not-allowed' : 'pointer', opacity: addingBenefit ? 0.7 : 1 }}
                >
                  {addingBenefit ? 'Adding…' : '+ Add benefit'}
                </button>
              </div>

              {tierBenefits.length === 0 ? (
                <div style={{ padding: '32px' }}>
                  <EmptyState
                    icon="M12 4v16m8-8H4"
                    title="No benefits yet"
                    description='Click "Add benefit" to define entitlements for this tier.'
                  />
                </div>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface-2)' }}>
                      <th style={{ width: '36px', padding: '10px 12px' }} />
                      {['Name', 'Value type', 'Value', 'Mandatory'].map(h => (
                        <th key={h} style={{ padding: '10px 8px', textAlign: 'left', fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {tierBenefits.map(benefit => (
                      <BenefitRow
                        key={benefit.id}
                        benefit={benefit}
                        onSave={onSaveBenefit}
                        onSaved={toast.show}
                      />
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default PolicyBuilder;
