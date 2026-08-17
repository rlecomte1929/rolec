import React, { useEffect, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Users, CalendarDays, Flag, ShieldCheck, FolderOpen, MapPin } from 'lucide-react';
import { Input } from '../components/antigravity/Input';
import { AppShell } from '../components/AppShell';
import { Alert, Badge, Button, Card, ProgressBar } from '../components/antigravity';
import { hrAPI } from '../api/client';
import { getCaseDetailsByAssignmentId } from '../api/caseDetails';
import type {
  AssignmentDetail,
  AssignmentSummary,
  CaseDraftDTO,
  CaseRequirementsDTO,
  ComplianceReport,
} from '../types';
import { DestinationRequirements } from '../features/platform-v2/dossier/DestinationRequirements';
import { buildRoute } from '../navigation/routes';
import { safeNavigate } from '../navigation/safeNavigate';
import { blockerSummaryMessage } from '../features/cases/blockerSummaryCopy';
import { HrAssignmentServicesCapPanel } from '../features/policy-config/HrAssignmentServicesCapPanel';
import { AssignmentDebugPanel } from './AssignmentDebugPanel';
import { VisaChecklistCard } from '../features/cases/VisaChecklistCard';
import { destinationPermitLabel } from './hrAssignmentPermit';
import { pathTileSubtitle } from './hrAssignmentPathCopy';

type TabKey = 'timeline' | 'intake' | 'documents' | 'providers' | 'messages';

// ── Chip (copied from Roadmap pattern — not imported to keep this self-contained) ──

type ChipTone = 'done' | 'progress' | 'ready' | 'wait' | 'muted';

const TONE_CHIP: Record<ChipTone, string> = {
  done: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  progress: 'bg-sky-50 text-sky-700 ring-sky-200',
  ready: 'bg-teal-50 text-teal-700 ring-teal-200',
  wait: 'bg-amber-50 text-amber-700 ring-amber-200',
  muted: 'bg-slate-100 text-slate-500 ring-slate-200',
};

function Chip({ tone, children }: { tone: ChipTone; children: React.ReactNode }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${TONE_CHIP[tone]}`}
    >
      {children}
    </span>
  );
}

// ── Intake section wrapper ────────────────────────────────────────────────────

function IntakeSummarySection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card padding="md" className="mb-4">
      <div className="text-sm font-semibold text-navy-800 mb-2">{title}</div>
      <div className="text-sm text-slate-600 space-y-1">{children}</div>
    </Card>
  );
}

type CaseMessage = {
  id: string;
  author: string;
  role: 'HR' | 'EMPLOYEE';
  message: string;
  timestamp: string;
};

export const HrAssignmentReview: React.FC = () => {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selectedCaseId, setSelectedCaseId] = useState('');
  const [activeTab, setActiveTab] = useState<TabKey>('timeline');
  const [isSwitchOpen, setIsSwitchOpen] = useState(false);
  const [isNudgeOpen, setIsNudgeOpen] = useState(false);
  const [nudgeMessage, setNudgeMessage] = useState('');
  const [messages, setMessages] = useState<CaseMessage[]>([]);
  const [assistantInput, setAssistantInput] = useState('');
  const [messageInput, setMessageInput] = useState('');
  const [hrFeedbackInput, setHrFeedbackInput] = useState('');
  const [hrFeedbackSending, setHrFeedbackSending] = useState(false);
  // `hrFeedbackError` is written by the send-feedback mutation; the read error is
  // folded into `displayedFeedbackError` below.
  const [hrFeedbackError, setHrFeedbackError] = useState('');

  const assignmentsQuery = useQuery({
    queryKey: ['hr', 'assignments'],
    queryFn: async () => {
      const res = await hrAPI.listAssignments();
      return res.assignments ?? [];
    },
  });
  const assignments: AssignmentSummary[] = assignmentsQuery.data ?? [];

  const assignmentQuery = useQuery({
    queryKey: ['hr', 'assignment', selectedCaseId],
    queryFn: async () => {
      const data = await hrAPI.getAssignment(selectedCaseId);
      localStorage.setItem('relopass_last_assignment_id', data.id);
      return data;
    },
    enabled: !!selectedCaseId,
  });
  const assignment: AssignmentDetail | null = assignmentQuery.data ?? null;
  const compliance: ComplianceReport | null = assignmentQuery.data?.complianceReport ?? null;

  const intakeQuery = useQuery({
    queryKey: ['hr', 'case-details', assignment?.id],
    queryFn: async (): Promise<{ draft: CaseDraftDTO | null; errorMsg: string }> => {
      const { data, error } = await getCaseDetailsByAssignmentId(assignment!.id);
      if (error) {
        return {
          draft: null,
          errorMsg: error.includes('Case row missing')
            ? error
            : 'Assignment not found or not visible under RLS. The employee may not have started the wizard yet.',
        };
      }
      if (data) return { draft: data.case?.draft ?? null, errorMsg: '' };
      return { draft: null, errorMsg: 'Unable to load intake responses. The employee may not have started the wizard yet.' };
    },
    enabled: !!assignment?.id,
  });
  const intakeDraft: CaseDraftDTO | null = intakeQuery.data?.draft ?? null;
  const intakeError = intakeQuery.isError
    ? 'Assignment not found or not visible under RLS.'
    : intakeQuery.data?.errorMsg ?? '';
  const intakeLoading = intakeQuery.isLoading;

  const feedbackQuery = useQuery({
    queryKey: ['hr', 'feedback', assignment?.id],
    queryFn: async (): Promise<Array<{ id: string; message: string; created_at: string }>> => {
      const data = await hrAPI.getFeedback(assignment!.id);
      return data?.map((f) => ({ id: f.id, message: f.message, created_at: f.created_at })) ?? [];
    },
    enabled: !!assignment?.id,
  });
  const hrFeedback = feedbackQuery.data ?? [];
  const feedbackReadError = feedbackQuery.isError
    ? (feedbackQuery.error instanceof Error ? feedbackQuery.error.message : 'Failed to load feedback')
    : '';
  const displayedFeedbackError = hrFeedbackError || feedbackReadError;

  const assignments401 =
    (assignmentsQuery.error as { response?: { status?: number } } | null)?.response?.status === 401;
  const assignment401 =
    (assignmentQuery.error as { response?: { status?: number } } | null)?.response?.status === 401;
  const error =
    assignmentsQuery.isError && !assignments401
      ? 'Unable to load cases.'
      : assignmentQuery.isError && !assignment401
        ? 'Assignment not found or not visible under RLS.'
        : '';
  // Original kept isLoading=true until an assignment load resolved; with no case
  // selected it never flips false.
  const isLoading = selectedCaseId ? assignmentQuery.isLoading : true;

  // Initial case selection (mirrors the old loadAssignments side effect). Runs
  // once — guarded on an empty selection so a refetch can't override a manual switch.
  useEffect(() => {
    const data = assignmentsQuery.data;
    if (!data || selectedCaseId) return;
    const paramCaseId = searchParams.get('caseId') || id || localStorage.getItem('relopass_last_assignment_id');
    if (data.length > 0) {
      // data.length > 0 guarantees data[0] exists
      const first = data[0]!;
      const match = paramCaseId
        ? data.find((item) => item.id === paramCaseId || item.caseId === paramCaseId)
        : null;
      const initial = match ? match.id : paramCaseId;
      const nextId = match
        ? match.id
        : initial && data.some((item) => item.id === initial)
          ? initial
          : first.id;
      setSelectedCaseId(nextId);
      localStorage.setItem('relopass_last_assignment_id', nextId);
    } else if (paramCaseId) {
      setSelectedCaseId(paramCaseId);
    }
  }, [assignmentsQuery.data, selectedCaseId, id, searchParams]);

  // Preserve the 401 → landing redirect from both reads.
  useEffect(() => {
    if ((assignmentsQuery.isError && assignments401) || (assignmentQuery.isError && assignment401)) {
      safeNavigate(navigate, 'landing');
    }
  }, [assignmentsQuery.isError, assignments401, assignmentQuery.isError, assignment401, navigate]);

  useEffect(() => {
    if (selectedCaseId) {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set('caseId', selectedCaseId);
        return next;
      });
    }
  }, [selectedCaseId, setSearchParams]);

  const handleSendHrFeedback = async () => {
    if (!assignment?.id || !hrFeedbackInput.trim()) return;
    setHrFeedbackSending(true);
    setHrFeedbackError('');
    try {
      await hrAPI.postFeedback(assignment.id, hrFeedbackInput.trim());
      setHrFeedbackInput('');
      await queryClient.invalidateQueries({ queryKey: ['hr', 'feedback', assignment.id] });
    } catch (err: unknown) {
      setHrFeedbackError(err instanceof Error ? err.message : 'Failed to send feedback');
    } finally {
      setHrFeedbackSending(false);
    }
  };

  const profile = assignment?.profile;
  const fullName = profile?.primaryApplicant?.fullName || assignment?.employeeIdentifier || 'Employee';
  const initials = fullName
    .split(' ')
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
  const roleTitle = profile?.primaryApplicant?.employer?.roleTitle || 'Relocation case';
  // The assignment profile (movePlan) is often empty; fall back to the REAL
  // relocation case (intake draft, then the assignment's case corridor hints)
  // so the header/corridor and permit reflect actual data, not a placeholder.
  const caseBasics = intakeDraft?.relocationBasics;
  const caseFamily = intakeDraft?.familyMembers;
  const origin =
    profile?.movePlan?.origin || caseBasics?.originCountry || assignment?.caseOriginHint || '';
  const destination =
    profile?.movePlan?.destination || caseBasics?.destCountry || assignment?.caseDestinationHint || '';
  const profileFamilyMembers =
    1 + (profile?.spouse?.fullName ? 1 : 0) + (profile?.dependents?.length || 0);
  const caseFamilyMembers = caseFamily
    ? 1 + (caseFamily.spouse?.fullName ? 1 : 0) + (caseFamily.children?.length || 0)
    : 0;
  const familyMembers = Math.max(profileFamilyMembers, caseFamilyMembers);
  const targetArrival = profile?.movePlan?.targetArrivalDate || caseBasics?.targetMoveDate;
  const targetDate = targetArrival
    ? new Date(targetArrival).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : '-';
  const permitLabel = destinationPermitLabel(destination);

  // [AIQ-1902] What the destination actually requires, reported up by the
  // DestinationRequirements section mounted below. The Path tile can then stop claiming
  // there is no mapping for a destination whose requirements are listed underneath it.
  //
  // `null` is "no answer yet" (loading, or the fetch failed), NOT "nothing required" —
  // so every branch below falls back to the old copy rather than inventing reassurance.
  const [requirementsDto, setRequirementsDto] = useState<CaseRequirementsDTO | null>(null);
  const requirementCount = requirementsDto?.requirements?.length ?? 0;
  // The tile's own `destination` comes from the intake draft and the assignment hints,
  // both of which are empty on cases created outside the wizard. The dossier resolves
  // the destination from the canonical case row, so it knows when they don't.
  const knownDestination = destination || (requirementsDto?.covered ? requirementsDto.destCountry : '');
  const stageLabel =
    assignment?.status === 'submitted'
      ? 'Stage: Intake - Profile Review'
      : assignment?.status === 'approved'
      ? 'Stage: Approved'
      : assignment?.status === 'rejected'
      ? 'Stage: Rejected'
      : 'Stage: Intake - In progress';
  const readiness = Math.max(0, Math.min(100, Math.round(assignment?.completeness ?? 0)));

  const missingItem = useMemo(() => {
    if (!profile?.complianceDocs?.hasPassportScans) return 'Passport scans missing';
    if (!profile?.complianceDocs?.hasEmploymentLetter) return 'Employment letter missing';
    if (!profile?.complianceDocs?.hasBankStatements) return 'Bank statements missing';
    return 'Profile details missing';
  }, [profile?.complianceDocs]);

  const docsList = useMemo(() => {
    const docs = profile?.complianceDocs;
    if (!docs) return [];
    return [
      { label: 'Passport scans', complete: Boolean(docs.hasPassportScans) },
      { label: 'Employment letter', complete: Boolean(docs.hasEmploymentLetter) },
      { label: 'Bank statements', complete: Boolean(docs.hasBankStatements) },
      { label: 'Marriage certificate', complete: Boolean(docs.hasMarriageCertificate) },
      { label: 'Birth certificates', complete: Boolean(docs.hasBirthCertificates) },
    ];
  }, [profile?.complianceDocs]);

  const docsComplete = docsList.filter((doc) => doc.complete).length;
  const docsTotal = docsList.length || 1;

  // TASK-017: visa progress as a step count (forward-looking) rather than a 0% alarm.
  const visaChecks = compliance?.checks ?? [];
  const visaStepsSatisfied = visaChecks.filter((c) => c.status === 'COMPLIANT').length;
  const visaStepsTotal = visaChecks.length;

  // TASK-003 (AIQ-1042): single source of truth for blocking items. The
  // "Attention Needed" checklist and the ReloPass Assistant summary both read
  // this array, so the assistant can never contradict the visible list. No
  // placeholder fallback — a case with no outstanding actions genuinely reads
  // as on-track rather than inventing fake blockers.
  const attentionItems: string[] = (compliance?.actions ?? []).map((a) =>
    typeof a === 'string' ? a : a.title,
  );
  // Real tasks only — no placeholder fallbacks. An empty list renders an honest
  // "nothing yet" state instead of inventing work that doesn't exist.
  const inProgressItems = (compliance?.checks ?? [])
    .filter((check) => check.status === 'NEEDS_REVIEW')
    .map((check) => check.name);
  const completedItems = (compliance?.checks ?? [])
    .filter((check) => check.status === 'COMPLIANT')
    .map((check) => check.name);

  // Real compliance signal only. When no review exists, show a neutral note
  // rather than a fabricated red status.
  const complianceStatus = compliance?.overallStatus ?? null;
  const complianceLabel =
    complianceStatus === 'COMPLIANT'
      ? 'On track'
      : complianceStatus === 'NEEDS_REVIEW'
        ? 'Needs review'
        : complianceStatus === 'NON_COMPLIANT'
          ? 'Action required'
          : 'No compliance review yet';
  const complianceBadgeVariant: 'success' | 'warning' | 'neutral' =
    complianceStatus === 'COMPLIANT'
      ? 'success'
      : complianceStatus === 'NEEDS_REVIEW' || complianceStatus === 'NON_COMPLIANT'
        ? 'warning'
        : 'neutral';

  const handleSelectCase = (caseId: string) => {
    setSelectedCaseId(caseId);
    setIsSwitchOpen(false);
  };

  const handleOpenNudge = () => {
    setNudgeMessage(`Hi ${fullName.split(' ')[0]}, complete your profile details and upload missing documents.`);
    setIsNudgeOpen(true);
  };

  const handleSendNudge = () => {
    if (!nudgeMessage.trim()) return;
    setMessages((prev) => [
      ...prev,
      {
        id: `msg-${prev.length + 1}`,
        author: 'HR Manager',
        role: 'HR',
        message: nudgeMessage.trim(),
        timestamp: 'Just now',
      },
    ]);
    setNudgeMessage('');
    setIsNudgeOpen(false);
  };

  return (
    <AppShell title="Assignment" subtitle="Progress, compliance, and next actions.">
      {error && (
        <Alert variant="error">
          {error}
          {import.meta.env.DEV && selectedCaseId && (
            <div className="mt-2 text-xs font-mono text-slate-500">
              assignmentId: {selectedCaseId}
            </div>
          )}
        </Alert>
      )}
      {isLoading && <div className="text-sm text-slate-500">Loading case...</div>}

      {!isLoading && assignment && (
        <div className="space-y-6">
          {/* Hero: Roadmap-style gradient card (navy→teal) */}
          <div className="rounded-2xl bg-gradient-to-br from-[#0b2b43] via-[#103e54] to-[#176f6b] px-6 py-5 text-white shadow-lg flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-4 text-sm">
              <span className="text-[11px] font-semibold uppercase tracking-widest text-white/60">
                Current case
              </span>
              <span className="text-white font-bold">
                {origin && destination ? `${origin} → ${destination}` : 'Relocation case'}
              </span>
              <span className="text-white/40">•</span>
              <span className="flex items-center gap-1.5 text-white/80">
                <Users size={13} />
                {familyMembers} Family Members
              </span>
              <span className="text-white/40">•</span>
              <span className="flex items-center gap-1.5 text-white/80">
                <CalendarDays size={13} />
                Target: {targetDate}
              </span>
              <span className="text-white/40">•</span>
              <span className="flex items-center gap-1.5 text-white/80">
                <Flag size={13} />
                {stageLabel}
              </span>
            </div>
            <div className="relative">
              <Button variant="outline" onClick={() => setIsSwitchOpen((prev) => !prev)}>
                Switch Case
              </Button>
              {isSwitchOpen && (
                <div className="absolute right-0 mt-2 w-72 rounded-xl border border-slate-200 bg-white shadow-lg z-20">
                  <div className="px-4 py-2 text-xs uppercase tracking-wide text-slate-500">
                    Available cases
                  </div>
                  <div className="max-h-64 overflow-auto">
                    {assignments.map((item) => (
                      <Button unstyled
                        key={item.id}
                        onClick={() => handleSelectCase(item.id)}
                        className="w-full text-left px-4 py-3 hover:bg-slate-50 text-sm text-navy-800"
                      >
                        <div className="font-medium">{item.employeeIdentifier}</div>
                        <div className="text-xs text-slate-500">Case ID: {item.id}</div>
                      </Button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-[2.1fr,1fr] gap-6">
            <div className="space-y-6">
              <Card padding="lg">
                {/* Employee profile row */}
                <div className="flex flex-wrap items-center gap-4">
                  <div className="h-14 w-14 rounded-full bg-slate-200 flex items-center justify-center text-navy-800 font-semibold overflow-hidden">
                    {profile?.primaryApplicant?.photoUrl ? (
                      <img
                        src={profile.primaryApplicant.photoUrl}
                        alt={fullName}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      initials
                    )}
                  </div>
                  <div>
                    <div className="text-lg font-semibold text-navy-800 flex items-center gap-2">
                      {fullName}
                      <Badge variant="info">Reviewing</Badge>
                    </div>
                    <div className="text-sm text-slate-500">{roleTitle}</div>
                  </div>
                </div>

                {/* AI Insight + Compliance as antigravity Alerts */}
                <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Alert variant="info" title="AI Insight">
                    Intake form {readiness}% complete · Next: {missingItem}.
                    <div className="text-xs text-slate-500 mt-1">
                      AI-assisted · Based on what we know so far.
                    </div>
                  </Alert>
                  <Alert
                    variant={
                      complianceStatus === 'NON_COMPLIANT' || complianceStatus === 'NEEDS_REVIEW'
                        ? 'warning'
                        : 'info'
                    }
                    title="Compliance status"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span>{complianceLabel}</span>
                      {complianceStatus && (
                        <Badge variant={complianceBadgeVariant}>{complianceLabel}</Badge>
                      )}
                    </div>
                    <Button unstyled
                      className="text-[11px] text-navy-800 mt-2 underline block"
                      onClick={() =>
                        navigate(`${buildRoute('hrComplianceIndex')}?caseId=${assignment.id}`)
                      }
                    >
                      View details →
                    </Button>
                  </Alert>
                </div>

                {/* Metric cards — icon chip + accent hierarchy */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
                  <Card padding="md">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-teal-50 text-accent-500">
                        <ShieldCheck size={16} />
                      </span>
                      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Visa checklist
                      </div>
                    </div>
                    <div className="text-lg font-semibold text-navy-800">
                      {visaStepsTotal > 0
                        ? `${visaStepsSatisfied} of ${visaStepsTotal} steps complete`
                        : 'Not started yet'}
                    </div>
                    <div className="mt-3">
                      <ProgressBar
                        value={
                          visaStepsTotal > 0
                            ? Math.round((visaStepsSatisfied / visaStepsTotal) * 100)
                            : 0
                        }
                      />
                    </div>
                    {attentionItems.length > 0 && (
                      <div className="text-xs text-amber-700 mt-2 font-medium">
                        Action required
                      </div>
                    )}
                  </Card>
                  <Card padding="md">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-teal-50 text-accent-500">
                        <FolderOpen size={16} />
                      </span>
                      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Documents
                      </div>
                    </div>
                    <div className="text-lg font-semibold text-navy-800">
                      {docsComplete} of {docsTotal} uploaded
                    </div>
                  </Card>
                  <Card padding="md">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-navy-50 text-navy-800">
                        <MapPin size={16} />
                      </span>
                      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Path
                      </div>
                    </div>
                    <div className="text-xl font-semibold text-navy-800">
                      {permitLabel ?? 'To be determined'}
                    </div>
                    <div className="text-xs text-slate-500 mt-1">
                      {pathTileSubtitle({
                        permitLabel,
                        requirementCount,
                        destination: knownDestination,
                      })}
                    </div>
                  </Card>
                </div>

                {/* Segmented navy-pill tab toggle (Roadmap pattern) */}
                <div className="mt-6">
                  <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 flex-wrap gap-0.5">
                    {(['timeline', 'intake', 'documents', 'providers', 'messages'] as TabKey[]).map(
                      (tab) => (
                        <button
                          key={tab}
                          type="button"
                          onClick={() => setActiveTab(tab)}
                          className={`capitalize rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors ${
                            activeTab === tab
                              ? 'bg-navy-800 text-white font-semibold'
                              : 'text-slate-500 hover:text-navy-800'
                          }`}
                        >
                          {tab === 'providers' ? 'Services' : tab}
                        </button>
                      ),
                    )}
                  </div>
                </div>
              </Card>

              {/* [AIQ-1902] What the destination requires, from the approved catalog.
                  Mounted OUTSIDE the tab switch on purpose: it feeds the Path tile above
                  via onLoaded, and inside a tab that tile's wording would change as HR
                  clicked between tabs. Same component and same HR copy as the case
                  dossier — the four-state "an empty list never claims anything" contract
                  lives in there and must not be reimplemented here. */}
              {selectedCaseId && (
                <Card padding="md">
                  <DestinationRequirements
                    caseId={selectedCaseId}
                    audience="hr"
                    onLoaded={setRequirementsDto}
                  />
                </Card>
              )}

              {activeTab === 'timeline' && (
                <div className="space-y-6">
                  <VisaChecklistCard caseId={assignment?.id} />
                  {/* Attention/On-track → antigravity Alert; task rows → Card + Chip */}
                  {attentionItems.length > 0 ? (
                    <>
                      <Alert variant="warning" title="Attention Needed">
                        Action required · {attentionItems.length} item
                        {attentionItems.length !== 1 ? 's' : ''} blocking
                      </Alert>
                      <div className="space-y-3">
                        {attentionItems.map((item) => (
                          <Card padding="sm" key={item}>
                            <div className="flex items-center justify-between gap-4">
                              <div>
                                <div className="text-sm font-medium text-navy-800">{item}</div>
                                <div className="mt-1">
                                  {/* TASK-002: neutral 'Priority' cue rather than a personal-jeopardy
                                      framing. No fabricated due/overdue date — only real data is shown. */}
                                  <Chip tone="wait">Priority</Chip>
                                </div>
                              </div>
                              <Button variant="outline" onClick={handleOpenNudge}>
                                Nudge
                              </Button>
                            </div>
                          </Card>
                        ))}
                      </div>
                    </>
                  ) : (
                    <Alert variant="success" title="On track">
                      No items are blocking this plan right now.
                    </Alert>
                  )}

                  <Card padding="lg">
                    <div className="text-sm font-semibold text-navy-800 mb-3">In progress</div>
                    <div className="space-y-3">
                      {inProgressItems.length === 0 && (
                        <div className="text-sm text-slate-500">No tasks in progress.</div>
                      )}
                      {inProgressItems.map((item) => (
                        <div
                          key={item}
                          className="flex items-center justify-between border border-slate-200 rounded-lg p-3"
                        >
                          <div className="text-sm text-navy-800">{item}</div>
                          <Chip tone="progress">In review</Chip>
                        </div>
                      ))}
                    </div>
                  </Card>

                  <Card padding="lg">
                    <div className="text-sm font-semibold text-navy-800 mb-3">Completed</div>
                    <div className="space-y-3">
                      {completedItems.length === 0 && (
                        <div className="text-sm text-slate-500">Nothing completed yet.</div>
                      )}
                      {completedItems.map((item) => (
                        <div
                          key={item}
                          className="flex items-center justify-between border border-slate-200 rounded-lg p-3 bg-slate-50 text-slate-500"
                        >
                          <div className="text-sm">{item}</div>
                          <Chip tone="done">Done</Chip>
                        </div>
                      ))}
                    </div>
                  </Card>
                </div>
              )}

              {activeTab === 'intake' && (
                <div className="space-y-4">
                  <div className="text-sm font-semibold text-navy-800">Employee intake responses</div>
                  {intakeError && <Alert variant="error">{intakeError}</Alert>}
                  {!intakeError && intakeDraft && (
                    <>
                      <IntakeSummarySection title="Relocation Basics">
                        <div>Origin: {[intakeDraft.relocationBasics?.originCity, intakeDraft.relocationBasics?.originCountry].filter(Boolean).join(', ') || '-'}</div>
                        <div>Destination: {[intakeDraft.relocationBasics?.destCity, intakeDraft.relocationBasics?.destCountry].filter(Boolean).join(', ') || '-'}</div>
                        <div>Purpose: {intakeDraft.relocationBasics?.purpose || '-'}</div>
                        <div>Target move date: {intakeDraft.relocationBasics?.targetMoveDate || '-'}</div>
                        <div>Duration: {intakeDraft.relocationBasics?.durationMonths != null ? `${intakeDraft.relocationBasics.durationMonths} months` : '-'}</div>
                      </IntakeSummarySection>
                      <IntakeSummarySection title="Employee Profile">
                        <div>Name: {intakeDraft.employeeProfile?.fullName || '-'}</div>
                        <div>Email: {intakeDraft.employeeProfile?.email || '-'}</div>
                        <div>Nationality: {intakeDraft.employeeProfile?.nationality || '-'}</div>
                        <div>Passport country: {intakeDraft.employeeProfile?.passportCountry || '-'}</div>
                        <div>Residence country: {intakeDraft.employeeProfile?.residenceCountry || '-'}</div>
                      </IntakeSummarySection>
                      <IntakeSummarySection title="Family Members">
                        <div>Spouse: {intakeDraft.familyMembers?.spouse?.fullName ? intakeDraft.familyMembers.spouse.fullName : '-'}</div>
                        <div>Children: {intakeDraft.familyMembers?.children?.length ? `${intakeDraft.familyMembers.children.length} child(ren)` : '-'}</div>
                      </IntakeSummarySection>
                      <IntakeSummarySection title="Assignment / Context">
                        <div>Employer: {intakeDraft.assignmentContext?.employerName || '-'}</div>
                        <div>Job title: {intakeDraft.assignmentContext?.jobTitle || '-'}</div>
                        <div>Contract start: {intakeDraft.assignmentContext?.contractStartDate || '-'}</div>
                        <div>Contract type: {intakeDraft.assignmentContext?.contractType || '-'}</div>
                      </IntakeSummarySection>
                    </>
                  )}
                  {!intakeError && intakeLoading && (
                    <div className="text-sm text-slate-500">Loading intake data...</div>
                  )}
                  {!intakeError && !intakeLoading && !intakeDraft && (
                    <div className="text-sm text-slate-500">No intake data available.</div>
                  )}
                </div>
              )}

              {activeTab === 'documents' && (
                <Card padding="lg">
                  <div className="text-sm font-semibold text-navy-800 mb-4">Documents</div>
                  <div className="space-y-3">
                    {docsList.map((doc) => (
                      <div
                        key={doc.label}
                        className="flex items-center justify-between border border-slate-200 rounded-lg p-3"
                      >
                        <div className="text-sm text-navy-800">{doc.label}</div>
                        <Badge variant={doc.complete ? 'success' : 'warning'}>
                          {doc.complete ? 'Uploaded' : 'Missing'}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {activeTab === 'providers' && (
                <Card padding="lg">
                  <div className="text-sm font-semibold text-navy-800 mb-2">
                    Services & provider estimates
                  </div>
                  <div className="text-xs text-slate-500 mb-4">
                    Relocation services and employee-entered estimates, with policy cap comparison for HR.
                  </div>
                  {assignment?.id ? (
                    <HrAssignmentServicesCapPanel assignmentId={assignment.id} />
                  ) : null}
                </Card>
              )}

              {activeTab === 'messages' && (
                <Card padding="lg">
                  <div className="text-sm font-semibold text-navy-800 mb-4">Messages</div>
                  <div className="space-y-3">
                    {messages.length === 0 && (
                      <div className="text-sm text-slate-500">No messages yet.</div>
                    )}
                    {messages.map((item) => (
                      <div key={item.id} className="border border-slate-200 rounded-lg p-3">
                        <div className="text-xs text-slate-500">{item.timestamp}</div>
                        <div className="text-sm text-navy-800 mt-1">
                          <span className="font-semibold">{item.author}</span>: {item.message}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-4 flex gap-2">
                    <Input unstyled
                      value={messageInput}
                      onChange={(event) => setMessageInput(event)}
                      placeholder="Write a message..."
                      className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-navy-800"
                    />
                    <Button
                      onClick={() => {
                        if (!messageInput.trim()) return;
                        setMessages((prev) => [
                          ...prev,
                          {
                            id: `msg-${prev.length + 1}`,
                            author: 'HR Manager',
                            role: 'HR',
                            message: messageInput.trim(),
                            timestamp: 'Just now',
                          },
                        ]);
                        setMessageInput('');
                      }}
                    >
                      Send
                    </Button>
                  </div>
                </Card>
              )}
            </div>

            <div className="space-y-4">
              <Card padding="lg">
                <div className="text-sm font-semibold text-navy-800 mb-3">Provide feedback</div>
                <textarea
                  value={hrFeedbackInput}
                  onChange={(e) => setHrFeedbackInput(e.target.value)}
                  placeholder="Add feedback for the employee..."
                  rows={3}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-navy-800"
                />
                {displayedFeedbackError && (
                  <div className="text-xs text-red-600 mt-2">{displayedFeedbackError}</div>
                )}
                <Button
                  onClick={handleSendHrFeedback}
                  disabled={!hrFeedbackInput.trim() || hrFeedbackSending}
                  className="mt-2"
                >
                  {hrFeedbackSending ? 'Sending...' : 'Send feedback'}
                </Button>
                <div className="mt-4 pt-4 border-t border-slate-200">
                  <div className="text-xs font-medium text-slate-500 mb-2">Feedback history</div>
                  {hrFeedback.length === 0 && (
                    <div className="text-xs text-slate-500">No feedback yet.</div>
                  )}
                  {hrFeedback.map((f) => (
                    <div key={f.id} className="mb-3 text-sm">
                      <div className="text-slate-500 text-xs">
                        {new Date(f.created_at).toLocaleString()}
                      </div>
                      <div className="text-navy-800 mt-0.5">{f.message}</div>
                    </div>
                  ))}
                </div>
              </Card>

              <Card padding="lg">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-semibold text-navy-800">ReloPass Assistant</div>
                    <div className="text-xs text-slate-500">AI Guidance</div>
                  </div>
                  <Button unstyled aria-label="More options" className="text-slate-500 hover:text-navy-800">
                    ⋯
                  </Button>
                </div>
                <div className="mt-4 space-y-3 text-sm text-slate-600">
                  <div className="border border-slate-200 rounded-lg p-3 bg-slate-50">
                    {/* TASK-003 (AIQ-1042): count the same `attentionItems` the checklist
                        renders so the assistant can't contradict the visible list. */}
                    {blockerSummaryMessage(attentionItems.length, attentionItems[0])}
                  </div>
                  <Button variant="outline" fullWidth>
                    Draft urgent reminder for Profile
                  </Button>
                  <Button variant="outline" fullWidth>
                    What&apos;s blocking {fullName.split(' ')[0]}&apos;s profile completion?
                  </Button>
                  <Button variant="outline" fullWidth>
                    What documents are needed for{' '}
                    {origin && destination ? `${origin} → ${destination}` : 'this route'}?
                  </Button>
                </div>
                <div className="mt-4 flex gap-2">
                  <Input unstyled
                    value={assistantInput}
                    onChange={(event) => setAssistantInput(event)}
                    placeholder="Ask about this case..."
                    className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-navy-800"
                  />
                  <Button variant="outline">Send</Button>
                </div>
                <div className="text-[11px] text-slate-500 mt-3">
                  ReloPass AI can make mistakes. Verify key details.
                </div>
              </Card>
            </div>
          </div>
        </div>
      )}

      {(import.meta.env.DEV || import.meta.env.VITE_DEV_TOOLS === 'true') && selectedCaseId && (
        <AssignmentDebugPanel assignmentIdFromRoute={selectedCaseId} />
      )}
      {isNudgeOpen && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <Card padding="lg" className="w-full max-w-lg">
            <div className="flex items-center justify-between mb-4">
              <div className="text-sm font-semibold text-navy-800">Send nudge</div>
              <Button unstyled
                onClick={() => setIsNudgeOpen(false)}
                className="text-sm text-slate-500 hover:text-navy-800"
              >
                Close
              </Button>
            </div>
            <textarea
              value={nudgeMessage}
              onChange={(event) => setNudgeMessage(event.target.value)}
              rows={4}
              className="w-full border border-slate-200 rounded-md p-2 text-sm focus:outline-none focus:ring-2 focus:ring-navy-800"
            />
            <div className="flex items-center justify-end gap-2 mt-4">
              <Button variant="outline" onClick={() => setIsNudgeOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleSendNudge}>Send</Button>
            </div>
          </Card>
        </div>
      )}
    </AppShell>
  );
};
