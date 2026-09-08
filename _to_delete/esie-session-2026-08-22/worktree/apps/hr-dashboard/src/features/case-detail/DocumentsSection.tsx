import { useState } from 'react';
import { FileText } from 'lucide-react';
import { cn } from '../../lib/utils';
import { useCaseDocumentsQuery } from '../../hooks/useCaseDetailQuery';
import { SectionShell } from './SectionShell';
import { DocumentViewerSheet } from './DocumentViewerSheet';
import type { CaseDocument } from './types';

interface DocumentsSectionProps {
  caseId: string;
}

function confidenceBand(confidence: number | null | undefined): {
  label: string;
  className: string;
} {
  if (confidence === null || confidence === undefined) {
    return { label: 'No data', className: 'bg-muted text-muted-foreground' };
  }
  if (confidence >= 0.9) {
    return { label: `${Math.round(confidence * 100)}%`, className: 'bg-success/20 text-success' };
  }
  if (confidence >= 0.75) {
    return { label: `${Math.round(confidence * 100)}%`, className: 'bg-warning/20 text-warning' };
  }
  return { label: `${Math.round(confidence * 100)}%`, className: 'bg-destructive/20 text-destructive' };
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

export function DocumentsSection({ caseId }: DocumentsSectionProps): JSX.Element {
  const query = useCaseDocumentsQuery(caseId);
  const documents = query.data ?? [];
  const [activeDoc, setActiveDoc] = useState<CaseDocument | null>(null);

  return (
    <SectionShell
      title="Documents"
      subtitle="Sources uploaded for this case. Click a row to open the PDF viewer."
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => void query.refetch()}
      isEmpty={!query.isLoading && documents.length === 0}
      emptyTitle="No documents yet"
      emptyDescription="When the employee uploads source documents, they appear here with extraction confidence."
    >
      <div className="overflow-x-auto rounded-lg border border-border bg-card shadow-sm">
        <table className="w-full text-sm">
          <thead className="text-xs uppercase tracking-wide text-muted-foreground">
            <tr className="border-b border-border">
              <th scope="col" className="px-4 py-2 text-left font-medium">Document</th>
              <th scope="col" className="px-4 py-2 text-left font-medium">Type</th>
              <th scope="col" className="px-4 py-2 text-left font-medium">Uploaded</th>
              <th scope="col" className="px-4 py-2 text-left font-medium">Mean conf.</th>
              <th scope="col" className="px-4 py-2 text-left font-medium">Min conf.</th>
              <th scope="col" className="px-4 py-2 text-left font-medium">Fields</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => {
              const mean = confidenceBand(doc.confidence_mean);
              const min = confidenceBand(doc.confidence_min);
              const canOpen = Boolean(doc.document_uri);
              return (
                <tr
                  key={doc.document_id}
                  className={cn(
                    'border-b border-border last:border-b-0',
                    canOpen ? 'cursor-pointer hover:bg-muted/40' : 'opacity-80',
                  )}
                  onClick={() => {
                    if (canOpen) setActiveDoc(doc);
                  }}
                  onKeyDown={(e) => {
                    if (!canOpen) return;
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setActiveDoc(doc);
                    }
                  }}
                  role={canOpen ? 'button' : undefined}
                  tabIndex={canOpen ? 0 : -1}
                  aria-label={canOpen ? `Open ${doc.filename} in viewer` : undefined}
                >
                  <td className="px-4 py-2 font-medium text-foreground">
                    <span className="inline-flex items-center gap-2">
                      <FileText className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                      {doc.filename}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {doc.document_type_label ?? doc.document_type_code}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">{formatDate(doc.uploaded_at)}</td>
                  <td className="px-4 py-2">
                    <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', mean.className)}>
                      {mean.label}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', min.className)}>
                      {min.label}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-muted-foreground tabular-nums">
                    {doc.extracted_field_count ?? '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <DocumentViewerSheet
        document={activeDoc}
        open={activeDoc !== null}
        onClose={() => setActiveDoc(null)}
      />
    </SectionShell>
  );
}
