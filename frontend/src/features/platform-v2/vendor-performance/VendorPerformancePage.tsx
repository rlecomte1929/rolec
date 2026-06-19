/**
 * VendorPerformancePage — NAV-SP-2 "Vendor Performance" tab
 *
 * Replaces the raw ProviderGridV2Page on the /hr/service-providers?tab=providers
 * tab with a proper analytics surface:
 *   • KPI strip (avg rating, avg cost, active vendors, avg response time)
 *   • Category + vendor name filters (live-filtered, no extra API call)
 *   • Cases-per-month bar chart + cost distribution (SVG, no chart lib dep)
 *   • Expandable per-category rows with vendor cards + employee review history
 *
 * Data: GET /api/hr/vendor-performance (hr_vendor_performance router)
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AppShell } from '../../../components/AppShell';
import { Button } from '../../../components/antigravity/Button';
import { hrAPI } from '../../../api/client';

// ── Types (derived from the API function's return shape) ──────────────────────

type VendorPerformanceData = Awaited<ReturnType<typeof hrAPI.getVendorPerformance>>;
type CategoryEntry = VendorPerformanceData['categories'][number];
type VendorEntry = CategoryEntry['vendors'][number];

// ── API fetch ─────────────────────────────────────────────────────────────────

async function fetchVendorPerformance(): Promise<VendorPerformanceData> {
  return hrAPI.getVendorPerformance();
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtCost(eur: number | null): string {
  if (eur == null) return '—';
  if (eur === 0) return '€0';
  return `€${eur.toLocaleString('en-EU')}`;
}

function fmtRating(r: number | null): string {
  return r != null ? r.toFixed(1) : '—';
}

function fmtSla(hours: number | null): string {
  if (hours == null) return '—';
  if (hours < 24) return `${hours}h`;
  return `${(hours / 24).toFixed(1)}d`;
}

function starsFill(rating: number): number[] {
  // Returns array of 5 values 0–100 representing fill % per star
  return [1, 2, 3, 4, 5].map((i) => Math.min(100, Math.max(0, (rating - (i - 1)) * 100)));
}

const STATUS_META: Record<string, { label: string; cls: string }> = {
  healthy:      { label: 'Healthy',       cls: 'bg-emerald-50 text-emerald-700' },
  low_coverage: { label: 'Low coverage',  cls: 'bg-amber-50 text-amber-700' },
  review:       { label: 'Review needed', cls: 'bg-amber-50 text-amber-700' },
  critical:     { label: 'Needs vendors', cls: 'bg-red-50 text-red-700' },
};

const CATEGORY_LABELS: Record<string, string> = {
  housing:      'Housing',
  immigration:  'Immigration',
  moving:       'Removals',
  school_search: 'Schooling',
  destination:  'Destination',
  banking:      'Banking',
  tax:          'Tax advisory',
};
function fmtCat(cat: string): string {
  return CATEGORY_LABELS[cat] ?? cat.replace(/_/g, ' ');
}

// Last 6 calendar months as "YYYY-MM" strings (oldest → newest)
function last6Months(): string[] {
  const months: string[] = [];
  const now = new Date();
  for (let i = 5; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    months.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`);
  }
  return months;
}

function monthLabel(ym: string): string {
  const [y, m] = ym.split('-');
  return new Date(Number(y), Number(m) - 1, 1).toLocaleString('en', { month: 'short' });
}

// ── SVG bar chart ─────────────────────────────────────────────────────────────

function BarChart({ data }: { data: { label: string; value: number }[] }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  const W = 400;
  const H = 100;
  const BAR_W = Math.floor((W - 32) / data.length - 6);
  return (
    <svg viewBox={`0 0 ${W} ${H + 24}`} className="w-full" aria-label="Cases per month bar chart">
      {data.map((d, i) => {
        const barH = Math.max(2, Math.round((d.value / max) * H));
        const x = 16 + i * (BAR_W + 6);
        const y = H - barH;
        return (
          <g key={d.label}>
            <rect x={x} y={y} width={BAR_W} height={barH}
              className="fill-[#1f8e8b]" rx={2} opacity={d.value === 0 ? 0.25 : 0.85} />
            {d.value > 0 && (
              <text x={x + BAR_W / 2} y={y - 3} textAnchor="middle"
                className="fill-slate-600" style={{ fontSize: 9 }}>
                {d.value}
              </text>
            )}
            <text x={x + BAR_W / 2} y={H + 16} textAnchor="middle"
              className="fill-slate-400" style={{ fontSize: 9 }}>
              {d.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ── SVG star row ──────────────────────────────────────────────────────────────

function StarRow({ rating, size = 12 }: { rating: number; size?: number }) {
  const fills = starsFill(rating);
  return (
    <span className="inline-flex gap-0.5" aria-label={`${rating} out of 5 stars`}>
      {fills.map((fill, i) => (
        <svg key={i} width={size} height={size} viewBox="0 0 12 12" aria-hidden="true">
          <defs>
            <linearGradient id={`sf-${rating}-${i}`}>
              <stop offset={`${fill}%`} stopColor="#f59e0b" />
              <stop offset={`${fill}%`} stopColor="#e2e8f0" />
            </linearGradient>
          </defs>
          <path
            d="M6 1l1.3 2.6 2.9.4-2.1 2 .5 2.9L6 7.5l-2.6 1.4.5-2.9-2.1-2 2.9-.4z"
            fill={`url(#sf-${rating}-${i})`}
          />
        </svg>
      ))}
    </span>
  );
}

// ── KPI card ──────────────────────────────────────────────────────────────────

function Kpi({ label, value, sub, tone = 'default' }: {
  label: string; value: string; sub?: string;
  tone?: 'default' | 'danger' | 'warning' | 'success';
}) {
  const numCls = tone === 'danger' ? 'text-red-600' : tone === 'warning' ? 'text-amber-600'
    : tone === 'success' ? 'text-emerald-600' : 'text-slate-900';
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">{label}</p>
      <p className={`mt-1 text-[24px] font-semibold leading-none tabular-nums ${numCls}`}>{value}</p>
      {sub && <p className="mt-1 text-[11px] text-slate-400">{sub}</p>}
    </div>
  );
}

// ── Vendor card ───────────────────────────────────────────────────────────────

function VendorCard({ vendor }: { vendor: VendorEntry }) {
  const ratingCls = vendor.rating == null ? 'text-slate-400'
    : vendor.rating >= 4.3 ? 'text-emerald-700'
    : vendor.rating >= 3.8 ? 'text-amber-700'
    : 'text-red-600';

  return (
    <div className="flex flex-col rounded-lg border border-slate-200 bg-white overflow-hidden text-sm">
      {/* Header */}
      <div className="px-3 py-2.5 border-b border-slate-100">
        <p className="font-medium text-[#0b2b43] truncate" title={vendor.name}>{vendor.name}</p>
        <p className="text-[11px] text-slate-400 mt-0.5 truncate">{vendor.location}</p>
        <div className="flex items-center gap-2 mt-1.5">
          <span className={`text-[15px] font-semibold ${ratingCls}`}>{fmtRating(vendor.rating)}</span>
          {vendor.rating != null && <StarRow rating={vendor.rating} />}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 divide-x divide-slate-100 bg-slate-50">
        <div className="px-2 py-1.5 text-center">
          <p className="text-[13px] font-medium text-slate-800">{vendor.review_count}</p>
          <p className="text-[10px] text-slate-400">reviews</p>
        </div>
        <div className="px-2 py-1.5 text-center">
          <p className="text-[13px] font-medium text-slate-800">{fmtCost(vendor.cost_eur)}</p>
          <p className="text-[10px] text-slate-400">avg cost</p>
        </div>
        <div className="px-2 py-1.5 text-center">
          <p className="text-[13px] font-medium text-slate-800">{fmtSla(vendor.response_sla_hours)}</p>
          <p className="text-[10px] text-slate-400">response</p>
        </div>
      </div>

      {/* Reviews */}
      {vendor.recent_reviews.length === 0 ? (
        <div className="px-3 py-2 text-[11px] text-slate-400 italic">No reviews yet</div>
      ) : (
        <div className="divide-y divide-slate-100">
          <p className="px-3 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-widest text-slate-400">
            Recent reviews
          </p>
          {vendor.recent_reviews.map((r, idx) => (
            <div key={idx} className="px-3 py-2">
              <div className="flex items-center justify-between mb-0.5">
                <StarRow rating={r.score} size={10} />
                <span className="text-[10px] text-slate-400">{r.date}</span>
              </div>
              {r.comment && (
                <p className="text-[11px] text-slate-500 leading-tight line-clamp-3">{r.comment}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Category row ──────────────────────────────────────────────────────────────

function CategoryRow({
  cat,
  open,
  onToggle,
  vendorFilter,
}: {
  cat: CategoryEntry;
  open: boolean;
  onToggle: () => void;
  vendorFilter: string;
}) {
  const meta = STATUS_META[cat.status] ?? STATUS_META.healthy;
  const filteredVendors = vendorFilter.trim()
    ? cat.vendors.filter((v) => v.name.toLowerCase().includes(vendorFilter.toLowerCase()))
    : cat.vendors;

  return (
    <div>
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors text-left border-b border-slate-100"
      >
        <span className="flex-1 min-w-0">
          <span className="text-sm font-medium text-[#0b2b43]">{fmtCat(cat.category)}</span>
          <span className="ml-2 text-[11px] text-slate-400">
            {cat.vendor_count} vendor{cat.vendor_count !== 1 ? 's' : ''}
            {cat.avg_cost_eur != null ? ` · avg ${fmtCost(cat.avg_cost_eur)}/case` : ''}
          </span>
        </span>
        {cat.avg_rating != null && (
          <span className="flex items-center gap-1 text-[12px] text-amber-500 font-medium shrink-0">
            ★ {fmtRating(cat.avg_rating)}
          </span>
        )}
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${meta.cls}`}>
          {meta.label}
        </span>
        <svg
          className={`h-4 w-4 text-slate-400 shrink-0 transition-transform ${open ? 'rotate-90' : ''}`}
          viewBox="0 0 16 16" fill="none" aria-hidden="true"
        >
          <path d="M6 4l4 4-4 4" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <div className="bg-slate-50 px-4 py-3 border-b border-slate-100">
          {filteredVendors.length === 0 ? (
            <p className="text-sm text-slate-400 py-2">No vendors match the filter.</p>
          ) : (
            <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))' }}>
              {filteredVendors.map((v) => (
                <VendorCard key={v.id} vendor={v} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function VendorPerformancePage({ embedded = false }: { embedded?: boolean }) {
  const [data, setData] = useState<VendorPerformanceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [catFilter, setCatFilter] = useState<string>('all');
  const [vendorFilter, setVendorFilter] = useState('');

  // Which category rows are expanded
  const [openCats, setOpenCats] = useState<Set<string>>(new Set());

  const toggleCat = useCallback((cat: string) => {
    setOpenCats((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await fetchVendorPerformance();
      setData(d);
    } catch {
      setError('Could not load vendor performance data. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  // ── Derived: filtered categories ─────────────────────────────────────────
  const filteredCats = useMemo(() => {
    if (!data) return [];
    return catFilter === 'all'
      ? data.categories
      : data.categories.filter((c) => c.category === catFilter);
  }, [data, catFilter]);

  // ── Derived: monthly trend chart data ────────────────────────────────────
  const MONTHS = useMemo(() => last6Months(), []);

  const trendChartData = useMemo((): { label: string; value: number }[] => {
    if (!data) return MONTHS.map((m) => ({ label: monthLabel(m), value: 0 }));
    const trend = data.monthly_trend.filter(
      (t) => catFilter === 'all' || t.category === catFilter,
    );
    return MONTHS.map((m) => ({
      label: monthLabel(m),
      value: trend.filter((t) => t.month === m).reduce((s, t) => s + t.case_count, 0),
    }));
  }, [data, catFilter, MONTHS]);

  // ── Cost distribution from current vendor pricing ────────────────────────
  // No historical billing table exists yet — show per-category avg cost as bars.
  const costChartData = useMemo((): { label: string; value: number }[] => {
    if (!data) return [];
    const cats = catFilter === 'all' ? data.categories : data.categories.filter((c) => c.category === catFilter);
    return cats
      .filter((c) => c.avg_cost_eur != null && c.avg_cost_eur > 0)
      .map((c) => ({ label: fmtCat(c.category).slice(0, 8), value: c.avg_cost_eur! }));
  }, [data, catFilter]);

  // ── Status counts for quick health read ─────────────────────────────────
  const statusCounts = useMemo(() => {
    const cats = data?.categories ?? [];
    return {
      healthy: cats.filter((c) => c.status === 'healthy').length,
      review: cats.filter((c) => c.status === 'review' || c.status === 'low_coverage').length,
      critical: cats.filter((c) => c.status === 'critical').length,
    };
  }, [data]);

  const inner = (
    <div className="px-6 py-6 space-y-5">
      {/* Page header */}
      <div className="flex items-baseline gap-3">
        <h1 className="text-[22px] font-semibold tracking-tight text-[#0b2b43]">Vendor performance</h1>
        <Button
          unstyled
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="ml-auto text-xs font-medium text-[#1f8e8b] underline-offset-2 hover:underline disabled:opacity-50"
        >
          {loading ? 'Loading…' : 'Refresh'}
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      {/* KPI strip */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Kpi
          label="Avg vendor rating"
          value={data ? `${fmtRating(data.summary.avg_rating)} / 5` : '—'}
          tone="default"
        />
        <Kpi
          label="Avg cost / case"
          value={data ? fmtCost(data.summary.avg_cost_eur) : '—'}
          tone="default"
        />
        <Kpi
          label="Active vendors"
          value={data ? String(data.summary.active_vendors) : '—'}
          sub={`${statusCounts.healthy} healthy · ${statusCounts.critical} critical`}
        />
        <Kpi
          label="Avg response time"
          value={data ? fmtSla(data.summary.avg_response_sla_hours) : '—'}
          tone="default"
        />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <label htmlFor="vp-cat-filter" className="text-[12px] font-medium text-slate-500">Category</label>
          <select
            id="vp-cat-filter"
            value={catFilter}
            onChange={(e) => { setCatFilter(e.target.value); setOpenCats(new Set()); }}
            className="rounded-md border border-slate-200 bg-white px-2 py-1.5 text-[13px] text-slate-700 shadow-none focus:outline-none focus:ring-1 focus:ring-[#1f8e8b]"
          >
            <option value="all">All categories</option>
            {(data?.categories ?? []).map((c) => (
              <option key={c.category} value={c.category}>{fmtCat(c.category)}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="vp-vendor-filter" className="text-[12px] font-medium text-slate-500">Vendor</label>
          <input
            id="vp-vendor-filter"
            type="text"
            placeholder="Filter by name…"
            value={vendorFilter}
            onChange={(e) => setVendorFilter(e.target.value)}
            className="rounded-md border border-slate-200 bg-white px-2 py-1.5 text-[13px] text-slate-700 placeholder-slate-300 focus:outline-none focus:ring-1 focus:ring-[#1f8e8b] w-40"
          />
        </div>
        {(catFilter !== 'all' || vendorFilter) && (
          <Button
            unstyled
            type="button"
            onClick={() => { setCatFilter('all'); setVendorFilter(''); setOpenCats(new Set()); }}
            className="text-[12px] text-slate-400 hover:text-slate-600 underline-offset-2 hover:underline"
          >
            Clear filters
          </Button>
        )}
        <span className="ml-auto text-[12px] text-slate-400">
          {filteredCats.length} categor{filteredCats.length !== 1 ? 'ies' : 'y'}
          {' · '}
          {filteredCats.reduce((s, c) => s + c.vendors.filter((v) =>
            !vendorFilter || v.name.toLowerCase().includes(vendorFilter.toLowerCase())).length, 0
          )} vendors
        </span>
      </div>

      {/* Trend charts */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* Cases per month */}
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
          <div className="mb-2">
            <p className="text-[13px] font-medium text-[#0b2b43]">Cases handled per month</p>
            <p className="text-[11px] text-slate-400">
              From employee reviews · {catFilter !== 'all' ? fmtCat(catFilter) : 'all categories'}
            </p>
          </div>
          {loading ? (
            <div className="h-[124px] animate-pulse rounded bg-slate-100" />
          ) : (
            <BarChart data={trendChartData} />
          )}
        </div>

        {/* Cost by category */}
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
          <div className="mb-2">
            <p className="text-[13px] font-medium text-[#0b2b43]">Avg cost per case by category</p>
            <p className="text-[11px] text-slate-400">
              Current pricing · cost history tracked per case from this point
            </p>
          </div>
          {loading ? (
            <div className="h-[124px] animate-pulse rounded bg-slate-100" />
          ) : costChartData.length === 0 ? (
            <div className="flex h-[124px] items-center justify-center text-[12px] text-slate-400">
              No cost data available for selected filter
            </div>
          ) : (
            <BarChart data={costChartData} />
          )}
        </div>
      </div>

      {/* Category rows with vendor cards */}
      <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <div>
            <p className="text-[13px] font-medium text-[#0b2b43]">
              Vendor roster — click a category to expand
            </p>
            <p className="text-[11px] text-slate-400">
              Ratings, costs, and recent employee reviews per vendor
            </p>
          </div>
          <div className="flex items-center gap-1.5 text-[11px]">
            <span className="rounded-full bg-emerald-50 text-emerald-700 px-2 py-0.5 font-medium">
              {statusCounts.healthy} healthy
            </span>
            <span className="rounded-full bg-amber-50 text-amber-700 px-2 py-0.5 font-medium">
              {statusCounts.review} review
            </span>
            <span className="rounded-full bg-red-50 text-red-700 px-2 py-0.5 font-medium">
              {statusCounts.critical} critical
            </span>
          </div>
        </div>

        {loading && (
          <div className="space-y-1 p-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-10 animate-pulse rounded bg-slate-100" />
            ))}
          </div>
        )}

        {!loading && filteredCats.length === 0 && (
          <div className="px-4 py-8 text-center text-sm text-slate-400">
            No vendor categories found.
          </div>
        )}

        {!loading &&
          filteredCats.map((cat) => (
            <CategoryRow
              key={cat.category}
              cat={cat}
              open={openCats.has(cat.category)}
              onToggle={() => toggleCat(cat.category)}
              vendorFilter={vendorFilter}
            />
          ))}
      </div>

      {/* Recommendations */}
      {!loading && data && (() => {
        const recs: string[] = [];
        for (const c of data.categories) {
          if (c.status === 'critical')
            recs.push(`${fmtCat(c.category)} has only ${c.vendor_count} vendor — qualify at least 2 more before the next assignment wave.`);
          else if (c.status === 'low_coverage')
            recs.push(`${fmtCat(c.category)} has thin coverage (${c.vendor_count} vendors). Consider onboarding 1 more to reduce single-vendor risk.`);
          else if (c.status === 'review' && c.avg_rating != null)
            recs.push(`${fmtCat(c.category)} average rating is ${fmtRating(c.avg_rating)} — review vendor contracts or request updated quotes.`);
        }
        if (recs.length === 0) return null;
        return (
          <div className="rounded-lg border-l-2 border-red-400 border-t border-r border-b border-slate-200 bg-white overflow-hidden">
            <div className="px-4 py-3">
              <p className="text-[13px] font-medium text-[#0b2b43] mb-2">Recommendations</p>
              <ul className="space-y-1.5">
                {recs.map((r, i) => (
                  <li key={i} className="flex gap-2 text-[12px] text-slate-600">
                    <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-red-400 shrink-0" />
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        );
      })()}
    </div>
  );

  return embedded ? inner : <AppShell>{inner}</AppShell>;
}

export default VendorPerformancePage;
