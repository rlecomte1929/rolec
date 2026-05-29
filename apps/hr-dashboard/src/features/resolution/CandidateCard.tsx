import { Check } from 'lucide-react';
import { cn } from '../../lib/utils';
import type { Candidate } from './types';

interface CandidateCardProps {
  candidate: Candidate;
  isSelected: boolean;
  onSelect: () => void;
  disabled?: boolean;
}

const SOURCE_LABEL_FALLBACK: Record<string, string> = {
  PASSPORT_TD3: 'Passport',
  EU_NATIONAL_ID: 'EU National ID',
  RESIDENCE_PERMIT_EU: 'EU Residence Permit',
  EMPLOYMENT_CONTRACT: 'Employment contract',
  PAYSLIP: 'Payslip',
  DIPLOMA_BACHELOR: 'Diploma (Bachelor)',
  DIPLOMA_MASTER: 'Diploma (Master)',
  MARRIAGE_CERT: 'Marriage certificate',
  BIRTH_CERT: 'Birth certificate',
  TAX_CERT: 'Tax certificate',
  HOUSING_LEASE: 'Lease',
};

function formatBbox(bbox: Candidate['bbox']): string {
  if (!bbox) return '';
  const [x0, y0, x1, y1] = bbox;
  return `(${x0}, ${y0}) → (${x1}, ${y1})`;
}

function formatConfidence(c: number): string {
  return `${Math.round(c * 100)}%`;
}

/**
 * One side of the side-by-side comparison. The HR user clicks the
 * checkmark button to nominate this candidate as the winner.
 *
 * C1-11e bbox-overlay PDF preview lives behind the "Show in document"
 * link. Until that subtask ships, the link renders as a disabled
 * placeholder (see DocumentPreviewLink).
 */
export function CandidateCard({
  candidate,
  isSelected,
  onSelect,
  disabled,
}: CandidateCardProps): JSX.Element {
  const sourceLabel =
    candidate.source_label ??
    (candidate.document_type_code
      ? SOURCE_LABEL_FALLBACK[candidate.document_type_code] ?? candidate.document_type_code
      : 'Unknown source');

  return (
    <article
      aria-label={`Candidate from ${sourceLabel}`}
      className={cn(
        'flex flex-col gap-4 rounded-lg border bg-card p-4 shadow-sm transition-colors',
        isSelected
          ? 'border-primary ring-2 ring-primary/30'
          : 'border-border hover:border-primary/60',
      )}
    >
      <header className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          {sourceLabel}
        </h3>
        <span
          className="text-xs font-medium tabular-nums text-muted-foreground"
          aria-label={`Confidence ${formatConfidence(candidate.confidence)}`}
        >
          confidence {formatConfidence(candidate.confidence)}
        </span>
      </header>

      <div className="flex flex-col gap-1">
        <p
          className="text-2xl font-semibold text-foreground"
          aria-label={`Value: ${candidate.value_raw}`}
        >
          {candidate.value_raw}
        </p>
        {candidate.value_canonical &&
        typeof candidate.value_canonical === 'object' &&
        'note' in candidate.value_canonical ? (
          <p className="text-xs text-muted-foreground">
            {String((candidate.value_canonical as { note?: unknown }).note ?? '')}
          </p>
        ) : null}
      </div>

      <DocumentPreviewLink
        documentId={candidate.document_id}
        page={candidate.bbox_page ?? null}
        bboxLabel={formatBbox(candidate.bbox)}
      />

      <button
        type="button"
        aria-pressed={isSelected}
        onClick={onSelect}
        disabled={disabled}
        className={cn(
          'mt-auto inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors',
          'border focus-visible:shadow-focus',
          isSelected
            ? 'border-primary bg-primary text-primary-foreground'
            : 'border-border bg-background text-foreground hover:bg-muted',
          disabled && 'cursor-not-allowed opacity-60',
        )}
      >
        {isSelected ? (
          <>
            <Check className="h-4 w-4" aria-hidden="true" />
            Selected winner
          </>
        ) : (
          <>
            <Check className="h-4 w-4 opacity-50" aria-hidden="true" />
            Pick winner
          </>
        )}
      </button>
    </article>
  );
}

interface DocumentPreviewLinkProps {
  documentId: string;
  page: number | null;
  bboxLabel: string;
}

/**
 * Placeholder for the C1-11e bbox-overlay PDF preview. Once that
 * subtask lands, replace this with the real <BboxOverlay /> component
 * that opens the document at the page + region.
 */
function DocumentPreviewLink({
  documentId,
  page,
  bboxLabel,
}: DocumentPreviewLinkProps): JSX.Element {
  const hasRegion = Boolean(page && bboxLabel);
  return (
    <div className="flex flex-col gap-1 rounded-md border border-dashed border-border bg-muted/40 p-3">
      <p className="text-xs font-medium text-muted-foreground">
        Source document
      </p>
      <p className="font-mono text-xs text-muted-foreground" title={documentId}>
        {documentId.slice(0, 8)}…
      </p>
      {hasRegion ? (
        <p className="text-xs text-muted-foreground">
          Page {page} · {bboxLabel}
        </p>
      ) : (
        <p className="text-xs text-muted-foreground italic">
          Page / region not captured
        </p>
      )}
      <p className="text-xs text-muted-foreground italic">
        PDF preview lands with C1-11e.
      </p>
    </div>
  );
}
