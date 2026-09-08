/**
 * [P5-6] unanswered-questions-digest — Supabase Edge Function
 *
 * Scheduled weekly (Monday 09:00 UTC via pg_cron + pg_net) or triggerable
 * manually via POST request.
 *
 * Pipeline:
 *   1. Fetch TOPIC_REJECTED + LOW_CONFIDENCE refusal logs for the past 7 days
 *      from ai_refusal_logs, grouped by company.
 *   2. Cluster semantically similar queries using k-means (k=5) on their
 *      stored embedding vectors.
 *   3. Identify the dominant policy category (CAT-01 … CAT-14) per cluster.
 *   4. Render a plain-text digest and send it to the company's configured
 *      HR email via Resend.
 *
 * Privacy:
 *   - Raw query text is NEVER stored in ai_refusal_logs (only embeddings).
 *   - The digest email never surfaces actual user queries — only cluster
 *     themes and counts.
 *
 * Environment variables:
 *   SUPABASE_URL              — set automatically by Supabase
 *   SUPABASE_SERVICE_ROLE_KEY — set automatically by Supabase
 *   RESEND_API_KEY            — Resend API key for email delivery
 *   EMAIL_FROM                — sender address (default: noreply@relopass.com)
 *   APP_URL                   — deep-link in digest email (default: https://app.relopass.com)
 */

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const K_CLUSTERS = 5;
export const MAX_KMEANS_ITER = 30;
export const DIGEST_WINDOW_DAYS = 7;

/** Policy category names (from P2-3 classification taxonomy) */
export const CAT_NAMES: Record<string, string> = {
  'CAT-01': 'Housing & Accommodation',
  'CAT-02': 'Goods Shipment',
  'CAT-03': 'Travel & Flights',
  'CAT-04': 'Tax Assistance',
  'CAT-05': 'Language Training',
  'CAT-06': 'Settling-In Services',
  'CAT-07': 'School & Education',
  'CAT-08': 'Partner & Family Support',
  'CAT-09': 'Insurance & Healthcare',
  'CAT-10': 'Cost-of-Living',
  'CAT-11': 'Lease Break',
  'CAT-12': 'Hardship Allowance',
  'CAT-13': 'Home Sale / Purchase',
  'CAT-14': 'Repatriation',
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface RefusalLog {
  id: string;
  company_id: string;
  query_embedding: number[];
  fallback_reason: string;
  suggested_cat_code: string | null;
  created_at: string;
}

interface CompanyRow {
  id: string;
  name: string;
  hr_contact_email: string | null;
}

export interface Cluster {
  centroid: number[];
  members: RefusalLog[];
  /** Most frequently occurring CAT code in this cluster (null if no suggestions) */
  dominant_cat: string | null;
  /** Per-CAT occurrence counts in this cluster */
  cat_counts: Record<string, number>;
}

// ---------------------------------------------------------------------------
// Vector math
// ---------------------------------------------------------------------------

export function dotProduct(a: number[], b: number[]): number {
  let sum = 0;
  for (let i = 0; i < a.length; i++) sum += a[i] * b[i];
  return sum;
}

export function magnitude(v: number[]): number {
  return Math.sqrt(dotProduct(v, v));
}

/**
 * Cosine distance in [0, 2]. Lower = more similar.
 * Returns 1 for zero vectors (maximum "unknown" distance).
 */
export function cosineDistance(a: number[], b: number[]): number {
  const magA = magnitude(a);
  const magB = magnitude(b);
  if (magA === 0 || magB === 0) return 1;
  const sim = dotProduct(a, b) / (magA * magB);
  // Clamp to [-1, 1] to guard against floating-point drift
  return 1 - Math.max(-1, Math.min(1, sim));
}

/**
 * Arithmetic mean of a set of equal-length vectors.
 */
export function centroidOf(vectors: number[][]): number[] {
  if (vectors.length === 0) return [];
  const dim = vectors[0].length;
  const sum = new Array<number>(dim).fill(0);
  for (const v of vectors) {
    for (let i = 0; i < dim; i++) sum[i] += v[i];
  }
  return sum.map((x) => x / vectors.length);
}

// ---------------------------------------------------------------------------
// K-means clustering (k-means++ initialisation, cosine distance)
// ---------------------------------------------------------------------------

/**
 * Select k initial centroids using the k-means++ strategy.
 * Each successive centroid is sampled with probability proportional to its
 * squared distance from the nearest existing centroid.
 */
export function kMeansInit(embeddings: number[][], k: number): number[][] {
  const n = embeddings.length;
  const actualK = Math.min(k, n);

  // Pick the first centroid uniformly at random
  const firstIdx = Math.floor(Math.random() * n);
  const centroids: number[][] = [embeddings[firstIdx]];

  while (centroids.length < actualK) {
    // Distance of each point to its nearest centroid
    const dists = embeddings.map((e) =>
      Math.min(...centroids.map((c) => cosineDistance(e, c))),
    );
    const total = dists.reduce((a, b) => a + b, 0);

    if (total < 1e-12) {
      // All remaining points are co-located with a centroid — just pick any
      for (let i = 0; i < n && centroids.length < actualK; i++) {
        if (!centroids.some((c) => cosineDistance(c, embeddings[i]) < 1e-10)) {
          centroids.push(embeddings[i]);
        }
      }
      break;
    }

    let r = Math.random() * total;
    let selected = n - 1;
    for (let i = 0; i < n; i++) {
      r -= dists[i];
      if (r <= 0) {
        selected = i;
        break;
      }
    }
    centroids.push(embeddings[selected]);
  }

  return centroids;
}

/**
 * Run k-means clustering on `embeddings` with `k` clusters.
 * Returns the final centroid vectors.
 */
export function kMeans(embeddings: number[][], k: number): number[][] {
  if (embeddings.length === 0) return [];
  const actualK = Math.min(k, embeddings.length);

  const centroids = kMeansInit(embeddings, actualK);

  for (let iter = 0; iter < MAX_KMEANS_ITER; iter++) {
    // Assign each point to the nearest centroid
    const assignments = embeddings.map((e) => {
      let best = 0;
      let bestDist = cosineDistance(e, centroids[0]);
      for (let c = 1; c < centroids.length; c++) {
        const d = cosineDistance(e, centroids[c]);
        if (d < bestDist) {
          bestDist = d;
          best = c;
        }
      }
      return best;
    });

    // Recompute centroids and check for convergence
    let changed = false;
    for (let c = 0; c < centroids.length; c++) {
      const memberVectors = embeddings.filter((_, i) => assignments[i] === c);
      if (memberVectors.length === 0) continue;
      const newCentroid = centroidOf(memberVectors);
      if (cosineDistance(newCentroid, centroids[c]) > 1e-8) {
        centroids[c] = newCentroid;
        changed = true;
      }
    }
    if (!changed) break;
  }

  return centroids;
}

/**
 * Assign each refusal log to its nearest centroid and compute per-cluster stats.
 */
export function assignToClusters(logs: RefusalLog[], centroids: number[][]): Cluster[] {
  const clusters: Cluster[] = centroids.map((c) => ({
    centroid: c,
    members: [],
    dominant_cat: null,
    cat_counts: {},
  }));

  for (const log of logs) {
    let best = 0;
    let bestDist = cosineDistance(log.query_embedding, centroids[0]);
    for (let c = 1; c < centroids.length; c++) {
      const d = cosineDistance(log.query_embedding, centroids[c]);
      if (d < bestDist) {
        bestDist = d;
        best = c;
      }
    }
    clusters[best].members.push(log);
    if (log.suggested_cat_code) {
      clusters[best].cat_counts[log.suggested_cat_code] =
        (clusters[best].cat_counts[log.suggested_cat_code] ?? 0) + 1;
    }
  }

  // Determine dominant CAT code per cluster
  for (const cluster of clusters) {
    const entries = Object.entries(cluster.cat_counts);
    if (entries.length > 0) {
      entries.sort((a, b) => b[1] - a[1]);
      cluster.dominant_cat = entries[0][0];
    }
  }

  return clusters;
}

// ---------------------------------------------------------------------------
// Email rendering
// ---------------------------------------------------------------------------

/**
 * Render the plain-text weekly digest email body.
 *
 * Privacy: never includes actual user queries — only cluster themes and counts.
 */
export function renderDigestEmail(
  companyName: string,
  totalRefusals: number,
  clusters: Cluster[],
  appUrl: string,
): string {
  const nonEmpty = clusters
    .filter((c) => c.members.length > 0)
    .sort((a, b) => b.members.length - a.members.length);

  if (totalRefusals === 0) {
    return [
      `Hi HR Admin,`,
      '',
      `No unanswered questions this week — your ${companyName} policy assistant answered everything employees asked. Great policy coverage!`,
      '',
      `Log into ReloPass to review your policy: ${appUrl}`,
      '',
      '— The ReloPass Team',
    ].join('\n');
  }

  const lines: string[] = [
    `Hi HR Admin,`,
    '',
    `This week, ${companyName} employees asked ${totalRefusals} question${totalRefusals !== 1 ? 's' : ''} the policy assistant couldn't answer.`,
    `Here are the top ${Math.min(nonEmpty.length, K_CLUSTERS)} question clusters:`,
    '',
  ];

  const top = nonEmpty.slice(0, K_CLUSTERS);
  for (let i = 0; i < top.length; i++) {
    const cluster = top[i];
    const catCode = cluster.dominant_cat;
    const catName = catCode ? (CAT_NAMES[catCode] ?? catCode) : 'General / Uncategorised';
    const count = cluster.members.length;

    lines.push(
      `${i + 1}. ${catName.toUpperCase()}${catCode ? ` (${catCode})` : ''} — ${count} question${count !== 1 ? 's' : ''}`,
    );
    if (catCode) {
      lines.push(
        `   → Consider reviewing and expanding your ${catName} policy section.`,
      );
    }
    lines.push('');
  }

  lines.push(`Log into ReloPass to update your policy: ${appUrl}`);
  lines.push('');
  lines.push('— The ReloPass Team');

  return lines.join('\n');
}

// ---------------------------------------------------------------------------
// Email delivery (Resend)
// ---------------------------------------------------------------------------

export async function sendViaResend(
  to: string,
  subject: string,
  body: string,
  resendKey: string,
  from: string,
): Promise<{ ok: boolean; error?: string }> {
  if (!resendKey || resendKey === 'stub') {
    console.log(`[unanswered-questions-digest] STUB → to=${to} subject="${subject}"`);
    return { ok: true };
  }

  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${resendKey}`,
    },
    body: JSON.stringify({ from, to: [to], subject, text: body }),
  });

  if (!res.ok) {
    const err = await res.text().catch(() => res.statusText);
    return { ok: false, error: `Resend ${res.status}: ${err}` };
  }
  return { ok: true };
}

// ---------------------------------------------------------------------------
// Main handler
// ---------------------------------------------------------------------------

Deno.serve(async (req) => {
  // CORS pre-flight
  if (req.method === 'OPTIONS') {
    return new Response('ok', {
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Authorization, Content-Type',
      },
    });
  }

  const t0 = Date.now();

  try {
    const supabase = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '',
    );

    const resendKey  = Deno.env.get('RESEND_API_KEY') ?? 'stub';
    const emailFrom  = Deno.env.get('EMAIL_FROM')    ?? 'noreply@relopass.com';
    const appUrl     = Deno.env.get('APP_URL')        ?? 'https://app.relopass.com';

    const windowStart = new Date(
      Date.now() - DIGEST_WINDOW_DAYS * 24 * 60 * 60 * 1000,
    ).toISOString();

    // ── 1. Fetch refusal logs for the past 7 days ─────────────────────────
    const { data: logs, error: logsErr } = await supabase
      .from('ai_refusal_logs')
      .select('id, company_id, query_embedding, fallback_reason, suggested_cat_code, created_at')
      .gte('created_at', windowStart)
      .in('fallback_reason', ['TOPIC_REJECTED', 'LOW_CONFIDENCE']);

    if (logsErr) throw new Error(`Refusal logs query failed: ${logsErr.message}`);

    const allLogs = (logs ?? []) as RefusalLog[];

    if (allLogs.length === 0) {
      console.log('[unanswered-questions-digest] No refusals in window — nothing to send.');
      return new Response(
        JSON.stringify({ sent: 0, companies: 0, latency_ms: Date.now() - t0 }),
        { headers: { 'Content-Type': 'application/json' } },
      );
    }

    // ── 2. Group by company ───────────────────────────────────────────────
    const byCompany = new Map<string, RefusalLog[]>();
    for (const log of allLogs) {
      const arr = byCompany.get(log.company_id) ?? [];
      arr.push(log);
      byCompany.set(log.company_id, arr);
    }

    // ── 3. Fetch company HR contact emails ────────────────────────────────
    const companyIds = [...byCompany.keys()];
    const { data: companies, error: companiesErr } = await supabase
      .from('companies')
      .select('id, name, hr_contact_email')
      .in('id', companyIds);

    if (companiesErr) throw new Error(`Companies query failed: ${companiesErr.message}`);

    const companyMap = new Map<string, CompanyRow>();
    for (const c of (companies ?? []) as CompanyRow[]) {
      companyMap.set(c.id, c);
    }

    // ── 4. Per-company: cluster + email ───────────────────────────────────
    let sent = 0;
    const results: Array<{ company_id: string; total: number; ok: boolean; error?: string }> = [];

    for (const [companyId, companyLogs] of byCompany) {
      const company = companyMap.get(companyId);
      if (!company?.hr_contact_email) {
        console.warn(
          `[unanswered-questions-digest] company=${companyId} has no hr_contact_email — skipping`,
        );
        continue;
      }

      // Filter to logs that have an embedding (nulls can't be clustered)
      const logsWithEmbedding = companyLogs.filter(
        (l) => Array.isArray(l.query_embedding) && l.query_embedding.length > 0,
      );

      let clusters: Cluster[] = [];
      if (logsWithEmbedding.length > 0) {
        const embeddings = logsWithEmbedding.map((l) => l.query_embedding);
        const centroids = kMeans(embeddings, K_CLUSTERS);
        clusters = assignToClusters(logsWithEmbedding, centroids);
      }

      const totalRefusals = companyLogs.length;
      const nonEmptyClusters = clusters.filter((c) => c.members.length > 0).length;

      const subject = totalRefusals > 0
        ? `ReloPass Policy Digest — ${nonEmptyClusters} question cluster${nonEmptyClusters !== 1 ? 's' : ''} this week`
        : 'ReloPass Policy Digest — all questions answered this week';

      const body = renderDigestEmail(
        company.name,
        totalRefusals,
        clusters,
        appUrl,
      );

      const { ok, error } = await sendViaResend(
        company.hr_contact_email,
        subject,
        body,
        resendKey,
        emailFrom,
      );

      results.push({ company_id: companyId, total: totalRefusals, ok, error });
      if (ok) sent++;

      console.log(
        `[unanswered-questions-digest] company=${companyId} ` +
        `total=${totalRefusals} clusters=${nonEmptyClusters} sent=${ok}`,
      );
    }

    return new Response(
      JSON.stringify({
        sent,
        companies: byCompany.size,
        results,
        latency_ms: Date.now() - t0,
      }),
      { headers: { 'Content-Type': 'application/json' } },
    );

  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error('[unanswered-questions-digest] ERROR:', msg);
    return new Response(
      JSON.stringify({ error: msg, latency_ms: Date.now() - t0 }),
      { status: 500, headers: { 'Content-Type': 'application/json' } },
    );
  }
});
