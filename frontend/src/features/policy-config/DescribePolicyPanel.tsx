/**
 * AIQ-1415 — Natural-Language Policy Builder panel.
 *
 * HR types a plain-English policy description; we call the read-only
 * `POST /api/hr/policy-config/generate` endpoint (Claude → config-matrix candidate),
 * preview the generated benefits, and save ONLY on explicit approval via the existing
 * draft path (ensure_draft → put_draft). Confirm-before-save by construction: generate
 * never persists, and the generated matrix always lands as an editable DRAFT — never
 * auto-published.
 */
import { useState } from 'react';
import { Sparkles, PencilLine } from 'lucide-react';
import { Alert, Button, Card } from '../../components/antigravity';
import { policyConfigMatrixAPI } from '../../api/client';

interface GenBenefit {
  benefit_key: string;
  benefit_label: string;
  category: string;
  covered: boolean;
  value_type: string;
  amount_value: number | null;
  currency_code: string | null;
  percentage_value: number | null;
  unit_frequency: string;
  notes: string | null;
}
interface GenCategory {
  category_key: string;
  benefits: GenBenefit[];
}
interface GenResult {
  categories: GenCategory[];
  warnings: string[];
  generated: boolean;
  covered_count: number;
}

const CATEGORY_LABELS: Record<string, string> = {
  pre_assignment_support: 'Pre-assignment support',
  relocation_assistance: 'Relocation assistance',
  compensation_allowances: 'Compensation & allowances',
  family_support_education: 'Family support & education',
  leave_repatriation: 'Leave & repatriation',
  tax_payroll: 'Tax & payroll',
};
const FREQ_SUFFIX: Record<string, string> = {
  monthly: ' / month',
  yearly: ' / year',
  per_trip: ' / trip',
  per_day: ' / day',
  per_dependent: ' / dependent',
};

function valueLabel(b: GenBenefit): string {
  if (b.value_type === 'currency' && b.amount_value != null) {
    const cur = b.currency_code ? `${b.currency_code} ` : '';
    return `${cur}${b.amount_value.toLocaleString()}${FREQ_SUFFIX[b.unit_frequency] ?? ''}`;
  }
  if (b.value_type === 'percentage' && b.percentage_value != null) return `${b.percentage_value}%`;
  if (b.value_type === 'text' && b.notes) return b.notes;
  return 'Included';
}

function errMessage(err: unknown): string {
  const data =
    err && typeof err === 'object' && 'response' in err
      ? (err as { response?: { status?: number; data?: { detail?: { code?: string; message?: string } } } }).response
      : null;
  const detail = data?.data?.detail;
  if (data?.status === 403) return "The natural-language policy builder isn't enabled for your account yet.";
  if (detail?.message) return detail.message;
  return 'Something went wrong. Please try again.';
}

const PLACEHOLDER =
  "e.g. We offer a lump-sum relocation allowance plus 3 months of temporary housing for domestic moves, " +
  'and a full package — shipment of goods, temporary living, tax equalisation, and spouse support — for ' +
  'international assignments.';

export function DescribePolicyPanel({ onSavedGoToBuilder }: { onSavedGoToBuilder?: () => void }) {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GenResult | null>(null);
  const [saved, setSaved] = useState(false);

  const generate = async () => {
    setError(null);
    setResult(null);
    setSaved(false);
    setLoading(true);
    try {
      const raw = (await policyConfigMatrixAPI.hrGenerate(text)) as unknown as GenResult;
      setResult(raw);
      if (!raw.generated) setError(raw.warnings?.[0] ?? 'No policy could be generated from that description.');
    } catch (err) {
      setError(errMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const approve = async () => {
    if (!result) return;
    setSaving(true);
    setError(null);
    try {
      const draft = await policyConfigMatrixAPI.hrPostDraft();
      await policyConfigMatrixAPI.hrPutDraft({
        policy_version: draft.policy_version,
        effective_date: draft.effective_date,
        categories: result.categories,
      });
      setSaved(true);
    } catch (err) {
      setError(errMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const coveredByCategory = (result?.categories ?? [])
    .map((c) => ({ key: c.category_key, covered: c.benefits.filter((b) => b.covered) }))
    .filter((c) => c.covered.length > 0);

  return (
    <div className="space-y-4">
      <Card padding="lg">
        <div className="flex items-center gap-2 text-[#0b2b43]">
          <Sparkles className="h-5 w-5 text-accent-600" aria-hidden />
          <h2 className="text-lg font-semibold">Describe your policy</h2>
        </div>
        <p className="text-sm text-slate-600 mt-1">
          Write what you offer in plain English. We&rsquo;ll turn it into a configured draft you can review, edit,
          and publish — nothing is saved until you approve it.
        </p>
        <label htmlFor="nlpb-text" className="sr-only">
          Policy description
        </label>
        <textarea
          id="nlpb-text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={5}
          placeholder={PLACEHOLDER}
          className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-[#0b2b43] focus:border-accent-500 focus:outline-none focus:ring-1 focus:ring-accent-500"
        />
        <div className="mt-3 flex items-center gap-3">
          <Button onClick={generate} disabled={loading || saving || !text.trim()}>
            {loading ? 'Generating…' : 'Generate policy'}
          </Button>
          <span className="text-xs text-slate-500">You&rsquo;ll review everything before it&rsquo;s saved.</span>
        </div>
      </Card>

      {error && <Alert variant="error">{error}</Alert>}

      {saved && (
        <Alert variant="success">
          Saved as a draft. Open the Policy builder to review the values and publish when you&rsquo;re ready.
          {onSavedGoToBuilder && (
            <div className="mt-2">
              <Button size="sm" onClick={onSavedGoToBuilder}>
                <PencilLine className="h-4 w-4 mr-1.5" aria-hidden /> Open Policy builder
              </Button>
            </div>
          )}
        </Alert>
      )}

      {result?.generated && !saved && (
        <Card padding="lg">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold text-[#0b2b43]">Generated policy — review before saving</h3>
              <p className="text-sm text-slate-600 mt-0.5">
                {result.covered_count} benefit{result.covered_count === 1 ? '' : 's'} configured. Benefits you
                didn&rsquo;t mention are left as not covered — you can adjust everything in the builder after saving.
              </p>
            </div>
          </div>

          {result.warnings.length > 0 && (
            <Alert variant="warning" className="mt-3">
              <ul className="list-disc pl-5 text-sm">
                {result.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </Alert>
          )}

          {coveredByCategory.length === 0 ? (
            <p className="text-sm text-slate-600 mt-3">
              No benefits were detected as offered. Try describing the specific allowances and services you provide.
            </p>
          ) : (
            <div className="mt-4 space-y-4">
              {coveredByCategory.map((c) => (
                <div key={c.key}>
                  <div className="text-sm font-medium text-[#0b2b43]">{CATEGORY_LABELS[c.key] ?? c.key}</div>
                  <ul className="mt-1 divide-y divide-slate-100 rounded-lg border border-slate-200">
                    {c.covered.map((b) => (
                      <li key={b.benefit_key} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                        <span className="text-[#0b2b43]">{b.benefit_label}</span>
                        <span className="text-slate-600">{valueLabel(b)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}

          <div className="mt-5 flex items-center gap-3 border-t border-slate-200 pt-4">
            <Button onClick={approve} disabled={saving}>
              {saving ? 'Saving…' : 'Approve & save as draft'}
            </Button>
            <Button variant="outline" onClick={() => setResult(null)} disabled={saving}>
              Discard
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
