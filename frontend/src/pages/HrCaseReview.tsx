/**
 * Block 5: HR Case Review - Read-only summary + feedback panel
 */

import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Alert, Button, Card } from '../components/antigravity';
import { getWizardCaseForReview, getAssignmentIdForCase } from '../api/review';
import {
  listFeedback,
  insertFeedback,
  FEEDBACK_SECTIONS,
  type CaseFeedbackRow,
  type FeedbackSection,
} from '../api/feedback';
import { buildRoute } from '../navigation/routes';

function SummarySection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card padding="md" className="mb-4">
      <div className="text-sm font-semibold text-[#0b2b43] mb-2">{title}</div>
      <div className="text-sm text-[#4b5563] space-y-1">{children}</div>
    </Card>
  );
}

export const HrCaseReview: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const [draft, setDraft] = useState<any>(null);
  const [assignmentId, setAssignmentId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<CaseFeedbackRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [section, setSection] = useState<FeedbackSection>('OVERALL');
  const [message, setMessage] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [sendError, setSendError] = useState('');

  const load = useCallback(async () => {
    if (!caseId) return;
    setIsLoading(true);
    setError('');
    const [caseRes, assignRes] = await Promise.all([
      getWizardCaseForReview(caseId),
      getAssignmentIdForCase(caseId),
    ]);
    if (caseRes.error) {
      setError(caseRes.error);
      setIsLoading(false);
      return;
    }
    if (assignRes.error || !assignRes.assignmentId) {
      setError(assignRes.error || 'Not authorized to view this case.');
      setIsLoading(false);
      return;
    }
    setDraft(caseRes.data?.draft ?? {});
    setAssignmentId(assignRes.assignmentId);

    const { data: fb } = await listFeedback(assignRes.assignmentId);
    setFeedback(fb ?? []);
    setIsLoading(false);
  }, [caseId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSendFeedback = async () => {
    if (!caseId || !assignmentId || !message.trim()) return;
    setIsSending(true);
    setSendError('');
    const { data, error: err } = await insertFeedback({ caseId, assignmentId, section, message });
    if (err) {
      setSendError(err);
    } else {
      setMessage('');
      if (data) setFeedback((prev) => [data, ...prev]);
    }
    setIsSending(false);
  };

  const b = draft?.relocationBasics || {};
  const ep = draft?.employeeProfile || {};
  const fm = draft?.familyMembers || {};
  const ac = draft?.assignmentContext || {};

  return (
    <AppShell title="Case review" subtitle="Read-only summary and feedback.">
      <Button variant="outline" className="mb-4" onClick={() => navigate(buildRoute('hrReview'))}>
        ← Back to list
      </Button>

      {error && <Alert variant="error">{error}</Alert>}
      {isLoading && <div className="text-sm text-[#6b7280]">Loading case...</div>}

      {!isLoading && draft && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-2">
            <SummarySection title="Relocation Basics">
              <div>Origin: {[b.originCity, b.originCountry].filter(Boolean).join(', ') || '-'}</div>
              <div>Destination: {[b.destCity, b.destCountry].filter(Boolean).join(', ') || '-'}</div>
              <div>Purpose: {b.purpose || '-'}</div>
              <div>Target move date: {b.targetMoveDate || '-'}</div>
              <div>Duration: {b.durationMonths ?? '-'} months</div>
            </SummarySection>
            <SummarySection title="Employee Profile">
              <div>Name: {ep.fullName || '-'}</div>
              <div>Email: {ep.email || '-'}</div>
              <div>Nationality: {ep.nationality || '-'}</div>
              <div>Role: {ep.roleTitle || '-'}</div>
            </SummarySection>
            <SummarySection title="Family Members">
              <div>Spouse: {fm.spouse?.fullName ? fm.spouse.fullName : '-'}</div>
              <div>Children: {fm.children?.length ? fm.children.length : 0}</div>
            </SummarySection>
            <SummarySection title="Assignment / Context">
              <div>Employer: {ac.employer || '-'}</div>
              <div>Contract start: {ac.contractStart || '-'}</div>
            </SummarySection>
          </div>

          <div>
            <Card padding="lg">
              <div className="text-sm font-semibold text-[#0b2b43] mb-3">Feedback</div>
              <div className="mb-3">
                <label className="text-xs text-[#6b7280] block mb-1">Section</label>
                <select
                  value={section}
                  onChange={(e) => setSection(e.target.value as FeedbackSection)}
                  className="w-full rounded border border-[#e2e8f0] px-2 py-1.5 text-sm"
                >
                  {FEEDBACK_SECTIONS.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </div>
              <div className="mb-3">
                <label className="text-xs text-[#6b7280] block mb-1">Message</label>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Add feedback for the employee..."
                  className="w-full min-h-[80px] rounded border border-[#e2e8f0] px-2 py-1.5 text-sm"
                  rows={3}
                />
              </div>
              {sendError && <div className="text-sm text-red-600 mb-2">{sendError}</div>}
              <Button onClick={handleSendFeedback} disabled={!message.trim() || isSending}>
                {isSending ? 'Sending...' : 'Send feedback'}
              </Button>

              <div className="mt-4 pt-4 border-t border-[#e2e8f0]">
                <div className="text-xs font-medium text-[#6b7280] mb-2">Previous feedback</div>
                {feedback.length === 0 && <div className="text-xs text-[#9ca3af]">No feedback yet.</div>}
                {feedback.map((f) => (
                  <div key={f.id} className="mb-3 text-sm">
                    <div className="text-[#6b7280]">
                      {FEEDBACK_SECTIONS.find((s) => s.value === f.section)?.label ?? f.section} · {new Date(f.created_at_ts).toLocaleString()}
                    </div>
                    <div className="text-[#0b2b43] mt-0.5">{f.message}</div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      )}
    </AppShell>
  );
};
