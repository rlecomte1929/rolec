/**
 * supplier-scorer.ts — outcome-aware supplier matching score algorithm
 * ─────────────────────────────────────────────────────────────────────────────
 * Reads from public.supplier_stats (materialised view, refreshed nightly) and
 * applies contextual adjustments to rank suppliers for a given assignment context.
 *
 * Score architecture:
 *   1. BASE score    — avg_overall_score from supplier_stats (1.0–5.0 range)
 *   2. VOLUME bonus  — small uplift for suppliers with more outcomes (trust signal)
 *   3. RECENCY decay — down-weight suppliers with no recent assignments
 *   4. ON-TIME boost  — on_time_rate directly amplifies the base score
 *   5. BUDGET bonus  — under-budget suppliers get a small boost
 *   6. NORMALISE     — scale to 0–100 for UI display
 *
 * Usage:
 *   const ranked = await rankSuppliers(supabase, { serviceType: 'immigration' });
 *   // → [{ supplier_id, name, score, rank, stats }, ...]
 * ─────────────────────────────────────────────────────────────────────────────
 */

import type { SupabaseClient } from '@supabase/supabase-js';
import { logger } from './logger';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface SupplierStats {
  supplier_id: string;
  supplier_name: string;
  total_assignments: number;
  avg_quality_score: number | null;
  avg_speed_score: number | null;
  avg_communication_score: number | null;
  avg_overall_score: number | null;
  on_time_rate: number | null;         // 0.0–1.0
  avg_budget_variance_pct: number | null; // negative = under budget (good)
  last_outcome_at: string | null;
}

export interface ScoredSupplier {
  supplier_id: string;
  supplier_name: string;
  score: number;          // 0–100 (normalised for display)
  raw_score: number;      // pre-normalisation composite score
  rank: number;           // 1 = best
  confidence: 'high' | 'medium' | 'low' | 'none';
  stats: SupplierStats;
  score_breakdown: ScoreBreakdown;
}

export interface ScoreBreakdown {
  base: number;           // avg_overall_score (or default if no outcomes yet)
  volume_bonus: number;
  recency_factor: number; // 0.0–1.0 multiplier
  on_time_bonus: number;
  budget_bonus: number;
  composite: number;      // sum before normalisation
}

export interface ScoringContext {
  /** Optional: only consider suppliers with at least N outcomes */
  min_outcomes?: number;
  /** Optional: ISO date string — outcomes older than this are excluded from recency calc */
  recency_cutoff_days?: number;
  /** Optional: exclude suppliers with on_time_rate below threshold */
  min_on_time_rate?: number;
}

// ─── Scoring constants ────────────────────────────────────────────────────────

const DEFAULT_SCORE = 3.0;        // score for suppliers with no outcomes yet
const MAX_VOLUME_BONUS = 0.5;     // bonus at 50+ outcomes
const VOLUME_SCALE = 50;          // outcomes needed to reach full volume bonus
const RECENCY_CUTOFF_DAYS = 180;  // 6 months — older outcomes get decay
const ON_TIME_WEIGHT = 0.4;       // multiplier for on_time_rate bonus
const BUDGET_WEIGHT = 0.05;       // per-percentage-point under budget

// ─── Score calculation ────────────────────────────────────────────────────────

function calculateRecencyFactor(lastOutcomeAt: string | null, cutoffDays: number): number {
  if (!lastOutcomeAt) return 0.5; // unknown recency → moderate discount
  const daysSince = (Date.now() - new Date(lastOutcomeAt).getTime()) / (1000 * 60 * 60 * 24);
  if (daysSince <= 30) return 1.0;   // very recent: no discount
  if (daysSince >= cutoffDays) return 0.6; // stale: max discount
  // Linear decay from 1.0 to 0.6 between 30 and cutoffDays
  return 1.0 - (0.4 * (daysSince - 30) / (cutoffDays - 30));
}

function calculateVolumeBonus(totalAssignments: number): number {
  return MAX_VOLUME_BONUS * Math.min(totalAssignments / VOLUME_SCALE, 1.0);
}

function calculateOnTimeBonus(onTimeRate: number | null): number {
  if (onTimeRate === null) return 0;
  // 1.0 rate → full bonus; 0.5 rate → 0 bonus; below 0.5 → slight penalty
  return ON_TIME_WEIGHT * (onTimeRate - 0.5) * 2;
}

function calculateBudgetBonus(avgBudgetVariancePct: number | null): number {
  if (avgBudgetVariancePct === null) return 0;
  // Negative variance = under budget = good; cap at ±10%
  const capped = Math.max(-10, Math.min(10, -avgBudgetVariancePct));
  return BUDGET_WEIGHT * capped;
}

function scoreSupplier(
  stats: SupplierStats,
  context: Required<ScoringContext>,
): { breakdown: ScoreBreakdown; composite: number } {
  const hasOutcomes = stats.total_assignments > 0 && stats.avg_overall_score !== null;

  const base = hasOutcomes ? (stats.avg_overall_score ?? DEFAULT_SCORE) : DEFAULT_SCORE;
  const volumeBonus = calculateVolumeBonus(stats.total_assignments);
  const recencyFactor = calculateRecencyFactor(stats.last_outcome_at, context.recency_cutoff_days);
  const onTimeBonus = calculateOnTimeBonus(stats.on_time_rate);
  const budgetBonus = calculateBudgetBonus(stats.avg_budget_variance_pct);

  // Apply recency factor to the base score (not the bonuses — those are already trust-adjusted)
  const composite = (base * recencyFactor) + volumeBonus + onTimeBonus + budgetBonus;

  return {
    breakdown: { base, volume_bonus: volumeBonus, recency_factor: recencyFactor, on_time_bonus: onTimeBonus, budget_bonus: budgetBonus, composite },
    composite,
  };
}

function normalise(value: number, min: number, max: number): number {
  if (max === min) return 50; // all tied — midpoint
  return Math.round(((value - min) / (max - min)) * 100);
}

function confidenceLevel(totalAssignments: number): ScoredSupplier['confidence'] {
  if (totalAssignments === 0) return 'none';
  if (totalAssignments < 3) return 'low';
  if (totalAssignments < 10) return 'medium';
  return 'high';
}

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Fetch supplier_stats from Supabase and return a ranked, scored list.
 *
 * Suppliers with no outcomes are included but ranked at the bottom with
 * confidence: 'none' so HR can still select them for new relationships.
 */
export async function rankSuppliers(
  supabase: SupabaseClient,
  context: ScoringContext = {},
): Promise<ScoredSupplier[]> {
  const ctx: Required<ScoringContext> = {
    min_outcomes: context.min_outcomes ?? 0,
    recency_cutoff_days: context.recency_cutoff_days ?? RECENCY_CUTOFF_DAYS,
    min_on_time_rate: context.min_on_time_rate ?? 0,
  };

  // Fetch all suppliers from the materialised view
  const { data, error } = await supabase
    .from('supplier_stats')
    .select('*')
    .order('total_assignments', { ascending: false });

  if (error) {
    logger.error('supplier-scorer: failed to fetch supplier_stats:', error.message);
    return [];
  }

  const stats = (data ?? []) as SupplierStats[];

  // Apply hard filters
  const filtered = stats.filter((s) => {
    if (ctx.min_outcomes > 0 && s.total_assignments < ctx.min_outcomes) return false;
    if (ctx.min_on_time_rate > 0 && (s.on_time_rate ?? 0) < ctx.min_on_time_rate) return false;
    return true;
  });

  if (filtered.length === 0) return [];

  // Score each supplier
  const scored = filtered.map((s) => {
    const { breakdown, composite } = scoreSupplier(s, ctx);
    return { stats: s, breakdown, composite };
  });

  // Normalise to 0–100
  const composites = scored.map((s) => s.composite);
  const min = Math.min(...composites);
  const max = Math.max(...composites);

  // Sort descending by composite score
  scored.sort((a, b) => b.composite - a.composite);

  return scored.map((s, idx) => ({
    supplier_id: s.stats.supplier_id,
    supplier_name: s.stats.supplier_name,
    score: normalise(s.composite, min, max),
    raw_score: Math.round(s.composite * 100) / 100,
    rank: idx + 1,
    confidence: confidenceLevel(s.stats.total_assignments),
    stats: s.stats,
    score_breakdown: s.breakdown,
  }));
}

/**
 * Score a single supplier against the full pool.
 * Returns null if the supplier is not found in supplier_stats.
 */
export async function scoreSupplierById(
  supabase: SupabaseClient,
  supplierId: string,
  context: ScoringContext = {},
): Promise<ScoredSupplier | null> {
  const ranked = await rankSuppliers(supabase, context);
  return ranked.find((s) => s.supplier_id === supplierId) ?? null;
}
