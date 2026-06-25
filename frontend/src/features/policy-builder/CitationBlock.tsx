/**
 * [P4-6] CitationBlock.tsx — Citation rendering system for AI policy responses
 *
 * Renders a grounded AI response with:
 *   1. Inline citation markers ([1], [2], ...) as superscript links
 *   2. Collapsible "Policy sources" panel (closed by default)
 *   3. Confidence badge — Verified (green) or Review recommended (amber)
 *   4. Signed document URLs that open at the cited page in a new tab
 *
 * Usage:
 *   <CitationBlock
 *     response="Your housing allowance is EUR 3,500/month [1] for Manager grade."
 *     citations={[{ index: 1, doc_name: "...", section: "...", page: 12, confidence: 0.94, text: "...", signed_url: "..." }]}
 *     verified={true}
 *   />
 *
 * Confidence logic:
 *   verified=true  → all citations ≥ 0.85 → ✅ Verified (green)
 *   verified=false → any citation < 0.85  → ⚠ Review recommended (amber)
 */

import React, { useState, useCallback, useId } from 'react';
import { Button } from '../../components/antigravity/Button';
import { CheckCircle2, AlertTriangle, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Citation {
  /** 1-based citation index that maps to [N] markers in the response text */
  index: number;
  /** Display name of the source document, e.g. "Global Mobility Policy 2025" */
  doc_name: string;
  /** Policy section reference, e.g. "4.2 Housing Cap by Grade" */
  section: string;
  /** Page number in the source PDF */
  page: number;
  /** Extraction confidence (0–1) from the policy pipeline */
  confidence: number;
  /** Short text excerpt from the cited chunk */
  text: string;
  /** Pre-signed URL to the source document — opens at the cited page */
  signed_url: string;
}

export interface CitationBlockProps {
  /**
   * Response text with inline citation markers.
   * Markers take the form `[N]` where N is a 1-based integer.
   * e.g. "Your housing allowance is EUR 3,500/month [1] for Manager grade."
   */
  response: string;
  /**
   * Retrieved policy citations — maximum 5 (top-5 from retrieval).
   * Rendered in the collapsible "Policy sources" panel.
   */
  citations: Citation[];
  /**
   * Pre-computed badge state:
   *   true  → all citations ≥ 0.85 → Verified (green)
   *   false → any citation < 0.85  → Review recommended (amber)
   */
  verified: boolean;
  /** Optional additional className for the outer wrapper */
  className?: string;
}

// ---------------------------------------------------------------------------
// Response text parser
// Replaces [N] markers with superscript anchor links
// ---------------------------------------------------------------------------

const CITATION_MARKER_RE = /\[(\d+)\]/g;

interface TextSegment {
  type: 'text' | 'cite';
  content: string;
  index?: number;
}

function parseResponseSegments(text: string): TextSegment[] {
  const segments: TextSegment[] = [];
  let lastIndex = 0;
  CITATION_MARKER_RE.lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = CITATION_MARKER_RE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: 'text', content: text.slice(lastIndex, match.index) });
    }
    segments.push({ type: 'cite', content: match[0], index: parseInt(match[1] ?? '', 10) });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    segments.push({ type: 'text', content: text.slice(lastIndex) });
  }

  return segments;
}

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

/** Renders a single citation row inside the collapsible panel */
const CitationRow: React.FC<{ citation: Citation; id: string }> = ({ citation, id }) => {
  const confidencePct = Math.round(citation.confidence * 100);
  const isHighConfidence = citation.confidence >= 0.85;

  return (
    <li
      id={id}
      className="flex flex-col gap-1 py-3 border-b border-[#e2e8f0] last:border-b-0"
    >
      {/* Header row: index + doc name + open link */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2 min-w-0">
          <span className="flex-shrink-0 inline-flex items-center justify-center w-5 h-5 rounded-full bg-[#0b2b43] text-white text-[10px] font-bold mt-0.5">
            {citation.index}
          </span>
          <div className="min-w-0">
            <span className="text-sm font-medium text-[#1f2937] leading-snug">
              {citation.doc_name}
            </span>
            <div className="text-xs text-[#6b7280] mt-0.5">
              Section {citation.section}
              {citation.page ? ` · p.${citation.page}` : ''}
            </div>
          </div>
        </div>
        <a
          href={citation.signed_url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-shrink-0 inline-flex items-center gap-1 text-xs text-[#1f8e8b] hover:text-[#167a77] hover:underline font-medium mt-0.5 transition-colors"
          aria-label={`Open ${citation.doc_name} at page ${citation.page}`}
        >
          Open
          <ExternalLink size={11} strokeWidth={2.5} aria-hidden="true" />
        </a>
      </div>

      {/* Excerpt */}
      {citation.text && (
        <p className="text-xs text-[#6b7280] italic leading-relaxed pl-7 line-clamp-2">
          "{citation.text.slice(0, 180).trim()}{citation.text.length > 180 ? '…' : ''}"
        </p>
      )}

      {/* Confidence pill */}
      <div className="pl-7">
        <span
          className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full ${
            isHighConfidence
              ? 'bg-[#eaf5f4] text-[#1f8e8b]'
              : 'bg-[#f4efe5] text-[#7a5e2a]'
          }`}
        >
          {isHighConfidence ? (
            <CheckCircle2 size={11} strokeWidth={2.5} aria-hidden="true" />
          ) : (
            <AlertTriangle size={11} strokeWidth={2.5} aria-hidden="true" />
          )}
          {confidencePct}% confidence
        </span>
      </div>
    </li>
  );
};

// ---------------------------------------------------------------------------
// Main: CitationBlock
// ---------------------------------------------------------------------------

export const CitationBlock: React.FC<CitationBlockProps> = ({
  response,
  citations,
  verified,
  className = '',
}) => {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const uid = useId();

  // Limit to top 5 citations per spec
  const displayedCitations = citations.slice(0, 5);

  const toggleSources = useCallback(() => {
    setSourcesOpen((prev) => !prev);
  }, []);

  const handleCiteClick = useCallback(
    (index: number, event: React.MouseEvent<HTMLElement>) => {
      event.preventDefault();
      // Open the sources panel and scroll to the specific citation
      setSourcesOpen(true);
      // Defer scroll so the panel has time to expand
      requestAnimationFrame(() => {
        const el = document.getElementById(`${uid}-cite-${index}`);
        el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      });
    },
    [uid],
  );

  // Parse response text into segments (text + citation markers)
  const segments = parseResponseSegments(response);

  return (
    <div className={`relative ${className}`} data-testid="citation-block">
      {/* ── Response card ─────────────────────────────────────── */}
      <div className="bg-white rounded-xl border border-[#e2e8f0] shadow-sm">
        {/* Confidence badge — top right of response card */}
        <div className="flex items-start justify-between gap-3 p-4 pb-0">
          <div className="flex-1" /> {/* spacer */}
          {verified ? (
            <span
              className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full bg-[#eaf5f4] text-[#1a7c79] border border-[#c8e8e7] flex-shrink-0"
              role="status"
              aria-label="All sources verified"
            >
              <CheckCircle2 size={13} strokeWidth={2.5} aria-hidden="true" />
              Verified
            </span>
          ) : (
            <span
              className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full bg-[#f4efe5] text-[#7a5e2a] border border-[#e8dcc8] flex-shrink-0"
              role="status"
              aria-label="Some sources have lower confidence — review recommended"
            >
              <AlertTriangle size={13} strokeWidth={2.5} aria-hidden="true" />
              Review recommended
            </span>
          )}
        </div>

        {/* Response text with inline citation superscripts */}
        <div className="px-4 pt-3 pb-4">
          <p className="text-sm text-[#1f2937] leading-relaxed">
            {segments.map((seg, i) => {
              if (seg.type === 'text') {
                return <React.Fragment key={i}>{seg.content}</React.Fragment>;
              }
              // Citation marker → superscript link
              const citeIndex = seg.index!;
              const hasCitation = displayedCitations.some((c) => c.index === citeIndex);
              return (
                <sup key={i}>
                  {hasCitation ? (
                    <Button unstyled
                      onClick={(e) => handleCiteClick(citeIndex, e)}
                      className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded bg-[#eaf1f7] text-[#0b2b43] text-[10px] font-bold hover:bg-[#d4e4f0] transition-colors cursor-pointer ml-0.5"
                      aria-label={`Source ${citeIndex}`}
                      type="button"
                    >
                      {citeIndex}
                    </Button>
                  ) : (
                    <span className="text-[#9ca3af] text-[10px] ml-0.5">[{citeIndex}]</span>
                  )}
                </sup>
              );
            })}
          </p>
        </div>

        {/* ── Collapsible "Policy sources" panel ──────────────── */}
        {displayedCitations.length > 0 && (
          <div className="border-t border-[#e2e8f0]">
            {/* Toggle button */}
            <Button unstyled
              onClick={toggleSources}
              className="flex w-full items-center justify-between px-4 py-2.5 text-xs font-medium text-[#6b7280] hover:text-[#1f2937] hover:bg-[#f9fafb] transition-colors rounded-b-xl"
              aria-expanded={sourcesOpen}
              aria-controls={`${uid}-sources`}
              type="button"
            >
              <span>
                Policy sources{' '}
                <span className="text-[#9ca3af] font-normal">
                  ({displayedCitations.length})
                </span>
              </span>
              {sourcesOpen ? (
                <ChevronUp size={14} strokeWidth={2} aria-hidden="true" />
              ) : (
                <ChevronDown size={14} strokeWidth={2} aria-hidden="true" />
              )}
            </Button>

            {/* Citation list */}
            {sourcesOpen && (
              <ul
                id={`${uid}-sources`}
                className="px-4 pb-4"
                role="list"
                aria-label="Policy source citations"
              >
                {displayedCitations.map((citation) => (
                  <CitationRow
                    key={citation.index}
                    citation={citation}
                    id={`${uid}-cite-${citation.index}`}
                  />
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default CitationBlock;

// ---------------------------------------------------------------------------
// Utility: derive verified status from raw PolicyChunk array
// ---------------------------------------------------------------------------

/**
 * Compute the `verified` prop from an array of retrieved chunks.
 * All chunks with confidence_score ≥ 0.85 → true (Verified).
 * Any chunk with confidence_score < 0.85 → false (Review recommended).
 * If no scores are present, defaults to true.
 */
export function computeVerifiedStatus(
  chunks: Array<{ confidence_score: number | null }>,
): boolean {
  if (chunks.length === 0) return true;
  return chunks.every(
    (c) => c.confidence_score === null || c.confidence_score >= 0.85,
  );
}

/**
 * Build a Citation array from AssistantResponse chunks and a response text
 * that uses [Source: section_path] notation.
 *
 * The router's `generateResponse` uses [Source: ...] inline citations.
 * This function converts the chunks into numbered Citation objects and
 * replaces the [Source: section_path] tokens with [N] markers in the text.
 *
 * @param responseText     Raw generated text with [Source: section_path] tokens
 * @param chunks           Retrieved PolicyChunk[] from AssistantResponse
 * @param getSignedUrl     Function that resolves a chunk id to a signed document URL
 */
export function buildCitationsFromChunks(
  responseText: string,
  chunks: Array<{
    id: string;
    section_path: string | null;
    text: string;
    confidence_score: number | null;
    page_start: number | null;
    doc_id: string | null;
  }>,
  docNames: Map<string, string> = new Map(),
  signedUrls: Map<string, string> = new Map(),
): { text: string; citations: Citation[]; verified: boolean } {
  // Build citations from chunks (top 5)
  const top5 = chunks.slice(0, 5);
  const citations: Citation[] = top5.map((chunk, i) => ({
    index: i + 1,
    doc_name: docNames.get(chunk.doc_id ?? '') ?? 'Company Policy',
    section: chunk.section_path ?? `Chunk ${i + 1}`,
    page: chunk.page_start ?? 1,
    confidence: chunk.confidence_score ?? 0.9,
    text: chunk.text,
    signed_url: signedUrls.get(chunk.id) ?? '#',
  }));

  // Replace [Source: section_path] tokens with [N] markers
  let text = responseText;
  for (const c of citations) {
    // Escape section_path for use in regex
    const escaped = c.section.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp(`\\[Source:\\s*${escaped}\\]`, 'gi');
    text = text.replace(re, `[${c.index}]`);
  }

  const verified = computeVerifiedStatus(top5);
  return { text, citations, verified };
}
