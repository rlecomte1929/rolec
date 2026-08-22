/**
 * CaseExtractedDataPanel — what the extraction engine actually read (AIQ-1790).
 *
 * HR-only. The extraction pipeline has produced structured fields in production
 * since 2026-08-10 and nothing in the product showed them: the deployed documents
 * panel reads the MVP OCR queue (`ocr_status`), which is gated on an unset
 * MISTRAL_API_KEY and therefore never advances past "pending", while the rce engine
 * that actually succeeded was exposed only on endpoints no deployed frontend called.
 *
 * Deliberately a SEPARATE panel from CaseDocumentsPanel rather than a mode of it:
 * the two read different backends with different document-id spaces, and merging
 * them would silently conflate an empty list from one with a populated list from the
 * other. This panel is additive and leaves the upload surface untouched.
 */
import { useCallback, useEffect, useState } from 'react';
import { Badge } from '../antigravity/Badge';
import { Button } from '../antigravity/Button';
import { ConfidenceBadge } from '../../features/platform-v2/roadmap/ConfidenceBadge';
import type { ConfidenceLevel } from '../../features/platform-v2/roadmap/confidence.tokens';
import {
  caseExtractionAPI,
  type ExtractedField,
  type ExtractionDocument,
} from '../../api/caseExtraction';

/** Human labels for the keys the passport agent emits. Unknown keys are prettified. */
const FIELD_LABELS: Record<string, string> = {
  surname: 'Surname',
  given_names: 'Given names',
  document_number: 'Document number',
  date_of_birth: 'Date of birth',
  expiry_date: 'Expiry date',
  nationality_iso3: 'Nationality',
  issuing_state_iso3: 'Issuing state',
  issuing_authority: 'Issuing authority',
  personal_number: 'Personal number',
  sex: 'Sex',
  endorsements: 'Endorsements',
  mrz_body_discrepancies: 'MRZ / body discrepancies',
  agent_confidence: 'Overall agent confidence',
};

function labelFor(key: string): string {
  return FIELD_LABELS[key] ?? key.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
}

/**
 * Thresholds are the 0.9 / 0.75 band inherited from the (now-deleted, AIQ-1865)
 * hr-dashboard app. Deliberately not
 * `resolveConfidenceLevel` from confidence.tokens — that one downgrades to UNKNOWN
 * without a source URL, which is a roadmap-citation rule, not an extraction one.
 */
function levelFor(score: number | null | undefined): ConfidenceLevel {
  if (score === null || score === undefined) return 'UNKNOWN';
  if (score >= 0.9) return 'HIGH';
  if (score >= 0.75) return 'MEDIUM';
  return 'LOW';
}

function formatDate(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString();
}

export interface CaseExtractedDataPanelProps {
  caseId: string;
}

export function CaseExtractedDataPanel({ caseId }: CaseExtractedDataPanelProps) {
  const [documents, setDocuments] = useState<ExtractionDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, ExtractedField[]>>({});
  const [fieldCounts, setFieldCounts] = useState<Record<string, number>>({});
  const [fieldsLoading, setFieldsLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      setDocuments(await caseExtractionAPI.listDocuments(caseId));
      setError(null);
    } catch {
      setError('Could not load extracted data. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    void load();
  }, [load]);

  // Extraction is asynchronous — the upload returns 200 and fields land ~5–15s
  // later. A panel that read once after upload would always show nothing.
  const awaitingExtraction = documents.some((d) => !d.extracted_field_count);
  useEffect(() => {
    if (!awaitingExtraction) return;
    const t = setInterval(() => void load(), 5000);
    return () => clearInterval(t);
  }, [awaitingExtraction, load]);

  const toggle = useCallback(
    async (documentId: string) => {
      if (expanded === documentId) {
        setExpanded(null);
        return;
      }
      setExpanded(documentId);
      if (fields[documentId]) return;
      setFieldsLoading(true);
      try {
        const res = await caseExtractionAPI.fields(caseId, documentId);
        setFields((prev) => ({ ...prev, [documentId]: res.fields }));
        setFieldCounts((prev) => ({ ...prev, [documentId]: res.field_count }));
      } catch {
        setFields((prev) => ({ ...prev, [documentId]: [] }));
      } finally {
        setFieldsLoading(false);
      }
    },
    [caseId, expanded, fields],
  );

  if (loading) {
    return <p className="py-8 text-center text-sm text-slate-400">Loading extracted data…</p>;
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        {error}
        <Button unstyled onClick={() => void load()} className="ml-2 underline">
          Retry
        </Button>
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-slate-400">
        No documents have been processed for this case yet.
      </p>
    );
  }

  return (
    <ul className="space-y-2">
      {documents.map((doc) => {
        const isOpen = expanded === doc.document_id;
        // Truthy field count means the engine produced something. The number itself
        // is NOT shown here: it counts every run's rows, so a re-processed document
        // reads 22 for 13 real fields. The deduplicated count comes with the fields.
        const hasData = Boolean(doc.extracted_field_count);
        const docFields = fields[doc.document_id];
        return (
          <li
            key={doc.document_id}
            className="rounded-lg border border-slate-200 bg-white px-4 py-3"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-900">{doc.filename}</p>
                <p className="mt-0.5 text-xs text-slate-400">
                  {doc.document_type_label ?? doc.document_type_code}
                  {doc.uploaded_at && ` · ${formatDate(doc.uploaded_at)}`}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {hasData ? (
                  <>
                    <Badge variant="success" size="sm">
                      Data extracted
                    </Badge>
                    {/* min, not mean: averaging deterministic MRZ 1.000 with
                        LLM-derived 0.50–0.95 makes a perfect read look mediocre. */}
                    <ConfidenceBadge
                      level={levelFor(doc.confidence_min)}
                      score={doc.confidence_min}
                    />
                  </>
                ) : (
                  // The majority case today: only passports extract — every other
                  // type is waiting on an OCR engine that is not enabled. This is a
                  // normal state, not a failure, and must not read as one.
                  <Badge variant="neutral" size="sm">
                    Not yet processed
                  </Badge>
                )}
                {hasData && (
                  <Button
                    unstyled
                    type="button"
                    onClick={() => void toggle(doc.document_id)}
                    aria-expanded={isOpen}
                    className="text-xs font-medium text-accent-600 hover:text-accent-800"
                  >
                    {isOpen ? 'Hide' : 'View data'}
                  </Button>
                )}
              </div>
            </div>

            {isOpen && (
              <div className="mt-3 border-t border-slate-100 pt-3">
                {fieldsLoading && !docFields ? (
                  <p className="text-xs text-slate-400">Loading…</p>
                ) : !docFields || docFields.length === 0 ? (
                  <p className="text-xs text-slate-400">
                    Nothing was extracted from this document yet.
                  </p>
                ) : (
                  <>
                    <table className="w-full text-xs">
                      <caption className="sr-only">
                        Data extracted from {doc.filename}
                      </caption>
                      <thead>
                        <tr className="text-left text-slate-500">
                          <th scope="col" className="pb-1 font-medium">Field</th>
                          <th scope="col" className="pb-1 font-medium">Value</th>
                          <th scope="col" className="pb-1 font-medium">Confidence</th>
                        </tr>
                      </thead>
                      <tbody>
                        {docFields.map((f) => (
                          <tr key={f.field_key} className="border-t border-slate-50">
                            <td className="py-1 pr-3 text-slate-500">{labelFor(f.field_key)}</td>
                            <td className="py-1 pr-3 text-slate-900">
                              {f.value ?? <span className="text-slate-300">—</span>}
                            </td>
                            <td className="py-1">
                              <ConfidenceBadge level={levelFor(f.confidence)} score={f.confidence} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <p className="mt-2 text-[11px] text-slate-400">
                      {fieldCounts[doc.document_id] ?? docFields.length} field
                      {(fieldCounts[doc.document_id] ?? docFields.length) === 1 ? '' : 's'} read
                      from this document.
                      {docFields.some((f) => f.masked) &&
                        ' Identifying numbers are masked.'}
                    </p>
                  </>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export default CaseExtractedDataPanel;
