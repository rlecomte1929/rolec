/**
 * AbTestExperimentCard.tsx — PRODUCT-6E
 * Card showing a single A/B experiment's status, metrics, and controls.
 */

import React, { useState } from 'react';
import { Button } from '../../components/antigravity/Button';
import { isSignificant } from '../../lib/stats';

// ─── Types (mirror AnalysisPayload from friction-analysis edge function) ───────

export interface StepResult {
  step: string;
  control_users: number;
  variant_users: number;
  control_conversions: number;
  variant_conversions: number;
  control_rate: number;
  variant_rate: number;
  significance: {
    significant: boolean;
    pValue: number;
    relativeUplift: number;
    confidenceInterval: [number, number];
  };
}

export interface ExperimentResult {
  flag_name: string;
  variant: string;
  total_control_users: number;
  total_variant_users: number;
  steps: StepResult[];
}

export interface FeatureFlag {
  enabled: boolean;
  variants: string[];
  traffic_split: number[];
  description?: string;
}

interface Props {
  flag_name: string;
  flag: FeatureFlag;
  experiment: ExperimentResult | null; // null = no data yet
  onPromote: (flagName: string, variant: string) => Promise<void>;
  onRollback: (flagName: string) => Promise<void>;
}

// ─── Status badge ─────────────────────────────────────────────────────────────

type ExperimentStatus = 'disabled' | 'running' | 'significant_winner' | 'insufficient_data';

function deriveStatus(flag: FeatureFlag, experiment: ExperimentResult | null): ExperimentStatus {
  if (!flag.enabled) return 'disabled';
  if (!experiment) return 'insufficient_data';

  // Check if any funnel step has a significant difference
  const hasSignificantStep = experiment.steps.some(s => s.significance.significant);
  if (hasSignificantStep) return 'significant_winner';

  const hasEnoughData =
    experiment.total_control_users >= 100 && experiment.total_variant_users >= 100;
  return hasEnoughData ? 'running' : 'insufficient_data';
}

const STATUS_CONFIG: Record<ExperimentStatus, { label: string; classes: string; dot: string }> = {
  disabled: {
    label: 'Disabled',
    classes: 'bg-slate-100 text-slate-500',
    dot: 'bg-slate-400',
  },
  running: {
    label: 'Running',
    classes: 'bg-blue-50 text-blue-700',
    dot: 'bg-blue-500',
  },
  significant_winner: {
    label: 'Significant Winner',
    classes: 'bg-emerald-50 text-emerald-700',
    dot: 'bg-emerald-500',
  },
  insufficient_data: {
    label: 'Insufficient Data',
    classes: 'bg-amber-50 text-amber-700',
    dot: 'bg-amber-400',
  },
};

function StatusBadge({ status }: { status: ExperimentStatus }) {
  const cfg = STATUS_CONFIG[status];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${cfg.classes}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function pct(rate: number) {
  return `${(rate * 100).toFixed(1)}%`;
}

function upliftLabel(uplift: number) {
  if (uplift === 0) return '—';
  const sign = uplift > 0 ? '+' : '';
  return `${sign}${(uplift * 100).toFixed(1)}%`;
}

function upliftColor(uplift: number) {
  if (uplift > 0) return 'text-emerald-600';
  if (uplift < 0) return 'text-red-500';
  return 'text-slate-500';
}

function friendlyStep(step: string) {
  return step.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// ─── Component ────────────────────────────────────────────────────────────────

export const AbTestExperimentCard: React.FC<Props> = ({
  flag_name,
  flag,
  experiment,
  onPromote,
  onRollback,
}) => {
  const status = deriveStatus(flag, experiment);
  const [promoting, setPromoting] = useState(false);
  const [rollingBack, setRollingBack] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  async function handlePromote() {
    if (!experiment) return;
    setPromoting(true);
    setActionMsg(null);
    try {
      await onPromote(flag_name, experiment.variant);
      setActionMsg('✅ Promote request sent. Refresh Edge Config to confirm.');
    } catch (err) {
      setActionMsg(`❌ ${err instanceof Error ? err.message : 'Promote failed'}`);
    } finally {
      setPromoting(false);
    }
  }

  async function handleRollback() {
    setRollingBack(true);
    setActionMsg(null);
    try {
      await onRollback(flag_name);
      setActionMsg('✅ Rollback request sent. Flag reset to 100% control.');
    } catch (err) {
      setActionMsg(`❌ ${err instanceof Error ? err.message : 'Rollback failed'}`);
    } finally {
      setRollingBack(false);
    }
  }

  // Re-compute significance against live stats library for display
  const significantSteps = experiment
    ? experiment.steps.filter(s => {
        const result = isSignificant(
          s.control_conversions, s.control_users,
          s.variant_conversions, s.variant_users,
        );
        return result.significant;
      })
    : [];

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 flex items-start justify-between gap-3 border-b border-slate-100">
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-1">
            Feature Flag
          </p>
          <h3 className="text-sm font-semibold text-slate-900 font-mono">{flag_name}</h3>
          {flag.description && (
            <p className="text-xs text-slate-500 mt-0.5">{flag.description}</p>
          )}
        </div>
        <StatusBadge status={status} />
      </div>

      {/* Traffic split */}
      <div className="px-5 py-3 flex items-center gap-4 bg-slate-50 border-b border-slate-100">
        <span className="text-xs text-slate-500">Traffic split:</span>
        {flag.variants.map((v, i) => (
          <span key={v} className="text-xs font-medium text-slate-700">
            {v}: <span className="text-slate-900">{flag.traffic_split[i] ?? 0}%</span>
          </span>
        ))}
        {experiment && (
          <>
            <span className="text-slate-200">|</span>
            <span className="text-xs text-slate-500">
              Control users: <span className="font-medium text-slate-700">{experiment.total_control_users.toLocaleString()}</span>
            </span>
            <span className="text-xs text-slate-500">
              Variant users: <span className="font-medium text-slate-700">{experiment.total_variant_users.toLocaleString()}</span>
            </span>
          </>
        )}
      </div>

      {/* Metrics table */}
      {experiment ? (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-100">
                <th className="px-5 py-2.5 text-left font-semibold text-slate-500 uppercase tracking-wide text-[10px]">Funnel Step</th>
                <th className="px-3 py-2.5 text-right font-semibold text-slate-500 uppercase tracking-wide text-[10px]">Control</th>
                <th className="px-3 py-2.5 text-right font-semibold text-slate-500 uppercase tracking-wide text-[10px]">Variant</th>
                <th className="px-3 py-2.5 text-right font-semibold text-slate-500 uppercase tracking-wide text-[10px]">Uplift</th>
                <th className="px-3 py-2.5 text-right font-semibold text-slate-500 uppercase tracking-wide text-[10px]">p-value</th>
                <th className="px-5 py-2.5 text-right font-semibold text-slate-500 uppercase tracking-wide text-[10px]">Sig.</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {experiment.steps.map(step => {
                const live = isSignificant(
                  step.control_conversions, step.control_users,
                  step.variant_conversions, step.variant_users,
                );
                return (
                  <tr key={step.step} className="hover:bg-slate-50 transition-colors">
                    <td className="px-5 py-2.5 text-slate-700 font-medium">{friendlyStep(step.step)}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-600">{pct(step.control_rate)}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-600">{pct(step.variant_rate)}</td>
                    <td className={`px-3 py-2.5 text-right tabular-nums font-medium ${upliftColor(live.relativeUplift)}`}>
                      {upliftLabel(live.relativeUplift)}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-500">
                      {live.pValue < 0.001 ? '<0.001' : live.pValue.toFixed(3)}
                    </td>
                    <td className="px-5 py-2.5 text-right">
                      {live.significant ? (
                        <span className="inline-flex items-center gap-1 text-emerald-600 font-semibold">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
                          Yes
                        </span>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="px-5 py-6 text-center">
          <p className="text-xs text-slate-500">
            {flag.enabled
              ? 'No friction analysis data yet — the daily job runs at 04:00 UTC.'
              : 'Enable this flag in Edge Config to start collecting data.'}
          </p>
        </div>
      )}

      {/* Significance summary */}
      {significantSteps.length > 0 && (
        <div className="px-5 py-3 bg-emerald-50 border-t border-emerald-100">
          <p className="text-xs text-emerald-700">
            <span className="font-semibold">{significantSteps.length} step{significantSteps.length > 1 ? 's' : ''} show statistically significant improvement</span>
            {' '}— variant_a is outperforming control at α = 0.05.
          </p>
        </div>
      )}

      {/* Actions */}
      <div className="px-5 py-3 flex items-center gap-3 border-t border-slate-100">
        <Button unstyled
          onClick={handlePromote}
          disabled={promoting || rollingBack || status !== 'significant_winner'}
          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          title={status !== 'significant_winner' ? 'Only available when experiment shows a significant winner' : 'Set variant to 100% traffic'}
        >
          {promoting ? 'Promoting…' : 'Promote Winner'}
        </Button>
        <Button unstyled
          onClick={handleRollback}
          disabled={promoting || rollingBack || !flag.enabled}
          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 hover:border-slate-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          title={!flag.enabled ? 'Flag is already disabled' : 'Reset to 100% control'}
        >
          {rollingBack ? 'Rolling back…' : 'Rollback'}
        </Button>
        {actionMsg && (
          <p className="text-xs text-slate-600 ml-1">{actionMsg}</p>
        )}
      </div>
    </div>
  );
};
