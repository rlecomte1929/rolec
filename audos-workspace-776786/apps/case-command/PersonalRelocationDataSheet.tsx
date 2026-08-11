// Personal Relocation Data Sheet — production view (Case Command · Data Sheet tab).
//
// Replaces the hardcoded UX prototypes (apps/FRNODataSheet, apps/
// CorridorDataSheetEngine) with a fully data-driven sheet: corridor steps and
// fields come from the requirement_entities / requirement_facts WorkspaceDB
// tables, values come from the live case data model (cases / persons /
// person_identities / case_facts) via lib/dataSheetBuilder.ts, and every field
// carries a provenance badge. The sheet itself is deliberately paper-white
// (validated in the prototypes) because it is a print-ready document.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { AlertTriangle, ChevronDown, ChevronRight, FileDown, Loader2, Pencil, RefreshCw } from 'lucide-react';
import {
  buildDataSheet,
  listDataSheetCases,
  listRequirementCorridors,
  saveDataSheetFieldValue,
} from '../../lib/dataSheetBuilder';
import type {
  DataSheetCaseSummary,
  DataSheetFieldValue,
  DataSheetSection,
  FieldSource,
  PersonalRelocationDataSheet as SheetModel,
} from '../../lib/datasheet-types';
import { ensureDataSheetSeed, GOLDEN_CASE_REF } from './datasheet-seed';

type Locale = 'en' | 'no';
type DisplayMode = 'full' | 'sparse';

// ── Badges ─────────────────────────────────────────────────────────────────

const BADGE_STYLE: Record<FieldSource, { label: string; bg: string; fg: string; border?: string }> = {
  intake: { label: 'intake', bg: '#D1FAE5', fg: '#065F46' },
  passport_ocr: { label: 'passport-ocr', bg: '#DBEAFE', fg: '#1E40AF' },
  prior_form: { label: 'prior-form', bg: '#EDE9FE', fg: '#5B21B6' },
  needs_input: { label: 'NEEDS INPUT', bg: '#FFEDD5', fg: '#9A3412', border: '#FB923C' },
  consult_professional: { label: 'CONSULT PROFESSIONAL', bg: '#FEF3C7', fg: '#92400E', border: '#F59E0B' },
};

function SourceBadge({ source }: { source: FieldSource }) {
  const s = BADGE_STYLE[source];
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        fontSize: 11,
        fontWeight: 600,
        lineHeight: 1,
        padding: '4px 8px',
        borderRadius: 999,
        whiteSpace: 'nowrap',
        background: s.bg,
        color: s.fg,
        border: s.border ? `1px solid ${s.border}` : 'none',
      }}
    >
      {source === 'needs_input' && <Pencil size={11} strokeWidth={2.5} />}
      {source === 'consult_professional' && <AlertTriangle size={11} strokeWidth={2.5} />}
      {s.label}
    </span>
  );
}

const LEGEND: { source: FieldSource; text: string }[] = [
  { source: 'intake', text: 'value entered at case intake' },
  { source: 'passport_ocr', text: 'read from the uploaded passport scan' },
  { source: 'prior_form', text: 'carried over from a previous case' },
  { source: 'needs_input', text: 'you must provide this value — click the cell to fill it in' },
  { source: 'consult_professional', text: 'a regulated tax, legal, or social security advisor must determine this — ReloPass never fills it' },
];

function ToggleGroup<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div style={{ display: 'flex', border: '1px solid #E5E7EB', borderRadius: 8, overflow: 'hidden', flexShrink: 0 }}>
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          style={{
            padding: '6px 12px',
            fontSize: 12.5,
            fontWeight: 700,
            border: 'none',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            background: value === o.value ? '#111827' : '#FFFFFF',
            color: value === o.value ? '#FFFFFF' : '#6B7280',
          }}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ── Field row ──────────────────────────────────────────────────────────────

function FieldRow({
  sectionId,
  field,
  locale,
  isFirst,
  saving,
  onSave,
}: {
  sectionId: string;
  field: DataSheetFieldValue;
  locale: Locale;
  isFirst: boolean;
  saving: boolean;
  onSave: (factKey: string, value: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [expanded, setExpanded] = useState(false);

  const label = locale === 'no' && field.label_no ? field.label_no : field.label_en;

  const commit = () => {
    setEditing(false);
    if (draft.trim()) onSave(field.fact_key, draft);
  };

  let valueCell: ReactNode;
  if (field.is_consult_professional) {
    valueCell = (
      <button
        onClick={() => setExpanded((v) => !v)}
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 6,
          width: '100%',
          textAlign: 'left',
          border: 'none',
          background: 'transparent',
          padding: 0,
          cursor: 'pointer',
          color: '#92400E',
          fontSize: 13,
        }}
      >
        {expanded ? (
          <ChevronDown size={14} style={{ flexShrink: 0, marginTop: 2 }} />
        ) : (
          <ChevronRight size={14} style={{ flexShrink: 0, marginTop: 2 }} />
        )}
        {expanded ? (
          <span style={{ lineHeight: 1.5, fontStyle: 'italic' }}>{field.guidance}</span>
        ) : (
          <span style={{ fontWeight: 600 }}>See guidance</span>
        )}
      </button>
    );
  } else if (field.source === 'needs_input') {
    valueCell = editing ? (
      <input
        autoFocus
        type="text"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit();
          if (e.key === 'Escape') setEditing(false);
        }}
        placeholder={locale === 'no' ? 'Skriv her…' : 'Type here…'}
        style={{
          width: '100%',
          fontSize: 14,
          padding: '6px 10px',
          border: '1px solid #FB923C',
          borderRadius: 6,
          outline: 'none',
          background: '#FFF7ED',
          color: '#111827',
          boxSizing: 'border-box',
        }}
      />
    ) : (
      <div>
        <button
          onClick={() => {
            if (!saving && !field.is_placeholder) {
              setDraft('');
              setEditing(true);
            }
          }}
          disabled={saving || field.is_placeholder}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            width: '100%',
            textAlign: 'left',
            fontSize: 14,
            padding: '6px 10px',
            border: '1px dashed #FB923C',
            borderRadius: 6,
            background: '#FFF7ED',
            color: '#B45309',
            cursor: field.is_placeholder ? 'default' : 'text',
            boxSizing: 'border-box',
            opacity: saving ? 0.6 : 1,
          }}
        >
          {saving ? <Loader2 size={13} className="prds-spin" style={{ flexShrink: 0 }} /> : <Pencil size={13} style={{ flexShrink: 0, opacity: 0.6 }} />}
          {saving
            ? locale === 'no'
              ? 'Lagrer…'
              : 'Saving…'
            : field.is_placeholder
              ? locale === 'no'
                ? 'Ikke definert ennå'
                : 'Not yet defined'
              : locale === 'no'
                ? 'Klikk for å fylle ut'
                : 'Click to fill in'}
        </button>
        {field.hint && (
          <div style={{ marginTop: 4, fontSize: 12, color: '#9A3412', lineHeight: 1.4 }}>{field.hint}</div>
        )}
      </div>
    );
  } else {
    valueCell = (
      <div>
        <div style={{ fontSize: 14, color: '#111827' }}>{field.value}</div>
        {field.confidence < 1 && (
          <div style={{ marginTop: 2, fontSize: 11, color: '#9CA3AF' }}>
            confidence {Math.round(field.confidence * 100)}% — verify against the original document
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      key={`${sectionId}:${field.fact_key}`}
      style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(140px, 4fr) minmax(170px, 6fr) minmax(110px, auto)',
        gap: 12,
        alignItems: 'start',
        padding: '9px 14px',
        borderTop: isFirst ? 'none' : '1px solid #F3F4F6',
      }}
    >
      <div style={{ fontSize: 13, color: '#6B7280', fontWeight: 500, paddingTop: 4 }}>{label}</div>
      <div>{valueCell}</div>
      <div style={{ textAlign: 'right', paddingTop: 2 }}>
        <SourceBadge source={field.source} />
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export default function PersonalRelocationDataSheet() {
  const [phase, setPhase] = useState<'seeding' | 'loading' | 'ready' | 'error'>('seeding');
  const [error, setError] = useState<string | null>(null);
  const [cases, setCases] = useState<DataSheetCaseSummary[]>([]);
  const [corridors, setCorridors] = useState<string[]>([]);
  const [caseId, setCaseId] = useState<number | null>(null);
  const [corridor, setCorridor] = useState<string>('FR-NO');
  const [sheet, setSheet] = useState<SheetModel | null>(null);
  const [locale, setLocale] = useState<Locale>('en');
  const [displayMode, setDisplayMode] = useState<DisplayMode>('full');
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const initDone = useRef(false);

  // Initial load: seed (idempotent) → case list → golden case sheet.
  const runInit = useCallback(async () => {
    setPhase('seeding');
    try {
      await ensureDataSheetSeed();
      const [caseList, corridorList] = await Promise.all([
        listDataSheetCases(),
        listRequirementCorridors(),
      ]);
      setCases(caseList);
      setCorridors(corridorList);
      initDone.current = true;
      const golden = caseList.find((c) => c.case_ref === GOLDEN_CASE_REF) ?? caseList[0];
      if (golden) {
        setCaseId(golden.case_id);
        setCorridor(
          corridorList.includes(golden.corridor) ? golden.corridor : corridorList[0] ?? golden.corridor,
        );
      } else {
        setPhase('ready'); // no cases at all — empty state
      }
    } catch (e: any) {
      setError(e?.message ?? String(e));
      setPhase('error');
    }
  }, []);

  useEffect(() => {
    void runInit();
    // ensureDataSheetSeed shares one promise per page load, so a double mount
    // (e.g. StrictMode) cannot double-seed.
  }, [runInit]);

  const rebuild = useCallback(async (cid: number, cor: string) => {
    setPhase('loading');
    try {
      const built = await buildDataSheet(cid, cor);
      setSheet(built);
      setPhase('ready');
    } catch (e: any) {
      setError(e?.message ?? String(e));
      setPhase('error');
    }
  }, []);

  useEffect(() => {
    if (caseId != null) void rebuild(caseId, corridor);
  }, [caseId, corridor, rebuild]);

  const handleSelectCase = (id: number) => {
    setCaseId(id);
    const selected = cases.find((c) => c.case_id === id);
    if (selected && corridors.includes(selected.corridor)) setCorridor(selected.corridor);
  };

  const handleSave = async (factKey: string, value: string) => {
    if (caseId == null) return;
    setSavingKey(factKey);
    try {
      await saveDataSheetFieldValue(caseId, factKey, value);
      await rebuild(caseId, corridor);
    } catch (e: any) {
      setError(e?.message ?? String(e));
      setPhase('error');
    } finally {
      setSavingKey(null);
    }
  };

  const visibleSections = useMemo((): DataSheetSection[] => {
    if (!sheet) return [];
    if (displayMode === 'full') return sheet.sections;
    // Sparse: gaps only — NEEDS INPUT and CONSULT PROFESSIONAL fields.
    return sheet.sections
      .map((s) => ({
        ...s,
        fields: s.fields.filter(
          (f) => f.source === 'needs_input' || f.source === 'consult_professional',
        ),
      }))
      .filter((s) => s.fields.length > 0);
  }, [sheet, displayMode]);

  const generatedDate = sheet ? sheet.generated_at.slice(0, 10) : '';

  if (phase === 'error') {
    return (
      <div className="p-6">
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
          <p className="font-semibold mb-1">Could not load the data sheet</p>
          <p className="mb-3">{error}</p>
          <button
            onClick={() => {
              setError(null);
              if (initDone.current && caseId != null) {
                void rebuild(caseId, corridor);
              } else {
                void runInit();
              }
            }}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/20 text-red-200 text-xs font-medium"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Retry
          </button>
        </div>
      </div>
    );
  }

  if (phase === 'seeding' || (phase === 'loading' && !sheet)) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3 text-[var(--space-text-secondary)]">
        <Loader2 className="w-6 h-6 prds-spin" />
        <p className="text-sm">
          {phase === 'seeding' ? 'Preparing corridor requirements…' : 'Building data sheet…'}
        </p>
        <style>{`.prds-spin { animation: prds-rotate 1s linear infinite; } @keyframes prds-rotate { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (!sheet) {
    return (
      <div className="p-6 text-sm text-[var(--space-text-secondary)]">
        No relocation cases found — create a case first, then generate its data sheet here.
      </div>
    );
  }

  return (
    <div
      className="prds-root"
      style={{
        position: 'relative',
        minHeight: '100%',
        background: '#FFFFFF',
        fontFamily: "'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
        color: '#111827',
      }}
    >
      <style>{`
        .prds-spin { animation: prds-rotate 1s linear infinite; }
        @keyframes prds-rotate { to { transform: rotate(360deg); } }
        @media print {
          .prds-no-print { display: none !important; }
          .prds-root { overflow: visible !important; height: auto !important; }
          .prds-section { break-inside: avoid; }
        }
      `}</style>

      <div style={{ maxWidth: 880, margin: '0 auto', padding: '24px 20px 64px' }}>
        {/* ── Header ── */}
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12, paddingBottom: 14, borderBottom: '2px solid #111827' }}>
          <div style={{ minWidth: 220 }}>
            <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.02em' }}>ReloPass</div>
            <div style={{ fontSize: 13, color: '#6B7280' }}>Personal Relocation Data Sheet</div>
          </div>
          <div style={{ fontSize: 12, color: '#6B7280', textAlign: 'right' }}>
            <div style={{ fontWeight: 700, color: '#111827' }}>
              {sheet.case_ref} · {sheet.employee_name}
            </div>
            <div>
              {sheet.corridor_label} · Generated {generatedDate}
            </div>
            <div style={{ marginTop: 2, fontWeight: 600, color: sheet.needs_input_count > 0 ? '#B45309' : '#065F46' }}>
              {sheet.completion_pct}% complete
              {sheet.needs_input_count > 0 ? ` — ${sheet.needs_input_count} field${sheet.needs_input_count === 1 ? '' : 's'} need input` : ' — all fields provided'}
            </div>
          </div>
        </div>

        {/* ── Controls ── */}
        <div className="prds-no-print" style={{ marginTop: 14, display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 10 }}>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12.5, fontWeight: 600, color: '#374151' }}>
              Case
              <select
                value={caseId ?? ''}
                onChange={(e) => handleSelectCase(Number(e.target.value))}
                style={{ fontSize: 13, fontWeight: 600, padding: '6px 10px', border: '1px solid #E5E7EB', borderRadius: 8, background: '#FFFFFF', color: '#111827', cursor: 'pointer', maxWidth: 260 }}
              >
                {cases.map((c) => (
                  <option key={c.case_id} value={c.case_id}>
                    {c.case_ref} · {c.employee_name}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12.5, fontWeight: 600, color: '#374151' }}>
              Corridor
              <select
                value={corridor}
                onChange={(e) => setCorridor(e.target.value)}
                style={{ fontSize: 13, fontWeight: 600, padding: '6px 10px', border: '1px solid #E5E7EB', borderRadius: 8, background: '#FFFFFF', color: '#111827', cursor: 'pointer' }}
              >
                {corridors.map((c) => (
                  <option key={c} value={c}>
                    {c.replace('-', ' → ')}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
            <ToggleGroup<DisplayMode>
              options={[{ value: 'full', label: 'Full data' }, { value: 'sparse', label: 'Sparse' }]}
              value={displayMode}
              onChange={setDisplayMode}
            />
            <ToggleGroup<Locale>
              options={[{ value: 'en', label: 'EN' }, { value: 'no', label: 'NO' }]}
              value={locale}
              onChange={setLocale}
            />
            <button
              onClick={() => window.print()}
              title="No PDF overlay engine exists in this workspace yet — exports via the browser print dialog (Save as PDF)."
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 14px', background: '#111827', color: '#FFFFFF', fontSize: 12.5, fontWeight: 700, border: 'none', borderRadius: 8, cursor: 'pointer' }}
            >
              <FileDown size={14} /> Export PDF
            </button>
          </div>
        </div>

        {/* ── Regulatory warning banner (always visible) ── */}
        <div style={{ marginTop: 14, background: '#FEF3C7', border: '1px solid #F59E0B', borderRadius: 8, padding: '12px 16px', fontSize: 13, color: '#92400E', lineHeight: 1.5, display: 'flex', gap: 10 }}>
          <AlertTriangle size={18} color="#D97706" style={{ flexShrink: 0, marginTop: 1 }} />
          <span>
            Fields marked <strong>Consult professional</strong> contain tax, social security, or legal determinations that ReloPass cannot make. A regulated advisor must confirm these before payroll or registration is finalised.
          </span>
        </div>

        {/* ── Sparse mode explainer ── */}
        {displayMode === 'sparse' && (
          <div className="prds-no-print" style={{ marginTop: 12, background: '#F9FAFB', border: '1px dashed #D1D5DB', borderRadius: 8, padding: '10px 14px', fontSize: 12.5, color: '#6B7280', lineHeight: 1.5 }}>
            <strong style={{ color: '#374151' }}>Sparse view</strong> — showing only the gaps: fields that still need your input and determinations that require a regulated professional. Switch to “Full data” to see every field including the pre-filled ones.
          </div>
        )}

        {/* ── Refresh overlay while rebuilding ── */}
        {phase === 'loading' && (
          <div className="prds-no-print" style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, color: '#6B7280' }}>
            <Loader2 size={14} className="prds-spin" /> Rebuilding…
          </div>
        )}

        {/* ── Sections ── */}
        {visibleSections.length === 0 && (
          <div style={{ marginTop: 20, padding: '14px 16px', border: '1px dashed #D1D5DB', borderRadius: 8, fontSize: 13, color: '#6B7280' }}>
            {displayMode === 'sparse'
              ? 'No gaps — every field is filled and no professional determinations are pending for this corridor.'
              : `No steps found in the requirements database for corridor ${corridor}.`}
          </div>
        )}
        {visibleSections.map((section, idx) => {
          const title = locale === 'no' && section.step_name_no ? section.step_name_no : section.step_name_en;
          const stepNumber = sheet.sections.findIndex((s) => s.step_id === section.step_id) + 1;
          return (
            <div key={section.step_id} className="prds-section" style={{ marginTop: 20, background: '#F9FAFB', border: '1px solid #E5E7EB', borderRadius: 8, padding: 16 }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 15, fontWeight: 700 }}>
                  {stepNumber > 0 ? stepNumber : idx + 1} · {title}
                </h2>
                <div style={{ marginTop: 2, fontSize: 12, color: '#6B7280' }}>
                  {section.authority ? `${section.authority} · ` : ''}
                  {section.official_source_url}
                </div>
                {section.official_process_note && (
                  <div style={{ marginTop: 10, background: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#1E3A5F', lineHeight: 1.5 }}>
                    {section.official_process_note}
                  </div>
                )}
              </div>

              <div style={{ marginTop: 12, background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, overflow: 'hidden' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'minmax(140px, 4fr) minmax(170px, 6fr) minmax(110px, auto)', gap: 12, padding: '8px 14px', background: '#F3F4F6', fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#9CA3AF' }}>
                  <div>{locale === 'no' ? 'Felt' : 'Field'}</div>
                  <div>{locale === 'no' ? 'Verdi' : 'Value'}</div>
                  <div style={{ textAlign: 'right' }}>{locale === 'no' ? 'Kilde' : 'Source'}</div>
                </div>
                {section.fields.map((f, i) => (
                  <FieldRow
                    key={`${section.step_id}:${f.fact_key}`}
                    sectionId={section.step_id}
                    field={f}
                    locale={locale}
                    isFirst={i === 0}
                    saving={savingKey === f.fact_key}
                    onSave={handleSave}
                  />
                ))}
              </div>
            </div>
          );
        })}

        {/* ── Badge legend ── */}
        <div style={{ marginTop: 24, borderTop: '1px solid #E5E7EB', paddingTop: 14 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#6B7280', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
            Badge legend
          </div>
          <div style={{ display: 'grid', gap: 6 }}>
            {LEGEND.map((item) => (
              <div key={item.source} style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: 12, alignItems: 'center', fontSize: 12, color: '#6B7280' }}>
                <div>
                  <SourceBadge source={item.source} />
                </div>
                <div>= {item.text}</div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 16, fontSize: 11, color: '#9CA3AF', lineHeight: 1.5 }}>
            ReloPass prepares and organises your official process — it never submits forms on your behalf and never makes legal, tax, or social security determinations. Values shown are sourced from your case record; verify against original documents before submission.
          </div>
        </div>
      </div>
    </div>
  );
}
