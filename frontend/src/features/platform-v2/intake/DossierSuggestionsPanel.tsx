import { useState } from 'react';
import { dossierAPI } from '../../../api/client';
import type { DossierSuggestion, DossierSource } from '../../../types';

/**
 * [P3-RAG-04] Surfaces the RAG dossier-suggestion feature in the v2 "Pathway"
 * intake wizard review step (EmployeeIntakePage step 5). The same capability was
 * shipped in the legacy CaseWizardPage / Step5ReviewCreate (PR #787), but the v2
 * wizard — the flow employees actually use — had no equivalent, so the
 * corpus-grounded AI suggestions were invisible to them.
 *
 * Self-contained + frontend-only: it reuses the live
 * `dossierAPI.searchSuggestions(caseId)` (RAG retrieve → LLM → structured) and
 * `dossierAPI.addCaseQuestion(...)`. Suggestions populate only for the corpus
 * corridors (US→FR, IN→DE, FR→NO, UK→DE, BR→PT); other corridors return [].
 *
 * Gated behind the same `VITE_FEATURE_DYNAMIC_DOSSIER` flag as the legacy wizard
 * so a single kill-switch hides the dossier feature in both flows.
 */
const DYNAMIC_DOSSIER_ENABLED =
  import.meta.env.VITE_FEATURE_DYNAMIC_DOSSIER === 'true' ||
  import.meta.env.NEXT_PUBLIC_FEATURE_DYNAMIC_DOSSIER === 'true';

const sourceLabel = (src: DossierSource): string =>
  src.chunk_id || src.title || src.url || 'source';

export function DossierSuggestionsPanel({ caseId }: { caseId: string }) {
  const [suggestions, setSuggestions] = useState<DossierSuggestion[]>([]);
  const [sources, setSources] = useState<DossierSource[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [degraded, setDegraded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState<string | null>(null);
  const [addedCount, setAddedCount] = useState(0);

  if (!DYNAMIC_DOSSIER_ENABLED) return null;

  const search = async () => {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    setDegraded(false);
    try {
      const res = await dossierAPI.searchSuggestions(caseId);
      setSuggestions(res.suggestions || []);
      setSources(res.sources || []);
      setDegraded(Boolean(res.degraded));
      setSearched(true);
    } catch {
      setError('Unable to fetch suggested questions right now.');
    } finally {
      setLoading(false);
    }
  };

  const add = async (s: DossierSuggestion) => {
    if (!caseId) return;
    setAdding(s.question_text);
    setError(null);
    try {
      await dossierAPI.addCaseQuestion({
        case_id: caseId,
        question_text: s.question_text,
        answer_type: s.answer_type,
        sources: s.sources,
      });
      setSuggestions((prev) => prev.filter((x) => x.question_text !== s.question_text));
      setAddedCount((n) => n + 1);
    } catch {
      setError('Unable to add that question.');
    } finally {
      setAdding(null);
    }
  };

  return (
    <div className="mt-5 rounded-xl border border-gray-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-base font-semibold text-[#0b2b43]">Additional questions for your dossier</div>
          <p className="text-sm text-gray-500 mt-0.5">
            AI-suggested questions grounded in official immigration sources for your route. Add any that apply.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void search()}
          disabled={loading || !caseId}
          className="shrink-0 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-[#0b2b43] hover:bg-gray-50 disabled:opacity-50"
        >
          {loading ? 'Finding…' : searched ? 'Refresh suggestions' : 'Find suggested questions'}
        </button>
      </div>

      {error && (
        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
      )}

      {addedCount > 0 && (
        <div className="mt-3 text-sm text-emerald-700">
          ✓ Added {addedCount} question{addedCount === 1 ? '' : 's'} to your dossier.
        </div>
      )}

      {searched && !loading && degraded && (
        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Suggested questions are temporarily unavailable — please try again shortly.
        </div>
      )}

      {searched && !loading && !degraded && suggestions.length === 0 && (
        <div className="mt-3 text-sm text-gray-500">No additional suggestions for this route right now.</div>
      )}

      {suggestions.length > 0 && (
        <ul className="mt-4 space-y-3">
          {suggestions.map((s, idx) => (
            <li key={`${s.question_text}-${idx}`} className="rounded-lg border border-gray-200 p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm text-gray-800">{s.question_text}</div>
                  {s.sources && s.sources.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      <span className="text-[10px] uppercase tracking-wide text-gray-400">Source</span>
                      {s.sources.map((src, sIdx) =>
                        src.url ? (
                          <a
                            key={sIdx}
                            href={src.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-xs text-[#1d4ed8] underline decoration-dotted"
                          >
                            {sourceLabel(src)}
                          </a>
                        ) : (
                          <span key={sIdx} className="text-xs text-gray-500">{sourceLabel(src)}</span>
                        ),
                      )}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => void add(s)}
                  disabled={adding === s.question_text}
                  className="shrink-0 rounded-lg bg-[#0b2b43] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#0d3456] disabled:opacity-50"
                >
                  {adding === s.question_text ? 'Adding…' : 'Add this question'}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {sources.length > 0 && (
        <details className="mt-4">
          <summary className="cursor-pointer text-xs font-medium text-gray-500">Sources used</summary>
          <ul className="mt-2 space-y-1 text-xs text-gray-500">
            {sources.map((src, idx) => (
              <li key={`${src.chunk_id || src.url}-${idx}`}>
                {src.url ? (
                  <a href={src.url} target="_blank" rel="noreferrer" className="text-[#1d4ed8] underline">
                    {sourceLabel(src)}
                  </a>
                ) : (
                  <span>{sourceLabel(src)}</span>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
