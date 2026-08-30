/**
 * [P2-3] FieldRow — renders a single form field with its value input.
 *
 * - AI-filled fields show a blue "AI" badge with a tooltip (confidence %).
 * - Missing required fields show a red outline on the input.
 * - `requires_original=true` fields show a document upload placeholder
 *   (full upload lands in P3-2).
 * - Supports field types: text, date, select, boolean, number, and a fallback
 *   textarea for everything else.
 */
import React, { useEffect, useState } from 'react';
import { Checkbox } from '../../../components/antigravity/Checkbox';
import { Input } from '../../../components/antigravity/Input';
import { Button } from '../../../components/antigravity/Button';
import { Badge } from '../../../components/antigravity/Badge';
import { translateText } from '../../../api/translation';
import type { FieldValueItem } from '../../../api/formEditor';

/** Display language for LABELS only. Field values are always rendered verbatim
 *  (the toggle never translates a name, passport number, D-number, or date).
 *
 *  Anything other than 'en' is a template's `source_language` — the language the
 *  authority's own form is in, not a user preference. Adding a language means adding it
 *  here and to SUPPORTED_LABEL_LANGUAGES in backend/app/services/localised_labels.py. */
export type FieldLang = 'en' | 'nb' | 'de' | 'fr';

interface FieldRowProps {
  field: FieldValueItem;
  /** Current live value (may differ from field.value if user has typed) */
  liveValue: string;
  onValueChange: (fieldId: string, value: string) => void;
  /** Highlight as missing required */
  showMissing?: boolean;
  /** Label display language — 'nb' shows label_nb when present. Values stay verbatim. */
  lang?: FieldLang;
}

// ---------------------------------------------------------------------------
// Source badge — provenance of a prefilled value (case_form_field_values.source)
// ---------------------------------------------------------------------------

const SOURCE_META: Record<string, { label: string; variant: 'success' | 'info' | 'warning' | 'neutral' }> = {
  intake_profile: { label: 'From your intake', variant: 'info' },
  contract: { label: 'From your contract', variant: 'info' },
  banking: { label: 'From your bank details', variant: 'info' },
  passport_ocr: { label: 'From your passport scan', variant: 'success' },
  prior_form: { label: 'From a form you completed', variant: 'success' },
  authority_lookup: { label: 'From an authority lookup', variant: 'info' },
  ai_inference: { label: 'AI suggestion', variant: 'warning' },
};

function SourceBadge({ source }: { source: string }) {
  const meta = SOURCE_META[source];
  if (!meta) return null;
  return (
    <Badge variant={meta.variant} size="sm">
      {meta.label}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Translatable label (AIQ-1757) — LABELS ONLY, never values.
//
// Renders a field label in the form's official language. A statically-seeded
// translation (label_nb) is authoritative and shown instantly; only labels
// WITHOUT one fall through to the /api/translate service (domain='ui', cached),
// degrading to the original English label on any error (503). A field VALUE is
// never passed here — only the label string, which carries no PII.
// ---------------------------------------------------------------------------

function TranslatableLabel({ text, tgt }: { text: string; tgt: string }) {
  const [translated, setTranslated] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!text || !tgt || tgt === 'en') {
      setTranslated(null);
      return;
    }
    translateText({ text, src: 'en', tgt, domain: 'ui' })
      .then((r) => {
        if (!cancelled) setTranslated(r.text);
      })
      .catch(() => {
        if (!cancelled) setTranslated(null); // degrade to the original label
      });
    return () => {
      cancelled = true;
    };
  }, [text, tgt]);

  return <>{translated ?? text}</>;
}

// ---------------------------------------------------------------------------
// AI badge
// ---------------------------------------------------------------------------

function AiBadge({
  confidence,
  prefillSource,
}: {
  confidence: number | null;
  prefillSource: string | null;
}) {
  const [open, setOpen] = useState(false);
  const pct = confidence !== null ? Math.round(confidence * 100) : null;

  // Human-readable data source from the prefill_source key
  // e.g. "profile.legal_full_name" → "Employee profile"
  //      "family.spouse.legal_full_name" → "Family data (spouse)"
  //      "contract.employer_name" → "Contract data"
  function humaniseSource(src: string | null): string | null {
    if (!src) return null;
    if (src.startsWith('profile.')) return 'Employee profile';
    if (src.startsWith('family.spouse.')) return 'Family data (spouse)';
    if (src.startsWith('family.child.')) return 'Family data (child)';
    if (src.startsWith('family.')) return 'Family data';
    if (src.startsWith('contract.')) return 'Contract data';
    if (src.startsWith('intake.')) return 'Intake answers';
    if (src.startsWith('person.')) return 'Person record';
    return src;
  }

  const sourceLabel = humaniseSource(prefillSource);

  return (
    <span className="relative inline-block">
      <Button unstyled
        type="button"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-100 text-blue-700 border border-blue-200 cursor-default"
        aria-label={`AI pre-filled${pct !== null ? ` · ${pct}% confidence` : ''}${sourceLabel ? ` · from ${sourceLabel}` : ''}`}
      >
        AI
      </Button>
      {open && (
        <div className="absolute z-10 bottom-full mb-1.5 left-1/2 -translate-x-1/2 rounded bg-slate-800 text-white text-xs px-2.5 py-1.5 shadow-lg pointer-events-none min-w-max max-w-[220px]">
          <div className="font-medium">Pre-filled by AI</div>
          {sourceLabel && (
            <div className="text-slate-500 mt-0.5">Source: {sourceLabel}</div>
          )}
          {pct !== null && (
            <div className="text-slate-500 mt-0.5">Confidence: {pct}%</div>
          )}
          <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-800" />
        </div>
      )}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Input controls by field_type
// ---------------------------------------------------------------------------

interface InputProps {
  field: FieldValueItem;
  value: string;
  onChange: (v: string) => void;
  hasError: boolean;
}

function FieldInput({ field, value, onChange, hasError }: InputProps) {
  const base =
    'w-full rounded border px-2.5 py-1.5 text-sm text-slate-900 bg-white ' +
    'focus:outline-none focus:ring-1 focus:ring-[#0b2b43] focus:border-[#0b2b43] transition-colors ';
  const errorClass = 'border-rose-400 bg-rose-50 ';
  const normalClass = 'border-slate-300 ';
  const cls = base + (hasError ? errorClass : normalClass);

  // Fields that need the original physical document still show their known
  // value (e.g. a prefilled passport number, verbatim) plus a reminder to bring
  // the original — the value must not be hidden behind an upload stub.
  const originalNote = field.requires_original ? (
    <p className="mt-1 text-xs text-slate-500 italic">
      Bring the original document to your appointment.
    </p>
  ) : null;

  let control: React.ReactNode;
  if (field.field_type === 'boolean') {
    control = (
      <label className="inline-flex items-center gap-2 cursor-pointer">
        <Checkbox
          checked={value === 'true'}
          onChange={(e) => onChange(e.target.checked ? 'true' : 'false')}
          className="w-4 h-4 rounded border-slate-300 text-[#0b2b43] focus:ring-[#0b2b43]"
        />
        <span className="text-sm text-slate-700">{value === 'true' ? 'Yes' : 'No'}</span>
      </label>
    );
  } else if (field.field_type === 'select' && field.options && field.options.length > 0) {
    control = (
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cls}
      >
        <option value="">— select —</option>
        {field.options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    );
  } else if (field.field_type === 'date') {
    control = (
      <Input unstyled type="date" value={value} onChange={(v) => onChange(v)} className={cls} />
    );
  } else if (field.field_type === 'number') {
    control = (
      <Input unstyled type="number" value={value} onChange={(v) => onChange(v)} className={cls} />
    );
  } else {
    control = (
      <Input unstyled
        type="text"
        value={value}
        onChange={(v) => onChange(v)}
        placeholder={field.required ? 'Required' : 'Optional'}
        className={cls}
      />
    );
  }

  return (
    <>
      {control}
      {originalNote}
    </>
  );
}

// ---------------------------------------------------------------------------
// FieldRow component
// ---------------------------------------------------------------------------

export const FieldRow: React.FC<FieldRowProps> = ({
  field,
  liveValue,
  onValueChange,
  showMissing = false,
  lang = 'en',
}) => {
  // A determination a regulated professional must make — never pre-filled, never editable.
  const isConsult = field.consult_professional === true;
  const hasValue = (liveValue ?? '').trim() !== '';
  // Nothing sourced the value and it isn't a consult determination → the
  // employee must supply it.
  const isNeedsInput = !isConsult && !hasValue && !field.source;
  const isAiFilled = field.filled_by === 'ai';
  const isMissing =
    !isConsult && showMissing && field.required && !hasValue;

  // Labels translate for comprehension; VALUES never do (verbatim identifiers).
  // A seeded label wins (authoritative, instant); labels without one fall through to the
  // translation service via TranslatableLabel, which degrades to English on a 503.
  //
  // `lang` is the template's own language, so the translation target follows it rather than
  // being hardcoded — that hardcoded 'nb' is why a label_de would have been ignored.
  // label_nb is read only as a fallback, for a response from a backend predating
  // label_localised.
  const seededLabel = field.label_localised ?? (lang === 'nb' ? field.label_nb : null);
  const labelNode: React.ReactNode =
    lang === 'en'
      ? field.label
      : (seededLabel ? seededLabel : <TranslatableLabel text={field.label} tgt={lang} />);

  return (
    <div className={`rounded-lg border px-4 py-3 transition-colors ${isConsult ? 'border-amber-200 bg-amber-50/40' : isMissing ? 'border-rose-300 bg-rose-50/40' : 'border-slate-200 bg-white hover:border-slate-300'}`}>
      {/* Label row */}
      <div className="flex items-center gap-2 mb-1.5">
        <label className="text-sm font-medium text-slate-800 flex-1 leading-snug">
          {labelNode}
          {field.required && !isConsult && (
            <span className="ml-0.5 text-rose-500" aria-label="required">*</span>
          )}
        </label>
        <div className="flex items-center gap-1.5 shrink-0">
          {isConsult ? (
            <Badge variant="warning" size="sm">Consult a professional</Badge>
          ) : (
            <>
              {field.source ? (
                <SourceBadge source={field.source} />
              ) : (
                isAiFilled && (
                  <AiBadge
                    confidence={field.ai_confidence}
                    prefillSource={field.prefill_source}
                  />
                )
              )}
              {isNeedsInput && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-rose-100 text-rose-700 border border-rose-200">
                  Needs input
                </span>
              )}
              {field.overridden && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-100 text-amber-700 border border-amber-200">
                  Edited
                </span>
              )}
              {field.reviewed && !field.overridden && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-100 text-emerald-700 border border-emerald-200">
                  Reviewed
                </span>
              )}
            </>
          )}
        </div>
      </div>

      {isConsult ? (
        // No value, no input — a regulated advisor determines this.
        <p className="text-xs text-amber-700 italic">
          A regulated advisor will determine this — ReloPass won&apos;t pre-fill it.
        </p>
      ) : (
        <>
          <FieldInput
            field={field}
            value={liveValue}
            onChange={(v) => onValueChange(field.field_id, v)}
            hasError={isMissing}
          />
          {isMissing && (
            <p className="mt-1 text-xs text-rose-600">This field is required.</p>
          )}
        </>
      )}

      {/* Guidance seeded on the template field. Rendered for consult fields too — a
          determination the employee can't fill still has a portal and a deadline. */}
      {field.note && (
        <p className="mt-1.5 text-xs leading-relaxed text-slate-600">{field.note}</p>
      )}
      {field.portal_url && (
        <a
          href={field.portal_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-accent-600 hover:text-accent-700 hover:underline focus:outline-none focus:ring-2 focus:ring-accent-500/40 rounded"
        >
          {portalLinkLabel(field.portal_url)}
          <span aria-hidden="true">→</span>
        </a>
      )}
    </div>
  );
};

/**
 * "https://www.skatteetaten.no/en/forms/d-number" → "Open in Skatteetaten".
 * Falls back to a generic label when the host can't be parsed, so a malformed
 * seeded URL degrades to a working link rather than throwing.
 */
function portalLinkLabel(url: string): string {
  try {
    const host = new URL(url).hostname.replace(/^www\./, '');
    const name = host.split('.')[0] || '';
    if (!name) return 'Open the official portal';
    return `Open in ${name.charAt(0).toUpperCase()}${name.slice(1)}`;
  } catch {
    return 'Open the official portal';
  }
}
