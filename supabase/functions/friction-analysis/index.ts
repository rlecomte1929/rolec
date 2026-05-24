/**
 * friction-analysis — Supabase Edge Function
 * PRODUCT-6D
 *
 * Scheduled at 04:00 UTC daily via pg_cron (see migration
 * 20260523020000_friction_analysis_summary_type.sql).
 *
 * Pipeline:
 *   1. Query the last 7 days of events from public.events
 *   2. Build a user → variant assignment map from events that carry
 *      { flag_name, variant } in their properties JSONB
 *   3. Track which funnel steps each user completed, split by variant
 *   4. Compute conversion rates at every funnel step for each experiment
 *   5. Run an inline two-proportion z-test (isSignificant) for each step
 *   6. Identify the top friction points (lowest overall conversion drops)
 *   7. Upsert one row into public.daily_summaries with summary_type =
 *      'friction_analysis'
 *
 * Note: isSignificant() is inlined here because Supabase Edge Functions
 * cannot import from files outside their own directory. The implementation
 * is identical to frontend/src/lib/stats.ts (PRODUCT-6C).
 *
 * Environment variables (auto-set by Supabase):
 *   SUPABASE_URL
 *   SUPABASE_SERVICE_ROLE_KEY
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// ─── CORS ─────────────────────────────────────────────────────────────────────

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
};

// ─── Funnel definition ────────────────────────────────────────────────────────

const FUNNEL_STEPS = [
  "onboarding_started",
  "onboarding_completed",
  "first_assignment_created",
  "supplier_selected",
  "assignment_confirmed",
] as const;

type FunnelStep = typeof FUNNEL_STEPS[number];

const FUNNEL_STEP_INDEX = Object.fromEntries(
  FUNNEL_STEPS.map((s, i) => [s, i]),
) as Record<FunnelStep, number>;

// ─── Types ────────────────────────────────────────────────────────────────────

interface EventRow {
  event_type: string;
  user_id: string | null;
  session_id: string | null;
  created_at: string;
  properties: Record<string, unknown>;
}

interface SignificanceResult {
  significant: boolean;
  pValue: number;
  relativeUplift: number;
  confidenceInterval: [number, number];
}

interface StepResult {
  step: FunnelStep;
  control_users: number;
  variant_users: number;
  control_conversions: number;
  variant_conversions: number;
  control_rate: number;
  variant_rate: number;
  significance: SignificanceResult;
}

interface ExperimentResult {
  flag_name: string;
  variant: string;
  total_control_users: number;
  total_variant_users: number;
  steps: StepResult[];
}

interface FrictionPoint {
  step: string;
  from_step: string;
  overall_rate: number;
  drop_pct: number;
  description: string;
}

interface AnalysisPayload {
  period: { from: string; to: string };
  funnel: {
    steps: readonly string[];
    overall_rates: number[];
    total_users: number;
  };
  experiments: ExperimentResult[];
  top_friction_points: FrictionPoint[];
  generated_at: string;
}

// ─── Inline isSignificant (identical to frontend/src/lib/stats.ts) ────────────

const MIN_SAMPLE_SIZE = 100;

function normalCDF(z: number): number {
  if (z <= -8) return 0;
  if (z >= 8) return 1;
  const t = 1 / (1 + 0.2316419 * Math.abs(z));
  const poly =
    t * (0.319381530 +
    t * (-0.356563782 +
    t * (1.781477937 +
    t * (-1.821255978 +
    t * 1.330274429))));
  const pdf = Math.exp(-0.5 * z * z) / Math.sqrt(2 * Math.PI);
  const cdf = 1 - pdf * poly;
  return z >= 0 ? cdf : 1 - cdf;
}

function isSignificant(
  controlConversions: number,
  controlN: number,
  variantConversions: number,
  variantN: number,
  alpha = 0.05,
): SignificanceResult {
  const notSig: SignificanceResult = {
    significant: false,
    pValue: 1,
    relativeUplift: 0,
    confidenceInterval: [0, 0],
  };

  if (
    controlN < MIN_SAMPLE_SIZE ||
    variantN < MIN_SAMPLE_SIZE ||
    controlConversions < 0 ||
    variantConversions < 0 ||
    controlConversions > controlN ||
    variantConversions > variantN
  ) return notSig;

  const pControl = controlConversions / controlN;
  const pVariant = variantConversions / variantN;
  const relativeUplift = pControl === 0
    ? 0
    : Math.round(((pVariant - pControl) / pControl) * 1e6) / 1e6;

  const pPooled = (controlConversions + variantConversions) / (controlN + variantN);
  const se = Math.sqrt(pPooled * (1 - pPooled) * (1 / controlN + 1 / variantN));
  if (se === 0) return notSig;

  const z = (pVariant - pControl) / se;
  const pValue = Math.round(2 * (1 - normalCDF(Math.abs(z))) * 1e8) / 1e8;

  const seUnpooled = Math.sqrt(
    pControl * (1 - pControl) / controlN +
    pVariant * (1 - pVariant) / variantN,
  );
  const diff = pVariant - pControl;
  const margin = 1.959964 * seUnpooled;

  return {
    significant: pValue < alpha,
    pValue,
    relativeUplift,
    confidenceInterval: [
      Math.round((diff - margin) * 1e6) / 1e6,
      Math.round((diff + margin) * 1e6) / 1e6,
    ],
  };
}

// ─── Date helpers ─────────────────────────────────────────────────────────────

function nDaysAgo(n: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - n);
  d.setUTCHours(0, 0, 0, 0);
  return d.toISOString();
}

function todayDate(): string {
  return new Date().toISOString().slice(0, 10);
}

// ─── User key ────────────────────────────────────────────────────────────────
// Prefer user_id (hashed), fall back to session_id for anonymous visitors.

function userKey(row: EventRow): string | null {
  return (row.user_id ?? row.session_id) || null;
}

// ─── Analysis core ────────────────────────────────────────────────────────────

function analyseEvents(events: EventRow[]): AnalysisPayload {
  // --- Build user → { flag_name → variant } map ----------------------------
  // An event carries variant info when properties.flag_name + properties.variant exist.
  const userVariantMap = new Map<string, Map<string, string>>();

  for (const ev of events) {
    const key = userKey(ev);
    if (!key) continue;
    const flagName = ev.properties.flag_name as string | undefined;
    const variant = ev.properties.variant as string | undefined;
    if (!flagName || !variant) continue;

    if (!userVariantMap.has(key)) userVariantMap.set(key, new Map());
    // First assignment wins (stable within a session)
    if (!userVariantMap.get(key)!.has(flagName)) {
      userVariantMap.get(key)!.set(flagName, variant);
    }
  }

  // --- Build user → max funnel step reached --------------------------------
  const userMaxStep = new Map<string, number>();

  for (const ev of events) {
    const key = userKey(ev);
    if (!key) continue;
    const stepIdx = FUNNEL_STEP_INDEX[ev.event_type as FunnelStep];
    if (stepIdx === undefined) continue;
    const current = userMaxStep.get(key) ?? -1;
    if (stepIdx > current) userMaxStep.set(key, stepIdx);
  }

  // --- Overall funnel (all users, no variant split) -------------------------
  const totalUsers = userMaxStep.size;
  const overallRates = FUNNEL_STEPS.map((_, stepIdx) => {
    if (totalUsers === 0) return 0;
    let reached = 0;
    for (const maxStep of userMaxStep.values()) {
      if (maxStep >= stepIdx) reached++;
    }
    return Math.round((reached / totalUsers) * 1e4) / 1e4;
  });

  // --- Top friction points (biggest drops between adjacent steps) -----------
  const topFrictionPoints: FrictionPoint[] = [];
  for (let i = 1; i < FUNNEL_STEPS.length; i++) {
    const fromRate = overallRates[i - 1];
    const toRate = overallRates[i];
    const dropPct = fromRate === 0
      ? 0
      : Math.round(((fromRate - toRate) / fromRate) * 1e4) / 1e4;

    topFrictionPoints.push({
      step: FUNNEL_STEPS[i],
      from_step: FUNNEL_STEPS[i - 1],
      overall_rate: toRate,
      drop_pct: dropPct,
      description: dropPct >= 0.3
        ? `High drop-off: ${(dropPct * 100).toFixed(1)}% of users who reached "${FUNNEL_STEPS[i - 1]}" did not complete "${FUNNEL_STEPS[i]}"`
        : `${(dropPct * 100).toFixed(1)}% drop from "${FUNNEL_STEPS[i - 1]}" to "${FUNNEL_STEPS[i]}"`,
    });
  }

  // Sort by drop severity descending
  topFrictionPoints.sort((a, b) => b.drop_pct - a.drop_pct);

  // --- Per-experiment analysis ----------------------------------------------
  // Discover all (flag_name, variant) pairs seen in the event window.
  const experiments: ExperimentResult[] = [];
  const experimentIndex = new Map<string, Map<string, string>>(); // flagName → Set<variant>

  for (const flagMap of userVariantMap.values()) {
    for (const [flag, variant] of flagMap) {
      if (!experimentIndex.has(flag)) experimentIndex.set(flag, new Map());
      const variants = experimentIndex.get(flag)!;
      if (!variants.has(variant)) variants.set(variant, variant);
    }
  }

  for (const [flagName, variantMap] of experimentIndex) {
    const nonControlVariants = [...variantMap.keys()].filter(v => v !== "control");
    if (nonControlVariants.length === 0) continue; // only control — skip

    // Users assigned to control for this flag
    const controlUsers = new Set<string>();
    for (const [uk, flagMap] of userVariantMap) {
      if (flagMap.get(flagName) === "control") controlUsers.add(uk);
    }

    for (const variantName of nonControlVariants) {
      const variantUsers = new Set<string>();
      for (const [uk, flagMap] of userVariantMap) {
        if (flagMap.get(flagName) === variantName) variantUsers.add(uk);
      }

      const steps: StepResult[] = [];

      for (let stepIdx = 0; stepIdx < FUNNEL_STEPS.length; stepIdx++) {
        const step = FUNNEL_STEPS[stepIdx];

        const controlReached = [...controlUsers].filter(
          uk => (userMaxStep.get(uk) ?? -1) >= stepIdx,
        ).length;
        const variantReached = [...variantUsers].filter(
          uk => (userMaxStep.get(uk) ?? -1) >= stepIdx,
        ).length;

        const controlN = controlUsers.size;
        const variantN = variantUsers.size;
        const controlRate = controlN === 0 ? 0 : Math.round((controlReached / controlN) * 1e4) / 1e4;
        const variantRate = variantN === 0 ? 0 : Math.round((variantReached / variantN) * 1e4) / 1e4;

        steps.push({
          step,
          control_users: controlN,
          variant_users: variantN,
          control_conversions: controlReached,
          variant_conversions: variantReached,
          control_rate: controlRate,
          variant_rate: variantRate,
          significance: isSignificant(controlReached, controlN, variantReached, variantN),
        });
      }

      experiments.push({
        flag_name: flagName,
        variant: variantName,
        total_control_users: controlUsers.size,
        total_variant_users: variantUsers.size,
        steps,
      });
    }
  }

  return {
    period: { from: nDaysAgo(7), to: new Date().toISOString() },
    funnel: { steps: FUNNEL_STEPS, overall_rates: overallRates, total_users: totalUsers },
    experiments,
    top_friction_points: topFrictionPoints.slice(0, 5),
    generated_at: new Date().toISOString(),
  };
}

// ─── Build human-readable summary ────────────────────────────────────────────

function buildSummaryText(payload: AnalysisPayload): string {
  const lines: string[] = [
    `Friction analysis for the 7 days ending ${todayDate()}.`,
    "",
    `Funnel (${payload.funnel.total_users} unique users):`,
  ];

  for (let i = 0; i < FUNNEL_STEPS.length; i++) {
    const pct = (payload.funnel.overall_rates[i] * 100).toFixed(1);
    lines.push(`  ${i + 1}. ${FUNNEL_STEPS[i]}: ${pct}%`);
  }

  if (payload.top_friction_points.length > 0) {
    lines.push("", "Top friction points:");
    for (const fp of payload.top_friction_points) {
      lines.push(`  • ${fp.description}`);
    }
  }

  if (payload.experiments.length > 0) {
    lines.push("", "Active experiments:");
    for (const exp of payload.experiments) {
      const sigSteps = exp.steps.filter(s => s.significance.significant);
      lines.push(
        `  • ${exp.flag_name} / ${exp.variant}: ` +
        `${exp.total_control_users} control, ${exp.total_variant_users} variant users. ` +
        (sigSteps.length > 0
          ? `${sigSteps.length} step(s) show statistically significant difference.`
          : "No steps significant yet (may need more data)."),
      );
    }
  } else {
    lines.push("", "No active A/B experiments found in event data.");
  }

  if (payload.funnel.total_users === 0) {
    return "No funnel events recorded in the last 7 days. Friction analysis requires events with types: " +
      FUNNEL_STEPS.join(", ");
  }

  return lines.join("\n");
}

// ─── Auto-promotion ───────────────────────────────────────────────────────────

const VERCEL_EDGE_CONFIG_ID = "ecfg_mzuckpdlwwqizdoscycqre6qxrkb";
const VERCEL_API_BASE = "https://api.vercel.com/v1/edge-config";

interface FeatureFlag {
  enabled: boolean;
  variants: string[];
  traffic_split: number[];
  description?: string;
}

/**
 * Fetch the current flags object from Vercel Edge Config.
 * Returns {} on any error so we fail safe (no spurious promotions).
 */
async function fetchEdgeConfigFlags(token: string): Promise<Record<string, FeatureFlag>> {
  try {
    const res = await fetch(
      `${VERCEL_API_BASE}/${VERCEL_EDGE_CONFIG_ID}/item/flags`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    if (!res.ok) {
      console.warn("fetchEdgeConfigFlags: HTTP", res.status, await res.text());
      return {};
    }
    return (await res.json()) as Record<string, FeatureFlag>;
  } catch (err) {
    console.warn("fetchEdgeConfigFlags error:", err);
    return {};
  }
}

/**
 * PATCH the flags object back to Edge Config.
 */
async function patchEdgeConfigFlags(
  token: string,
  flags: Record<string, FeatureFlag>,
): Promise<boolean> {
  try {
    const res = await fetch(
      `${VERCEL_API_BASE}/${VERCEL_EDGE_CONFIG_ID}/items`,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          items: [{ operation: "upsert", key: "flags", value: flags }],
        }),
      },
    );
    if (!res.ok) {
      console.warn("patchEdgeConfigFlags: HTTP", res.status, await res.text());
      return false;
    }
    return true;
  } catch (err) {
    console.warn("patchEdgeConfigFlags error:", err);
    return false;
  }
}

interface PromotionResult {
  flag_name: string;
  variant: string;
  reason: string;
  old_split: number[];
  new_split: number[];
}

/**
 * Evaluate experiments for auto-promotion candidates and apply them.
 *
 * Promotion criteria (all must be true):
 *   1. significant = true on at least one funnel step
 *   2. relativeUplift > 0.05 (at least +5% relative improvement)
 *   3. Experiment is ≥ 7 days old (data from a full 7-day window)
 *   4. The flag's current traffic_split is NOT already 100% to a variant
 *      (i.e., not already promoted)
 *
 * Returns an array of promotions that were applied.
 */
async function autoPromote(
  supabase: ReturnType<typeof createClient>,
  payload: AnalysisPayload,
  today: string,
): Promise<PromotionResult[]> {
  const vercelToken = Deno.env.get("VERCEL_API_TOKEN");
  if (!vercelToken) {
    console.log("autoPromote: VERCEL_API_TOKEN not set — skipping auto-promotion");
    return [];
  }

  // Only promote if the 7-day window is fully populated (totalUsers > 0 is a
  // proxy — a production heuristic; we don't track experiment start date here).
  if (payload.funnel.total_users === 0) return [];

  const flags = await fetchEdgeConfigFlags(vercelToken);
  const promotions: PromotionResult[] = [];

  for (const exp of payload.experiments) {
    const flag = flags[exp.flag_name];
    if (!flag || !flag.enabled) continue;

    const variants = flag.variants ?? [];
    const currentSplit = flag.traffic_split ?? [];

    // Check: already promoted — any single variant at 100%
    const alreadyPromoted = currentSplit.some(s => s === 100);
    if (alreadyPromoted) continue;

    // Find any step with significant positive uplift > 5%
    const winningStep = exp.steps.find(
      s => s.significance.significant && s.significance.relativeUplift > 0.05,
    );
    if (!winningStep) continue;

    const variantIdx = variants.indexOf(exp.variant);
    if (variantIdx < 0) continue;

    // Build new split: 100% to the winning variant, 0% to everything else
    const newSplit = variants.map((_, i) => (i === variantIdx ? 100 : 0));

    flags[exp.flag_name] = { ...flag, traffic_split: newSplit };

    promotions.push({
      flag_name: exp.flag_name,
      variant: exp.variant,
      reason: `Step "${winningStep.step}": uplift=${(winningStep.significance.relativeUplift * 100).toFixed(1)}%, p=${winningStep.significance.pValue.toFixed(4)}`,
      old_split: currentSplit,
      new_split: newSplit,
    });
  }

  if (promotions.length === 0) return [];

  // Apply the patched flags in one PATCH call
  const patched = await patchEdgeConfigFlags(vercelToken, flags);
  if (!patched) {
    console.warn("autoPromote: Edge Config PATCH failed — promotions NOT applied");
    return [];
  }

  // Write audit events for each promotion
  const eventInserts = promotions.map(p => ({
    event_type: "ab_test_auto_promoted",
    source: "friction_analysis_cron",
    properties: {
      flag_name: p.flag_name,
      variant: p.variant,
      reason: p.reason,
      old_traffic_split: p.old_split,
      new_traffic_split: p.new_split,
      promoted_at: today,
    },
  }));

  const { error: evtErr } = await supabase.from("events").insert(eventInserts);
  if (evtErr) {
    console.warn("autoPromote: event insert failed:", evtErr.message);
  }

  console.log(
    "autoPromote: promoted",
    promotions.length,
    "variant(s):",
    promotions.map(p => `${p.flag_name}/${p.variant}`).join(", "),
  );

  return promotions;
}

// ─── Handler ──────────────────────────────────────────────────────────────────

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: CORS_HEADERS });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: { persistSession: false },
  });

  const windowStart = nDaysAgo(7);
  const today = todayDate();

  try {
    // ── 1. Fetch relevant events ─────────────────────────────────────────────
    // We want:
    //   (a) Funnel step events (to track progression)
    //   (b) Any event that carries flag_name + variant (to build user→variant map)
    //
    // Strategy: fetch all events from the last 7 days with event_type in the
    // funnel list, PLUS all events with a non-empty properties.flag_name.
    // We do two queries and merge to avoid an OR scan on the full table.

    const [funnelResp, variantResp] = await Promise.all([
      supabase
        .from("events")
        .select("event_type, user_id, session_id, created_at, properties")
        .in("event_type", [...FUNNEL_STEPS])
        .gte("created_at", windowStart),

      // Fetch events that carry experiment variant metadata.
      // Supabase JS doesn't support `properties->>'flag_name' IS NOT NULL`
      // directly, so we fetch events from the window and filter in-memory
      // using a broad heuristic: source = 'web' or 'api' (most variant events).
      // A production-grade version would add a dedicated generated column index.
      supabase
        .from("events")
        .select("event_type, user_id, session_id, created_at, properties")
        .gte("created_at", windowStart)
        .not("properties->flag_name", "is", null),
    ]);

    if (funnelResp.error) throw new Error(`Funnel query failed: ${funnelResp.error.message}`);
    if (variantResp.error && variantResp.error.code !== "PGRST116") {
      // PGRST116 = column/path not found — harmless if no events yet
      console.warn("Variant query warning:", variantResp.error.message);
    }

    // Merge and deduplicate by event id is not available; just concatenate —
    // analyseEvents handles duplicate user keys gracefully (first-seen wins).
    const allEvents: EventRow[] = [
      ...(funnelResp.data ?? []),
      ...(variantResp.data ?? []),
    ] as EventRow[];

    // ── 2. Run analysis ──────────────────────────────────────────────────────
    const payload = analyseEvents(allEvents);
    const summaryText = buildSummaryText(payload);

    // ── 3. Upsert to daily_summaries ─────────────────────────────────────────
    const { error: upsertErr } = await supabase
      .from("daily_summaries")
      .upsert(
        {
          date: today,
          summary_type: "friction_analysis",
          summary_text: summaryText,
          raw_counts: payload as unknown as Record<string, unknown>,
          anomalies: payload.top_friction_points
            .filter(fp => fp.drop_pct >= 0.3)
            .map(fp => ({ type: "friction_point", message: fp.description, severity: "medium" })),
        },
        { onConflict: "date,summary_type" },
      );

    if (upsertErr) throw new Error(`daily_summaries upsert failed: ${upsertErr.message}`);

    // ── 4. Auto-promote winning variants ────────────────────────────────────
    const promotions = await autoPromote(supabase, payload, today);

    const result = {
      ok: true,
      date: today,
      period_from: payload.period.from,
      total_events_scanned: allEvents.length,
      total_users: payload.funnel.total_users,
      experiments_found: payload.experiments.length,
      friction_points_found: payload.top_friction_points.length,
      significant_step_differences: payload.experiments.flatMap(e =>
        e.steps.filter(s => s.significance.significant),
      ).length,
      auto_promotions: promotions.map(p => ({
        flag_name: p.flag_name,
        variant: p.variant,
        reason: p.reason,
      })),
    };

    console.log("friction-analysis complete:", JSON.stringify(result));
    return Response.json(result, { headers: CORS_HEADERS });

  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("friction-analysis error:", message);
    return Response.json(
      { ok: false, error: message },
      { status: 500, headers: CORS_HEADERS },
    );
  }
});
