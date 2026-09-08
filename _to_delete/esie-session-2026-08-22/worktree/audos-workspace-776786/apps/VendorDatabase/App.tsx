import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Database, Download, FileJson, FileText, RefreshCw, AlertCircle, AlertTriangle,
  Globe, Building2, CheckCircle2, MapPin, Search, Star, ExternalLink, ShieldCheck,
  UploadCloud, Info,
} from 'lucide-react';
import { useSpaceRuntime } from '../../SpaceRuntimeContext';

// ---------------------------------------------------------------------------
// Vendor Database — the live, queryable ReloPass vendor database.
//
// Source of truth for CONTENT: the country seed files under
//   supabase/seed/vendors/<country>.json   (ledger: supabase/seed/vendors/index.json,
//   row contract: supabase/seed/vendors/_SCHEMA.md)
// Source of truth for STATE: the WorkspaceDB table `relopass_vendors`
//   (physical name app_relopass_vendors), keyed by the deterministic unique
//   `vendor_key` so loading is idempotent.
//
// This app contains the LOADER: it reads every country file listed in the
// coverage ledger, validates each row against the _SCHEMA.md contract, and
// upserts into `relopass_vendors` keyed on vendor_key (insert new keys,
// update changed research fields on existing keys). Re-running a sync with
// unchanged seed files is a no-op.
//
// Founder-workflow fields (is_preferred, verification_status, verified_at)
// are written once at insert and never overwritten by a re-sync, so human
// verification work in the database is never stomped by research batches.
//
// NOTE: this table is intentionally separate from the legacy GlobeIQ demo
// table `vendors` (app_vendors), which has a different, pre-pipeline shape.
// ---------------------------------------------------------------------------

const TABLE = 'relopass_vendors';
const INDEX_PATH = 'supabase/seed/vendors/index.json';

const SERVICE_TYPES = [
  'mover_international', 'mover_domestic', 'dsp', 'immigration', 'corporate_housing',
  'tax_advisory', 'international_schools', 'school_search', 'language_training',
  'expat_banking', 'healthcare_navigation',
] as const;

const CATEGORY_LABELS: Record<string, string> = {
  mover_international: 'International movers',
  mover_domestic: 'Domestic movers (FR)',
  dsp: 'Destination services (DSP)',
  immigration: 'Immigration',
  corporate_housing: 'Corporate housing',
  tax_advisory: 'Tax advisory',
  international_schools: 'International schools',
  school_search: 'School search',
  language_training: 'Language training',
  expat_banking: 'Expat banking',
  healthcare_navigation: 'Healthcare navigation',
};

const PRIORITIES = ['critical', 'important', 'light'];
const CONFIDENCES = ['high', 'medium', 'low'];
const VERIFICATION_STATUSES = ['unverified', 'verified', 'rejected'];

// Research-owned fields: overwritten on re-sync when the seed changes.
const RESEARCH_FIELDS = [
  'name', 'service_type', 'country_coverage', 'primary_country', 'cities',
  'priority_at_hub', 'regulatory_gate', 'website', 'contact_name',
  'contact_email', 'contact_phone', 'notes', 'confidence', 'source',
] as const;

interface VendorRow {
  id: number;
  vendor_key: string;
  name: string;
  service_type: string;
  country_coverage: string[];
  primary_country: string;
  cities: string[];
  priority_at_hub: string;
  regulatory_gate: string | null;
  website: string;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  is_preferred: boolean;
  notes: string | null;
  confidence: string;
  verification_status: string;
  verified_at: string | null;
  source: string;
}

interface CountryLedgerEntry {
  country: string;
  iso2: string;
  file: string;
  row_count: number;
  status?: string;
}

interface SyncReport {
  finishedAt: string;
  filesRead: number;
  seedRows: number;
  inserted: number;
  updated: number;
  unchanged: number;
  skipped: number;
  issues: string[];
}

type SyncPhase = 'idle' | 'reading' | 'diffing' | 'writing' | 'done' | 'error';

function db() {
  return (window as any).__workspaceDb;
}

function asArray(v: unknown): string[] {
  if (Array.isArray(v)) return v.map(String);
  if (typeof v === 'string') {
    try {
      const parsed = JSON.parse(v);
      return Array.isArray(parsed) ? parsed.map(String) : [];
    } catch {
      return [];
    }
  }
  return [];
}

function normalizeText(v: unknown): string | null {
  if (v === null || v === undefined || v === '') return null;
  return String(v);
}

// Validate one seed row against the _SCHEMA.md contract. Returns error strings.
function validateSeedRow(row: any, fileLabel: string, i: number): string[] {
  const errs: string[] = [];
  const at = `${fileLabel}[${i}]`;
  if (!row || typeof row !== 'object') return [`${at}: not an object`];
  const key = row.vendor_key;
  if (typeof key !== 'string' || !key.trim()) errs.push(`${at}: missing vendor_key`);
  if (typeof row.name !== 'string' || !row.name.trim()) errs.push(`${at} (${key}): missing name`);
  if (!SERVICE_TYPES.includes(row.service_type)) errs.push(`${at} (${key}): invalid service_type "${row.service_type}"`);
  if (!Array.isArray(row.country_coverage) || row.country_coverage.length === 0) errs.push(`${at} (${key}): country_coverage must be a non-empty array`);
  if (typeof row.primary_country !== 'string' || row.primary_country.length !== 2) errs.push(`${at} (${key}): invalid primary_country`);
  if (Array.isArray(row.country_coverage) && typeof row.primary_country === 'string' && !row.country_coverage.includes(row.primary_country)) {
    errs.push(`${at} (${key}): primary_country not in country_coverage`);
  }
  if (!Array.isArray(row.cities) || row.cities.length === 0) errs.push(`${at} (${key}): cities must be a non-empty array`);
  if (!PRIORITIES.includes(row.priority_at_hub)) errs.push(`${at} (${key}): invalid priority_at_hub "${row.priority_at_hub}"`);
  if (typeof row.website !== 'string' || !row.website.trim()) errs.push(`${at} (${key}): missing website`);
  if (typeof row.is_preferred !== 'boolean') errs.push(`${at} (${key}): is_preferred must be boolean`);
  if (!CONFIDENCES.includes(row.confidence)) errs.push(`${at} (${key}): invalid confidence "${row.confidence}"`);
  if (!VERIFICATION_STATUSES.includes(row.verification_status)) errs.push(`${at} (${key}): invalid verification_status "${row.verification_status}"`);
  if (typeof row.source !== 'string' || !row.source.trim()) errs.push(`${at} (${key}): missing source`);
  return errs;
}

function researchFieldsDiffer(seed: any, existing: VendorRow): boolean {
  for (const f of RESEARCH_FIELDS) {
    const s = seed[f];
    const e = (existing as any)[f];
    if (f === 'country_coverage' || f === 'cities') {
      if (JSON.stringify(asArray(s)) !== JSON.stringify(asArray(e))) return true;
    } else {
      if ((normalizeText(s) ?? '') !== (normalizeText(e) ?? '')) return true;
    }
  }
  return false;
}

function chunk<T>(arr: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}

function triggerDownload(content: string, fileName: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

function csvCell(value: unknown): string {
  const s = value === null || value === undefined ? '' : String(value);
  return `"${s.replace(/"/g, '""')}"`;
}

function buildCsv(rows: VendorRow[]): string {
  const header = [
    'vendor_key', 'name', 'service_type', 'primary_country', 'country_coverage', 'cities',
    'priority_at_hub', 'regulatory_gate', 'website', 'contact_name', 'contact_email',
    'contact_phone', 'is_preferred', 'confidence', 'verification_status', 'verified_at',
    'source', 'notes',
  ];
  const lines = [header.join(',')];
  for (const r of rows) {
    lines.push([
      csvCell(r.vendor_key), csvCell(r.name), csvCell(r.service_type), csvCell(r.primary_country),
      csvCell(asArray(r.country_coverage).join('|')), csvCell(asArray(r.cities).join('|')),
      csvCell(r.priority_at_hub), csvCell(r.regulatory_gate), csvCell(r.website),
      csvCell(r.contact_name), csvCell(r.contact_email), csvCell(r.contact_phone),
      csvCell(r.is_preferred), csvCell(r.confidence), csvCell(r.verification_status),
      csvCell(r.verified_at), csvCell(r.source), csvCell(r.notes),
    ].join(','));
  }
  return lines.join('\n');
}

async function fetchAllVendors(): Promise<VendorRow[]> {
  const all: VendorRow[] = [];
  const pageSize = 200;
  let offset = 0;
  for (let page = 0; page < 25; page++) {
    const { data } = await db().from(TABLE, { shared: true })
      .orderBy('id', 'asc')
      .limit(pageSize)
      .offset(offset)
      .get();
    const rows = (data || []) as VendorRow[];
    all.push(...rows);
    if (rows.length < pageSize) break;
    offset += pageSize;
  }
  return all;
}

export default function VendorDatabase() {
  const { readTemplateFile } = useSpaceRuntime();

  const [vendors, setVendors] = useState<VendorRow[]>([]);
  const [ledger, setLedger] = useState<CountryLedgerEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [syncPhase, setSyncPhase] = useState<SyncPhase>('idle');
  const [syncError, setSyncError] = useState<string | null>(null);
  const [report, setReport] = useState<SyncReport | null>(null);
  const autoSyncRef = useRef(false);

  const [search, setSearch] = useState('');
  const [filterCountry, setFilterCountry] = useState('all');
  const [filterCategory, setFilterCategory] = useState('all');
  const [filterPriority, setFilterPriority] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');

  const refreshVendors = async () => {
    setLoadError(null);
    try {
      const rows = await fetchAllVendors();
      setVendors(rows);
    } catch (err: any) {
      setLoadError(err?.message || 'Failed to query the vendor database.');
    } finally {
      setLoading(false);
    }
  };

  // The loader: seed files -> validate -> idempotent upsert keyed on vendor_key.
  const runSync = async () => {
    if (syncPhase === 'reading' || syncPhase === 'diffing' || syncPhase === 'writing') return;
    setSyncError(null);
    setSyncPhase('reading');
    const issues: string[] = [];
    try {
      const indexRaw = await readTemplateFile(INDEX_PATH);
      const index = JSON.parse(indexRaw);
      const countries: CountryLedgerEntry[] = Array.isArray(index?.countries) ? index.countries : [];
      if (countries.length === 0) throw new Error(`No countries listed in ${INDEX_PATH}.`);
      setLedger(countries);

      const seedByKey = new Map<string, any>();
      let seedRows = 0;
      let skipped = 0;
      let filesRead = 0;

      for (const entry of countries) {
        const fileLabel = entry.file.split('/').pop() || entry.file;
        let rows: any[];
        try {
          const raw = await readTemplateFile(entry.file);
          rows = JSON.parse(raw);
          if (!Array.isArray(rows)) throw new Error('file is not a JSON array');
        } catch (err: any) {
          issues.push(`${fileLabel}: could not read/parse (${err?.message || err}) — file skipped`);
          continue;
        }
        filesRead += 1;
        if (typeof entry.row_count === 'number' && entry.row_count !== rows.length) {
          issues.push(`${fileLabel}: ledger says ${entry.row_count} rows but file has ${rows.length}`);
        }
        rows.forEach((row, i) => {
          seedRows += 1;
          const errs = validateSeedRow(row, fileLabel, i);
          if (errs.length > 0) {
            skipped += 1;
            issues.push(...errs);
            return;
          }
          if (seedByKey.has(row.vendor_key)) {
            skipped += 1;
            issues.push(`${fileLabel}[${i}]: duplicate vendor_key "${row.vendor_key}" — kept first occurrence`);
            return;
          }
          seedByKey.set(row.vendor_key, row);
        });
      }

      if (filesRead === 0) throw new Error('No seed files could be read.');

      setSyncPhase('diffing');
      const existing = await fetchAllVendors();
      const existingByKey = new Map(existing.map((r) => [r.vendor_key, r]));

      const toInsert: any[] = [];
      const toUpdate: { id: number; patch: Record<string, unknown> }[] = [];
      let unchanged = 0;

      for (const [key, seed] of seedByKey) {
        const current = existingByKey.get(key);
        if (!current) {
          toInsert.push(seed);
        } else if (researchFieldsDiffer(seed, current)) {
          const patch: Record<string, unknown> = {};
          for (const f of RESEARCH_FIELDS) patch[f] = seed[f];
          toUpdate.push({ id: current.id, patch });
        } else {
          unchanged += 1;
        }
      }

      setSyncPhase('writing');
      let inserted = 0;
      for (const batch of chunk(toInsert, 100)) {
        const payload = batch.map((r) => ({
          vendor_key: r.vendor_key,
          name: r.name,
          service_type: r.service_type,
          country_coverage: r.country_coverage,
          primary_country: r.primary_country,
          cities: r.cities,
          priority_at_hub: r.priority_at_hub,
          regulatory_gate: r.regulatory_gate,
          website: r.website,
          contact_name: r.contact_name,
          contact_email: r.contact_email,
          contact_phone: r.contact_phone,
          is_preferred: r.is_preferred,
          notes: r.notes,
          confidence: r.confidence,
          verification_status: r.verification_status,
          verified_at: r.verified_at,
          source: r.source,
        }));
        try {
          await db().from(TABLE, { shared: true }).bulkInsert(payload);
          inserted += payload.length;
        } catch {
          // Fall back to row-by-row so one bad/conflicting row can't sink the batch
          // (e.g. a unique vendor_key conflict from a concurrent sync).
          for (const row of payload) {
            try {
              await db().from(TABLE, { shared: true }).insert(row);
              inserted += 1;
            } catch (err: any) {
              issues.push(`insert failed for "${row.vendor_key}": ${err?.message || err}`);
            }
          }
        }
      }

      let updated = 0;
      for (const u of toUpdate) {
        try {
          await db().from(TABLE, { shared: true }).update(u.id, u.patch);
          updated += 1;
        } catch (err: any) {
          issues.push(`update failed for row #${u.id}: ${err?.message || err}`);
        }
      }

      setReport({
        finishedAt: new Date().toISOString(),
        filesRead,
        seedRows,
        inserted,
        updated,
        unchanged,
        skipped,
        issues,
      });
      setSyncPhase('done');
      await refreshVendors();
    } catch (err: any) {
      setSyncError(err?.message || 'Sync failed.');
      setSyncPhase('error');
    }
  };

  useEffect(() => {
    (async () => {
      // Load the coverage ledger for display even before any sync.
      try {
        const indexRaw = await readTemplateFile(INDEX_PATH);
        const index = JSON.parse(indexRaw);
        if (Array.isArray(index?.countries)) setLedger(index.countries);
      } catch {
        // ledger is informational; the table query below is authoritative
      }
      try {
        const rows = await fetchAllVendors();
        setVendors(rows);
        setLoading(false);
        // First run: table empty -> load the seed files automatically.
        if (rows.length === 0 && !autoSyncRef.current) {
          autoSyncRef.current = true;
          runSync();
        }
      } catch (err: any) {
        setLoadError(err?.message || 'Failed to query the vendor database.');
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const countryNames = useMemo(() => {
    const map: Record<string, string> = {};
    ledger.forEach((c) => { map[c.iso2] = c.country; });
    return map;
  }, [ledger]);

  const countries = useMemo(
    () => Array.from(new Set(vendors.map((v) => v.primary_country))).sort(),
    [vendors],
  );

  const filtered = useMemo(() => {
    let out = vendors;
    if (filterCountry !== 'all') out = out.filter((v) => v.primary_country === filterCountry);
    if (filterCategory !== 'all') out = out.filter((v) => v.service_type === filterCategory);
    if (filterPriority !== 'all') out = out.filter((v) => v.priority_at_hub === filterPriority);
    if (filterStatus !== 'all') out = out.filter((v) => v.verification_status === filterStatus);
    if (search.trim()) {
      const q = search.toLowerCase();
      out = out.filter((v) =>
        v.name.toLowerCase().includes(q) ||
        v.vendor_key.toLowerCase().includes(q) ||
        asArray(v.cities).some((c) => c.toLowerCase().includes(q)) ||
        (v.notes || '').toLowerCase().includes(q) ||
        (v.regulatory_gate || '').toLowerCase().includes(q),
      );
    }
    return [...out].sort((a, b) =>
      a.primary_country.localeCompare(b.primary_country) ||
      a.service_type.localeCompare(b.service_type) ||
      a.name.localeCompare(b.name),
    );
  }, [vendors, filterCountry, filterCategory, filterPriority, filterStatus, search]);

  const stats = useMemo(() => ({
    total: vendors.length,
    countries: countries.length,
    verified: vendors.filter((v) => v.verification_status === 'verified').length,
    critical: vendors.filter((v) => v.priority_at_hub === 'critical').length,
  }), [vendors, countries]);

  const syncBusy = syncPhase === 'reading' || syncPhase === 'diffing' || syncPhase === 'writing';
  const syncLabel =
    syncPhase === 'reading' ? 'Reading seed files…'
    : syncPhase === 'diffing' ? 'Diffing against database…'
    : syncPhase === 'writing' ? 'Writing rows…'
    : 'Sync seed files';

  const confidenceBadge = (c: string) =>
    c === 'high' ? 'bg-[var(--space-semantic-success)]/15 text-[var(--space-semantic-success)]'
    : c === 'medium' ? 'bg-amber-500/15 text-amber-400'
    : 'bg-red-500/15 text-red-400';

  const statusBadge = (s: string) =>
    s === 'verified' ? 'bg-[var(--space-semantic-success)]/15 text-[var(--space-semantic-success)]'
    : s === 'rejected' ? 'bg-red-500/15 text-red-400'
    : 'bg-[var(--space-surface-muted)] text-[var(--space-text-muted)]';

  return (
    <div className="h-full flex flex-col bg-[var(--space-surface-page)]">
      {/* Header */}
      <div className="px-5 pt-5 pb-4 border-b border-[var(--space-border-default)]">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-[var(--space-surface-accent-soft)] flex items-center justify-center flex-shrink-0">
              <Database className="w-5 h-5 text-[var(--space-text-accent)]" />
            </div>
            <div className="min-w-0">
              <h1 className="text-lg font-bold text-[var(--space-text-primary)]">Vendor Database</h1>
              <p className="text-xs text-[var(--space-text-secondary)] mt-0.5">
                Live vendor coverage database (<span className="font-mono">relopass_vendors</span>), loaded from the
                country seed files in <span className="font-mono">supabase/seed/vendors/</span> and keyed by <span className="font-mono">vendor_key</span>.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={runSync}
              disabled={syncBusy}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-[var(--space-brand-primary)] text-[var(--space-text-on-primary)] hover:brightness-110 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <UploadCloud className={`w-4 h-4 ${syncBusy ? 'animate-pulse' : ''}`} /> {syncLabel}
            </button>
            <button
              onClick={() => triggerDownload(JSON.stringify(vendors, null, 2), 'relopass-vendors.json', 'application/json')}
              disabled={vendors.length === 0}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-[var(--space-surface-accent-soft)] text-[var(--space-text-accent)] border border-[var(--space-border-default)] hover:brightness-110 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <FileJson className="w-4 h-4" /> JSON
            </button>
            <button
              onClick={() => triggerDownload(buildCsv(vendors), 'relopass-vendors.csv', 'text/csv;charset=utf-8')}
              disabled={vendors.length === 0}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-[var(--space-surface-accent-soft)] text-[var(--space-text-accent)] border border-[var(--space-border-default)] hover:brightness-110 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <FileText className="w-4 h-4" /> CSV
            </button>
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {loading && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <RefreshCw className="w-6 h-6 text-[var(--space-text-muted)] animate-spin mb-3" />
            <p className="text-sm text-[var(--space-text-secondary)]">Loading the vendor database…</p>
          </div>
        )}

        {!loading && loadError && (
          <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-5 text-center">
            <AlertCircle className="w-6 h-6 text-red-400 mx-auto mb-2" />
            <p className="text-sm font-medium text-[var(--space-text-primary)] mb-1">Couldn't query the database</p>
            <p className="text-xs text-[var(--space-text-secondary)] mb-3">{loadError}</p>
            <button
              onClick={() => { setLoading(true); refreshVendors(); }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-[var(--space-surface-accent-soft)] text-[var(--space-text-accent)] hover:brightness-110"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Try again
            </button>
          </div>
        )}

        {!loading && !loadError && (
          <>
            {/* Sync status / report */}
            {syncBusy && (
              <div className="rounded-2xl border border-[var(--space-border-default)] bg-[var(--space-surface-panel)] p-4 flex items-center gap-3">
                <RefreshCw className="w-4 h-4 text-[var(--space-text-accent)] animate-spin flex-shrink-0" />
                <p className="text-xs text-[var(--space-text-secondary)]">
                  {syncLabel} Loading the vendor seed files into <span className="font-mono">relopass_vendors</span> — this runs once and is idempotent (re-running with unchanged files changes nothing).
                </p>
              </div>
            )}
            {syncPhase === 'error' && syncError && (
              <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-4 flex items-start gap-3">
                <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs font-semibold text-[var(--space-text-primary)] mb-0.5">Seed sync failed</p>
                  <p className="text-xs text-[var(--space-text-secondary)]">{syncError}</p>
                </div>
              </div>
            )}
            {report && !syncBusy && (
              <div className="rounded-2xl border border-[var(--space-border-default)] bg-[var(--space-surface-panel)] p-4">
                <div className="flex items-center gap-2 mb-1.5">
                  <CheckCircle2 className="w-4 h-4 text-[var(--space-semantic-success)] flex-shrink-0" />
                  <p className="text-xs font-semibold text-[var(--space-text-primary)]">
                    Seed sync complete — {report.inserted} inserted · {report.updated} updated · {report.unchanged} unchanged
                    {report.skipped > 0 ? ` · ${report.skipped} skipped` : ''}
                  </p>
                </div>
                <p className="text-[10px] text-[var(--space-text-muted)]">
                  {report.filesRead} country files · {report.seedRows} seed rows · keyed on vendor_key · founder fields
                  (preferred / verification) are never overwritten by a re-sync · {new Date(report.finishedAt).toLocaleString()}
                </p>
                {report.issues.length > 0 && (
                  <details className="mt-2">
                    <summary className="text-[10px] font-semibold text-amber-400 cursor-pointer flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" /> {report.issues.length} validation issue{report.issues.length !== 1 ? 's' : ''}
                    </summary>
                    <ul className="mt-1.5 space-y-0.5 max-h-40 overflow-y-auto">
                      {report.issues.map((iss, i) => (
                        <li key={i} className="text-[10px] text-[var(--space-text-secondary)] font-mono">{iss}</li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            )}

            {/* Metrics */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: 'Vendors loaded', value: String(stats.total), Icon: Building2 },
                { label: 'Destination countries', value: String(stats.countries), Icon: Globe },
                { label: 'Critical-priority rows', value: String(stats.critical), Icon: Star },
                { label: 'Verified', value: `${stats.verified} / ${stats.total}`, Icon: ShieldCheck },
              ].map(({ label, value, Icon }) => (
                <div key={label} className="rounded-2xl border border-[var(--space-border-default)] bg-[var(--space-surface-panel)] px-4 py-3 flex items-center gap-3">
                  <Icon className="w-4 h-4 text-[var(--space-text-accent)] flex-shrink-0" />
                  <div>
                    <p className="text-base font-bold text-[var(--space-text-primary)] leading-tight">{value}</p>
                    <p className="text-[10px] text-[var(--space-text-muted)]">{label}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Coverage ledger */}
            {ledger.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {ledger.map((c) => {
                  const loaded = vendors.filter((v) => v.primary_country === c.iso2).length;
                  const active = filterCountry === c.iso2;
                  return (
                    <button
                      key={c.iso2}
                      onClick={() => setFilterCountry(active ? 'all' : c.iso2)}
                      className={`px-3 py-1.5 rounded-full text-[11px] font-medium border transition-all ${
                        active
                          ? 'bg-[var(--space-brand-primary)] text-[var(--space-text-on-primary)] border-[var(--space-brand-primary)]'
                          : 'bg-[var(--space-surface-panel)] text-[var(--space-text-secondary)] border-[var(--space-border-default)] hover:border-[var(--space-border-strong)]'
                      }`}
                    >
                      {c.country} <span className="font-bold">{loaded}</span>
                      {loaded !== c.row_count ? <span className="opacity-70"> / {c.row_count} in seed</span> : ''}
                    </button>
                  );
                })}
              </div>
            )}

            {/* Filters */}
            <div className="space-y-2">
              <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-[var(--space-surface-panel)] border border-[var(--space-border-default)]">
                <Search className="w-3.5 h-3.5 text-[var(--space-text-muted)] flex-shrink-0" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search vendor, city, gate, or notes…"
                  className="flex-1 text-sm bg-transparent border-none outline-none text-[var(--space-text-primary)] placeholder:text-[var(--space-text-muted)]"
                />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={filterCategory}
                  onChange={(e) => setFilterCategory(e.target.value)}
                  className="text-xs border border-[var(--space-border-default)] rounded-lg px-2.5 py-1.5 bg-[var(--space-surface-panel)] text-[var(--space-text-secondary)]"
                >
                  <option value="all">All categories</option>
                  {SERVICE_TYPES.map((t) => <option key={t} value={t}>{CATEGORY_LABELS[t]}</option>)}
                </select>
                <select
                  value={filterCountry}
                  onChange={(e) => setFilterCountry(e.target.value)}
                  className="text-xs border border-[var(--space-border-default)] rounded-lg px-2.5 py-1.5 bg-[var(--space-surface-panel)] text-[var(--space-text-secondary)]"
                >
                  <option value="all">All countries</option>
                  {countries.map((c) => <option key={c} value={c}>{countryNames[c] || c}</option>)}
                </select>
                <select
                  value={filterPriority}
                  onChange={(e) => setFilterPriority(e.target.value)}
                  className="text-xs border border-[var(--space-border-default)] rounded-lg px-2.5 py-1.5 bg-[var(--space-surface-panel)] text-[var(--space-text-secondary)]"
                >
                  <option value="all">All priorities</option>
                  {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="text-xs border border-[var(--space-border-default)] rounded-lg px-2.5 py-1.5 bg-[var(--space-surface-panel)] text-[var(--space-text-secondary)]"
                >
                  <option value="all">All statuses</option>
                  {VERIFICATION_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <p className="text-[10px] text-[var(--space-text-muted)] ml-auto">
                  {filtered.length} of {vendors.length} vendors
                </p>
              </div>
            </div>

            {/* Vendor list */}
            {vendors.length === 0 && !syncBusy ? (
              <div className="rounded-2xl border border-[var(--space-border-default)] bg-[var(--space-surface-panel)] p-8 text-center">
                <Info className="w-6 h-6 text-[var(--space-text-muted)] mx-auto mb-2" />
                <p className="text-sm text-[var(--space-text-secondary)]">
                  The vendor table is empty. Click “Sync seed files” to load the country seed files.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {filtered.map((v) => (
                  <div key={v.vendor_key} className="rounded-2xl border border-[var(--space-border-default)] bg-[var(--space-surface-panel)] p-3.5">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {v.is_preferred && <Star className="w-3.5 h-3.5 text-amber-400 fill-amber-400 flex-shrink-0" />}
                          <h3 className="text-sm font-semibold text-[var(--space-text-primary)]">{v.name}</h3>
                          <a
                            href={v.website}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[var(--space-text-accent)] hover:brightness-110 flex-shrink-0"
                            title={v.website}
                          >
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        </div>
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 text-[10px] text-[var(--space-text-muted)]">
                          <span className="flex items-center gap-1">
                            <MapPin className="w-3 h-3" />
                            {countryNames[v.primary_country] || v.primary_country} · {asArray(v.cities).join(', ')}
                          </span>
                          {v.regulatory_gate && (
                            <span className="px-1.5 py-0.5 rounded bg-[var(--space-surface-accent-soft)] text-[var(--space-text-accent)] font-medium">
                              Gate: {v.regulatory_gate}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5 flex-wrap flex-shrink-0">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-[var(--space-surface-muted)] text-[var(--space-text-secondary)] border border-[var(--space-border-default)]">
                          {CATEGORY_LABELS[v.service_type] || v.service_type}
                        </span>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                          v.priority_at_hub === 'critical' ? 'bg-red-500/15 text-red-400'
                          : v.priority_at_hub === 'important' ? 'bg-amber-500/15 text-amber-400'
                          : 'bg-[var(--space-surface-muted)] text-[var(--space-text-muted)]'
                        }`}>
                          {v.priority_at_hub}
                        </span>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${confidenceBadge(v.confidence)}`}>
                          {v.confidence}
                        </span>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${statusBadge(v.verification_status)}`}>
                          {v.verification_status}
                        </span>
                      </div>
                    </div>
                    {v.notes && (
                      <details className="mt-2">
                        <summary className="text-[10px] font-medium text-[var(--space-text-muted)] cursor-pointer">Research notes</summary>
                        <p className="text-[11px] text-[var(--space-text-secondary)] mt-1 leading-relaxed">{v.notes}</p>
                      </details>
                    )}
                  </div>
                ))}
                {filtered.length === 0 && vendors.length > 0 && (
                  <p className="text-xs text-[var(--space-text-muted)] text-center py-8">No vendors match your filters.</p>
                )}
              </div>
            )}

            <p className="text-[10px] text-[var(--space-text-muted)] flex items-center gap-1.5 pb-2">
              <Download className="w-3 h-3" />
              Downloads export the live table (one row per vendor). Seed contract: supabase/seed/vendors/_SCHEMA.md.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
