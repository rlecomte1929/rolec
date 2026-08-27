/**
 * ImmigrationPage — IMM-10
 *
 * Employee-facing container for the full immigration intake flow.
 * Route: /employee/case/:caseId/immigration
 *
 * Flow:
 *   1. Load profile/status → if no consent, show ImmigrationConsentScreen
 *   2. Show PassportOCRFlow (can be skipped)
 *   3. Show ImmigrationInterviewShell
 *   4. Completion screen with link back to case
 */

import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Alert, Button, Card } from '../../components/antigravity';
import { ImmigrationConsentScreen } from '../../features/immigration/ImmigrationConsentScreen';
import { PassportOCRFlow } from '../../features/immigration/PassportOCRFlow';
import { ImmigrationInterviewShell } from '../../features/immigration/ImmigrationInterviewShell';
import { getAuthItem } from '../../utils/demo';
import api from '../../api/client';
import { buildRoute } from '../../navigation/routes';

type FlowStage = 'loading' | 'error' | 'consent' | 'ocr' | 'interview' | 'complete';

interface InterviewStatus {
  completion_pct: number;
  is_complete: boolean;
  section_progress: Record<string, unknown>;
  session_exists: boolean;
}

export const ImmigrationPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const employeeId = getAuthItem('relopass_user_id') || '';

  const [stage, setStage] = useState<FlowStage>('loading');
  const [loadError, setLoadError] = useState<string | null>(null);
  const [interviewPct, setInterviewPct] = useState(0);

  const load = useCallback(async () => {
    if (!caseId) { setLoadError('No case ID in URL.'); setStage('error'); return; }
    setStage('loading');
    setLoadError(null);

    try {
      // Check consent: attempt to call interview/status; a 403 means no consent yet.
      const resp = await api.get<InterviewStatus>(
        `/api/employee/cases/${caseId}/interview/status`
      );
      const d = resp.data;
      setInterviewPct(d.completion_pct || 0);
      if (d.is_complete) {
        setStage('complete');
      } else if (d.session_exists && d.completion_pct > 0) {
        // Resume interview, skip OCR
        setStage('interview');
      } else {
        // Fresh start: show OCR first
        setStage('ocr');
      }
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 403) {
        // No consent yet
        setStage('consent');
      } else {
        const detail =
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          'Failed to load your immigration profile. Please try again.';
        setLoadError(detail);
        setStage('error');
      }
    }
  }, [caseId]);

  useEffect(() => {
    void load();
  }, [load]);

  const caseRoadmapHref = caseId
    ? buildRoute('employeeCaseRoadmap', { caseId })
    : buildRoute('employeeDashboard');

  return (
    <AppShell
      title="Immigration intake"
      subtitle="Complete your immigration profile — required to start your visa application."
    >
      {/* Progress indicator strip */}
      {stage !== 'loading' && stage !== 'error' && (
        <div className="flex items-center gap-2 mb-6 text-xs text-[#6b7280]">
          <StepPip label="1" title="Consent"
            done={(['ocr', 'interview', 'complete'] as FlowStage[]).includes(stage)}
            active={stage === 'consent'} />
          <div className="h-px flex-1 bg-[#e2e8f0]" />
          <StepPip label="2" title="Passport scan"
            done={(['interview', 'complete'] as FlowStage[]).includes(stage)}
            active={stage === 'ocr'} />
          <div className="h-px flex-1 bg-[#e2e8f0]" />
          <StepPip label="3" title="Interview" done={stage === 'complete'} active={stage === 'interview'} />
        </div>
      )}

      {/* Loading */}
      {stage === 'loading' && (
        <div className="text-sm text-[#6b7280] py-12 text-center">
          <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-4 border-[#e2e8f0] border-t-[#0b2b43]" />
          Loading immigration profile…
        </div>
      )}

      {/* Error */}
      {stage === 'error' && (
        <div className="max-w-lg mx-auto">
          <Alert variant="error" className="mb-4">{loadError}</Alert>
          <Button variant="outline" onClick={() => void load()}>Try again</Button>
        </div>
      )}

      {/* Consent */}
      {stage === 'consent' && caseId && (
        <ImmigrationConsentScreen
          caseId={caseId}
          employeeId={employeeId}
          onConsented={() => setStage('ocr')}
        />
      )}

      {/* OCR */}
      {stage === 'ocr' && caseId && (
        <PassportOCRFlow
          caseId={caseId}
          onComplete={() => setStage('interview')}
          onSkip={() => setStage('interview')}
        />
      )}

      {/* Interview */}
      {stage === 'interview' && caseId && (
        <ImmigrationInterviewShell
          caseId={caseId}
          onComplete={() => setStage('complete')}
          onSaveAndExit={() => navigate(caseRoadmapHref)}
        />
      )}

      {/* GDPR data-management entry point — available throughout the journey */}
      {stage !== 'loading' && stage !== 'error' && caseId && (
        <div className="mt-8 border-t border-[#e2e8f0] pt-4 text-center">
          <Button unstyled
            type="button"
            onClick={() => navigate(buildRoute('employeeCaseMyData', { caseId }))}
            className="text-sm font-medium text-[#0b2b43] underline hover:text-[#1f8e8b]"
          >
            Manage my data
          </Button>
          <p className="text-xs text-slate-500 mt-1">
            View, download, or request deletion of the data we hold for you.
          </p>
        </div>
      )}

      {/* Complete */}
      {stage === 'complete' && (
        <div className="max-w-lg mx-auto">
          <Card padding="lg" className="text-center">
            <div className="text-5xl mb-4">🎉</div>
            <h2 className="text-xl font-semibold text-[#0b2b43]">Immigration profile complete</h2>
            <p className="text-sm text-[#475569] mt-2 leading-relaxed">
              Your immigration profile is now {interviewPct}% complete. Your case manager will
              review the information and prepare your visa application documents. You will be
              notified of any next steps.
            </p>
            {interviewPct < 100 && (
              <p className="text-xs text-slate-500 mt-2">
                You can return to this page at any time to complete remaining optional sections.
              </p>
            )}
            <div className="mt-6 flex flex-col gap-2 items-center">
              <Button variant="primary" onClick={() => navigate(caseRoadmapHref)}>
                Back to my roadmap
              </Button>
              <Button unstyled
                type="button"
                onClick={() => setStage('interview')}
                className="text-sm text-[#64748b] hover:text-[#0b2b43]"
              >
                Review / edit my answers
              </Button>
            </div>
          </Card>
        </div>
      )}
    </AppShell>
  );
};

// ---------------------------------------------------------------------------
// Step pip helper
// ---------------------------------------------------------------------------

function StepPip({ label, title, done, active }: { label: string; title: string; done: boolean; active: boolean }) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <div className={`h-6 w-6 rounded-full flex items-center justify-center text-xs font-semibold ${
        done ? 'bg-[#eaf5f4] text-[#1f8e8b]'
             : active ? 'bg-[#0b2b43] text-white'
             : 'bg-[#e2e8f0] text-slate-500'
      }`}>
        {done ? '✓' : label}
      </div>
      <span className={`text-[10px] ${active ? 'text-[#0b2b43] font-medium' : 'text-slate-500'}`}>{title}</span>
    </div>
  );
}
