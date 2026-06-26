/**
 * AdminAbTestsPage.tsx — PRODUCT-6E
 * /admin/ab-tests — A/B experiment health dashboard.
 *
 * Fetches:
 *   1. Current feature flags from get-feature-flags Supabase edge function
 *   2. Latest friction_analysis daily_summary for experiment metrics
 *
 * Admin-only. Non-admin users are blocked by RequireAdminRoute in App.tsx,
 * but we also guard inline for defence-in-depth.
 */

import React, { useEffect, useState } from 'react';
import { useIsAdmin } from '../../features/admin/useIsAdmin';
import { supabase } from '../../lib/supabase';
import { logger } from '../../lib/logger';
import { AbTestExperimentCard } from './AbTestExperimentCard';
import { AdminLayout } from './AdminLayout';
import type { FeatureFlag, ExperimentResult } from './AbTestExperimentCard';

// ─── Types ────────────────────────────────────────────────────────────────────

interface AnalysisPayload {
  period: { from: string; to: string };
  funnel: { steps: string[]; overall_rates: number[]; total_users: number };
  experiments: ExperimentResult[];
  top_friction_points: Array<{ step: string; from_step: string; drop_pct: number; description: string }>;
  generated_at: string;
}

// ─── Promote / Rollback API calls ─────────────────────────────────────────────

async function callPromote(flagName: string, variant: string): Promise<void> {
  const res = await fetch('/api/ab-tests/promote', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ flag_name: flagName, variant }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Promote failed (${res.status}): ${body}`);
  }
}

async function callRollback(flagName: string): Promise<void> {
  const res = await fetch('/api/ab-tests/rollback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ flag_name: flagName }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Rollback failed (${res.status}): ${body}`);
  }
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export const AdminAbTestsPage: React.FC = () => {
  const isAdmin = useIsAdmin();

  const [flags, setFlags] = useState<Record<string, FeatureFlag> | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  useEffect(() => {
    if (!isAdmin) return;

    async function load() {
      setLoading(true);
      setError(null);

      try {
        // 1. Fetch feature flags from edge function
        const { data: flagData, error: flagErr } = await supabase.functions.invoke('get-feature-flags');
        if (flagErr) throw new Error(`Failed to load flags: ${flagErr.message}`);
        setFlags(flagData?.flags ?? {});

        // 2. Fetch latest friction_analysis daily summary
        const { data: summary, error: summaryErr } = await supabase
          .from('daily_summaries')
          .select('date, raw_counts, summary_text')
          .eq('summary_type', 'friction_analysis')
          .order('date', { ascending: false })
          .limit(1)
          .maybeSingle();

        if (summaryErr) {
          logger.warn('[AdminAbTestsPage] friction_analysis query error:', summaryErr.message);
        }

        if (summary?.raw_counts) {
          setAnalysis(summary.raw_counts);
          setLastUpdated(summary.date as string);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error loading dashboard');
      } finally {
        setLoading(false);
      }
    }

    void load();
  }, [isAdmin]);

  // ── 403 guard ────────────────────────────────────────────────────────────────
  if (!isAdmin) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="bg-white rounded-xl border border-red-200 px-8 py-6 text-center shadow-sm">
          <p className="text-2xl font-semibold text-red-600 mb-1">403</p>
          <p className="text-sm text-slate-600">Admin access required.</p>
        </div>
      </div>
    );
  }

  // ── Loading ──────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <AdminLayout title="A/B Tests" subtitle="Experiment health dashboard">
        <div className="flex items-center justify-center py-24">
          <div className="text-sm text-slate-400">Loading experiment data…</div>
        </div>
      </AdminLayout>
    );
  }

  // ── Error ────────────────────────────────────────────────────────────────────
  if (error) {
    return (
      <AdminLayout title="A/B Tests" subtitle="Experiment health dashboard">
        <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-4">
          <p className="text-sm font-semibold text-red-700">Failed to load dashboard</p>
          <p className="text-xs text-red-600 mt-1">{error}</p>
        </div>
      </AdminLayout>
    );
  }

  const flagEntries = Object.entries(flags ?? {});
  const experimentsByFlag = new Map<string, ExperimentResult>(
    (analysis?.experiments ?? []).map(e => [e.flag_name, e]),
  );

  return (
    <AdminLayout
      title="A/B Tests"
      subtitle="Experiment health dashboard"
      headerRight={
        lastUpdated ? (
          <span className="text-xs text-slate-400">
            Last analysis: <span className="font-medium text-slate-600">{lastUpdated}</span>
            {' · '}
            <span className="text-slate-400">runs daily at 04:00 UTC</span>
          </span>
        ) : null
      }
    >
      <div className="space-y-6 max-w-5xl">

        {/* Summary row */}
        {analysis && (
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-white rounded-xl border border-slate-200 px-5 py-4">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">Total Users (7d)</p>
              <p className="text-2xl font-semibold text-slate-900">{analysis.funnel.total_users.toLocaleString()}</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 px-5 py-4">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">Active Experiments</p>
              <p className="text-2xl font-semibold text-slate-900">{analysis.experiments.length}</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 px-5 py-4">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">Top Friction Point</p>
              <p className="text-sm font-semibold text-slate-900 leading-snug">
                {analysis.top_friction_points[0]
                  ? analysis.top_friction_points[0].step.replace(/_/g, ' ')
                  : '—'}
              </p>
              {analysis.top_friction_points[0] && (
                <p className="text-xs text-red-500 mt-0.5">
                  {(analysis.top_friction_points[0].drop_pct * 100).toFixed(1)}% drop-off
                </p>
              )}
            </div>
          </div>
        )}

        {/* Experiment cards */}
        {flagEntries.length === 0 ? (
          <div className="bg-white rounded-xl border border-slate-200 px-6 py-10 text-center">
            <p className="text-sm text-slate-500">No feature flags found in Edge Config.</p>
            <p className="text-xs text-slate-400 mt-1">
              Add flags to the <code className="font-mono bg-slate-100 px-1 rounded">relopass-flags</code> Edge Config store.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {flagEntries.map(([name, flag]) => (
              <AbTestExperimentCard
                key={name}
                flag_name={name}
                flag={flag}
                experiment={experimentsByFlag.get(name) ?? null}
                onPromote={callPromote}
                onRollback={callRollback}
              />
            ))}
          </div>
        )}

        {/* No analysis data notice */}
        {!analysis && flagEntries.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-4">
            <p className="text-xs font-semibold text-amber-700">No friction analysis data yet</p>
            <p className="text-xs text-amber-600 mt-0.5">
              The daily job runs at 04:00 UTC. Enable a flag in Edge Config and wait for the next run,
              or trigger <code className="font-mono bg-amber-100 px-1 rounded">friction-analysis</code> manually from the Supabase dashboard.
            </p>
          </div>
        )}
      </div>
    </AdminLayout>
  );
};
