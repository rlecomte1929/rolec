import React from 'react';
import { AppShell } from '../../components/AppShell';
import { DocumentsScreen } from '../../features/platform-v2/documents/DocumentsScreen';
import { useDocuments } from '../../features/platform-v2/documents/useDocuments';

// Shared inline styles for the non-DocumentsScreen states.
const centeredMessage = (color: string): React.CSSProperties => ({
  padding: '48px 24px',
  textAlign: 'center',
  color,
  fontSize: '14px',
});

export function EmployeeDocumentsPage() {
  const {
    documents,
    isLoading,
    error,
    handleUpload,
    handleDelete,
    handleRemind,
    caseId,
  } = useDocuments();

  // ── No active case ─────────────────────────────────────────────────────────
  if (!caseId && !isLoading) {
    return (
      <AppShell wide>
        <p style={centeredMessage('#475569')}>
          No active relocation case found. Please contact your HR team to get started.
        </p>
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
        onDelete={handleDelete}
        onReupload={handleDelete} // re-upload = delete old then UploadZone handles new file
        onRemind={handleRemind}
        onPreview={(doc) => {
          if (caseId) {
            window.open(`/api/cases/${caseId}/documents/${doc.id}/download`, '_blank');
          }
        }}
        onDownload={(doc) => {
          if (caseId) {
            const link = window.document.createElement('a');
            link.href = `/api/cases/${caseId}/documents/${doc.id}/download`;
            link.download = doc.filename;
            link.click();
          }
        }}
      />
    </AppShell>
  );
}
