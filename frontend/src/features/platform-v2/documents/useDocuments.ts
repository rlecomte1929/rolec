/**
 * useDocuments — data hook for the Employee Document Vault.
 *
 * Reads the primary assignment id from EmployeeAssignmentContext (which equals the
 * case_id in the current architecture) and drives all document CRUD operations
 * through documentsAPI.
 */

import { useState, useEffect, useCallback } from 'react';
import { useEmployeeAssignment } from '../../../contexts/EmployeeAssignmentContext';
import { ownedEmployeeCaseId } from '../../../utils/employeeAssignmentScope';
import { documentsAPI } from '../../../api/documents';
import { notifyHrEmployeeSaved } from '../../../api/notifications';
import type { DocumentItem } from './DocumentsScreen';

// ── Public interface ───────────────────────────────────────────────────────────

export interface UseDocumentsResult {
  /** Live document list. Empty array while loading or when no case is active. */
  documents: DocumentItem[];
  /** True while the initial fetch is in flight. */
  isLoading: boolean;
  /** Non-null when a fetch or mutation failed. */
  error: string | null;
  /** Trigger a manual refresh (e.g. after navigating back to the page). */
  refetch: () => Promise<void>;
  /**
   * Upload a file against a specific required document (by document_key).
   * Refreshes the document list on success so the row's status flips.
   */
  handleUpload: (file: File, documentKey: string) => Promise<void>;
  /**
   * Delete / retract a document.
   * Optimistically removes the item from local state; re-fetches on error.
   */
  handleDelete: (doc: DocumentItem) => Promise<void>;
  /**
   * Trigger an HR reminder notification for the current case.
   * Wired to POST /api/notifications/notify-hr.
   */
  handleRemind: (doc: DocumentItem) => Promise<void>;
  /**
   * The resolved case id (same as assignmentId today).
   * Null when the employee has no active assignment yet.
   */
  caseId: string | null;
}

// ── Hook ───────────────────────────────────────────────────────────────────────

export function useDocuments(caseIdOverride?: string): UseDocumentsResult {
  const { assignmentId, isLoading: assignmentLoading, linkedSummaries } = useEmployeeAssignment();

  // Case-scoped routes pass a caseId in the URL. Never honor it unless it is
  // one of this employee's linked assignments (stale localStorage / copied UUID).
  const caseId = ownedEmployeeCaseId(linkedSummaries, [caseIdOverride, assignmentId]);

  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Fetch ──────────────────────────────────────────────────────────────────

  const fetchDocuments = useCallback(async () => {
    if (!caseId) return;
    setIsLoading(true);
    setError(null);
    try {
      const docs = await documentsAPI.list(caseId);
      setDocuments(docs);
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : 'Failed to load documents. Please refresh.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    // With an explicit caseId we can fetch immediately; otherwise wait until the
    // assignment context has resolved the fallback case id.
    if (!caseIdOverride && assignmentLoading) return;
    void fetchDocuments();
  }, [caseIdOverride, assignmentLoading, fetchDocuments]);

  // ── Mutations ──────────────────────────────────────────────────────────────

  const handleUpload = useCallback(
    async (file: File, documentKey: string): Promise<void> => {
      if (!caseId) throw new Error('No active relocation case.');
      await documentsAPI.upload(caseId, file, documentKey);
      // Refresh so the row's status flips from "required" to "submitted".
      await fetchDocuments();
    },
    [caseId, fetchDocuments],
  );

  const handleDelete = useCallback(
    async (doc: DocumentItem): Promise<void> => {
      if (!caseId) throw new Error('No active relocation case.');
      // Optimistic update — remove from list immediately.
      setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
      try {
        await documentsAPI.remove(caseId, doc.id);
      } catch (err: unknown) {
        // Roll back on failure.
        await fetchDocuments();
        throw err;
      }
    },
    [caseId, fetchDocuments],
  );

  const handleRemind = useCallback(
    async (_doc: DocumentItem): Promise<void> => {
      if (!caseId) return;
      await notifyHrEmployeeSaved(caseId);
    },
    [caseId],
  );

  // ── Result ─────────────────────────────────────────────────────────────────

  return {
    documents,
    isLoading: (!caseIdOverride && assignmentLoading) || isLoading,
    error,
    refetch: fetchDocuments,
    handleUpload,
    handleDelete,
    handleRemind,
    caseId,
  };
}
