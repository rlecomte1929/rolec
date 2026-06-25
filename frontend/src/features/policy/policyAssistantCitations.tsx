/**
 * Citation rendering for the Policy Assistant.
 *
 * The RAG engine returns answers with inline `[chunk:<id>]` tokens.
 * `formatAnswerWithCitations` tokenizes those out of the answer text
 * and renders each as a clickable chip that:
 *   - shows the chunk_text in a native title tooltip on hover
 *   - on click, scrolls to + briefly highlights the source row on the
 *     policy page (rows must carry `data-policy-source-ref="<source_ref>"`)
 *
 * When no `cited_chunks` are passed (legacy assistant flow), the
 * `[chunk:<id>]` tokens render as muted superscripts so the answer
 * reads cleanly without surfacing internal ids.
 *
 * Bold spans (`**text**`) inside the answer are still respected — the
 * citation parser splits on `[chunk:<id>]` first, then defers to
 * formatRichMessage for each non-citation segment.
 */
import React from 'react';
import { Button } from '../../components/antigravity/Button';
import { formatRichMessage } from '../../utils/richMessage';
import type { PolicyAssistantCitedChunk } from '../../types/policyAssistant';

const CITATION_RE = /\[chunk:([a-zA-Z0-9_\-]+)\]/g;
const HIGHLIGHT_CLASS = 'policy-source-highlight';
const HIGHLIGHT_DURATION_MS = 1800;

export function extractChunkIdsInOrder(text: string): string[] {
  const seen = new Set<string>();
  const ids: string[] = [];
  let m: RegExpExecArray | null;
  CITATION_RE.lastIndex = 0;
  while ((m = CITATION_RE.exec(text)) !== null) {
    const id = m[1];
    if (id && !seen.has(id)) {
      seen.add(id);
      ids.push(id);
    }
  }
  return ids;
}

/** Find the source DOM row (if any) and scroll-into-view + flash it. */
export function scrollToSourceRef(sourceRef: string): boolean {
  if (typeof document === 'undefined') return false;
  const el = document.querySelector<HTMLElement>(
    `[data-policy-source-ref="${CSS.escape(sourceRef)}"]`
  );
  if (!el) return false;
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  el.classList.add(HIGHLIGHT_CLASS);
  window.setTimeout(() => el.classList.remove(HIGHLIGHT_CLASS), HIGHLIGHT_DURATION_MS);
  return true;
}

/**
 * Map a backend `evidence.reference` (typically a `benefit_key` like
 * "shipment_allowance" or a canonical topic value like "shipment") to a
 * stable HTML element id we mark up on policy-clause rows. Slugifies
 * to keep the id readable in DevTools and avoid collisions with other
 * id schemes already in use on the page.
 */
export function referenceToElementId(ref: string): string {
  const slug = String(ref || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
  return `policy-clause-${slug || 'unknown'}`;
}

/**
 * Resolve a Policy Assistant `evidence.reference` to a DOM element on
 * the policy page and scroll-into-view + flash it. Tries (in order):
 *   1. The id produced by `referenceToElementId` — direct anchor
 *   2. `[data-policy-reference="<ref>"]` — explicit attribute match
 *
 * The two-step lookup is intentional: it lets the policy page mark up
 * clauses with EITHER a stable id OR an attribute, without forcing one
 * convention onto callers. Returns false when no element is found so
 * callers can log + degrade gracefully.
 */
export function scrollToPolicyReference(reference: string): boolean {
  if (typeof document === 'undefined') return false;
  const ref = String(reference || '').trim();
  if (!ref) return false;
  let el = document.getElementById(referenceToElementId(ref));
  if (!el) {
    el = document.querySelector<HTMLElement>(
      `[data-policy-reference="${CSS.escape(ref)}"]`
    );
  }
  if (!el) return false;
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  el.classList.add(HIGHLIGHT_CLASS);
  window.setTimeout(() => el.classList.remove(HIGHLIGHT_CLASS), HIGHLIGHT_DURATION_MS);
  return true;
}

/**
 * True when the viewport is wide enough that the docked Policy
 * Assistant panel sits side-by-side with the policy page (lg+, ≥1024px).
 * Citation deep-linking is disabled below this breakpoint because the
 * mobile bottom-sheet covers the policy underneath — scrolling the
 * page behind a modal yields nothing the user can see.
 */
export function isCitationDeepLinkAvailable(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false;
  }
  return window.matchMedia('(min-width: 1024px)').matches;
}

type CitationChipProps = {
  index: number;
  chunk?: PolicyAssistantCitedChunk;
  rawId: string;
  onActivate?: (chunk: PolicyAssistantCitedChunk) => void;
};

const CitationChip: React.FC<CitationChipProps> = ({ index, chunk, rawId, onActivate }) => {
  // Unknown chunk id (no metadata available): render as muted superscript.
  if (!chunk) {
    return (
      <sup className="text-[10px] text-slate-400 align-super ml-0.5" aria-hidden="true">
        [{index}]
      </sup>
    );
  }
  const tooltip = chunk.chunk_text;
  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    if (onActivate) {
      onActivate(chunk);
      return;
    }
    scrollToSourceRef(chunk.source_ref);
  };
  return (
    <Button unstyled
      type="button"
      onClick={handleClick}
      title={tooltip}
      aria-label={`Citation ${index} — ${chunk.source_ref}`}
      data-testid="policy-citation-chip"
      data-source-ref={chunk.source_ref}
      className="inline-flex items-center align-middle ml-0.5 px-1.5 py-0 text-[10px] font-medium rounded-full bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
    >
      [{index}]
      <span className="sr-only"> — view source row in policy</span>
      {/* Use raw id only for test selectors; visible label is the index. */}
      <span className="hidden" data-chunk-id={rawId} />
    </Button>
  );
};

/**
 * Render the assistant answer text as React nodes with `[chunk:<id>]`
 * tokens replaced by interactive chips. Bold spans (`**text**`) inside
 * each non-citation segment are preserved.
 */
export function formatAnswerWithCitations(
  text: string,
  citedChunks?: PolicyAssistantCitedChunk[],
  onActivate?: (chunk: PolicyAssistantCitedChunk) => void
): React.ReactNode {
  if (!text) return text;
  const chunkById = new Map<string, PolicyAssistantCitedChunk>();
  (citedChunks ?? []).forEach((c) => chunkById.set(c.id, c));
  // Stable index per unique chunk id (in citation order across the text).
  const orderedIds = extractChunkIdsInOrder(text);
  const indexById = new Map<string, number>();
  orderedIds.forEach((id, i) => indexById.set(id, i + 1));

  const out: React.ReactNode[] = [];
  let last = 0;
  let segIdx = 0;
  CITATION_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = CITATION_RE.exec(text)) !== null) {
    const start = m.index;
    const end = start + m[0].length;
    if (start > last) {
      const segment = text.slice(last, start);
      out.push(
        <React.Fragment key={`seg-${segIdx++}`}>{formatRichMessage(segment)}</React.Fragment>
      );
    }
    const id = m[1];
    if (id) {
      const idx = indexById.get(id) ?? out.length + 1;
      out.push(
        <CitationChip
          key={`cite-${segIdx++}-${id}`}
          index={idx}
          chunk={chunkById.get(id)}
          rawId={id}
          onActivate={onActivate}
        />
      );
    }
    last = end;
  }
  if (last < text.length) {
    const tail = text.slice(last);
    out.push(<React.Fragment key={`seg-${segIdx++}`}>{formatRichMessage(tail)}</React.Fragment>);
  }
  return <>{out}</>;
}
