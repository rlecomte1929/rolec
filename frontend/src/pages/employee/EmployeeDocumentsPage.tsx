import React from 'react';
import { useSearchParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { NoCaseLinkedEmptyState } from '../../components/employee/NoCaseLinkedEmptyState';
import { DocumentsScreen } from '../../features/platform-v2/documents/DocumentsScreen';
import { useDocuments } from '../../features/platform-v2/documents/useDocuments';
import { useValidatedParams, caseParamsSchema } from '../../hooks/useValidatedParams';

// Shared inline styles for the non-DocumentsScreen states.
const centeredMessage = (color: string): React.CSSProperties => ({
  padding: '48px 24px',
  textAlign: 'center',
  color,
  fontSize: '14px',
});

export function EmployeeDocumentsPage() {
  // Case-scoped route (/employee/case/:caseId/documents) supplies caseId via the
  // URL. The bare /employee/documents route has no param — useValidatedParams
  // returns null there (no redirect), so useDocuments falls back to the primary
  // assignment.
  const routeCaseId = useValidatedParams(caseParamsSchema)?.caseId;
  const [searchParams] = useSearchParams();
  // Deep-link: ?doc=<document_key> scrolls to + highlights + focuses that row.
  const deepLinkKey = searchParams.get('doc');

  const {
    documents,
    isLoading,
    error,
    handleUpload,
    handleRemind,
    caseId,
  } = useDocuments(routeCaseId);

  // ── No active case ─────────────────────────────────────────────────────────
  if (!caseId && !isLoading) {
    return (
      <AppShell wide>
        <NoCaseLinkedEmptyState explanation="Select a case to access documents for this relocation." />
      </AppShell>
    );
  }

  // ── API error ──────────────────────────────────────────────────────────────
  if (error) {
    return (
      <AppShell wide>
        <p style={centeredMessage('#b91c1c')}>{error}</p>
      </AppShell>
    );
  }

  // ── Loading skeleton ───────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <AppShell wide>
        <p style={centeredMessage('#94a3b8')}>Loading your documents…</p>
      </AppShell>
    );
  }

  // ── Main view ──────────────────────────────────────────────────────────────
  return (
    <AppShell wide>
      <DocumentsScreen
        documents={documents}
        onUpload={handleUpload}
        onRemind={handleRemind}
        deepLinkKey={deepLinkKey}
        onPreview={(doc) => {
          if (doc.file_url) window.open(doc.file_url, '_blank', 'noopener,noreferrer');
        }}
        onDownload={(doc) => {
          if (!doc.file_url) return;
          const link = window.document.createElement('a');
          link.href = doc.file_url;
          link.download = doc.filename;
          link.click();
        }}
      />
    </AppShell>
  );
}
