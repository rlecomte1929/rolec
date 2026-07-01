// HrPolicyBuilderV2Page.tsx — Policy Builder canvas + benefit matrix
import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  Sparkles, Check, Eye, Clock, Plus, Filter,
  ChevronDown, ChevronRight, Info, Users, X, Upload,
  Pencil, Activity, Minus, AlertTriangle, MessageSquare,
} from 'lucide-react';
import { Checkbox } from '../../../components/antigravity/Checkbox';
import { Input } from '../../../components/antigravity/Input';
import { AppShell } from '../../../components/AppShell';
import { Button } from '../../../components/antigravity/Button';
import { Alert } from '../../../components/antigravity';
import { Breadcrumb } from '../../../components/Breadcrumb';
import { policyConfigMatrixAPI, policyDocumentsAPI } from '../../../api/client';
import { PolicyAssistantDockedShell } from '../../../features/policy/PolicyAssistantDockedShell';
import { HrPolicyAssistantPanel } from '../../../features/policy/HrPolicyAssistantPanel';
import { HrNoCompanyOnboarding, isNoCompanyError } from '../../../features/policy/hrNoCompanyOnboarding';
import { ConfidenceBadge } from '../roadmap/ConfidenceBadge';
import type { ConfidenceLevel } from '../roadmap/confidence.tokens';
import { trackPolicyPublished } from '../../../perf/hrOnboardingInstrumentation';
import { canvasPolicyToConfigDraft, type CanvasMapResult } from './canvasPolicyToConfigDraft';
import { configDraftToCanvasPolicy } from './configDraftToCanvasPolicy';

// ─── Types ────────────────────────────────────────────────────────────────────
type BenefitValueType = 'currency' | 'percentage' | 'text' | 'none';
type Freq = 'one_time' | 'monthly' | 'yearly' | 'per_trip' | 'per_dependent';
type LumpInc = 'included' | 'optional' | 'excluded';
type AssignmentMode = 'lump' | 'caps';

interface BenefitValue {
  covered: boolean;
  value_type: BenefitValueType;
  amount: number;
  freq: Freq;
  lump_inc: LumpInc | null;
  cap: boolean;
  conditions: boolean;
  // Provenance + extraction confidence (AIQ-991) — only set on AI-extracted rows
  // loaded from the config-matrix; used to badge confidence in the matrix cell.
  source?: string | null;
  field_confidence?: number | null;
}

interface Targeting {
  level: string[];
  type: string[];
  family: string[];
}

interface Tier {
  id: string;
  name: string;
  color: string;
  targeting: Targeting;
  mode: AssignmentMode;
  lump: number;
  emp: number;
  benefits: Record<string, BenefitValue>;
}

interface BenefitDef { k: string; lbl: string; tip: string }
interface CategoryDef { id: number; key: string; t: string; benefits: BenefitDef[] }

// ─── Constants ────────────────────────────────────────────────────────────────
const CATEGORIES: CategoryDef[] = [
  { id: 1, key: 'pre_assignment', t: 'Pre-assignment support', benefits: [
    { k: 'visa_work_permit_assistance', lbl: 'Visa & work permit assistance', tip: 'Application fees, legal support, document gathering.' },
    { k: 'medical_exam_reimbursement',  lbl: 'Medical exam reimbursement',    tip: 'Required by some destinations as part of visa.' },
    { k: 'pre_assignment_visit',        lbl: 'Pre-assignment visit',          tip: 'Scouting trip for housing, schools, neighborhoods.' },
    { k: 'cultural_training',           lbl: 'Cultural & intercultural training', tip: 'Briefings on workplace culture, customs, language norms.' },
    { k: 'language_training',           lbl: 'Language training',              tip: 'Lessons for the employee and/or family.' },
  ]},
  { id: 2, key: 'relocation', t: 'Relocation assistance', benefits: [
    { k: 'relocation_allowance_assignee_partner', lbl: 'Relocation allowance (assignee + partner)', tip: 'One-off lump sum for misc relocation costs.' },
    { k: 'relocation_allowance_dependent',        lbl: 'Relocation allowance (per dependent)',     tip: 'Per child/dependent additional allowance.' },
    { k: 'removal_expenses',                      lbl: 'Removal & shipping expenses',               tip: 'Movers, packing, customs.' },
    { k: 'shipment_of_goods',                     lbl: 'Shipment of personal goods',                tip: 'Container or air-freight of household effects.' },
    { k: 'storage',                               lbl: 'Storage (temporary)',                       tip: 'Storage between origin departure and host arrival.' },
    { k: 'temporary_living',                      lbl: 'Temporary living accommodation',            tip: 'Serviced apartment / hotel while finding permanent.' },
    { k: 'settling_in_services',                  lbl: 'Settling-in services',                      tip: 'Local registration, utilities, bank, school admin.' },
  ]},
  { id: 3, key: 'compensation', t: 'Compensation & allowances', benefits: [
    { k: 'mobility_premium',           lbl: 'Mobility premium',                tip: 'Bonus for accepting the assignment.' },
    { k: 'location_allowance',         lbl: 'Location / hardship allowance',   tip: 'Extra pay for difficult or expensive destinations.' },
    { k: 'living_allowance',           lbl: 'Cost-of-living allowance',        tip: 'Compensates for cost-of-living differences.' },
    { k: 'cola',                       lbl: 'COLA (Cost of living adjustment)', tip: 'Index-linked recurring allowance.' },
    { k: 'host_housing_cap',           lbl: 'Host country housing cap',         tip: 'Monthly housing budget at destination.' },
    { k: 'host_transportation',        lbl: 'Host country transportation',      tip: 'Car lease, commute card, etc.' },
    { k: 'driving_test_reimbursement', lbl: 'Driving test reimbursement',       tip: 'If a local license is required.' },
    { k: 'dual_career_support',        lbl: 'Dual-career support',              tip: 'Partner job search, coaching, networking.' },
  ]},
  { id: 4, key: 'family', t: 'Family support & education', benefits: [
    { k: 'spouse_partner_assistance', lbl: 'Spouse / partner assistance', tip: 'Career counseling, language, networking.' },
    { k: 'child_education_support',   lbl: 'Child education support',     tip: 'School fees, enrollment, tutoring.' },
  ]},
  { id: 5, key: 'leave', t: 'Leave & repatriation', benefits: [
    { k: 'home_leave_trips',                       lbl: 'Home leave trips',                           tip: 'Annual trips back to origin country.' },
    { k: 'extra_holiday_days',                     lbl: 'Extra holiday days',                          tip: 'Additional PTO for relocated employees.' },
    { k: 'repatriation_allowance_assignee_partner', lbl: 'Repatriation allowance (assignee + partner)', tip: 'End-of-assignment lump sum.' },
    { k: 'repatriation_allowance_dependent',        lbl: 'Repatriation allowance (per dependent)',      tip: 'Per dependent return.' },
    { k: 'return_shipment_travel',                  lbl: 'Return shipment & travel',                    tip: 'Shipping goods and travel back.' },
  ]},
  { id: 6, key: 'tax', t: 'Tax & payroll', benefits: [
    { k: 'tax_equalisation',       lbl: 'Tax equalisation',         tip: 'Company covers any extra tax burden from the move.' },
    { k: 'payroll_structure',      lbl: 'Payroll structure',         tip: 'Split payroll, host country payment.' },
    { k: 'banking_assistance',     lbl: 'Banking setup assistance',  tip: 'Open a local bank account.' },
    { k: 'tax_return_preparation', lbl: 'Tax return preparation',    tip: 'Annual filing in one or both jurisdictions.' },
  ]},
];

const TIER_PALETTE = ['#2962ff', '#1f8e8b', '#7a4ea3', '#c2761a', '#16a34a'];
const CUR_SYM: Record<string, string> = { EUR: '€', USD: '$', GBP: '£', CHF: 'CHF' };

const TEMPLATES = [
  { id: 'standard',   ico: '🌐', t: 'Standard global mobility', s: 'Three tiers (Manager / Director / VP). Permanent transfers + long-term assignments. Most-used baseline.', tiers: ['Manager', 'Director', 'VP'] },
  { id: 'tech',       ico: '💻', t: 'Tech / startup',           s: 'Two flexible tiers (IC / Senior IC). Lean on lump-sum budgets. Generous remote.', tiers: ['Engineer', 'Senior Eng'] },
  { id: 'banking',    ico: '🏦', t: 'Banking & finance',        s: 'Four tiers including C-Suite. Hardship allowances + tax equalisation enabled by default.', tiers: ['Manager', 'Director', 'MD', 'C-Suite'] },
  { id: 'short_term', ico: '✈️', t: 'Short-term focused',       s: 'Built around 3-12mo assignments. Generous temp living, limited household shipping.', tiers: ['Standard', 'Senior'] },
];

const FREQ_OPTS: { v: Freq; l: string }[] = [
  { v: 'one_time', l: 'ONE-TIME' },
  { v: 'monthly',  l: '/ MO' },
  { v: 'yearly',   l: '/ YR' },
  { v: 'per_trip', l: '/ TRIP' },
  { v: 'per_dependent', l: '/ DEP' },
];
const VAL_OPTS: { v: BenefitValueType; l: string }[] = [
  { v: 'currency',   l: '€' },
  { v: 'percentage', l: '%' },
  { v: 'text',       l: 'TXT' },
  { v: 'none',       l: '—' },
];

const LEVEL_LBL: Record<string, string> = { entry: 'Entry', manager: 'Manager', director: 'Director', vp: 'VP', c_suite: 'C-Suite' };
const TYPE_LBL: Record<string, string>  = { long_term: 'Long-term', short_term: 'Short-term', permanent: 'Permanent', commuter: 'Commuter', extended_business_trip: 'Ext. business trip' };
const FAMILY_LBL: Record<string, string> = { single: 'Single', married: 'Married', accompanied_family: 'With family' };

// ─── Helpers ──────────────────────────────────────────────────────────────────
function buildDefaultBenefits(tierName: string, lumpMode: boolean): Record<string, BenefitValue> {
  const isSr   = /Director|VP|MD|C-Suite|Senior/.test(tierName);
  const isExec = /VP|MD|C-Suite/.test(tierName);
  const out: Record<string, BenefitValue> = {};
  CATEGORIES.forEach(cat => {
    cat.benefits.forEach(b => {
      let covered = true;
      let value_type: BenefitValueType = 'currency';
      let amount = 0;
      let freq: Freq = 'one_time';
      switch (b.k) {
        case 'visa_work_permit_assistance':           covered = true; value_type = 'none'; break;
        case 'medical_exam_reimbursement':             amount = 200; break;
        case 'pre_assignment_visit':                   covered = isSr; amount = isSr ? 3000 : 0; break;
        case 'cultural_training':                      covered = true; amount = 800; break;
        case 'language_training':                      covered = true; amount = 1500; freq = 'yearly'; break;
        case 'relocation_allowance_assignee_partner':  amount = isExec ? 12000 : isSr ? 8000 : 5000; break;
        case 'relocation_allowance_dependent':         amount = 2500; freq = 'per_dependent'; break;
        case 'removal_expenses':                       amount = isSr ? 10000 : 7000; break;
        case 'shipment_of_goods':                      amount = isExec ? 15000 : isSr ? 10000 : 6000; break;
        case 'storage':                                covered = isSr; amount = 2400; freq = 'monthly'; break;
        case 'temporary_living':                       amount = isExec ? 5000 : 2800; freq = 'monthly'; break;
        case 'settling_in_services':                   covered = true; amount = 2400; break;
        case 'mobility_premium':                       covered = isSr; amount = isExec ? 25 : 15; value_type = 'percentage'; break;
        case 'location_allowance':                     covered = isSr; amount = isExec ? 15 : 8; value_type = 'percentage'; break;
        case 'living_allowance':                       covered = false; break;
        case 'cola':                                   covered = isExec; amount = 10; value_type = 'percentage'; freq = 'monthly'; break;
        case 'host_housing_cap':                       amount = isExec ? 5500 : isSr ? 3800 : 2400; freq = 'monthly'; break;
        case 'host_transportation':                    amount = isExec ? 1200 : isSr ? 800 : 0; covered = isSr; freq = 'monthly'; break;
        case 'driving_test_reimbursement':             amount = 300; break;
        case 'dual_career_support':                    covered = isSr; amount = 3500; break;
        case 'spouse_partner_assistance':              covered = isSr; amount = 2000; break;
        case 'child_education_support':                covered = isSr; amount = isExec ? 18000 : 12000; freq = 'yearly'; break;
        case 'home_leave_trips':                       amount = isExec ? 4 : 2; value_type = 'text'; freq = 'yearly'; break;
        case 'extra_holiday_days':                     amount = isExec ? 10 : 5; value_type = 'text'; freq = 'yearly'; break;
        case 'repatriation_allowance_assignee_partner': amount = 5000; break;
        case 'repatriation_allowance_dependent':        amount = 2000; freq = 'per_dependent'; break;
        case 'return_shipment_travel':                 amount = 8000; break;
        case 'tax_equalisation':                       covered = isSr; value_type = 'none'; break;
        case 'payroll_structure':                      covered = true; value_type = 'none'; break;
        case 'banking_assistance':                     covered = true; value_type = 'none'; break;
        case 'tax_return_preparation':                 covered = isSr; value_type = 'none'; break;
        default:                                       amount = 1000;
      }
      const capKeys = ['host_housing_cap','child_education_support','temporary_living','storage'];
      const condKeys = ['relocation_allowance_dependent','repatriation_allowance_dependent'];
      out[b.k] = { covered, value_type, amount, freq,
        lump_inc: lumpMode ? (covered ? 'included' : 'excluded') : null,
        cap: capKeys.includes(b.k),
        conditions: condKeys.includes(b.k) };
    });
  });
  return out;
}

function tiersForTemplate(tplId: string): Tier[] {
  const tpls: Record<string, Omit<Tier, 'id' | 'benefits'>[]> = {
    standard: [
      { name: 'Manager',  color: TIER_PALETTE[0] ?? '', targeting: { level: ['manager'],  type: ['long_term','permanent'], family: ['single','married','accompanied_family'] }, mode: 'caps', lump: 14000, emp: 8 },
      { name: 'Director', color: TIER_PALETTE[1] ?? '', targeting: { level: ['director'], type: ['long_term','permanent'], family: ['single','married','accompanied_family'] }, mode: 'caps', lump: 28000, emp: 4 },
      { name: 'VP',       color: TIER_PALETTE[2] ?? '', targeting: { level: ['vp'],       type: ['long_term','permanent'], family: ['single','married','accompanied_family'] }, mode: 'lump', lump: 68000, emp: 2 },
    ],
    tech: [
      { name: 'Engineer',   color: TIER_PALETTE[0] ?? '', targeting: { level: ['entry','manager'], type: ['long_term','permanent'], family: ['single','married','accompanied_family'] }, mode: 'lump', lump: 18000, emp: 12 },
      { name: 'Senior Eng', color: TIER_PALETTE[1] ?? '', targeting: { level: ['director'],        type: ['long_term','permanent'], family: ['single','married','accompanied_family'] }, mode: 'lump', lump: 38000, emp: 5 },
    ],
    banking: [
      { name: 'Manager',  color: TIER_PALETTE[0] ?? '', targeting: { level: ['manager'],  type: ['long_term'],  family: ['single','married','accompanied_family'] }, mode: 'caps', lump: 18000, emp: 14 },
      { name: 'Director', color: TIER_PALETTE[1] ?? '', targeting: { level: ['director'], type: ['long_term'],  family: ['single','married','accompanied_family'] }, mode: 'caps', lump: 38000, emp: 6 },
      { name: 'MD',       color: TIER_PALETTE[2] ?? '', targeting: { level: ['vp'],       type: ['long_term'],  family: ['single','married','accompanied_family'] }, mode: 'caps', lump: 72000, emp: 3 },
      { name: 'C-Suite',  color: TIER_PALETTE[3] ?? '', targeting: { level: ['c_suite'],  type: ['long_term','permanent'], family: ['single','married','accompanied_family'] }, mode: 'lump', lump: 120000, emp: 1 },
    ],
    short_term: [
      { name: 'Standard', color: TIER_PALETTE[0] ?? '', targeting: { level: ['manager'],  type: ['short_term','extended_business_trip'], family: ['single','married'] }, mode: 'caps', lump: 12000, emp: 6 },
      { name: 'Senior',   color: TIER_PALETTE[1] ?? '', targeting: { level: ['director'], type: ['short_term','extended_business_trip'], family: ['single','married'] }, mode: 'caps', lump: 22000, emp: 3 },
    ],
  };
  const arr = tpls[tplId] ?? tpls.standard ?? [];
  return arr.map((t, i) => ({ ...t, id: `t${i}-${Date.now()}`, benefits: buildDefaultBenefits(t.name, t.mode === 'lump') }));
}

function targetingSummary(tg: Targeting): string {
  const parts: string[] = [];
  if (tg.level?.length) parts.push(tg.level.map(l => LEVEL_LBL[l]).join('/'));
  if (tg.type?.length)  parts.push(tg.type.map(t => TYPE_LBL[t]).join('/'));
  if (tg.family?.length === 3) parts.push('Any family');
  else if (tg.family?.length) parts.push(tg.family.map(f => FAMILY_LBL[f]).join('/'));
  return parts.join(' · ') || 'No rules set';
}

function timeAgo(ts: number): string {
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 5) return 'just now';
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

// ─── Main page ────────────────────────────────────────────────────────────────
export function HrPolicyBuilderV2Page({ embedded = false }: { embedded?: boolean } = {}) {
  const [tiers, setTiers]             = useState<Tier[]>([]);
  const [mode, setMode]               = useState<'template' | 'document'>('template');
  const [templateOpen, setTemplateOpen] = useState(false);
  const [importOpen, setImportOpen]   = useState(false);
  const [collapsed, setCollapsed]     = useState<Record<number, boolean>>({});
  const [rulesDrawerFor, setRulesDrawerFor] = useState<string | null>(null);
  const [savedAt, setSavedAt]         = useState<number | null>(null);
  const [version, setVersion]         = useState<string | null>(null);
  const [loadingDraft, setLoadingDraft] = useState(true);
  const [noCompany, setNoCompany] = useState(false);  // [T2.4] HR not linked to a company yet
  const [ctxOpen, setCtxOpen]         = useState(false);
  const [currency, setCurrency]       = useState('EUR');
  const [focusedBenefit]              = useState('host_housing_cap');
  const [focusedTierId]               = useState<string | null>(null);

  // ── Persistence / publish wiring (policy_config matrix system) ──
  const [draftVersionId, setDraftVersionId] = useState<string | null>(null);
  const [effectiveDate, setEffectiveDate]   = useState<string>(() => new Date().toISOString().slice(0, 10));
  const [saving, setSaving]           = useState(false);
  const [publishing, setPublishing]   = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [banner, setBanner]           = useState<{ kind: 'success' | 'error' | 'info'; msg: string } | null>(null);

  const errMsg = (e: unknown, fallback: string): string => {
    const data = e && typeof e === 'object' && 'response' in e
      ? (e as { response?: { data?: { detail?: unknown; message?: string } } }).response?.data
      : null;
    const detail = data?.detail;
    if (typeof detail === 'string') return detail;
    if (data?.message) return data.message;
    if (e instanceof Error) return e.message;
    return fallback;
  };

  // On mount, load the company's existing config-matrix draft/published policy
  // (GET /api/hr/policy-config) and reconstruct the canvas tiers from it, so HR
  // sees their real policy instead of a blank template. A company with no policy
  // yet returns an empty scaffold (no rows) → tiers stay [] and the template
  // picker shows as before.
  useEffect(() => {
    let alive = true;
    void (async () => {
      try {
        const payload = (await policyConfigMatrixAPI.hrGet()) as {
          policy_version?: string | null;
          status?: string | null;
          categories?: unknown;
        };
        const { tiers: loaded } = configDraftToCanvasPolicy(payload as never);
        if (!alive || loaded.length === 0) return;
        const fullTiers: Tier[] = loaded.map((lt, i) => ({
          id: `loaded-${i}`,
          name: lt.name,
          color: TIER_PALETTE[i % TIER_PALETTE.length] ?? '',
          targeting: lt.targeting,
          mode: lt.mode,
          lump: lt.lump,
          emp: 0,
          // Loaded rows are the source of truth; the default scaffold only fills
          // any catalog key the payload happens to omit so every benefit renders.
          benefits: { ...buildDefaultBenefits(lt.name, lt.mode === 'lump'), ...lt.benefits },
        }));
        setTiers(fullTiers);
        const status = String(payload.status || '');
        if (status === 'published') {
          setVersion('published');
        } else if (payload.policy_version) {
          setDraftVersionId(payload.policy_version);
        }
        setSavedAt(Date.now());
      } catch (e) {
        // [T2.4] 403 = HR not linked to a company → show onboarding, not a blank
        // template the user can't actually save. Other errors are non-fatal here
        // (fall back to the template flow, tiers stay []).
        if (isNoCompanyError(e) && alive) setNoCompany(true);
      } finally {
        if (alive) setLoadingDraft(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  // Ensure a policy_config draft exists, returning its version id.
  const ensureDraftId = async (): Promise<string> => {
    if (draftVersionId) return draftVersionId;
    const draft = await policyConfigMatrixAPI.hrPostDraft();
    const pv = (draft?.policy_version as string | null) || null;
    if (!pv) throw new Error('Could not create a draft (no policy_version returned).');
    setDraftVersionId(pv);
    return pv;
  };

  // Re-read the company's config-matrix draft and rebuild the canvas tiers from
  // it. Used after a document import merges extracted benefits into the draft, so
  // the canvas reflects the REAL imported rows (notes + field_confidence ride
  // through). Mirrors the on-mount hydration; non-fatal on error.
  const reloadFromDraft = async () => {
    try {
      const payload = (await policyConfigMatrixAPI.hrGet()) as {
        policy_version?: string | null;
        status?: string | null;
        categories?: unknown;
      };
      const { tiers: loaded } = configDraftToCanvasPolicy(payload as never);
      if (loaded.length === 0) return;
      const fullTiers: Tier[] = loaded.map((lt, i) => ({
        id: `loaded-${i}`,
        name: lt.name,
        color: TIER_PALETTE[i % TIER_PALETTE.length] ?? '',
        targeting: lt.targeting,
        mode: lt.mode,
        lump: lt.lump,
        emp: 0,
        benefits: { ...buildDefaultBenefits(lt.name, lt.mode === 'lump'), ...lt.benefits },
      }));
      setTiers(fullTiers);
      const status = String(payload.status || '');
      if (status === 'published') setVersion('published');
      else if (payload.policy_version) setDraftVersionId(payload.policy_version);
      setSavedAt(Date.now());
    } catch {
      // Non-fatal: the import already merged server-side; a reload hiccup just
      // means the canvas won't refresh until the next load.
    }
  };

  const handleSaveDraft = async () => {
    if (tiers.length === 0) { setBanner({ kind: 'info', msg: 'Add at least one tier first.' }); return; }
    setSaving(true); setBanner(null);
    try {
      const pv = await ensureDraftId();
      const { body, rowCount, warnings } = canvasPolicyToConfigDraft({ tiers, categories: CATEGORIES, effectiveDate, currency, policyVersion: pv });
      if (rowCount === 0) { setBanner({ kind: 'info', msg: 'No covered benefits yet — mark some benefits as covered, then save.' }); return; }
      await policyConfigMatrixAPI.hrPutDraft(body);
      setSavedAt(Date.now());
      setVersion(null); // back to draft state after edits
      setBanner({ kind: 'success', msg: `Draft saved — ${rowCount} benefit row(s)${warnings.length ? ` · ${warnings.length} mapping note(s)` : ''}.` });
    } catch (e) {
      setBanner({ kind: 'error', msg: errMsg(e, 'Save failed.') });
    } finally { setSaving(false); }
  };

  const handlePublish = async () => {
    if (tiers.length === 0) return;
    setPublishing(true); setBanner(null);
    try {
      const pv = await ensureDraftId();
      const { body, rowCount } = canvasPolicyToConfigDraft({ tiers, categories: CATEGORIES, effectiveDate, currency, policyVersion: pv });
      if (rowCount === 0) { setBanner({ kind: 'info', msg: 'Add at least one covered benefit before publishing.' }); return; }
      await policyConfigMatrixAPI.hrPutDraft(body);
      await policyConfigMatrixAPI.hrPublish({ policy_version: pv });
      // AIQ-1223b: HR onboarding signal — publish reveals policy tier count.
      // PII-free: counts only.
      trackPolicyPublished({ tier_count: tiers.length, benefit_row_count: rowCount });
      setVersion('published');
      setSavedAt(Date.now());
      setDraftVersionId(null); // next edit starts a fresh draft
      setBanner({ kind: 'success', msg: 'Published. Employees can now see this policy, and the Policy Assistant can answer about it.' });
    } catch (e) {
      setBanner({ kind: 'error', msg: errMsg(e, 'Publish failed.') });
    } finally { setPublishing(false); }
  };

  const previewResult = useMemo(
    () => canvasPolicyToConfigDraft({ tiers, categories: CATEGORIES, effectiveDate, currency, policyVersion: 'preview' }),
    [tiers, effectiveDate, currency],
  );

  const applyTemplate = (tpl: typeof TEMPLATES[0]) => {
    setTiers(tiersForTemplate(tpl.id));
    setTemplateOpen(false);
    setSavedAt(Date.now());
  };

  const addTier = () => {
    const id = `t-${Date.now()}`;
    const idx = tiers.length;
    setTiers(prev => [...prev, {
      id, name: `Tier ${idx + 1}`, color: TIER_PALETTE[idx % TIER_PALETTE.length] ?? '',
      targeting: { level: [], type: [], family: [] }, mode: 'caps', lump: 10000, emp: 0,
      benefits: buildDefaultBenefits(`Tier ${idx + 1}`, false),
    }]);
  };
  const updateTier = (id: string, next: Partial<Tier>) =>
    setTiers(ts => ts.map(t => t.id === id ? { ...t, ...next } : t));
  const updateBenefit = (tierId: string, bKey: string, patch: Partial<BenefitValue>) =>
    setTiers(ts => ts.map(t => {
      if (t.id !== tierId) return t;
      const existing = t.benefits[bKey];
      if (!existing) return t;
      return { ...t, benefits: { ...t.benefits, [bKey]: { ...existing, ...patch } } };
    }));

  useEffect(() => {
    if (tiers.length === 0) return;
    const tm = setTimeout(() => setSavedAt(Date.now()), 1200);
    return () => clearTimeout(tm);
  }, [tiers]);

  const status = tiers.length === 0 ? 'no-policy' : version ? 'published' : 'draft';
  const statusColour = status === 'draft' ? 'bg-amber-100 text-amber-700' : status === 'published' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500';
  const statusLbl = status === 'no-policy' ? 'No policy yet' : status === 'draft' ? 'Draft' : 'Published';

  // When embedded as a tab inside another AppShell (e.g. HrPolicy.tsx), we
  // skip the outer AppShell and Breadcrumb to avoid double-shell nesting.
  const inner = (
    <>
      {!embedded && <Breadcrumb section="HR Operations" title="Policy builder" className="px-6 pt-4 pb-2" />}
      {/* ── Header — two-row layout so content never overflows ── */}
      <div className="sticky top-0 z-20 bg-white border-b border-gray-200">
        {/* Row 1: title + primary publish actions */}
        <div className="flex items-center gap-3 px-6 pt-2.5 pb-1.5">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <h1 className="text-[14px] font-semibold text-gray-900 leading-none whitespace-nowrap">Policy Builder</h1>
            <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full shrink-0 ${statusColour}`}>{statusLbl}</span>
            {version && <span className="text-[11px] text-gray-400 font-mono truncate">{version}</span>}
            {savedAt && (
              <span className="text-[11px] text-gray-400 flex items-center gap-1 shrink-0">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500"/>
                Saved {timeAgo(savedAt)}
              </span>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Button unstyled onClick={handleSaveDraft} disabled={saving || tiers.length === 0}
              className="text-[12px] px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-40">
              {saving ? 'Saving…' : 'Save draft'}
            </Button>
            <Button unstyled onClick={() => setPreviewOpen(true)} disabled={tiers.length === 0}
              className="text-[12px] px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-40 flex items-center gap-1.5">
              <Eye size={12}/> Preview
            </Button>
            <Button unstyled onClick={handlePublish} disabled={publishing || tiers.length === 0}
              className="text-[12px] px-3 py-1.5 rounded-lg bg-navy-800 text-white font-semibold hover:bg-navy-900 disabled:opacity-40 flex items-center gap-1.5">
              <Check size={12}/> {publishing ? 'Publishing…' : 'Publish'}
            </Button>
          </div>
        </div>
        {/* Row 2: source toggle + currency + secondary tools */}
        <div className="flex items-center gap-3 px-6 pb-2">
          {/* mode tabs */}
          <div className="flex rounded-lg border border-gray-200 overflow-hidden text-[12px] font-medium shrink-0">
            <Button unstyled onClick={() => setMode('template')}
              className={`px-3 py-1 transition-colors ${mode === 'template' ? 'bg-gray-900 text-white' : 'text-gray-500 hover:text-gray-700'}`}>
              Build from template
            </Button>
            <Button unstyled onClick={() => setImportOpen(true)}
              className={`px-3 py-1 transition-colors border-l border-gray-200 ${mode === 'document' ? 'bg-gray-900 text-white' : 'text-gray-500 hover:text-gray-700'}`}>
              Import from document
            </Button>
          </div>
          {/* currency */}
          <div className="flex shrink-0 items-center gap-1.5 text-[12px] text-gray-500">
            <span className="font-semibold text-gray-700">{CUR_SYM[currency]}</span>
            <select value={currency} onChange={e => setCurrency(e.target.value)}
              className="border border-gray-200 rounded px-2 py-1 text-[12px] bg-white focus:outline-none">
              <option value="EUR">EUR (€)</option>
              <option value="USD">USD ($)</option>
              <option value="GBP">GBP (£)</option>
              <option value="CHF">CHF</option>
            </select>
          </div>
          <div className="flex shrink-0 items-center gap-2 ml-auto">
            <Button unstyled onClick={() => setAssistantOpen(o => !o)}
              className={`flex items-center gap-1.5 text-[12px] px-3 py-1 rounded-lg border transition-colors font-medium ${assistantOpen ? 'bg-blue-600 text-white border-blue-600' : 'border-gray-200 text-gray-600 hover:border-blue-400 hover:text-blue-600'}`}>
              <MessageSquare size={12}/> Ask about this policy
            </Button>
            <Button unstyled onClick={() => setCtxOpen(o => !o)}
              className={`flex items-center gap-1.5 text-[12px] px-3 py-1 rounded-lg border transition-colors font-medium ${ctxOpen ? 'bg-blue-600 text-white border-blue-600' : 'border-gray-200 text-gray-600 hover:border-blue-400 hover:text-blue-600'}`}>
              <Activity size={12}/> {ctxOpen ? 'Context on' : 'Context'}
            </Button>
            {/* Effective date — required by the publish pipeline */}
            <label className="flex items-center gap-1.5 text-[11px] text-gray-500 shrink-0">
              <Clock size={12} className="text-gray-400"/>
              <input type="date" value={effectiveDate} onChange={e => setEffectiveDate(e.target.value)}
                title="Effective date"
                className="border border-gray-200 rounded px-2 py-1 text-[11px] bg-white focus:outline-none"/>
            </label>
          </div>
        </div>
      </div>

      {banner && (
        <div className="px-6 pt-3">
          <Alert variant={banner.kind}>{banner.msg}</Alert>
        </div>
      )}

      {/* ── Loading the company's existing policy (avoids a template-picker flash) ── */}
      {loadingDraft && tiers.length === 0 && (
        <div className="flex flex-col items-center justify-center py-24 gap-3 text-center text-gray-400">
          <Clock size={20} className="animate-pulse"/>
          <p className="text-sm">Loading your policy…</p>
        </div>
      )}

      {/* ── Empty state — template ── */}
      {!loadingDraft && mode === 'template' && tiers.length === 0 && (
        <div className="flex flex-col items-center justify-center py-24 gap-4 text-center">
          <h2 className="text-xl font-semibold text-gray-900">No tiers yet</h2>
          <p className="text-sm text-gray-500 max-w-sm">Start from a template to get set up in minutes, or build a custom tier structure from scratch.</p>
          <div className="flex gap-3 mt-2">
            <Button unstyled onClick={() => setTemplateOpen(true)}
              className="flex items-center gap-2 px-4 py-2 bg-navy-800 text-white rounded-lg text-sm font-semibold hover:bg-navy-900">
              <Sparkles size={14}/> Start from a template
            </Button>
            <Button unstyled onClick={addTier}
              className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50">
              <Plus size={14}/> Add a tier
            </Button>
          </div>
        </div>
      )}

      {/* ── Empty state — document ── */}
      {!loadingDraft && mode === 'document' && tiers.length === 0 && (
        <div className="flex flex-col items-center justify-center py-24 gap-4 text-center">
          <svg viewBox="0 0 96 96" width={96} height={96}>
            <path d="M20 14h40l20 20v48H20z" fill="#dbeafe" stroke="#3b82f6" strokeWidth="1.5"/>
            <path d="M60 14v20h20" fill="none" stroke="#3b82f6" strokeWidth="1.5"/>
            <path d="M34 50h28M34 60h28M34 70h20" stroke="#3b82f6" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <h2 className="text-xl font-semibold text-gray-900">Upload your existing policy document</h2>
          <p className="text-sm text-gray-500 max-w-sm">PDF or Word. Our AI extracts benefits, caps, and conditions, then you review and apply to the canvas.</p>
          <div className="flex gap-3 mt-2">
            <Button unstyled onClick={() => setImportOpen(true)}
              className="flex items-center gap-2 px-4 py-2 bg-navy-800 text-white rounded-lg text-sm font-semibold hover:bg-navy-900">
              <Upload size={14}/> Choose file
            </Button>
            <Button unstyled onClick={() => setMode('template')}
              className="px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50">
              Use a template instead
            </Button>
          </div>
        </div>
      )}

      {/* ── Canvas ── */}
      {tiers.length > 0 && (
        <div className={`flex min-h-0 ${ctxOpen ? 'pr-[300px]' : ''}`}>
          <div className="flex overflow-x-auto flex-1">
            {/* Sidebar */}
            <div className="w-[272px] flex-shrink-0 sticky left-0 z-10 bg-white border-r border-gray-200">
              {/* AIQ-1108: spacer matches the TierColumn header height (h-[168px])
                  so each benefit label below aligns with its tier-cell row. */}
              <div className="h-[168px] border-b border-gray-200 bg-white" aria-hidden="true" />
              {CATEGORIES.map(cat => {
                const isCol = collapsed[cat.id];
                return (
                  <div key={cat.id}>
                    {/* category header */}
                    <div
                      role="button"
                      tabIndex={0}
                      className="h-[41px] flex items-center gap-2 px-4 bg-gray-50 border-b border-gray-200 cursor-pointer select-none"
                      onClick={() => setCollapsed(c => ({ ...c, [cat.id]: !c[cat.id] }))}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setCollapsed(c => ({ ...c, [cat.id]: !c[cat.id] })); } }}>
                      {isCol ? <ChevronRight size={12} className="text-gray-400 flex-shrink-0"/> : <ChevronDown size={12} className="text-gray-400 flex-shrink-0"/>}
                      <span className="text-[11.5px] font-semibold text-gray-700 flex-1 truncate">{cat.t}</span>
                      <span className="text-[10px] text-gray-400 font-medium bg-gray-200 px-1.5 py-0.5 rounded-full">{cat.benefits.length}</span>
                    </div>
                    {!isCol && cat.benefits.map(b => (
                      <div key={b.k} className="h-9 flex items-center gap-2 px-4 border-b border-gray-100 group">
                        <Info size={11} className="text-gray-300 flex-shrink-0 group-hover:text-gray-400" aria-label={b.tip}/>
                        <span className="text-[11.5px] text-gray-600 truncate" title={b.lbl}>{b.lbl}</span>
                      </div>
                    ))}
                    {!isCol && (
                      <div className="h-9 flex items-center px-4 border-b border-gray-100">
                        <span className="text-[11px] text-blue-500 hover:text-blue-700 cursor-pointer">+ Add custom benefit</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Tier columns */}
            <div className="flex flex-1">
              {tiers.map(tier => {
                const maxTotal = Math.max(...tiers.map(t => t.lump || 0)) || 1;
                return (
                  <TierColumn
                    key={tier.id}
                    tier={tier}
                    categories={CATEGORIES}
                    collapsed={collapsed}
                    currency={currency}
                    onRename={name => updateTier(tier.id, { name })}
                    onModeChange={m => updateTier(tier.id, { mode: m })}
                    onLumpChange={v => updateTier(tier.id, { lump: v })}
                    onOpenRules={() => setRulesDrawerFor(tier.id)}
                    onBenefitChange={(bKey, patch) => updateBenefit(tier.id, bKey, patch)}
                    maxTotal={maxTotal}
                  />
                );
              })}
              {/* Add tier */}
              <div
                role="button"
                tabIndex={0}
                onClick={addTier}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); addTier(); } }}
                className="w-[52px] flex-shrink-0 flex items-center justify-center border-l border-gray-200 cursor-pointer hover:bg-blue-50 transition-colors group">
                <div className="flex flex-col items-center gap-1 text-gray-400 group-hover:text-blue-600">
                  <Plus size={18}/>
                  <span className="text-[10px] font-medium" style={{ writingMode: 'vertical-rl' }}>Add tier</span>
                </div>
              </div>
            </div>
          </div>

          {/* Context sidebar */}
          {ctxOpen && (
            <div className="fixed right-0 top-0 bottom-0 w-[300px] bg-white border-l border-gray-200 z-30 overflow-y-auto">
              <ContextSidebar
                focusedBenefit={focusedBenefit}
                focusedTier={focusedTierId ? tiers.find(t => t.id === focusedTierId) ?? tiers[0] ?? null : tiers[0] ?? null}
                tiers={tiers}
                currency={currency}
                onClose={() => setCtxOpen(false)}
                onApplyMedian={amount => {
                  const tId = focusedTierId || tiers[0]?.id;
                  if (tId && focusedBenefit) updateBenefit(tId, focusedBenefit, { amount, covered: true, value_type: 'currency' });
                }}
              />
            </div>
          )}
        </div>
      )}

      {tiers.length > 0 && (
        <div className="px-6 py-2 text-[12px] text-gray-500 border-t border-gray-200 bg-gray-50 flex items-center gap-2">
          <strong className="text-gray-700">Tiers are evaluated left to right.</strong>
          The first matching tier wins.
          <Button unstyled className="ml-auto text-blue-600 hover:underline text-[12px]">Reorder tiers →</Button>
        </div>
      )}

      {/* ── Rules drawer ── */}
      {rulesDrawerFor && (() => {
        const tier = tiers.find(t => t.id === rulesDrawerFor);
        return tier ? (
          <RulesDrawer
            tier={tier}
            allTiers={tiers}
            onChange={targeting => updateTier(tier.id, { targeting })}
            onClose={() => setRulesDrawerFor(null)}
          />
        ) : null;
      })()}

      {/* ── Import flow ── */}
      {importOpen && (
        <ImportFlow
          onClose={() => setImportOpen(false)}
          onImported={async () => {
            // The import already merged the extracted benefits into the draft
            // server-side; re-hydrate the canvas so HR sees the real rows.
            await reloadFromDraft();
            setImportOpen(false);
            setSavedAt(Date.now());
          }}
        />
      )}

      {/* ── Template picker ── */}
      {templateOpen && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-6"
             role="button" tabIndex={-1} aria-label="Close template picker"
             onClick={(e) => { if (e.target === e.currentTarget) setTemplateOpen(false); }}
             onKeyDown={(e) => { if (e.key === 'Escape') setTemplateOpen(false); }}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl">
            <div className="flex items-center gap-3 p-5 border-b border-gray-200">
              <Sparkles size={18} className="text-blue-600"/>
              <h2 className="text-base font-semibold text-gray-900 flex-1">Choose a template</h2>
              <Button unstyled onClick={() => setTemplateOpen(false)} className="text-gray-400 hover:text-gray-700"><X size={16}/></Button>
            </div>
            <div className="p-5">
              <p className="text-[13px] text-gray-500 mb-4">Pick a starting point. You can fully customise every tier and benefit after applying.</p>
              <div className="grid grid-cols-2 gap-3">
                {TEMPLATES.map(tpl => (
                  <Button unstyled key={tpl.id} onClick={() => applyTemplate(tpl)}
                    className="text-left p-4 rounded-xl border border-gray-200 hover:border-blue-400 hover:bg-blue-50 transition-colors">
                    <div className="text-2xl mb-2">{tpl.ico}</div>
                    <div className="text-[13px] font-semibold text-gray-900 mb-1">{tpl.t}</div>
                    <div className="text-[11.5px] text-gray-500 mb-3">{tpl.s}</div>
                    <div className="flex flex-wrap gap-1">
                      {tpl.tiers.map(t => (
                        <span key={t} className="text-[10px] font-semibold bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{t}</span>
                      ))}
                    </div>
                  </Button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
      {/* ── Preview (read-only summary of the mapped, to-be-published matrix) ── */}
      {previewOpen && (
        <PreviewModal
          result={previewResult}
          currency={currency}
          effectiveDate={effectiveDate}
          onClose={() => setPreviewOpen(false)}
        />
      )}
    </>
  );

  // [T2.4] HR not linked to a company yet → onboarding, not a blank builder.
  // Respect embedded vs standalone so the tab and the direct route both degrade.
  if (noCompany) {
    return embedded ? <HrNoCompanyOnboarding /> : <AppShell wide><HrNoCompanyOnboarding /></AppShell>;
  }

  // The Policy Assistant docked shell wraps the builder so HR can ask about the
  // published policy without leaving the page (reuses the same shell + panel as
  // the Published-policy tab).
  const shell = (
    <PolicyAssistantDockedShell
      open={assistantOpen}
      onOpenChange={setAssistantOpen}
      title="Ask about this policy"
      subtitle="Bounded Q&A on your published policy."
      titleId="hr-builder-assistant-shell-title"
      assistant={() => <HrPolicyAssistantPanel policyId={draftVersionId} variant="embedded" />}
    >
      {inner}
    </PolicyAssistantDockedShell>
  );

  if (embedded) return shell;
  return <AppShell wide>{shell}</AppShell>;
}

// ─── Preview modal ──────────────────────────────────────────────────────────
const CATEGORY_TITLES: Record<string, string> = {
  pre_assignment_support: 'Pre-assignment support',
  relocation_assistance: 'Relocation assistance',
  compensation_allowances: 'Compensation & allowances',
  family_support_education: 'Family support & education',
  leave_repatriation: 'Leave & repatriation',
  tax_payroll: 'Tax & payroll',
};

function PreviewModal({
  result,
  currency,
  effectiveDate,
  onClose,
}: {
  result: CanvasMapResult;
  currency: string;
  effectiveDate: string;
  onClose: () => void;
}) {
  const cur = CUR_SYM[currency] || currency;
  const fmtValue = (b: CanvasMapResult['body']['categories'][number]['benefits'][number]): string => {
    if (b.value_type === 'currency' && b.amount_value != null) return `${cur}${b.amount_value.toLocaleString()}${b.unit_frequency !== 'one_time' ? ` ${b.unit_frequency}` : ''}`;
    if (b.value_type === 'percentage' && b.percentage_value != null) return `${b.percentage_value}%`;
    if (b.value_type === 'text' && b.notes) return b.notes;
    if (b.value_type === 'none') return 'Service';
    return b.notes || '—';
  };
  const fmtTargeting = (b: CanvasMapResult['body']['categories'][number]['benefits'][number]): string => {
    const parts = [...b.employee_levels, ...b.assignment_types, ...b.family_statuses];
    return parts.length ? parts.join(' · ') : 'All employees';
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-6"
         role="button" tabIndex={-1} aria-label="Close preview"
         onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
         onKeyDown={(e) => { if (e.key === 'Escape') onClose(); }}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col">
        <div className="flex items-center gap-3 p-5 border-b border-gray-200">
          <Eye size={18} className="text-blue-600"/>
          <div className="flex-1">
            <h2 className="text-base font-semibold text-gray-900">Preview — published policy</h2>
            <p className="text-[12px] text-gray-500">
              {result.rowCount} benefit row(s) · effective {effectiveDate}. This is exactly what will be saved/published to the policy matrix.
            </p>
          </div>
          <Button unstyled onClick={onClose} className="text-gray-400 hover:text-gray-700"><X size={16}/></Button>
        </div>
        <div className="p-5 overflow-y-auto">
          {result.rowCount === 0 ? (
            <p className="text-sm text-gray-500">No covered benefits yet. Mark benefits as covered (or included) to populate the policy.</p>
          ) : (
            <div className="space-y-5">
              {result.body.categories.map(cat => (
                <div key={cat.category_key}>
                  <div className="text-[13px] font-semibold text-gray-900 mb-2">{CATEGORY_TITLES[cat.category_key] || cat.category_key}</div>
                  <div className="border border-gray-200 rounded-lg divide-y divide-gray-100">
                    {cat.benefits.map((b, i) => (
                      <div key={`${b.benefit_key}-${i}`} className="flex items-start justify-between gap-4 px-3 py-2">
                        <div className="min-w-0">
                          <div className="text-[13px] text-gray-800">{b.benefit_label}</div>
                          <div className="text-[11px] text-gray-400">{fmtTargeting(b)}</div>
                        </div>
                        <div className="text-[12px] font-medium text-gray-700 whitespace-nowrap">{fmtValue(b)}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
          {result.warnings.length > 0 && (
            <div className="mt-5">
              <Alert variant="info">
                <div className="text-[12px]">
                  <div className="font-semibold mb-1">Mapping notes</div>
                  <ul className="list-disc pl-4 space-y-0.5">
                    {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                </div>
              </Alert>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── TierColumn ───────────────────────────────────────────────────────────────
interface TierColumnProps {
  tier: Tier;
  categories: CategoryDef[];
  collapsed: Record<number, boolean>;
  currency: string;
  onRename: (name: string) => void;
  onModeChange: (m: AssignmentMode) => void;
  onLumpChange: (v: number) => void;
  onOpenRules: () => void;
  onBenefitChange: (bKey: string, patch: Partial<BenefitValue>) => void;
  maxTotal: number;
}

function TierColumn({ tier, categories, collapsed, currency, onRename, onModeChange, onLumpChange, onOpenRules, onBenefitChange, maxTotal }: TierColumnProps) {
  const isLump = tier.mode === 'lump';
  const total = useMemo(() => {
    if (isLump) return tier.lump;
    let sum = 0;
    categories.forEach(cat => cat.benefits.forEach(b => {
      const v = tier.benefits[b.k];
      if (!v || !v.covered || v.value_type !== 'currency' || !v.amount) return;
      sum += v.freq === 'monthly' ? v.amount * 12 : v.amount;
    }));
    return sum;
  }, [tier, categories, isLump]);

  const cur = CUR_SYM[currency] ?? currency;
  const fmt = (n: number) => cur + (n || 0).toLocaleString();
  const pct = Math.round((total / maxTotal) * 100);

  return (
    <div className="w-[220px] flex-shrink-0 border-r border-gray-200 flex flex-col" style={{ '--tier-color': tier.color } as React.CSSProperties}>
      {/* Tier header */}
      {/* AIQ-1108: fixed header height keeps every tier column's benefit grid
          starting at the same Y (independent of lump vs caps mode), and matches
          the sidebar's top spacer so labels line up with their cells. */}
      <div className="sticky top-0 z-10 bg-white border-b border-gray-200 pb-3 pt-3 px-3 h-[168px]"
           style={{ borderTop: `3px solid ${tier.color}` }}>
        <div className="flex items-center gap-2 mb-1.5">
          <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: tier.color }}/>
          <Input unstyled value={tier.name} onChange={v => onRename(v)}
            className="flex-1 min-w-0 text-[13px] font-semibold text-gray-900 bg-transparent border-none outline-none"/>
          <Button unstyled className="text-gray-400 hover:text-gray-600 text-lg leading-none">⋯</Button>
        </div>
        <div className="flex items-center gap-1 text-[11px] text-gray-400 mb-2">
          <Users size={11}/>
          {tier.emp ? `${tier.emp} employee${tier.emp > 1 ? 's' : ''}` : '0 employees'}
        </div>
        <Button unstyled onClick={onOpenRules}
          className="w-full flex items-center gap-1.5 text-[11px] text-gray-500 hover:text-blue-600 bg-gray-50 border border-gray-200 rounded-lg px-2 py-1.5 mb-2 transition-colors">
          <Filter size={11} className="flex-shrink-0"/>
          <span className="flex-1 text-left truncate">{targetingSummary(tier.targeting)}</span>
          <ChevronRight size={10}/>
        </Button>
        <div className="flex rounded-lg overflow-hidden border border-gray-200 text-[11px] font-semibold">
          <Button unstyled onClick={() => onModeChange('lump')}
            className={`flex-1 py-1 transition-colors ${tier.mode === 'lump' ? 'bg-gray-900 text-white' : 'text-gray-500 hover:bg-gray-50'}`}>
            Lump sum
          </Button>
          <Button unstyled onClick={() => onModeChange('caps')}
            className={`flex-1 py-1 transition-colors ${tier.mode === 'caps' ? 'bg-gray-900 text-white' : 'text-gray-500 hover:bg-gray-50'}`}>
            Caps
          </Button>
        </div>
        {isLump && (
          <div className="flex items-center gap-2 mt-2 text-[11.5px]">
            <span className="text-gray-500">Budget</span>
            <Input unstyled type="number" value={tier.lump} onChange={v => onLumpChange(Number(v))}
              className="w-20 border border-gray-200 rounded px-1.5 py-0.5 text-[11.5px] focus:outline-none focus:border-blue-400"/>
            <span className="text-gray-400">{cur}/yr</span>
          </div>
        )}
      </div>

      {/* Benefit cells */}
      <div className="flex-1">
        {categories.map(cat => {
          if (collapsed[cat.id]) return <div key={cat.id} className="h-[41px] border-b border-gray-100 bg-gray-50"/>;
          return (
            <React.Fragment key={cat.id}>
              <div className="h-[41px] border-b border-gray-200 bg-gray-50"/>
              {cat.benefits.map(b => (
                <Cell key={b.k} bk={b.k} v={tier.benefits[b.k]} lump={isLump}
                      onChange={patch => onBenefitChange(b.k, patch)} cur={cur}/>
              ))}
              <div className="h-9 border-b border-gray-100"/>
            </React.Fragment>
          );
        })}
      </div>

      {/* Tier total */}
      <div className="sticky bottom-0 bg-white border-t-2 border-gray-200 p-3">
        <div className="flex items-center justify-between text-[11.5px] mb-1.5">
          <span className="text-gray-500">{isLump ? 'Lump-sum budget' : 'Est. annual cost'}</span>
          <span className="font-bold text-gray-900">{fmt(total)}</span>
        </div>
        <div className="flex items-center gap-2 text-[10.5px] text-gray-400">
          <span>vs other tiers</span>
          <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div className="h-full rounded-full transition-all" style={{ width: pct + '%', background: tier.color }}/>
          </div>
          <span className="font-semibold">{pct}%</span>
        </div>
      </div>
    </div>
  );
}

// Map a 0–1 extraction confidence score to the shared 4-level confidence scale
// (HIGH ≥0.85, MEDIUM ≥0.6, LOW >0 — the low-confidence "review me" signal — else UNKNOWN).
function confidenceLevel(score: number): ConfidenceLevel {
  if (score >= 0.85) return 'HIGH';
  if (score >= 0.6) return 'MEDIUM';
  if (score > 0) return 'LOW';
  return 'UNKNOWN';
}

// ─── Cell ─────────────────────────────────────────────────────────────────────
interface CellProps {
  bk: string;
  v: BenefitValue | undefined;
  lump: boolean;
  onChange: (patch: Partial<BenefitValue>) => void;
  cur: string;
}

function Cell({ v, lump, onChange, cur }: CellProps) {
  if (!v) return <div className="h-9 border-b border-gray-100"/>;

  if (lump) {
    const inc: LumpInc = v.lump_inc || (v.covered ? 'included' : 'excluded');
    const next: LumpInc = inc === 'included' ? 'optional' : inc === 'optional' ? 'excluded' : 'included';
    const style = inc === 'included' ? 'bg-blue-50 text-blue-700 border-blue-200' : inc === 'optional' ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-gray-50 text-gray-400 border-gray-200';
    return (
      <div className="h-9 flex items-center justify-center border-b border-gray-100 px-2">
        <Button unstyled onClick={() => onChange({ lump_inc: next })}
          className={`flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-full border cursor-pointer ${style}`}>
          {inc === 'included' && <><Check size={9}/> Included</>}
          {inc === 'optional' && <>• Optional</>}
          {inc === 'excluded' && <><Minus size={9}/> Excluded</>}
        </Button>
      </div>
    );
  }

  return (
    <div className={`h-9 flex items-center gap-1 border-b border-gray-100 px-1.5 group ${!v.covered ? 'bg-gray-50/50' : ''}`}>
      <Button unstyled onClick={() => onChange({ covered: !v.covered })}
        className={`w-5 h-5 rounded flex items-center justify-center flex-shrink-0 text-[11px] font-bold border transition-colors ${v.covered ? 'bg-blue-600 border-blue-600 text-white' : 'border-gray-200 text-gray-300 hover:border-gray-400'}`}>
        {v.covered ? '✓' : '—'}
      </Button>
      {v.covered && (
        <>
          <select value={v.value_type} onChange={e => onChange({ value_type: e.target.value as BenefitValueType })}
            onClick={e => e.stopPropagation()}
            className="text-[10px] border border-gray-200 rounded px-0.5 py-0 bg-white w-9 focus:outline-none">
            {VAL_OPTS.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
          </select>
          {v.value_type === 'currency' && (
            <>
              <div className="flex items-center gap-0.5">
                <Input unstyled type="number" value={v.amount} onChange={v => onChange({ amount: Number(v) })}
                  className="w-14 text-[11px] border border-gray-200 rounded px-1 py-0 focus:outline-none focus:border-blue-400"/>
                <span className="text-[10px] text-gray-400">{cur}</span>
              </div>
              <select value={v.freq} onChange={e => onChange({ freq: e.target.value as Freq })}
                className="text-[9.5px] border border-gray-200 rounded px-0.5 py-0 bg-white focus:outline-none">
                {FREQ_OPTS.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
              </select>
            </>
          )}
          {v.value_type === 'percentage' && (
            <div className="flex items-center gap-0.5">
              <Input unstyled type="number" value={v.amount} onChange={v => onChange({ amount: Number(v) })}
                className="w-10 text-[11px] border border-gray-200 rounded px-1 py-0 focus:outline-none focus:border-blue-400"/>
              <span className="text-[10px] text-gray-400">%</span>
            </div>
          )}
          {v.value_type === 'text' && (
            <div className="flex items-center gap-0.5">
              <Input unstyled type="number" value={v.amount} onChange={v => onChange({ amount: Number(v) })}
                className="w-8 text-[11px] border border-gray-200 rounded px-1 py-0 focus:outline-none focus:border-blue-400"/>
              <span className="text-[9.5px] text-gray-400">days</span>
            </div>
          )}
          {v.value_type === 'none' && <span className="text-[10.5px] text-gray-400 flex-1">Service</span>}
          {v.cap && <span className="text-[9px] font-bold bg-blue-100 text-blue-700 px-1 py-0 rounded" title="Cap rule attached">CAP</span>}
          {v.conditions && <span className="text-[9px] font-bold bg-amber-100 text-amber-700 px-1 py-0 rounded" title="Conditional">IF</span>}
          {v.source === 'extracted_llm' && typeof v.field_confidence === 'number' && (
            <ConfidenceBadge level={confidenceLevel(v.field_confidence)} score={v.field_confidence} size="sm"/>
          )}
        </>
      )}
      <Button unstyled className="ml-auto opacity-0 group-hover:opacity-100 text-gray-400 hover:text-gray-600 flex-shrink-0">
        <Pencil size={10}/>
      </Button>
    </div>
  );
}

// ─── Rules Drawer ─────────────────────────────────────────────────────────────
interface RulesDrawerProps {
  tier: Tier;
  allTiers: Tier[];
  onChange: (tg: Targeting) => void;
  onClose: () => void;
}

function RulesDrawer({ tier, allTiers, onChange, onClose }: RulesDrawerProps) {
  const [local, setLocal] = useState<Targeting>({
    level: tier.targeting.level || [],
    type:  tier.targeting.type  || [],
    family: tier.targeting.family || [],
  });
  const toggle = (axis: keyof Targeting, v: string) =>
    setLocal(L => ({ ...L, [axis]: L[axis].includes(v) ? L[axis].filter(x => x !== v) : [...L[axis], v] }));

  const conflict = allTiers.find(t => t.id !== tier.id &&
    t.targeting.level.some(l => local.level.includes(l)) &&
    t.targeting.type.some(tp => local.type.includes(tp)) &&
    t.targeting.family.some(f => local.family.includes(f)));

  const LEVELS = Object.entries(LEVEL_LBL);
  const TYPES: [string, string][] = [
    ['long_term', 'Long-term assignment (>12 months)'],
    ['short_term', 'Short-term assignment (3–12 months)'],
    ['permanent', 'Permanent transfer'],
    ['commuter', 'Cross-border commuter'],
    ['extended_business_trip', 'Extended business trip (<3 months)'],
  ];
  const FAMILY: [string, string][] = [
    ['single', 'Single / No dependents'],
    ['married', 'Married / Partner (no dependents)'],
    ['accompanied_family', 'With accompanying dependents'],
  ];

  return (
    <>
      {/* eslint-disable-next-line local/no-clickable-div -- presentational mouse-dismiss overlay (aria-hidden); keyboard users dismiss via the panel's own controls */}
      <div className="fixed inset-0 bg-black/20 z-30" aria-hidden="true" onClick={onClose}/>
      <aside className="fixed right-0 top-0 bottom-0 w-[420px] bg-white shadow-2xl z-40 flex flex-col">
        <div className="flex items-start gap-3 p-5 border-b border-gray-200">
          <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
            <Filter size={16} className="text-blue-600"/>
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold text-gray-900">{tier.name} · targeting rules</div>
            <div className="text-[11.5px] text-gray-500 mt-0.5">
              An employee matching <strong>all three</strong> criteria is assigned to this tier.
            </div>
          </div>
          <Button unstyled onClick={onClose} className="text-gray-400 hover:text-gray-700"><X size={16}/></Button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {([
            { axis: 'level' as const, lbl: 'Employee level', opts: LEVELS.map(([v, l]) => [v, l + (v === 'manager' ? ' / Senior IC' : v === 'vp' ? ' / Head of' : v === 'c_suite' ? ' / Executive' : '')]) },
            { axis: 'type' as const,  lbl: 'Assignment type', opts: TYPES },
            { axis: 'family' as const, lbl: 'Family status', opts: FAMILY },
          ]).map(({ axis, lbl, opts }) => (
            <div key={axis}>
              <div className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider mb-2">{lbl}</div>
              <div className="space-y-1">
                {opts.map(([v, l]) => {
                  const on = local[axis].includes(v);
                  return (
                    <button key={v}
                      type="button"
                      className={`flex w-full items-center gap-3 p-2.5 rounded-lg border cursor-pointer transition-colors text-left ${on ? 'border-blue-300 bg-blue-50' : 'border-gray-200 hover:border-gray-300'}`}
                      onClick={() => toggle(axis, v)}>
                      <Checkbox readOnly checked={on} className="accent-blue-600"/>
                      <span className={`text-[12.5px] ${on ? 'text-blue-900 font-medium' : 'text-gray-700'}`}>{l}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}

          {conflict && (
            <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-[12px] text-amber-800">
              <AlertTriangle size={14} className="flex-shrink-0 mt-0.5 text-amber-600"/>
              <span><strong>Overlap detected with &quot;{conflict.name}&quot;.</strong> The first matching tier (left-to-right) wins. Drag to reorder or refine rules to remove the overlap.</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3 p-4 border-t border-gray-200">
          <Button unstyled onClick={onClose} className="flex-1 py-2 rounded-lg border border-gray-200 text-sm font-medium text-gray-700 hover:bg-gray-50">Cancel</Button>
          <Button unstyled onClick={() => { onChange(local); onClose(); }}
            className="flex-1 py-2 rounded-lg bg-navy-800 text-white text-sm font-semibold hover:bg-navy-900">
            Save rules
          </Button>
        </div>
      </aside>
    </>
  );
}

// ─── Import Flow ──────────────────────────────────────────────────────────────
// Progress stages are driven off the REAL document status returned by
// GET /api/hr/policy-documents/{id} — not a timer. The assistant-import pipeline
// advances extracting_text → classified (or failed); LLM value-extraction then
// moves processing_status to `normalized`. Both happen in one background pass, so
// `classified`/`normalized` is our "ready to import" signal.
interface ImportStage { lbl: string; pct: number }
const STAGE_UPLOADING: ImportStage = { lbl: 'Uploading document…', pct: 15 };
const STAGE_READING:   ImportStage = { lbl: 'Reading document text…', pct: 45 };
const STAGE_EXTRACTING: ImportStage = { lbl: 'Extracting benefit rules…', pct: 75 };
const STAGE_IMPORTING: ImportStage = { lbl: 'Importing into your draft…', pct: 92 };

const READY_STATUSES = new Set(['classified', 'normalized']);

function stageForStatus(assistant?: string | null, processing?: string | null): ImportStage {
  const a = (assistant || '').toLowerCase();
  const p = (processing || '').toLowerCase();
  if (READY_STATUSES.has(a) || p === 'normalized') return STAGE_EXTRACTING;
  return STAGE_READING;
}
function isImportReady(assistant?: string | null, processing?: string | null): boolean {
  return READY_STATUSES.has((assistant || '').toLowerCase()) || (processing || '').toLowerCase() === 'normalized';
}
function isImportFailed(assistant?: string | null, processing?: string | null): boolean {
  return (assistant || '').toLowerCase() === 'failed' || (processing || '').toLowerCase() === 'failed';
}

// Canonical matrix benefit key → human label + category, built from CATEGORIES so
// the import summary can render the REAL imported keys (import-extraction returns
// matrix keys, not rich rows).
const BENEFIT_META: Record<string, { lbl: string; cat: string }> = (() => {
  const out: Record<string, { lbl: string; cat: string }> = {};
  CATEGORIES.forEach(c => c.benefits.forEach(b => { out[b.k] = { lbl: b.lbl, cat: c.t }; }));
  return out;
})();

const POLL_INTERVAL_MS = 1800;
const MAX_POLLS = 60; // ~1.8 min ceiling before we surface an honest timeout.

interface ImportFlowProps {
  onClose: () => void;
  /** Called after the extraction has been imported into the draft server-side. */
  onImported: () => void | Promise<void>;
}

type ImportStep = 'upload' | 'processing' | 'review' | 'error';

export function ImportFlow({ onClose, onImported }: ImportFlowProps) {
  const [step, setStep]           = useState<ImportStep>('upload');
  const [file, setFile]           = useState<File | null>(null);
  const [dragOver, setDragOver]   = useState(false);
  const [docId, setDocId]         = useState<string | null>(null);
  const [stage, setStage]         = useState<ImportStage>(STAGE_UPLOADING);
  const [result, setResult]       = useState<{ imported: string[]; unmapped: string[]; skipped_existing: string[] } | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [errorMsg, setErrorMsg]   = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fmtSize = (bytes: number) => bytes < 1_000_000
    ? `${(bytes / 1024).toFixed(0)} KB`
    : `${(bytes / 1_048_576).toFixed(1)} MB`;

  const handleFiles = (picked: FileList | null) => {
    const f = picked?.[0];
    if (!f) return;
    setFile(f);
    setUploadError(null);
  };

  // Kick off: real upload → capture the returned document id → poll for status.
  const handleStartExtraction = async () => {
    if (!file) return;
    setUploadError(null);
    setErrorMsg(null);
    setStage(STAGE_UPLOADING);
    setStep('processing');
    try {
      const res = await policyDocumentsAPI.upload(file);
      const id = res?.document?.id;
      if (!id) throw new Error('Upload did not return a document id.');
      setDocId(id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      setUploadError(msg);
      setStep('upload');
    }
  };

  // Poll GET /api/hr/policy-documents/{id} until the extraction is ready
  // (classified/normalized), then import into the draft — or surface an honest
  // failure/timeout. The progress bar reflects the REAL status, never a timer.
  useEffect(() => {
    if (step !== 'processing' || !docId) return;
    let cancelled = false;
    let attempts = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const runImport = async () => {
      setStage(STAGE_IMPORTING);
      try {
        const res = await policyConfigMatrixAPI.hrImportExtraction({ policy_id: docId });
        if (cancelled) return;
        setResult({ imported: res.imported ?? [], unmapped: res.unmapped ?? [], skipped_existing: res.skipped_existing ?? [] });
        setStep('review');
      } catch (e: unknown) {
        if (cancelled) return;
        setErrorMsg(e instanceof Error ? e.message : 'Import failed.');
        setStep('error');
      }
    };

    const poll = async () => {
      if (cancelled) return;
      attempts += 1;
      try {
        const { document } = await policyDocumentsAPI.get(docId);
        if (cancelled) return;
        const a = document?.assistant_import_status;
        const p = document?.processing_status;
        setStage(stageForStatus(a, p));
        if (isImportFailed(a, p)) {
          setErrorMsg(document?.extraction_error || 'We could not read this document. Try a different file, or contact support.');
          setStep('error');
          return;
        }
        if (isImportReady(a, p)) {
          await runImport();
          return;
        }
        if (attempts >= MAX_POLLS) {
          setErrorMsg('Extraction is taking longer than expected. Please try again in a moment.');
          setStep('error');
          return;
        }
        timer = setTimeout(() => { void poll(); }, POLL_INTERVAL_MS);
      } catch (e: unknown) {
        if (cancelled) return;
        setErrorMsg(e instanceof Error ? e.message : 'Could not check extraction status.');
        setStep('error');
      }
    };
    void poll();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [step, docId]);

  const imported = result?.imported ?? [];
  const unmapped = result?.unmapped ?? [];
  const skippedExisting = result?.skipped_existing ?? [];
  // "All skipped" = we found benefits in the doc but they're already in the draft
  // (a re-import). Distinct from "nothing found" so we don't mislead the user.
  const allSkipped = step === 'review' && imported.length === 0 && skippedExisting.length > 0;
  const nothingImported = step === 'review' && imported.length === 0 && skippedExisting.length === 0;

  const STEPS = ['Upload', 'Extract', 'Review'];
  const stepNum = step === 'upload' ? 1 : step === 'review' ? 3 : 2;

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-6"
         role="button" tabIndex={-1} aria-label="Close document import"
         onClick={e => { if (e.target === e.currentTarget) onClose(); }}
         onKeyDown={(e) => { if (e.key === 'Escape') onClose(); }}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center gap-3 px-6 py-4 border-b border-gray-200">
          <Upload size={18} className="text-blue-600"/>
          <h2 className="text-base font-semibold text-gray-900 flex-1">Import policy from document</h2>
          <Button unstyled onClick={onClose} className="text-gray-400 hover:text-gray-700"><X size={16}/></Button>
        </div>

        {/* Stepper */}
        <div className="flex items-center px-6 py-3 border-b border-gray-200 gap-0">
          {STEPS.map((lbl, i) => {
            const idx = i + 1;
            const active = stepNum === idx;
            const done = stepNum > idx;
            return (
              <React.Fragment key={lbl}>
                <div className={`flex items-center gap-2 text-[12px] font-medium ${active ? 'text-blue-600' : done ? 'text-green-600' : 'text-gray-400'}`}>
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold border-2 ${active ? 'border-blue-600 bg-blue-600 text-white' : done ? 'border-green-600 bg-green-600 text-white' : 'border-gray-300 text-gray-400'}`}>
                    {done ? <Check size={10}/> : idx}
                  </div>
                  {lbl}
                </div>
                {i < STEPS.length - 1 && <div className="flex-1 h-px bg-gray-200 mx-3"/>}
              </React.Fragment>
            );
          })}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-hidden">
          {/* Step 1: Upload */}
          {step === 'upload' && (
            <div className="p-6">
              {/* Hidden real file input */}
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                className="hidden"
                onChange={e => handleFiles(e.target.files)}
              />
              {!file ? (
                <div
                  role="button"
                  tabIndex={0}
                  className={`border-2 border-dashed rounded-xl p-10 flex flex-col items-center gap-3 cursor-pointer transition-colors ${dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-blue-300'}`}
                  onClick={() => fileInputRef.current?.click()}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInputRef.current?.click(); } }}
                  onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={e => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files); }}>
                  <Upload size={28} className="text-gray-300"/>
                  <div className="text-sm font-semibold text-gray-700">Drop your policy document here</div>
                  <div className="text-[12px] text-gray-400">PDF or Word (.docx) · max 50 MB</div>
                  <Button unstyled className="text-[12px] text-blue-600 font-medium hover:underline">Browse files</Button>
                </div>
              ) : (
                <div className="flex items-center gap-3 p-4 border border-gray-200 rounded-xl">
                  <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center text-[11px] font-bold text-red-600">
                    {file.name.toLowerCase().endsWith('.docx') ? 'DOC' : 'PDF'}
                  </div>
                  <div className="flex-1">
                    <div className="text-[13px] font-semibold text-gray-900">{file.name}</div>
                    <div className="text-[11.5px] text-gray-400">{fmtSize(file.size)} · ready to extract</div>
                  </div>
                  <Button unstyled onClick={() => { setFile(null); setUploadError(null); if (fileInputRef.current) fileInputRef.current.value = ''; }} className="text-gray-400 hover:text-gray-600"><X size={16}/></Button>
                </div>
              )}
              {uploadError && (
                <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-xl text-[12.5px] text-red-700">
                  Upload failed: {uploadError}. Please try again.
                </div>
              )}
              <div className="mt-4 p-4 bg-blue-50 rounded-xl text-[12.5px] text-blue-700">
                For best results, upload your full assignment policy document — not a summary sheet. The AI extracts benefit rules, caps, and conditions automatically.
              </div>
            </div>
          )}

          {/* Step 2: Processing — progress driven by the REAL document status */}
          {step === 'processing' && (
            <div className="p-8 flex flex-col items-center gap-6">
              <div className="w-full max-w-lg">
                <div className="h-2 bg-gray-100 rounded-full overflow-hidden mb-3">
                  <div className="h-full bg-blue-600 rounded-full transition-all duration-700" style={{ width: stage.pct + '%' }}/>
                </div>
                <div className="flex items-center gap-2 text-[13px] text-gray-600">
                  <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"/>
                  {stage.lbl}
                </div>
              </div>
              <p className="text-[12px] text-gray-400 max-w-sm text-center">
                Reading your document and extracting benefit rules. This can take up to a minute for a full policy.
              </p>
            </div>
          )}

          {/* Error — honest failure / timeout state */}
          {step === 'error' && (
            <div className="p-8 flex flex-col items-center gap-4 text-center">
              <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
                <AlertTriangle size={22} className="text-red-600"/>
              </div>
              <h3 className="text-sm font-semibold text-gray-900">Extraction failed</h3>
              <p className="text-[13px] text-gray-500 max-w-sm">{errorMsg || 'Something went wrong while reading this document.'}</p>
            </div>
          )}

          {/* Step 3: Review — the REAL imported benefit keys from the draft */}
          {step === 'review' && (
            <div className="p-6 overflow-y-auto max-h-[55vh]">
              {(nothingImported || allSkipped) ? (
                <div className="flex flex-col items-center gap-3 py-10 text-center">
                  <div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center">
                    <Info size={22} className="text-amber-600"/>
                  </div>
                  {allSkipped ? (
                    <>
                      <h3 className="text-sm font-semibold text-gray-900">Already in your draft</h3>
                      <p className="text-[13px] text-gray-500 max-w-md">
                        Your draft already contains all {skippedExisting.length} benefit{skippedExisting.length === 1 ? '' : 's'} we found in this document — nothing new to import.
                      </p>
                    </>
                  ) : (
                    <>
                      <h3 className="text-sm font-semibold text-gray-900">No benefits could be imported</h3>
                      <p className="text-[13px] text-gray-500 max-w-md">
                        We couldn&apos;t map any structured benefits from this document into your policy. You can still build the policy from a template, or try a more detailed policy document.
                      </p>
                    </>
                  )}
                  {unmapped.length > 0 && (
                    <div className="mt-2 w-full max-w-md text-left">
                      <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-1">
                        Extracted terms with no automatic mapping ({unmapped.length})
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {unmapped.map(k => (
                          <span key={k} className="text-[11px] bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{k}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <>
                  <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-xl text-[12.5px] text-green-700">
                    <strong>{imported.length}</strong> benefit{imported.length !== 1 ? 's' : ''} imported into your draft. Review and adjust amounts on the canvas before publishing — extracted values start at defaults with the source term captured in each row&apos;s notes.
                  </div>
                  <div className="border border-gray-200 rounded-xl divide-y divide-gray-100">
                    {imported.map(k => {
                      const meta = BENEFIT_META[k];
                      return (
                        <div key={k} className="flex items-center gap-3 px-4 py-2.5">
                          <Check size={14} className="text-green-600 flex-shrink-0"/>
                          <div className="min-w-0">
                            <div className="text-[13px] text-gray-800 truncate">{meta?.lbl || k}</div>
                            {meta?.cat && <div className="text-[11px] text-gray-400">{meta.cat}</div>}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  {unmapped.length > 0 && (
                    <div className="mt-4">
                      <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                        Couldn&apos;t auto-map ({unmapped.length}) — add these manually on the canvas
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {unmapped.map(k => (
                          <span key={k} className="text-[11px] bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{k}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-3 px-6 py-4 border-t border-gray-200">
          {step === 'upload' && <Button unstyled onClick={onClose} className="text-[13px] text-gray-400 hover:text-gray-600">Cancel</Button>}
          <div className="flex-1"/>
          {step === 'upload' && (
            <Button unstyled disabled={!file} onClick={handleStartExtraction}
              className="px-5 py-2 bg-navy-800 text-white rounded-lg text-sm font-semibold hover:bg-navy-900 disabled:opacity-40">
              Start extraction →
            </Button>
          )}
          {step === 'processing' && <span className="text-[13px] text-gray-400">Processing…</span>}
          {step === 'error' && (
            <>
              <Button unstyled onClick={onClose} className="text-[13px] text-gray-400 hover:text-gray-600">Close</Button>
              <Button unstyled onClick={() => { setErrorMsg(null); setDocId(null); setStep('upload'); }}
                className="px-5 py-2 bg-navy-800 text-white rounded-lg text-sm font-semibold hover:bg-navy-900">
                Try again
              </Button>
            </>
          )}
          {step === 'review' && (
            <Button unstyled onClick={() => { void onImported(); }}
              className="px-5 py-2 bg-navy-800 text-white rounded-lg text-sm font-semibold hover:bg-navy-900">
              {nothingImported ? 'Close' : 'View on canvas →'}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Context Sidebar ──────────────────────────────────────────────────────────
const BENCH_COUNTRIES = [
  { code: 'DE', name: 'Germany',        flag: '🇩🇪' },
  { code: 'FR', name: 'France',         flag: '🇫🇷' },
  { code: 'GB', name: 'United Kingdom', flag: '🇬🇧' },
  { code: 'NO', name: 'Norway',         flag: '🇳🇴' },
  { code: 'US', name: 'United States',  flag: '🇺🇸' },
  { code: 'CH', name: 'Switzerland',    flag: '🇨🇭' },
  { code: 'SG', name: 'Singapore',      flag: '🇸🇬' },
  { code: 'JP', name: 'Japan',          flag: '🇯🇵' },
];

type BenchEntry = { range: [number,number]; avg: number; providers: number };
const BENCH_DATA: Record<string, Record<string, BenchEntry>> = {
  host_housing_cap: {
    DE: { range: [1200, 3800], avg: 2100, providers: 7 },
    FR: { range: [1400, 4200], avg: 2400, providers: 9 },
    GB: { range: [1800, 5500], avg: 3000, providers: 12 },
    NO: { range: [1500, 4000], avg: 2300, providers: 5 },
    US: { range: [2000, 6000], avg: 3200, providers: 14 },
    CH: { range: [2400, 6500], avg: 3800, providers: 6 },
    SG: { range: [2200, 5800], avg: 3400, providers: 8 },
    JP: { range: [1800, 4800], avg: 2700, providers: 7 },
  },
  child_education_support: {
    DE: { range: [8000, 22000], avg: 13500, providers: 5 },
    FR: { range: [6000, 18000], avg: 11000, providers: 4 },
    GB: { range: [12000, 28000], avg: 18000, providers: 6 },
    NO: { range: [4000, 14000], avg: 8000,  providers: 3 },
  },
  temporary_living: {
    DE: { range: [1400, 4500], avg: 2400, providers: 11 },
    FR: { range: [1600, 5000], avg: 2700, providers: 8 },
  },
};

type Provider = { name: string; verified: boolean; preferred: boolean; rating: number; reviews: number; price: string; tags: string[] };
const PROVIDERS_BY_COUNTRY: Record<string, Provider[]> = {
  DE: [
    { name: 'NestPick Berlin',     verified: true,  preferred: true,  rating: 4.7, reviews: 142, price: '€1,800–€3,200', tags: ['Furnished','Corporate','EN-speaking'] },
    { name: 'HousingAnywhere DE',  verified: true,  preferred: false, rating: 4.5, reviews: 89,  price: '€1,400–€2,800', tags: ['Online platform','EN-speaking'] },
    { name: 'Munich Relocation Hub', verified: true, preferred: false, rating: 4.6, reviews: 56, price: '€1,900–€3,500', tags: ['Local agent','Family-focused'] },
    { name: 'Hamburg Living Co',   verified: false, preferred: false, rating: 4.2, reviews: 24,  price: '€1,500–€2,400', tags: ['Hamburg only'] },
  ],
  FR: [
    { name: 'Paris Attitude',  verified: true, preferred: true,  rating: 4.8, reviews: 218, price: '€2,000–€4,000', tags: ['Furnished','Concierge'] },
    { name: 'Lodgis',          verified: true, preferred: false, rating: 4.6, reviews: 174, price: '€1,800–€3,800', tags: ['Long-term','Multilingual'] },
    { name: 'My Paris Agency', verified: true, preferred: false, rating: 4.5, reviews: 67,  price: '€2,200–€4,500', tags: ['White-glove'] },
  ],
  NO: [
    { name: 'Stavanger Relocation Co.', verified: true, preferred: true,  rating: 4.7, reviews: 87, price: '€1,500–€3,400', tags: ['Local agent'] },
    { name: 'Bolig Direkte',            verified: true, preferred: false, rating: 4.4, reviews: 42, price: '€1,200–€2,800', tags: ['Direct rentals'] },
  ],
};

const BENEFIT_LABELS: Record<string, string> = {
  host_housing_cap: 'Host country housing',
  child_education_support: 'Child education support',
  temporary_living: 'Temporary living',
  language_training: 'Language training',
};

interface ContextSidebarProps {
  focusedBenefit: string | null;
  focusedTier: Tier | null;
  tiers: Tier[];
  currency: string;
  onClose: () => void;
  onApplyMedian: (amount: number) => void;
}

function ContextSidebar({ focusedBenefit, focusedTier, currency, onClose, onApplyMedian }: ContextSidebarProps) {
  const [country, setCountry] = useState('DE');
  const [tab, setTab] = useState<'bench' | 'providers' | 'historical'>('bench');
  const cur = CUR_SYM[currency];
  const lbl = focusedBenefit ? (BENEFIT_LABELS[focusedBenefit] || focusedBenefit) : 'All benefits';
  const data: BenchEntry | null = focusedBenefit ? (BENCH_DATA[focusedBenefit]?.[country] ?? null) : null;
  const providers: Provider[] = PROVIDERS_BY_COUNTRY[country] || [];

  const yourCap = useMemo<number | null>(() => {
    if (!focusedTier || !focusedBenefit) return null;
    const v = focusedTier.benefits[focusedBenefit];
    return v && v.covered && v.value_type === 'currency' ? v.amount : null;
  }, [focusedTier, focusedBenefit]);

  const widths = useMemo(() => {
    if (!data) return null;
    const max = Math.max(data.range[1], yourCap ?? 0) * 1.1;
    return {
      rangeStart: (data.range[0] / max) * 100,
      rangeEnd:   (data.range[1] / max) * 100,
      avg:        (data.avg / max) * 100,
      your:       yourCap != null ? (yourCap / max) * 100 : null,
    };
  }, [data, yourCap]);

  const verdict = useMemo(() => {
    if (!data || yourCap == null) return null;
    if (yourCap > data.range[1]) return { tone: 'green', txt: <>Your cap is <strong>above the market median</strong> — generous relative to the network.</> };
    if (yourCap < data.range[0]) return { tone: 'amber', txt: <>Your cap is <strong>below the market floor</strong> — employees may struggle to find suitable housing within this budget.</> };
    if (yourCap < data.avg)      return { tone: 'gray',  txt: <>Your cap is in range but <strong>below the platform average</strong> of {cur}{data.avg.toLocaleString()}.</> };
    return { tone: 'green', txt: <>Your cap is <strong>within typical range</strong>, slightly above the platform average. Comfortable.</> };
  }, [data, yourCap, cur]);

  const ctryName = BENCH_COUNTRIES.find(c => c.code === country)?.name ?? '';

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-start justify-between mb-1">
          <div className="text-[13px] font-semibold text-gray-900">Market context</div>
          <Button unstyled onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={14}/></Button>
        </div>
        <div className="text-[11.5px] text-gray-400 mb-3">{lbl}{focusedTier ? ` · ${focusedTier.name}` : ''}</div>
        <select value={country} onChange={e => setCountry(e.target.value)}
          className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-[12px] bg-white focus:outline-none">
          {BENCH_COUNTRIES.map(c => <option key={c.code} value={c.code}>{c.flag} {c.name}</option>)}
        </select>
      </div>

      <div className="flex border-b border-gray-200">
        {(['bench','providers','historical'] as const).map(t => (
          <Button unstyled key={t} onClick={() => setTab(t)}
            className={`flex-1 py-2 text-[11.5px] font-medium transition-colors ${tab === t ? 'border-b-2 border-blue-600 text-blue-600' : 'text-gray-400 hover:text-gray-600'}`}>
            {t === 'bench' ? 'Benchmarks' : t === 'providers' ? `Providers (${providers.length})` : 'History'}
          </Button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {!focusedBenefit && (
          <div className="text-center py-8 text-[12.5px] text-gray-400">
            <div className="text-2xl mb-2">👈</div>
            Hover over a benefit cell to see live market context.
          </div>
        )}

        {focusedBenefit && tab === 'bench' && (
          data ? (
            <div>
              <div className="text-[12px] font-semibold text-gray-700 mb-3">{lbl} — {ctryName}</div>
              <div className="space-y-3">
                {[
                  { k: 'Market range', pos: widths!.rangeStart, w: widths!.rangeEnd - widths!.rangeStart, v: `${cur}${data.range[0].toLocaleString()}–${data.range[1].toLocaleString()}`, color: 'bg-blue-200' },
                  { k: 'Avg on platform', pos: widths!.avg, w: 3, v: `${cur}${data.avg.toLocaleString()}`, color: 'bg-blue-600' },
                  ...(yourCap != null ? [{ k: 'Your cap', pos: widths!.your!, w: 3, v: `${cur}${yourCap.toLocaleString()}`, color: 'bg-green-500' }] : []),
                ].map(row => (
                  <div key={row.k}>
                    <div className="flex items-center justify-between text-[11.5px] mb-1">
                      <span className="text-gray-500">{row.k}</span>
                      <span className="font-semibold text-gray-900">{row.v}</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full relative">
                      <div className={`absolute h-full rounded-full ${row.color}`} style={{ left: row.pos + '%', width: Math.max(row.w, 0.5) + '%' }}/>
                    </div>
                  </div>
                ))}
              </div>
              {verdict && (
                <div className={`mt-4 p-3 rounded-xl text-[12px] leading-relaxed ${verdict.tone === 'green' ? 'bg-green-50 text-green-800 border border-green-200' : verdict.tone === 'amber' ? 'bg-amber-50 text-amber-800 border border-amber-200' : 'bg-gray-50 text-gray-700 border border-gray-200'}`}>
                  {verdict.txt}
                </div>
              )}
              <div className="mt-3 text-[11px] text-gray-400">
                Based on {data.providers} active suppliers + historical assignments in {ctryName}.
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-[12.5px] text-gray-400">
              <div className="text-2xl mb-2">📊</div>
              No benchmark data for <strong>{lbl}</strong> in {ctryName} yet.
            </div>
          )
        )}

        {focusedBenefit && tab === 'providers' && (
          providers.length === 0 ? (
            <div className="text-center py-8 text-[12.5px] text-gray-400">
              <div className="text-2xl mb-2">🏢</div>
              No active providers found in {ctryName} for this service.
            </div>
          ) : (
            <div className="space-y-3">
              {providers.map(p => (
                <div key={p.name} className="border border-gray-200 rounded-xl p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[12.5px] font-semibold text-gray-900 flex-1">{p.name}</span>
                    {p.verified && <span className="text-[9px] font-bold text-blue-600 bg-blue-100 px-1.5 py-0.5 rounded">VERIFIED</span>}
                    {p.preferred && <span className="text-[9px] font-bold text-green-600 bg-green-100 px-1.5 py-0.5 rounded">PREFERRED</span>}
                  </div>
                  <div className="flex items-center gap-2 text-[11.5px] text-gray-500 mb-2">
                    <span className="text-yellow-500">{'★'.repeat(Math.round(p.rating))}</span>
                    <span>{p.rating} ({p.reviews})</span>
                    <span>·</span>
                    <span className="font-medium text-gray-700">{p.price}</span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {p.tags.map(t => <span key={t} className="text-[10px] bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">{t}</span>)}
                  </div>
                </div>
              ))}
            </div>
          )
        )}

        {focusedBenefit && tab === 'historical' && (
          <div>
            <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Selection rate</div>
            <p className="text-[12.5px] text-gray-600 mb-4">Of <strong>12 employees</strong> who had this benefit available in {ctryName}, <strong>9 (75%)</strong> used it.</p>
            <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Actual spend distribution</div>
            <div className="space-y-1 mb-4">
              {[['Min','€1,400/mo'],['Median','€2,200/mo'],['Max','€3,600/mo']].map(([k,v]) => (
                <div key={k} className="flex items-center justify-between text-[12px]">
                  <span className="text-gray-500">{k}</span><span className="font-semibold text-gray-900">{v}</span>
                </div>
              ))}
              {yourCap != null && (
                <div className="flex items-center justify-between text-[12px]">
                  <span className="text-gray-500">Your cap</span>
                  <span className="font-semibold text-green-600">{cur}{yourCap.toLocaleString()} · ≈{Math.min(99,Math.round((yourCap/3000)*70))}% of cases</span>
                </div>
              )}
            </div>
            <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Last 5 selections (anonymised)</div>
            <div className="space-y-2">
              {[
                { ref:'Employee A', dest:'Berlin',    type:'Long-term', sel:'€2,100/mo' },
                { ref:'Employee B', dest:'Munich',    type:'Long-term', sel:'€2,800/mo' },
                { ref:'Employee C', dest:'Hamburg',   type:'Permanent', sel:'€1,700/mo' },
                { ref:'Employee D', dest:'Berlin',    type:'Long-term', sel:'€2,400/mo' },
                { ref:'Employee E', dest:'Frankfurt', type:'Long-term', sel:'€2,200/mo' },
              ].map(s => (
                <div key={s.ref} className="text-[11.5px] text-gray-500 border-b border-gray-100 pb-1.5">
                  <span className="font-semibold text-gray-700">{s.ref}</span> · {s.dest} · {s.type} · <span className="font-mono text-gray-800">{s.sel}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {focusedBenefit && data && yourCap != null && (
        <div className="p-4 border-t border-gray-200">
          <Button unstyled onClick={() => onApplyMedian(data.avg)}
            className="w-full py-2 text-[12.5px] font-semibold text-blue-700 bg-blue-50 border border-blue-200 rounded-xl hover:bg-blue-100 transition-colors">
            Apply median ({cur}{data.avg.toLocaleString()}) to this tier
          </Button>
          <div className="mt-2 text-[10.5px] text-gray-400 text-center">Benchmarks are indicative, sourced from the ReloPass network. Not legal or tax advice.</div>
        </div>
      )}
    </div>
  );
}
