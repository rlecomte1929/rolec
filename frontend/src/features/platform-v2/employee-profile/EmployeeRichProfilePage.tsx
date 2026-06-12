import { useState, useMemo, useRef, useCallback, useEffect } from 'react';
import { Input } from '../../../components/antigravity/Input';
import { Button } from '../../../components/antigravity/Button';
import { AppShell } from '../../../components/AppShell';
import { useEmployeeAssignment } from '../../../contexts/EmployeeAssignmentContext';
import { getRichProfile, saveRichProfile } from '../../../api/relocationProfile';

// ─── Types ────────────────────────────────────────────────────────────────────

type Tier = 'basic' | 'standard' | 'premium';
type SectionState = 'complete' | 'partial' | 'empty' | 'na';

interface HouseholdMember {
  id: string;
  kind: 'self' | 'partner' | 'child' | 'pet';
  name?: string;
  dob?: string;
  pet_type?: string;
  breed?: string;
}

interface ChildExtra {
  school_pref?: string;
  lang?: string;
  curriculum?: string;
  special_needs?: string;
}

interface PetExtra {
  name?: string;
  age?: number;
  vaccinations_uptodate?: string;
  eu_pet_passport?: string;
}

interface NeighborhoodPriorities {
  commute: number;
  intl_school: number;
  parks: number;
  expat: number;
  nightlife: number;
  safety: number;
  transit: number;
}

interface ProfileData {
  // A — Origin
  origin_housing_status: string;
  lease_end_date: string;
  has_break_clause: string;
  is_selling: string;
  sale_date: string;
  household_volume: string;
  vehicles_to_ship: string[];
  important_docs: string[];
  // B — Housing prefs
  intent_rent_or_buy: string;
  housing_type: string;
  bedrooms_needed: number;
  must_haves: string[];
  neighborhood_priorities: NeighborhoodPriorities;
  monthly_budget_min: number | '';
  monthly_budget_max: number | '';
  policy_cap: number;
  // C — Spouse
  spouse_employment: string;
  spouse_sector: string;
  spouse_contract: string;
  spouse_resigning: string;
  spouse_lang_level: string;
  spouse_wants_lang: string;
  spouse_right_to_work: string;
  spouse_needs_dep_visa: string;
  spouse_credentials_ok: string;
  // D — Children (per child id)
  children_extra: Record<string, ChildExtra>;
  // E — Pets (per pet id)
  pets_extra: Record<string, PetExtra>;
  // F — Temp housing
  temp_needed: string;
  temp_duration: string;
  temp_type: string;
  // G — Financial
  dual_tax: string;
  has_corporate_tax_support: string;
  need_bank_account: string;
  need_fx_transfer: string;
  fx_amount_range: string;
}

// ─── Mock seed data (Marc Bouchard — France → Norway, family) ────────────────

const MEMBERS: HouseholdMember[] = [
  { id: 'self',    kind: 'self',    name: 'Marc Bouchard' },
  { id: 'partner', kind: 'partner', name: 'Isabelle Bouchard' },
  { id: 'c1',      kind: 'child',   name: 'Léa',   dob: '2016-05-12' },
  { id: 'c2',      kind: 'child',   name: 'Hugo',  dob: '2019-10-28' },
];

const DEFAULTS: ProfileData = {
  origin_housing_status: '',
  lease_end_date: '',
  has_break_clause: '',
  is_selling: '',
  sale_date: '',
  household_volume: '',
  vehicles_to_ship: [],
  important_docs: [],

  intent_rent_or_buy: '',
  housing_type: '',
  bedrooms_needed: 0,
  must_haves: [],
  neighborhood_priorities: { commute: 0, intl_school: 0, parks: 0, expat: 0, nightlife: 0, safety: 0, transit: 0 },
  monthly_budget_min: '',
  monthly_budget_max: '',
  policy_cap: 0,

  spouse_employment: '',
  spouse_sector: '',
  spouse_contract: '',
  spouse_resigning: '',
  spouse_lang_level: '',
  spouse_wants_lang: '',
  spouse_right_to_work: '',
  spouse_needs_dep_visa: '',
  spouse_credentials_ok: '',

  children_extra: {},
  pets_extra: {},

  temp_needed: '',
  temp_duration: '',
  temp_type: '',

  dual_tax: '',
  has_corporate_tax_support: '',
  need_bank_account: '',
  need_fx_transfer: '',
  fx_amount_range: '',
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function computeAge(dob?: string): number | null {
  if (!dob) return null;
  const d = new Date(dob);
  if (isNaN(d.getTime())) return null;
  return Math.floor((Date.now() - d.getTime()) / (1000 * 60 * 60 * 24 * 365.25));
}

function sectionCompletionState(id: string, profile: ProfileData, members: HouseholdMember[]): SectionState {
  const children = members.filter((m) => m.kind === 'child');
  const pets = members.filter((m) => m.kind === 'pet');
  const partner = members.find((m) => m.kind === 'partner');

  if (id === 'C') {
    if (!partner) return 'na';
    const filled = ['spouse_employment', 'spouse_lang_level', 'spouse_right_to_work'].filter(
      (f) => (profile as unknown as Record<string, unknown>)[f],
    );
    return filled.length === 3 ? 'complete' : filled.length > 0 ? 'partial' : 'empty';
  }
  if (id === 'D') {
    if (!children.length) return 'na';
    const all = children.every((c) => profile.children_extra[c.id]?.school_pref);
    const some = children.some((c) => profile.children_extra[c.id]?.school_pref);
    return all ? 'complete' : some ? 'partial' : 'empty';
  }
  if (id === 'E') {
    if (!pets.length) return 'na';
    const all = pets.every((p) => profile.pets_extra[p.id]?.vaccinations_uptodate);
    const some = pets.some((p) => profile.pets_extra[p.id]?.vaccinations_uptodate);
    return all ? 'complete' : some ? 'partial' : 'empty';
  }
  const SECTION_KEY_FIELDS: Record<string, (keyof ProfileData)[]> = {
    A: ['origin_housing_status', 'household_volume', 'vehicles_to_ship', 'important_docs'],
    B: ['intent_rent_or_buy', 'housing_type', 'bedrooms_needed', 'must_haves', 'monthly_budget_max'],
    F: ['temp_needed'],
    G: ['has_corporate_tax_support', 'need_bank_account'],
  };
  const fields = SECTION_KEY_FIELDS[id] ?? [];
  const filled = fields.filter((f) => {
    const v = profile[f];
    if (v == null || v === '') return false;
    if (Array.isArray(v)) return v.length > 0;
    return true;
  });
  if (filled.length === fields.length) return 'complete';
  if (filled.length > 0) return 'partial';
  return 'empty';
}

// ─── Small UI components ──────────────────────────────────────────────────────

function MultiChip({ value, onChange, options }: { value: string[]; onChange: (v: string[]) => void; options: string[] }) {
  const toggle = (opt: string) => {
    onChange(value.includes(opt) ? value.filter((x) => x !== opt) : [...value, opt]);
  };
  return (
    <div className="flex flex-wrap gap-1.5 mt-1">
      {options.map((o) => (
        <Button unstyled
          key={o}
          type="button"
          onClick={() => toggle(o)}
          className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
            value.includes(o)
              ? 'bg-accent-600 text-white border-accent-600'
              : 'border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50'
          }`}
        >
          {o}
        </Button>
      ))}
    </div>
  );
}

function StarRating({ value, onChange, max = 5 }: { value: number; onChange: (v: number) => void; max?: number }) {
  return (
    <span className="flex gap-0.5">
      {Array.from({ length: max }).map((_, i) => (
        <Button unstyled
          key={i}
          type="button"
          onClick={() => onChange(i + 1)}
          className={`text-base leading-none transition-colors ${i < value ? 'text-accent-500' : 'text-gray-200'}`}
        >
          ★
        </Button>
      ))}
    </span>
  );
}

function FieldWrap({
  label,
  hint,
  why,
  optional,
  className = '',
  children,
}: {
  label: string;
  hint?: string;
  why?: string;
  optional?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  const [whyOpen, setWhyOpen] = useState(false);
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <label className="text-xs font-semibold text-gray-700 flex items-center gap-1.5">
        {label}
        {optional && <span className="text-gray-400 font-normal">(optional)</span>}
        {why && (
          <Button unstyled
            type="button"
            onClick={() => setWhyOpen((o) => !o)}
            className="text-accent-500 text-[10px] font-medium hover:text-accent-700"
          >
            Why?
          </Button>
        )}
      </label>
      {children}
      {whyOpen && why && (
        <div className="text-xs text-gray-500 bg-accent-50 border border-accent-100 rounded-lg px-3 py-2">{why}</div>
      )}
      {hint && <div className="text-xs text-gray-400">{hint}</div>}
    </div>
  );
}

function SelectField({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: string[] }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-300 bg-white"
    >
      {options.map((o) => {
        const optValue = o === '' ? '' : o;
        const optLabel = o === '' ? 'Select…' : o;
        return (
          <option key={o} value={optValue}>
            {optLabel}
          </option>
        );
      })}
    </select>
  );
}

function TierGate({ tier, required, label, children }: { tier: Tier; required: Tier; label: string; children: React.ReactNode }) {
  const RANK: Record<Tier, number> = { basic: 0, standard: 1, premium: 2 };
  const LABEL: Record<Tier, string> = { basic: 'Basic', standard: 'Standard', premium: 'Premium' };
  if (RANK[tier] >= RANK[required]) return <>{children}</>;
  return (
    <div className="relative rounded-xl overflow-hidden">
      <div className="opacity-30 pointer-events-none">{children}</div>
      <div className="absolute inset-0 flex items-center justify-center bg-white/70 backdrop-blur-sm rounded-xl">
        <div className="text-center p-6 max-w-xs">
          <div className="text-2xl mb-2">🔒</div>
          <div className="text-sm font-semibold text-gray-900">
            Available on{' '}
            <span className="px-1.5 py-0.5 rounded bg-accent-100 text-accent-700 text-xs font-bold">{LABEL[required]}</span>
          </div>
          <div className="text-xs text-gray-500 mt-1">Ask your HR team to upgrade your ReloPass plan to unlock {label}.</div>
          <Button unstyled className="mt-3 px-4 py-1.5 rounded-lg bg-navy-800 text-white text-xs font-semibold hover:bg-navy-900 transition-colors">
            Request upgrade
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Section card ─────────────────────────────────────────────────────────────

const STATE_LABEL: Record<SectionState, string> = {
  complete: '✓ Complete',
  partial: 'In progress',
  empty: 'Not started',
  na: 'Not applicable',
};
const STATE_CLS: Record<SectionState, string> = {
  complete: 'text-green-600 bg-green-50',
  partial: 'text-amber-600 bg-amber-50',
  empty: 'text-gray-400 bg-gray-50',
  na: 'text-gray-300 bg-gray-50',
};

function SectionCard({
  id,
  marker,
  title,
  sub,
  state,
  est,
  unlocks,
  urgent,
  urgentReason,
  expanded,
  onToggle,
  cardRef,
  children,
}: {
  id: string;
  marker: string;
  title: string;
  sub: string;
  state: SectionState;
  est?: number;
  unlocks?: string;
  urgent?: boolean;
  urgentReason?: string;
  expanded: boolean;
  onToggle: () => void;
  cardRef?: (el: HTMLDivElement | null) => void;
  children: React.ReactNode;
}) {
  return (
    <div
      ref={cardRef}
      id={`rp-${id}`}
      className={`border rounded-xl overflow-hidden transition-all ${
        urgent ? 'border-amber-300' : expanded ? 'border-accent-200' : 'border-gray-100'
      } ${state === 'complete' ? 'bg-green-50/30' : 'bg-white'}`}
    >
      {/* Header */}
      <Button unstyled
        type="button"
        onClick={onToggle}
        className="w-full flex items-start gap-4 px-5 py-4 text-left hover:bg-gray-50/50 transition-colors"
      >
        <div
          className={`flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold mt-0.5 ${
            state === 'complete'
              ? 'bg-green-500 text-white'
              : urgent
              ? 'bg-amber-400 text-white'
              : 'bg-accent-100 text-accent-700'
          }`}
        >
          {state === 'complete' ? '✓' : marker}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-gray-900">{title}</span>
            {urgent && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-semibold">
                ⚠ {urgentReason}
              </span>
            )}
          </div>
          <div className="text-xs text-gray-500 mt-0.5">{sub}</div>
          {!expanded && unlocks && (
            <div className="text-[10px] text-accent-600 mt-1">
              <span className="mr-1">✦</span>Unlocks: <strong>{unlocks}</strong>
            </div>
          )}
        </div>
        <div className="flex-shrink-0 flex items-center gap-2 mt-0.5">
          {est && <span className="text-[10px] text-gray-400">~{est} min</span>}
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${STATE_CLS[state]}`}>
            {STATE_LABEL[state]}
          </span>
          <span className={`text-gray-400 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}>▾</span>
        </div>
      </Button>

      {/* Body */}
      {expanded && <div className="px-5 pb-5 border-t border-gray-100">{children}</div>}
    </div>
  );
}

// ─── Completion ring (SVG) ────────────────────────────────────────────────────

function CompletionRing({ pct, size = 72 }: { pct: number; size?: number }) {
  const stroke = 6;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const off = c * (1 - pct / 100);
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: 'rotate(-90deg)' }}>
      <circle cx={size / 2} cy={size / 2} r={r} strokeWidth={stroke} stroke="#e5e7eb" fill="none" />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        strokeWidth={stroke}
        stroke="#1f8e8b"
        fill="none"
        strokeDasharray={c}
        strokeDashoffset={off}
        strokeLinecap="round"
      />
    </svg>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function EmployeeRichProfilePage() {
  const tier: Tier = 'standard';
  const { primaryCaseId } = useEmployeeAssignment();
  const [profile, setProfile] = useState<ProfileData>(DEFAULTS);
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ B: true });
  const sectionRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const set = useCallback(<K extends keyof ProfileData>(k: K, v: ProfileData[K]) => {
    setProfile((p) => ({ ...p, [k]: v }));
    setSaveState((s) => (s === 'saving' ? s : 'idle'));
  }, []);

  // Load the saved profile for this case; keep DEFAULTS if none / on error.
  useEffect(() => {
    if (!primaryCaseId) return;
    let cancelled = false;
    getRichProfile(primaryCaseId)
      .then((res) => {
        if (cancelled) return;
        const stored = res?.data;
        if (stored && typeof stored === 'object' && Object.keys(stored).length > 0) {
          setProfile((prev) => ({ ...prev, ...(stored as Partial<ProfileData>) }));
        }
      })
      .catch(() => { /* keep DEFAULTS — empty-first */ });
    return () => { cancelled = true; };
  }, [primaryCaseId]);

  const handleSave = useCallback(async () => {
    if (!primaryCaseId) return;
    setSaveState('saving');
    try {
      await saveRichProfile(primaryCaseId, profile);
      setSaveState('saved');
    } catch {
      setSaveState('error');
    }
  }, [primaryCaseId, profile]);

  const partner = MEMBERS.find((m) => m.kind === 'partner');
  const children = MEMBERS.filter((m) => m.kind === 'child');
  const pets = MEMBERS.filter((m) => m.kind === 'pet');

  const toggle = (id: string) => setExpanded((e) => ({ ...e, [id]: !e[id] }));
  const focusSection = (id: string) => {
    setExpanded((e) => ({ ...e, [id]: true }));
    setTimeout(() => {
      sectionRefs.current[id]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
  };

  const SECTIONS = [
    { id: 'A', marker: 'A', title: 'Origin details',             sub: 'Build the outbound leg — lease, household volume, vehicles.', tier: 'premium' as Tier, est: 2, unlocks: 'Estate agent or lease-break milestones', show: true },
    { id: 'B', marker: 'B', title: 'Destination housing',        sub: 'Pre-filter your housing recommendations.',                     tier: 'standard' as Tier, est: 3, unlocks: 'Housing shortlist with commute + neighborhood scoring', show: true },
    { id: 'C', marker: 'C', title: 'Spouse / partner',           sub: `Building ${partner?.name ?? 'your partner'}'s parallel track.`, tier: 'standard' as Tier, est: 3, unlocks: 'Partner immigration + career services', show: !!partner },
    { id: 'D', marker: 'D', title: 'Children',                   sub: 'School preferences, language, special needs.',                  tier: 'standard' as Tier, est: 2, unlocks: 'School search + enrollment deadlines', show: !!children.length, urgent: true, urgentReason: 'Sep 1 enrollment' },
    { id: 'E', marker: 'E', title: 'Pet relocation',             sub: `Health certs, microchips, quarantine prep.`,                   tier: 'standard' as Tier, est: 3, unlocks: 'Pet transport providers + health-cert milestones', show: !!pets.length },
    { id: 'F', marker: 'F', title: 'Temporary housing',          sub: 'Where you stay between arrival and your permanent home.',       tier: 'standard' as Tier, est: 1, unlocks: 'Arrival sequence + temp housing providers', show: true },
    { id: 'G', marker: 'G', title: 'Financial & tax',            sub: 'Tax equalization, banking, FX transfers.',                     tier: 'premium' as Tier, est: 2, unlocks: 'Tax advisor + banking services', show: true },
  ].filter((s) => s.show);

  const totalCompletion = useMemo(() => {
    const states = SECTIONS.map((s) => sectionCompletionState(s.id, profile, MEMBERS));
    const scored = states.map((st) => (st === 'complete' ? 1 : st === 'partial' ? 0.5 : 0));
    return Math.round(((scored as number[]).reduce((a, b) => a + b, 0) / SECTIONS.length) * 100);
  }, [profile, SECTIONS]);

  const completeCount = SECTIONS.filter(
    (s) => sectionCompletionState(s.id, profile, MEMBERS) === 'complete',
  ).length;

  // ── Grid helper: 2-column responsive grid ───────────────────────
  const Grid = ({ children }: { children: React.ReactNode }) => (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">{children}</div>
  );

  return (
    <AppShell wide>
      <div className="mx-auto max-w-5xl px-6 py-8">
        {/* Header */}
        <div className="mb-6">
          <div className="text-xs font-semibold text-accent-600 uppercase tracking-widest mb-1">
            Employee · Profile &amp; Preferences
          </div>
          <div className="flex items-end justify-between gap-4">
            <h1 className="text-2xl font-bold text-gray-900">Your profile &amp; preferences</h1>
            <div className="flex items-center gap-2">
              <Button
                unstyled
                onClick={handleSave}
                disabled={!primaryCaseId || saveState === 'saving'}
                className="px-4 py-2 text-sm font-medium rounded-lg bg-accent-600 text-white hover:bg-accent-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {saveState === 'saving' ? 'Saving…' : saveState === 'saved' ? 'Saved ✓' : saveState === 'error' ? 'Retry save' : 'Save'}
              </Button>
              <Button unstyled className="px-3 py-2 text-sm font-medium border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
                ↓ Export data
              </Button>
            </div>
          </div>
          <p className="mt-2 text-sm text-gray-500 max-w-2xl">
            Each completed section unlocks smarter recommendations and adds milestones to your roadmap. None of this blocks your case.
          </p>
        </div>

        {/* Phase 0 summary */}
        <div className="flex items-center gap-4 p-4 rounded-xl bg-green-50 border border-green-100 mb-5">
          <div className="flex-shrink-0 w-7 h-7 rounded-full bg-green-500 flex items-center justify-center text-white text-xs font-bold">✓</div>
          <div className="flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-bold text-gray-700">Phase 0 · Quick setup</span>
              <span className="px-2 py-0.5 rounded-full bg-green-200 text-green-800 text-[10px] font-bold">Complete</span>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-0.5 text-xs text-gray-500">
              <span>🇫🇷 France → 🇳🇴 Norway</span>
              <span>Employment</span>
              <span><strong>Partner + 2 children</strong></span>
              <span>Start: Within 6 weeks</span>
            </div>
          </div>
          <Button unstyled className="text-xs text-accent-600 font-medium hover:text-accent-800">Edit →</Button>
        </div>

        {/* Two-column layout: side + main */}
        <div className="flex gap-6 items-start">
          {/* Sidebar */}
          <aside className="hidden lg:flex flex-col gap-4 w-52 flex-shrink-0 sticky top-6">
            {/* Completion ring */}
            <div className="bg-white border border-gray-100 rounded-xl p-4 flex flex-col items-center gap-2">
              <div className="relative">
                <CompletionRing pct={totalCompletion} />
                <span className="absolute inset-0 flex items-center justify-center text-base font-bold text-gray-900">
                  {totalCompletion}%
                </span>
              </div>
              <div className="text-xs font-semibold text-gray-700 text-center">Profile completion</div>
              <div className="text-[11px] text-gray-400 text-center">
                {completeCount} of {SECTIONS.length} sections complete
              </div>
            </div>

            {/* ToC */}
            <div className="bg-white border border-gray-100 rounded-xl p-2 flex flex-col gap-0.5">
              {SECTIONS.map((s) => {
                const st = sectionCompletionState(s.id, profile, MEMBERS);
                return (
                  <Button unstyled
                    key={s.id}
                    type="button"
                    onClick={() => focusSection(s.id)}
                    className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-left transition-colors text-xs ${
                      expanded[s.id] ? 'bg-accent-50 text-accent-700' : 'text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <span
                      className={`w-2 h-2 rounded-full flex-shrink-0 ${
                        st === 'complete' ? 'bg-green-500' : st === 'partial' ? 'bg-amber-400' : 'bg-gray-200'
                      }`}
                    />
                    <span className="font-medium truncate">{s.title}</span>
                    <span className="ml-auto text-gray-300 text-[10px]">{s.marker}</span>
                  </Button>
                );
              })}
            </div>
          </aside>

          {/* Main sections */}
          <div className="flex-1 min-w-0 flex flex-col gap-3">

            {/* ── Section A — Origin ── */}
            {SECTIONS.find((s) => s.id === 'A') && (
              <TierGate tier={tier} required="premium" label="origin details">
                <SectionCard
                  id="A" marker="A" title="Origin details"
                  sub="Help us build the outbound leg of your roadmap."
                  state={sectionCompletionState('A', profile, MEMBERS)}
                  est={2} unlocks="Estate agent or lease-break milestones"
                  expanded={!!expanded.A} onToggle={() => toggle('A')}
                  cardRef={(el) => { sectionRefs.current.A = el; }}
                >
                  <Grid>
                    <FieldWrap label="Housing situation at origin">
                      <SelectField value={profile.origin_housing_status} onChange={(v) => set('origin_housing_status', v)}
                        options={['', 'Renting', 'Own (mortgage)', 'Own (no mortgage)', 'Living with family / employer']} />
                    </FieldWrap>
                    {profile.origin_housing_status === 'Renting' && (
                      <>
                        <FieldWrap label="Lease end date">
                          <Input unstyled type="date" value={profile.lease_end_date}
                            onChange={(v) => set('lease_end_date', v)}
                            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-300" />
                        </FieldWrap>
                        <FieldWrap label="Break clause in your lease?">
                          <SelectField value={profile.has_break_clause} onChange={(v) => set('has_break_clause', v)}
                            options={['', 'Yes', 'No', 'Not sure']} />
                        </FieldWrap>
                      </>
                    )}
                    {profile.origin_housing_status.startsWith('Own') && (
                      <>
                        <FieldWrap label="Planning to sell?">
                          <SelectField value={profile.is_selling} onChange={(v) => set('is_selling', v)}
                            options={['', 'Yes', 'No']} />
                        </FieldWrap>
                        {profile.is_selling === 'Yes' && (
                          <FieldWrap label="Expected sale completion" optional>
                            <Input unstyled type="date" value={profile.sale_date}
                              onChange={(v) => set('sale_date', v)}
                              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-300" />
                          </FieldWrap>
                        )}
                      </>
                    )}
                    <FieldWrap label="Current household volume" why="Movers use this for the volume estimate that drives shipping quotes.">
                      <SelectField value={profile.household_volume} onChange={(v) => set('household_volume', v)}
                        options={['', 'Studio', '1-bed', '2-bed', '3-bed', '4-bed+']} />
                    </FieldWrap>
                    <FieldWrap label="Vehicles to ship internationally" className="sm:col-span-2">
                      <MultiChip value={profile.vehicles_to_ship} onChange={(v) => set('vehicles_to_ship', v)}
                        options={['None', '1 car', '2+ cars', 'Motorbike', 'Other']} />
                    </FieldWrap>
                    <FieldWrap label="Important documents to relocate" className="sm:col-span-2">
                      <MultiChip value={profile.important_docs} onChange={(v) => set('important_docs', v)}
                        options={['Diplomas & certificates', 'Medical records', 'Birth certificates', 'Marriage certificate', 'Other']} />
                    </FieldWrap>
                  </Grid>
                </SectionCard>
              </TierGate>
            )}

            {/* ── Section B — Housing prefs ── */}
            {SECTIONS.find((s) => s.id === 'B') && (
              <SectionCard
                id="B" marker="B" title="Destination housing preferences"
                sub="The more you tell us here, the sharper your shortlist."
                state={sectionCompletionState('B', profile, MEMBERS)}
                est={3} unlocks="Housing shortlist with commute + neighborhood scoring"
                expanded={!!expanded.B} onToggle={() => toggle('B')}
                cardRef={(el) => { sectionRefs.current.B = el; }}
              >
                <Grid>
                  <FieldWrap label="Rent or buy?">
                    <SelectField value={profile.intent_rent_or_buy} onChange={(v) => set('intent_rent_or_buy', v)}
                      options={['Rent', 'Buy', 'Not sure yet']} />
                  </FieldWrap>
                  <FieldWrap label="Housing type">
                    <SelectField value={profile.housing_type} onChange={(v) => set('housing_type', v)}
                      options={['Apartment', 'House', 'Either']} />
                  </FieldWrap>
                  <FieldWrap label="Bedrooms" hint={`Auto-suggested ${children.length + 1} based on your household.`}>
                    <Input unstyled type="number" min={1} max={8} value={profile.bedrooms_needed}
                      onChange={(v) => set('bedrooms_needed', Number(v))}
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-300" />
                  </FieldWrap>
                  <FieldWrap label="Monthly housing budget (€/mo)">
                    <div className="flex items-center gap-2">
                      <Input unstyled type="number" placeholder="min" value={profile.monthly_budget_min}
                        onChange={(v) => set('monthly_budget_min', v === '' ? '' : Number(v))}
                        className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-300" />
                      <span className="text-gray-400 text-sm">—</span>
                      <Input unstyled type="number" placeholder="max" value={profile.monthly_budget_max}
                        onChange={(v) => set('monthly_budget_max', v === '' ? '' : Number(v))}
                        className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-300" />
                    </div>
                    {profile.policy_cap && (
                      <div className="text-xs text-accent-700 bg-accent-50 rounded-lg px-3 py-1.5 mt-1">
                        ℹ <strong>Your company covers up to €{profile.policy_cap.toLocaleString()}/month.</strong>
                      </div>
                    )}
                  </FieldWrap>
                  <FieldWrap label="Must-haves (up to 5)" className="sm:col-span-2">
                    <MultiChip
                      value={profile.must_haves}
                      onChange={(v) => v.length <= 5 && set('must_haves', v)}
                      options={['Garden / outdoor space', 'Elevator', 'Parking', 'Accessibility features', 'Pets allowed', 'Quiet neighborhood', 'Close to international school', 'Co-working space']}
                    />
                  </FieldWrap>
                  <div className="sm:col-span-2">
                    <FieldWrap label="Neighborhood priorities" hint="Rate by importance (1–5)">
                      <div className="flex flex-col gap-2 mt-1">
                        {[
                          { id: 'commute' as const,     lbl: 'Short commute to work' },
                          { id: 'intl_school' as const, lbl: 'International school proximity', hidden: !children.length },
                          { id: 'parks' as const,       lbl: 'Nature & parks' },
                          { id: 'expat' as const,       lbl: 'Expat community' },
                          { id: 'nightlife' as const,   lbl: 'Nightlife & culture' },
                          { id: 'safety' as const,      lbl: 'Safety' },
                          { id: 'transit' as const,     lbl: 'Public transit quality' },
                        ].filter((p) => !p.hidden).map((p) => (
                          <div key={p.id} className="flex items-center gap-3">
                            <span className="flex-1 text-xs text-gray-600">{p.lbl}</span>
                            <StarRating
                              value={profile.neighborhood_priorities[p.id] ?? 0}
                              onChange={(v) =>
                                set('neighborhood_priorities', { ...profile.neighborhood_priorities, [p.id]: v })
                              }
                            />
                          </div>
                        ))}
                      </div>
                    </FieldWrap>
                  </div>
                </Grid>
              </SectionCard>
            )}

            {/* ── Section C — Spouse ── */}
            {partner && SECTIONS.find((s) => s.id === 'C') && (
              <SectionCard
                id="C" marker="C" title="Spouse / partner full profile"
                sub={`Building ${partner.name ?? 'your partner'}'s parallel relocation track.`}
                state={sectionCompletionState('C', profile, MEMBERS)}
                est={3} unlocks="Partner immigration milestones + career services"
                expanded={!!expanded.C} onToggle={() => toggle('C')}
                cardRef={(el) => { sectionRefs.current.C = el; }}
              >
                <Grid>
                  <FieldWrap label="Employment status">
                    <SelectField value={profile.spouse_employment} onChange={(v) => set('spouse_employment', v)}
                      options={['', 'Working', 'Self-employed', 'Student', 'Not working']} />
                  </FieldWrap>
                  {(profile.spouse_employment === 'Working' || profile.spouse_employment === 'Self-employed') && (
                    <>
                      <FieldWrap label="Industry / sector">
                        <SelectField value={profile.spouse_sector} onChange={(v) => set('spouse_sector', v)}
                          options={['', 'Technology', 'Finance', 'Legal', 'Healthcare', 'Education', 'Creative', 'Other']} />
                      </FieldWrap>
                      <FieldWrap label="Current contract">
                        <SelectField value={profile.spouse_contract} onChange={(v) => set('spouse_contract', v)}
                          options={['', 'Permanent', 'Fixed-term', 'Freelance']} />
                      </FieldWrap>
                      <FieldWrap label="Resigning to follow you?" why="If their current job is contingent on the move, we surface job-search and career-coaching services earlier.">
                        <SelectField value={profile.spouse_resigning} onChange={(v) => set('spouse_resigning', v)}
                          options={['', 'Yes', 'No', 'Not sure']} />
                      </FieldWrap>
                    </>
                  )}
                  <FieldWrap label="Language level at destination">
                    <SelectField value={profile.spouse_lang_level} onChange={(v) => set('spouse_lang_level', v)}
                      options={['', 'Fluent', 'Conversational', 'Basic', 'Beginner', 'None']} />
                  </FieldWrap>
                  {(profile.spouse_lang_level === 'Basic' || profile.spouse_lang_level === 'Beginner' || profile.spouse_lang_level === 'None') && (
                    <FieldWrap label="Would they like language training?">
                      <SelectField value={profile.spouse_wants_lang} onChange={(v) => set('spouse_wants_lang', v)}
                        options={['', 'Yes', 'No']} />
                    </FieldWrap>
                  )}
                  <FieldWrap label="Right to work at destination?">
                    <SelectField value={profile.spouse_right_to_work} onChange={(v) => set('spouse_right_to_work', v)}
                      options={['', 'Yes', 'No', 'Not sure']} />
                  </FieldWrap>
                  {profile.spouse_right_to_work !== 'Yes' && (
                    <FieldWrap label="Need a dependent visa?">
                      <SelectField value={profile.spouse_needs_dep_visa} onChange={(v) => set('spouse_needs_dep_visa', v)}
                        options={['', 'Yes', 'No', 'Not sure']} />
                    </FieldWrap>
                  )}
                  <FieldWrap label="Professional credentials recognized at destination?" className="sm:col-span-2">
                    <SelectField value={profile.spouse_credentials_ok} onChange={(v) => set('spouse_credentials_ok', v)}
                      options={['', 'Yes', 'No', 'Not sure', 'Not applicable']} />
                  </FieldWrap>
                </Grid>
              </SectionCard>
            )}

            {/* ── Section D — Children ── */}
            {!!children.length && SECTIONS.find((s) => s.id === 'D') && (
              <SectionCard
                id="D" marker="D" title="Children details"
                sub="One card per child. We use this for school search and enrollment timing."
                state={sectionCompletionState('D', profile, MEMBERS)}
                est={2} unlocks="School search + enrollment deadlines"
                urgent urgentReason="Sep 1 enrollment"
                expanded={!!expanded.D} onToggle={() => toggle('D')}
                cardRef={(el) => { sectionRefs.current.D = el; }}
              >
                <div className="flex flex-col gap-4 mt-4">
                  {children.map((child, i) => {
                    const extra = profile.children_extra[child.id] ?? {};
                    const age = computeAge(child.dob);
                    const setExtra = (k: keyof ChildExtra, v: string) =>
                      set('children_extra', { ...profile.children_extra, [child.id]: { ...extra, [k]: v } });
                    return (
                      <div key={child.id} className="border border-gray-100 rounded-xl p-4 bg-teal-50/30">
                        <div className="flex items-center gap-2 mb-3 text-sm font-semibold text-gray-700">
                          <span className="text-base">🧒</span>
                          Child {i + 1} · {child.name ?? `Child ${i + 1}`}
                          {age != null && <span className="text-xs font-normal text-gray-400">({age}y)</span>}
                        </div>
                        <Grid>
                          <FieldWrap label="School type">
                            <SelectField value={extra.school_pref ?? ''} onChange={(v) => setExtra('school_pref', v)}
                              options={['', 'Public', 'Private', 'International', 'Bilingual', 'Not sure yet']} />
                          </FieldWrap>
                          <FieldWrap label="Language of instruction">
                            <SelectField value={extra.lang ?? ''} onChange={(v) => setExtra('lang', v)}
                              options={['', 'Destination country language', 'English', 'French', 'German', 'Spanish', 'Other']} />
                          </FieldWrap>
                          <FieldWrap label="Current curriculum">
                            <SelectField value={extra.curriculum ?? ''} onChange={(v) => setExtra('curriculum', v)}
                              options={['', 'National', 'IB', 'British', 'American', 'French', 'German', 'Other']} />
                          </FieldWrap>
                          <FieldWrap label="Any special educational needs?">
                            <SelectField value={extra.special_needs ?? ''} onChange={(v) => setExtra('special_needs', v)}
                              options={['', 'Yes — tell us more', 'No']} />
                          </FieldWrap>
                        </Grid>
                      </div>
                    );
                  })}
                  <div className="flex items-start gap-2 p-3 bg-blue-50 border border-blue-100 rounded-xl text-xs text-blue-700">
                    <span>ℹ</span>
                    <div>
                      <strong>Roadmap milestone added:</strong> for each child, a <code className="font-mono text-[10px] bg-blue-100 px-1 rounded">school_enrollment_deadline</code> milestone is computed from your contract start date.
                    </div>
                  </div>
                </div>
              </SectionCard>
            )}

            {/* ── Section E — Pets ── */}
            {!!pets.length && SECTIONS.find((s) => s.id === 'E') && (
              <SectionCard
                id="E" marker="E" title="Pet relocation details"
                sub={`Health certs, microchips, quarantine prep for ${pets.length} pet${pets.length > 1 ? 's' : ''}.`}
                state={sectionCompletionState('E', profile, MEMBERS)}
                est={3} unlocks="Pet transport providers + health-cert milestones"
                expanded={!!expanded.E} onToggle={() => toggle('E')}
                cardRef={(el) => { sectionRefs.current.E = el; }}
              >
                <div className="flex flex-col gap-4 mt-4">
                  {pets.map((pet, i) => {
                    const extra = profile.pets_extra[pet.id] ?? {};
                    const setExtra = (k: keyof PetExtra, v: string | number) =>
                      set('pets_extra', { ...profile.pets_extra, [pet.id]: { ...extra, [k]: v } });
                    return (
                      <div key={pet.id} className="border border-gray-100 rounded-xl p-4 bg-amber-50/30">
                        <div className="flex items-center gap-2 mb-3 text-sm font-semibold text-gray-700">
                          <span className="text-base">🐕</span>
                          Pet {i + 1} · {pet.pet_type}{pet.breed ? ` (${pet.breed})` : ''}
                        </div>
                        <Grid>
                          <FieldWrap label="Name" optional>
                            <Input unstyled value={extra.name ?? ''} onChange={(v) => setExtra('name', v)} placeholder="e.g. Hugo"
                              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-300" />
                          </FieldWrap>
                          <FieldWrap label="Age (years)">
                            <Input unstyled type="number" min={0} max={25} value={extra.age ?? ''}
                              onChange={(v) => setExtra('age', Number(v))}
                              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-300" />
                          </FieldWrap>
                          <FieldWrap label="Vaccinations up to date?">
                            <SelectField value={extra.vaccinations_uptodate ?? ''} onChange={(v) => setExtra('vaccinations_uptodate', v)}
                              options={['', 'Yes', 'No']} />
                          </FieldWrap>
                          <FieldWrap label="EU pet passport / health certificate">
                            <select
                              value={extra.eu_pet_passport ?? ''}
                              onChange={(e) => setExtra('eu_pet_passport', e.target.value)}
                              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-300 bg-white"
                            >
                              <option value="">Select…</option>
                              <option value="have">Has one</option>
                              <option value="need">Need to get one</option>
                              <option value="unknown">Don't know</option>
                            </select>
                          </FieldWrap>
                        </Grid>
                      </div>
                    );
                  })}
                </div>
              </SectionCard>
            )}

            {/* ── Section F — Temp housing ── */}
            {SECTIONS.find((s) => s.id === 'F') && (
              <SectionCard
                id="F" marker="F" title="Temporary housing on arrival"
                sub="Where you stay before your permanent home."
                state={sectionCompletionState('F', profile, MEMBERS)}
                est={1} unlocks="Arrival sequence + temp housing providers"
                expanded={!!expanded.F} onToggle={() => toggle('F')}
                cardRef={(el) => { sectionRefs.current.F = el; }}
              >
                <Grid>
                  <FieldWrap label="Need temporary accommodation when you arrive?">
                    <SelectField value={profile.temp_needed} onChange={(v) => set('temp_needed', v)}
                      options={['', 'Yes', 'No', 'Company is arranging it']} />
                  </FieldWrap>
                  {profile.temp_needed === 'Yes' && (
                    <>
                      <FieldWrap label="How long?">
                        <SelectField value={profile.temp_duration} onChange={(v) => set('temp_duration', v)}
                          options={['', '1–2 weeks', 'Up to 1 month', '1–3 months', '3+ months', 'Not sure']} />
                      </FieldWrap>
                      <FieldWrap label="Type preference">
                        <SelectField value={profile.temp_type} onChange={(v) => set('temp_type', v)}
                          options={['', 'Serviced apartment', 'Corporate housing', 'Hotel', 'Extended stay', 'No preference']} />
                      </FieldWrap>
                    </>
                  )}
                </Grid>
              </SectionCard>
            )}

            {/* ── Section G — Financial ── */}
            {SECTIONS.find((s) => s.id === 'G') && (
              <TierGate tier={tier} required="premium" label="financial & tax planning">
                <SectionCard
                  id="G" marker="G" title="Financial & tax context"
                  sub="Surface tax & banking services at the right time."
                  state={sectionCompletionState('G', profile, MEMBERS)}
                  est={2} unlocks="Tax advisor + banking services"
                  expanded={!!expanded.G} onToggle={() => toggle('G')}
                  cardRef={(el) => { sectionRefs.current.G = el; }}
                >
                  <Grid>
                    <FieldWrap label="Will you owe taxes in two countries this year?">
                      <SelectField value={profile.dual_tax} onChange={(v) => set('dual_tax', v)}
                        options={['', 'Yes', 'Possibly', 'No', 'Not sure']} />
                    </FieldWrap>
                    <FieldWrap label="Does your company offer tax equalization?" why="Activates the tax-equalization milestone and brings in a tax advisor automatically.">
                      <SelectField value={profile.has_corporate_tax_support} onChange={(v) => set('has_corporate_tax_support', v)}
                        options={['', 'Yes', 'No', 'Not sure']} />
                    </FieldWrap>
                    <FieldWrap label="Need to open a destination bank account?">
                      <SelectField value={profile.need_bank_account} onChange={(v) => set('need_bank_account', v)}
                        options={['', 'Yes', 'No', 'Company is handling it']} />
                    </FieldWrap>
                    <FieldWrap label="Need to transfer funds internationally?">
                      <SelectField value={profile.need_fx_transfer} onChange={(v) => set('need_fx_transfer', v)}
                        options={['', 'Yes', 'No']} />
                    </FieldWrap>
                    {profile.need_fx_transfer === 'Yes' && (
                      <FieldWrap label="Estimated amount">
                        <SelectField value={profile.fx_amount_range} onChange={(v) => set('fx_amount_range', v)}
                          options={['', '<€10k', '€10k–50k', '€50k–100k', '€100k+']} />
                      </FieldWrap>
                    )}
                  </Grid>
                </SectionCard>
              </TierGate>
            )}

          </div>{/* end main */}
        </div>{/* end two-col */}
      </div>
    </AppShell>
  );
}
