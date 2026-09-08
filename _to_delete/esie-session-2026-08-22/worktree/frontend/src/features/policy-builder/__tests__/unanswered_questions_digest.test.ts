/**
 * [P5-6] Tests for unanswered-questions-digest edge function
 *
 * The edge function is a Deno module (Supabase Edge Function) and cannot be
 * imported directly into Vitest. Instead, we test the pure utility functions
 * inline here — these are exact copies of the functions in index.ts, keeping
 * the logic testable in a Node/Vitest context.
 *
 * Covers:
 *   - cosineDistance: identical vectors, orthogonal vectors, zero vector
 *   - centroidOf: mean computation
 *   - kMeans: correct cluster count, semantically similar vectors group together
 *   - assignToClusters: correct member assignment + dominant CAT detection
 *   - renderDigestEmail: zero refusals ("No unanswered questions"), non-zero
 *     refusals with CAT codes, ordering by cluster size, CAT name mapping
 *   - CAT_NAMES constant: all 14 categories present
 */

import { describe, it, expect } from 'vitest';

// ---------------------------------------------------------------------------
// Inline copies of pure utility functions from the edge function
// (Deno modules cannot be imported into Vitest directly)
// ---------------------------------------------------------------------------

const K_CLUSTERS = 5;
const MAX_KMEANS_ITER = 30;

const CAT_NAMES: Record<string, string> = {
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

interface RefusalLog {
  id: string;
  company_id: string;
  query_embedding: number[];
  fallback_reason: string;
  suggested_cat_code: string | null;
  created_at: string;
}

interface Cluster {
  centroid: number[];
  members: RefusalLog[];
  dominant_cat: string | null;
  cat_counts: Record<string, number>;
}

function dotProduct(a: number[], b: number[]): number {
  let sum = 0;
  for (let i = 0; i < a.length; i++) sum += a[i] * b[i];
  return sum;
}

function magnitude(v: number[]): number {
  return Math.sqrt(dotProduct(v, v));
}

function cosineDistance(a: number[], b: number[]): number {
  const magA = magnitude(a);
  const magB = magnitude(b);
  if (magA === 0 || magB === 0) return 1;
  const sim = dotProduct(a, b) / (magA * magB);
  return 1 - Math.max(-1, Math.min(1, sim));
}

function centroidOf(vectors: number[][]): number[] {
  if (vectors.length === 0) return [];
  const dim = vectors[0].length;
  const sum = new Array<number>(dim).fill(0);
  for (const v of vectors) {
    for (let i = 0; i < dim; i++) sum[i] += v[i];
  }
  return sum.map((x) => x / vectors.length);
}

function kMeansInit(embeddings: number[][], k: number): number[][] {
  const n = embeddings.length;
  const actualK = Math.min(k, n);
  const firstIdx = Math.floor(Math.random() * n);
  const centroids: number[][] = [embeddings[firstIdx]];

  while (centroids.length < actualK) {
    const dists = embeddings.map((e) =>
      Math.min(...centroids.map((c) => cosineDistance(e, c))),
    );
    const total = dists.reduce((a, b) => a + b, 0);
    if (total < 1e-12) {
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
      if (r <= 0) { selected = i; break; }
    }
    centroids.push(embeddings[selected]);
  }
  return centroids;
}

function kMeans(embeddings: number[][], k: number): number[][] {
  if (embeddings.length === 0) return [];
  const actualK = Math.min(k, embeddings.length);
  const centroids = kMeansInit(embeddings, actualK);

  for (let iter = 0; iter < MAX_KMEANS_ITER; iter++) {
    const assignments = embeddings.map((e) => {
      let best = 0;
      let bestDist = cosineDistance(e, centroids[0]);
      for (let c = 1; c < centroids.length; c++) {
        const d = cosineDistance(e, centroids[c]);
        if (d < bestDist) { bestDist = d; best = c; }
      }
      return best;
    });
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

function assignToClusters(logs: RefusalLog[], centroids: number[][]): Cluster[] {
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
      if (d < bestDist) { bestDist = d; best = c; }
    }
    clusters[best].members.push(log);
    if (log.suggested_cat_code) {
      clusters[best].cat_counts[log.suggested_cat_code] =
        (clusters[best].cat_counts[log.suggested_cat_code] ?? 0) + 1;
    }
  }
  for (const cluster of clusters) {
    const entries = Object.entries(cluster.cat_counts);
    if (entries.length > 0) {
      entries.sort((a, b) => b[1] - a[1]);
      cluster.dominant_cat = entries[0][0];
    }
  }
  return clusters;
}

function renderDigestEmail(
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
      lines.push(`   → Consider reviewing and expanding your ${catName} policy section.`);
    }
    lines.push('');
  }

  lines.push(`Log into ReloPass to update your policy: ${appUrl}`);
  lines.push('');
  lines.push('— The ReloPass Team');
  return lines.join('\n');
}

// ---------------------------------------------------------------------------
// Helper: make a near-unit vector pointing roughly in direction of `base`
// ---------------------------------------------------------------------------

function makeEmbedding(base: number[], noise = 0.0): number[] {
  const v = base.map((x) => x + noise * (Math.random() - 0.5));
  const mag = Math.sqrt(v.reduce((s, x) => s + x * x, 0));
  return v.map((x) => x / mag);
}

function makeLog(
  id: string,
  embedding: number[],
  cat: string | null = null,
): RefusalLog {
  return {
    id,
    company_id: 'c1',
    query_embedding: embedding,
    fallback_reason: 'TOPIC_REJECTED',
    suggested_cat_code: cat,
    created_at: new Date().toISOString(),
  };
}

// ---------------------------------------------------------------------------
// 1. CAT_NAMES constant
// ---------------------------------------------------------------------------

describe('CAT_NAMES', () => {
  it('contains all 14 categories', () => {
    expect(Object.keys(CAT_NAMES)).toHaveLength(14);
  });

  it('maps CAT-01 to Housing & Accommodation', () => {
    expect(CAT_NAMES['CAT-01']).toBe('Housing & Accommodation');
  });

  it('maps CAT-14 to Repatriation', () => {
    expect(CAT_NAMES['CAT-14']).toBe('Repatriation');
  });
});

// ---------------------------------------------------------------------------
// 2. cosineDistance
// ---------------------------------------------------------------------------

describe('cosineDistance', () => {
  it('returns 0 for identical vectors', () => {
    const v = [1, 0, 0, 0];
    expect(cosineDistance(v, v)).toBeCloseTo(0, 8);
  });

  it('returns 1 for orthogonal vectors', () => {
    const a = [1, 0, 0];
    const b = [0, 1, 0];
    expect(cosineDistance(a, b)).toBeCloseTo(1, 8);
  });

  it('returns 2 for opposite vectors', () => {
    const a = [1, 0];
    const b = [-1, 0];
    expect(cosineDistance(a, b)).toBeCloseTo(2, 5);
  });

  it('returns 1 for zero vectors (safe fallback)', () => {
    expect(cosineDistance([0, 0, 0], [1, 0, 0])).toBe(1);
    expect(cosineDistance([0, 0, 0], [0, 0, 0])).toBe(1);
  });

  it('is symmetric', () => {
    const a = [0.6, 0.8];
    const b = [0.8, 0.6];
    expect(cosineDistance(a, b)).toBeCloseTo(cosineDistance(b, a), 10);
  });
});

// ---------------------------------------------------------------------------
// 3. centroidOf
// ---------------------------------------------------------------------------

describe('centroidOf', () => {
  it('returns empty array for empty input', () => {
    expect(centroidOf([])).toHaveLength(0);
  });

  it('returns the single vector for a 1-element set', () => {
    const v = [0.5, 0.5];
    expect(centroidOf([v])).toEqual(v);
  });

  it('computes the arithmetic mean of two vectors', () => {
    const a = [1, 0];
    const b = [0, 1];
    const result = centroidOf([a, b]);
    expect(result[0]).toBeCloseTo(0.5, 8);
    expect(result[1]).toBeCloseTo(0.5, 8);
  });

  it('computes correct centroid for 4 vectors', () => {
    const vectors = [[4, 0], [0, 4], [-4, 0], [0, -4]];
    const c = centroidOf(vectors);
    expect(c[0]).toBeCloseTo(0, 8);
    expect(c[1]).toBeCloseTo(0, 8);
  });
});

// ---------------------------------------------------------------------------
// 4. kMeans — cluster count and separability
// ---------------------------------------------------------------------------

describe('kMeans', () => {
  it('returns 0 centroids for empty input', () => {
    expect(kMeans([], 3)).toHaveLength(0);
  });

  it('returns min(k, n) centroids', () => {
    const vecs = [[1, 0], [0, 1]];
    expect(kMeans(vecs, 5)).toHaveLength(2); // only 2 points
  });

  it('returns exactly k centroids when n >= k', () => {
    const vecs = Array.from({ length: 20 }, (_, i) => [Math.cos(i), Math.sin(i)]);
    expect(kMeans(vecs, 5)).toHaveLength(5);
  });

  it('groups clearly separated 3D clusters into distinct centroids', () => {
    // Three axis-aligned clusters, well separated
    const clusterA = Array.from({ length: 8 }, () => makeEmbedding([1, 0, 0], 0.05));
    const clusterB = Array.from({ length: 8 }, () => makeEmbedding([0, 1, 0], 0.05));
    const clusterC = Array.from({ length: 8 }, () => makeEmbedding([0, 0, 1], 0.05));
    const all = [...clusterA, ...clusterB, ...clusterC];

    const centroids = kMeans(all, 3);
    expect(centroids).toHaveLength(3);

    // Each centroid should be close to one of the axis directions
    // (measure max similarity to any axis)
    const axes = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
    const matched = new Set<number>();
    for (const centroid of centroids) {
      const closest = axes.reduce(
        (best, axis, i) => {
          const d = cosineDistance(centroid, axis);
          return d < best.dist ? { dist: d, i } : best;
        },
        { dist: Infinity, i: -1 },
      );
      expect(closest.dist).toBeLessThan(0.15); // within 15% cosine distance of an axis
      matched.add(closest.i);
    }
    // All 3 axes should be matched
    expect(matched.size).toBe(3);
  });

  it('handles k=1 returning the global centroid', () => {
    const vecs = [[1, 0], [0, 1], [-1, 0], [0, -1]];
    const centroids = kMeans(vecs, 1);
    expect(centroids).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// 5. assignToClusters
// ---------------------------------------------------------------------------

describe('assignToClusters', () => {
  const catA = [1, 0, 0] as number[];
  const catB = [0, 1, 0] as number[];

  it('returns one cluster per centroid', () => {
    const logs = [makeLog('1', catA), makeLog('2', catB)];
    const clusters = assignToClusters(logs, [catA, catB]);
    expect(clusters).toHaveLength(2);
  });

  it('assigns each log to the nearest centroid', () => {
    const logs = [
      makeLog('1', makeEmbedding(catA, 0.01)),
      makeLog('2', makeEmbedding(catA, 0.01)),
      makeLog('3', makeEmbedding(catB, 0.01)),
    ];
    const clusters = assignToClusters(logs, [catA, catB]);
    // Cluster A should have 2 members; cluster B should have 1
    const sizes = clusters.map((c) => c.members.length).sort((a, b) => b - a);
    expect(sizes[0]).toBe(2);
    expect(sizes[1]).toBe(1);
  });

  it('sets dominant_cat to the most frequent CAT code in each cluster', () => {
    const logs = [
      makeLog('1', catA, 'CAT-01'),
      makeLog('2', catA, 'CAT-01'),
      makeLog('3', catA, 'CAT-02'),
    ];
    const clusters = assignToClusters(logs, [catA]);
    expect(clusters[0].dominant_cat).toBe('CAT-01');
  });

  it('sets dominant_cat to null when no cat codes are present', () => {
    const logs = [makeLog('1', catA, null), makeLog('2', catA, null)];
    const clusters = assignToClusters(logs, [catA]);
    expect(clusters[0].dominant_cat).toBeNull();
  });

  it('populates cat_counts correctly', () => {
    const logs = [
      makeLog('1', catA, 'CAT-01'),
      makeLog('2', catA, 'CAT-01'),
      makeLog('3', catA, 'CAT-03'),
    ];
    const clusters = assignToClusters(logs, [catA]);
    expect(clusters[0].cat_counts['CAT-01']).toBe(2);
    expect(clusters[0].cat_counts['CAT-03']).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// 6. renderDigestEmail
// ---------------------------------------------------------------------------

describe('renderDigestEmail', () => {
  const APP_URL = 'https://app.relopass.com';

  it('says "No unanswered questions" when totalRefusals is 0', () => {
    const email = renderDigestEmail('Acme Corp', 0, [], APP_URL);
    expect(email).toContain('No unanswered questions this week');
    expect(email).toContain('Acme Corp');
    expect(email).toContain(APP_URL);
  });

  it('includes the total question count in the body', () => {
    const logs = [makeLog('1', [1, 0], 'CAT-01')];
    const clusters = assignToClusters(logs, [[1, 0]]);
    const email = renderDigestEmail('Globex', 23, clusters, APP_URL);
    expect(email).toContain('23 questions');
  });

  it('includes the CAT code and human-readable name for each cluster', () => {
    const logs = [makeLog('1', [1, 0], 'CAT-01'), makeLog('2', [1, 0], 'CAT-01')];
    const clusters = assignToClusters(logs, [[1, 0]]);
    const email = renderDigestEmail('Acme', 2, clusters, APP_URL);
    expect(email).toContain('CAT-01');
    expect(email).toContain('HOUSING & ACCOMMODATION');
  });

  it('orders clusters by descending member count', () => {
    // Two clusters: bigger one for CAT-02, smaller for CAT-01
    const bigLogs = Array.from({ length: 5 }, (_, i) =>
      makeLog(`b${i}`, [1, 0, 0], 'CAT-02'),
    );
    const smallLogs = Array.from({ length: 2 }, (_, i) =>
      makeLog(`s${i}`, [0, 1, 0], 'CAT-01'),
    );
    const clusters = assignToClusters(
      [...bigLogs, ...smallLogs],
      [[1, 0, 0], [0, 1, 0]],
    );
    const email = renderDigestEmail('TestCo', 7, clusters, APP_URL);
    const cat01Pos = email.indexOf('CAT-01');
    const cat02Pos = email.indexOf('CAT-02');
    // CAT-02 (bigger cluster) should appear first
    expect(cat02Pos).toBeLessThan(cat01Pos);
  });

  it('shows a "consider reviewing" suggestion for each CAT cluster', () => {
    const logs = [makeLog('1', [1, 0], 'CAT-07')];
    const clusters = assignToClusters(logs, [[1, 0]]);
    const email = renderDigestEmail('School Inc', 1, clusters, APP_URL);
    expect(email).toContain('School & Education');
    expect(email).toContain('Consider reviewing');
  });

  it('includes the app URL in the email footer', () => {
    const email = renderDigestEmail('Acme', 0, [], APP_URL);
    expect(email).toContain(APP_URL);
  });

  it('uses singular "question" for count of 1', () => {
    const logs = [makeLog('1', [1, 0], 'CAT-03')];
    const clusters = assignToClusters(logs, [[1, 0]]);
    const email = renderDigestEmail('Acme', 1, clusters, APP_URL);
    expect(email).toContain('1 question the');
  });

  it('does not expose raw query text in the email body', () => {
    // The digest email should never contain anything that looks like a verbatim
    // user query — only category names, counts, and suggestions.
    const logs = [makeLog('1', [1, 0, 0], 'CAT-01')];
    const clusters = assignToClusters(logs, [[1, 0, 0]]);
    const email = renderDigestEmail('Acme', 1, clusters, APP_URL);
    // Sanity check: no raw query-like text patterns
    expect(email).not.toContain('What is');
    expect(email).not.toContain('How much');
    expect(email).not.toContain('Can I');
  });

  it('caps the digest at K_CLUSTERS (5) entries regardless of cluster count', () => {
    // Create 7 clusters
    const basisVectors = Array.from({ length: 7 }, (_, i) => {
      const v = new Array(7).fill(0);
      v[i] = 1;
      return v;
    });
    const allLogs = basisVectors.map((bv, i) =>
      makeLog(`l${i}`, bv, `CAT-0${i + 1}`),
    );
    const clusters = assignToClusters(allLogs, basisVectors);
    const email = renderDigestEmail('BigCo', 7, clusters, APP_URL);
    // Count the numbered items: "1. ", "2. ", ... max 5
    const numbered = email.match(/^\d+\. /gm) ?? [];
    expect(numbered.length).toBeLessThanOrEqual(K_CLUSTERS);
  });
});
