import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Alert, Badge, Button, Card, ProgressBar } from '../components/antigravity';
import { hrAPI } from '../api/client';
import type { AssignmentDetail, AssignmentSummary, ComplianceReport } from '../types';
import { buildRoute } from '../navigation/routes';
import { safeNavigate } from '../navigation/safeNavigate';

type TabKey = 'timeline' | 'documents' | 'providers' | 'messages';

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
  const [assignments, setAssignments] = useState<AssignmentSummary[]>([]);
  const [assignment, setAssignment] = useState<AssignmentDetail | null>(null);
  const [compliance, setCompliance] = useState<ComplianceReport | null>(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [selectedCaseId, setSelectedCaseId] = useState('');
  const [activeTab, setActiveTab] = useState<TabKey>('timeline');
  const [isSwitchOpen, setIsSwitchOpen] = useState(false);
  const [isNudgeOpen, setIsNudgeOpen] = useState(false);
  const [nudgeMessage, setNudgeMessage] = useState('');
  const [messages, setMessages] = useState<CaseMessage[]>([]);
  const [assistantInput, setAssistantInput] = useState('');
  const [messageInput, setMessageInput] = useState('');

  const loadAssignments = async () => {
    try {
      const data = await hrAPI.listAssignments();
      setAssignments(data);
      if (data.length > 0) {
        const initial = id || searchParams.get('caseId') || localStorage.getItem('relopass_last_assignment_id');
        const nextId = initial && data.some((item) => item.id === initial) ? initial : data[0].id;
        setSelectedCaseId(nextId);
        localStorage.setItem('relopass_last_assignment_id', nextId);
      }
    } catch (err: any) {
      if (err.response?.status === 401) {
        safeNavigate(navigate, 'landing');
      } else {
        setError('Unable to load cases.');
      }
    }
  };

  const loadAssignment = async (caseId: string) => {
    if (!caseId) return;
    setIsLoading(true);
    try {
      const data = await hrAPI.getAssignment(caseId);
      setAssignment(data);
      setCompliance(data.complianceReport || null);
      localStorage.setItem('relopass_last_assignment_id', data.id);
    } catch (err: any) {
      if (err.response?.status === 401) {
        safeNavigate(navigate, 'landing');
      } else {
        setError('Unable to load case details.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAssignments();
  }, []);

  useEffect(() => {
    if (selectedCaseId) {
      loadAssignment(selectedCaseId);
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set('caseId', selectedCaseId);
        return next;
      });
    }
  }, [selectedCaseId]);

  useEffect(() => {
    if (!assignment) return;
    const seedMessages: CaseMessage[] = [
      {
        id: 'msg-1',
        author: assignment.employeeIdentifier || 'Employee',
        role: 'EMPLOYEE',
        message: 'Started uploading documents. Will complete the profile today.',
        timestamp: 'Today, 9:45 AM',
      },
      {
        id: 'msg-2',
        author: 'HR Manager',
        role: 'HR',
        message: 'Thanks! Please prioritize passport scans and employment letter.',
        timestamp: 'Today, 10:05 AM',
      },
    ];
    setMessages(seedMessages);
  }, [assignment?.id]);

  const profile = assignment?.profile;
  const fullName = profile?.primaryApplicant?.fullName || assignment?.employeeIdentifier || 'Employee';
  const initials = fullName
    .split(' ')
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
  const roleTitle = profile?.primaryApplicant?.employer?.roleTitle || 'Relocation case';
  const origin = profile?.movePlan?.origin;
  const destination = profile?.movePlan?.destination;
  const familyMembers = 1 + (profile?.spouse?.fullName ? 1 : 0) + (profile?.dependents?.length || 0);
  const targetDate = profile?.movePlan?.targetArrivalDate
    ? new Date(profile.movePlan.targetArrivalDate).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : '—';
  const stageLabel = assignment?.status === 'EMPLOYEE_SUBMITTED'
    ? 'Stage: Intake - Profile Review'
    : assignment?.status === 'CHANGES_REQUESTED'
    ? 'Stage: Changes Requested'
    : assignment?.status === 'HR_APPROVED'
    ? 'Stage: Approved'
    : 'Stage: Intake - In progress';
  const readiness = Math.max(0, Math.min(100, Math.round(assignment?.completeness ?? 0)));
  const complianceStatus = compliance?.overallStatus || 'NEEDS_REVIEW';
  const blockingItems = compliance?.checks?.filter((check) => check.status !== 'COMPLIANT') || [];

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

  const attentionItems = compliance?.actions?.length
    ? compliance.actions
    : ['Complete employee profile', 'Collect passport scans'];
  const inProgressItems = compliance?.checks?.length
    ? compliance.checks.filter((check) => check.status === 'NEEDS_REVIEW').map((check) => check.name)
    : ['Confirm housing budget', 'Verify assignment details'];
  const completedItems = compliance?.checks?.length
    ? compliance.checks.filter((check) => check.status === 'COMPLIANT').map((check) => check.name)
    : ['Case created', 'Employee onboarded'];

  const handleSelectCase = (caseId: string) => {
    setSelectedCaseId(caseId);
    setIsSwitchOpen(false);
  };

  const handleOpenNudge = () => {
    setNudgeMessage(`Hi ${fullName.split(' ')[0]}, please complete your profile details and upload missing documents.`);
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
    <AppShell title="Employee Dashboard" subtitle="Review case progress, compliance, and next actions.">
      {error && <Alert variant="error">{error}</Alert>}
      {isLoading && <div className="text-sm text-[#6b7280]">Loading case...</div>}

      {!isLoading && assignment && (
        <div className="space-y-6">
          <div className="bg-[#0b1d33] text-white rounded-xl px-6 py-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-4 text-xs uppercase tracking-wide text-[#bfdbfe]">
              <span>Current case</span>
              <span className="text-white text-sm font-semibold normal-case">
                {origin && destination ? `${origin} → ${destination}` : 'Relocation case'}
              </span>
              <span className="text-[#bfdbfe]">•</span>
              <span className="flex items-center gap-1 normal-case">
                <span>👥</span>
                {familyMembers} Family Members
              </span>
              <span className="text-[#bfdbfe]">•</span>
              <span className="flex items-center gap-1 normal-case">
                <span>📅</span>
                Target: {targetDate}
              </span>
              <span className="text-[#bfdbfe]">•</span>
              <span className="flex items-center gap-1 normal-case">
                <span>🚩</span>
                {stageLabel}
              </span>
            </div>
            <div className="relative">
              <Button variant="outline" onClick={() => setIsSwitchOpen((prev) => !prev)}>
                Switch Case
              </Button>
              {isSwitchOpen && (
                <div className="absolute right-0 mt-2 w-72 rounded-xl border border-[#e2e8f0] bg-white shadow-lg z-20">
                  <div className="px-4 py-2 text-xs uppercase tracking-wide text-[#6b7280]">
                    Available cases
                  </div>
                  <div className="max-h-64 overflow-auto">
                    {assignments.map((item) => (
                      <button
                        key={item.id}
                        onClick={() => handleSelectCase(item.id)}
                        className="w-full text-left px-4 py-3 hover:bg-[#f8fafc] text-sm text-[#0b2b43]"
                      >
                        <div className="font-medium">{item.employeeIdentifier}</div>
                        <div className="text-xs text-[#6b7280]">Case ID: {item.id}</div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-[2.1fr,1fr] gap-6">
            <div className="space-y-6">
              <Card padding="lg">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="flex items-center gap-4">
                    <div className="h-14 w-14 rounded-full bg-[#e2e8f0] flex items-center justify-center text-[#0b2b43] font-semibold overflow-hidden">
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
                      <div className="text-lg font-semibold text-[#0b2b43] flex items-center gap-2">
                        {fullName}
                        <Badge variant="info">Reviewing</Badge>
                      </div>
                      <div className="text-sm text-[#6b7280]">{roleTitle}</div>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <div className="border border-[#d7e3ed] bg-[#f4f7fb] rounded-lg px-3 py-2 text-xs text-[#0b2b43] max-w-xs">
                      <div className="font-semibold uppercase text-[10px] text-[#5b6b7a] mb-1">AI Insight</div>
                      <div>Profile completion {readiness}%. {missingItem}. Est. delay 4 days.</div>
                      <div className="text-[10px] text-[#6b7280] mt-2">
                        AI-generated summary. Not a final decision.
                      </div>
                    </div>
                    <div className="border border-[#f3d6d6] bg-[#fff5f5] rounded-lg px-3 py-2 text-xs text-[#7a2a2a]">
                      <div className="font-semibold uppercase text-[10px] text-[#a34b4b] mb-1">Compliance status</div>
                      <div className="flex items-center justify-between gap-2">
                        <span>Specialist Required</span>
                        <Badge variant="warning">High Risk</Badge>
                      </div>
                      <button
                        className="text-[11px] text-[#0b2b43] mt-2 underline"
                        onClick={() =>
                          navigate(`${buildRoute('hrComplianceIndex')}?caseId=${assignment.id}`)
                        }
                      >
                        View details →
                      </button>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
                  <Card padding="md">
                    <div className="text-xs uppercase tracking-wide text-[#6b7280]">Visa readiness</div>
                    <div className="text-2xl font-semibold text-[#0b2b43] mt-2">{readiness}%</div>
                    <div className="mt-3">
                      <ProgressBar value={readiness} />
                    </div>
                    {blockingItems.length > 0 && (
                      <div className="text-xs text-[#b45309] mt-2">Action required</div>
                    )}
                  </Card>
                  <Card padding="md">
                    <div className="text-xs uppercase tracking-wide text-[#6b7280]">Docs collected</div>
                    <div className="text-2xl font-semibold text-[#0b2b43] mt-2">
                      {docsComplete}/{docsTotal}
                    </div>
                    <div className="text-xs text-[#6b7280] mt-1">Critical documents</div>
                  </Card>
                  <Card padding="md">
                    <div className="text-xs uppercase tracking-wide text-[#6b7280]">Path</div>
                    <div className="text-2xl font-semibold text-[#0b2b43] mt-2">L-1B Visa</div>
                    <div className="text-xs text-[#6b7280] mt-1">Mobility track</div>
                  </Card>
                </div>

                <div className="border-b border-[#e2e8f0] mt-6" />
                <div className="flex flex-wrap gap-6 text-sm text-[#6b7280] mt-3">
                  {(['timeline', 'documents', 'providers', 'messages'] as TabKey[]).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className={`capitalize ${
                        activeTab === tab ? 'text-[#0b2b43] font-semibold' : 'hover:text-[#0b2b43]'
                      }`}
                    >
                      {tab}
                    </button>
                  ))}
                </div>
              </Card>

              {activeTab === 'timeline' && (
                <div className="space-y-6">
                  <Card padding="lg" className="border border-[#fde2e2] bg-[#fff5f5]">
                    <div className="flex items-center gap-2 text-sm font-semibold text-[#7a2a2a]">
                      Attention Needed
                      <span className="text-xs text-[#6b7280]">Action required / Blocking</span>
                    </div>
                    <div className="mt-4 space-y-3">
                      {attentionItems.map((item) => (
                        <div
                          key={item}
                          className="flex items-center justify-between gap-4 border border-[#f4c7c7] bg-white rounded-lg p-3"
                        >
                          <div>
                            <div className="text-sm font-medium text-[#0b2b43]">{item}</div>
                            <div className="text-xs text-[#6b7280]">
                              <span className="inline-flex items-center gap-1 mr-2">
                                <Badge variant="warning">EMPLOYEE</Badge>
                                <Badge variant="warning">HIGH RISK</Badge>
                              </span>
                              Overdue by 3 days
                            </div>
                          </div>
                          <Button variant="outline" onClick={handleOpenNudge}>
                            Nudge
                          </Button>
                        </div>
                      ))}
                    </div>
                  </Card>

                  <Card padding="lg">
                    <div className="text-sm font-semibold text-[#0b2b43] mb-3">In progress</div>
                    <div className="space-y-3">
                      {inProgressItems.map((item) => (
                        <div key={item} className="flex items-center justify-between border border-[#e2e8f0] rounded-lg p-3">
                          <div>
                            <div className="text-sm text-[#0b2b43]">{item}</div>
                            <div className="text-xs text-[#6b7280]">Owner: HR team</div>
                          </div>
                          <Badge variant="neutral">Due tomorrow</Badge>
                        </div>
                      ))}
                    </div>
                  </Card>

                  <Card padding="lg">
                    <div className="text-sm font-semibold text-[#0b2b43] mb-3">Completed</div>
                    <div className="space-y-3">
                      {completedItems.map((item) => (
                        <div key={item} className="flex items-center justify-between border border-[#e2e8f0] rounded-lg p-3 bg-[#f8fafc] text-[#94a3b8]">
                          <div className="text-sm">{item}</div>
                          <Badge variant="success">Done</Badge>
                        </div>
                      ))}
                    </div>
                  </Card>
                </div>
              )}

              {activeTab === 'documents' && (
                <Card padding="lg">
                  <div className="text-sm font-semibold text-[#0b2b43] mb-4">Documents</div>
                  <div className="space-y-3">
                    {docsList.map((doc) => (
                      <div key={doc.label} className="flex items-center justify-between border border-[#e2e8f0] rounded-lg p-3">
                        <div className="text-sm text-[#0b2b43]">{doc.label}</div>
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
                  <div className="text-sm font-semibold text-[#0b2b43] mb-4">Providers</div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {[
                      { title: 'Housing partner', status: 'Shortlist', owner: 'HR' },
                      { title: 'Immigration counsel', status: 'Specialist Required', owner: 'HR' },
                      { title: 'Movers & logistics', status: 'Quotes pending', owner: 'Employee' },
                      { title: 'Schooling advisor', status: 'On hold', owner: 'HR' },
                    ].map((item) => (
                      <div key={item.title} className="border border-[#e2e8f0] rounded-lg p-4 bg-white">
                        <div className="text-sm font-semibold text-[#0b2b43]">{item.title}</div>
                        <div className="text-xs text-[#6b7280] mt-1">Owner: {item.owner}</div>
                        <div className="text-xs text-[#6b7280] mt-3">Status: {item.status}</div>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {activeTab === 'messages' && (
                <Card padding="lg">
                  <div className="text-sm font-semibold text-[#0b2b43] mb-4">Messages</div>
                  <div className="space-y-3">
                    {messages.map((item) => (
                      <div key={item.id} className="border border-[#e2e8f0] rounded-lg p-3">
                        <div className="text-xs text-[#6b7280]">{item.timestamp}</div>
                        <div className="text-sm text-[#0b2b43] mt-1">
                          <span className="font-semibold">{item.author}</span>: {item.message}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-4 flex gap-2">
                    <input
                      value={messageInput}
                      onChange={(event) => setMessageInput(event.target.value)}
                      placeholder="Write a message..."
                      className="flex-1 rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
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
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-semibold text-[#0b2b43]">ReloPass Assistant</div>
                    <div className="text-xs text-[#6b7280]">AI Guidance</div>
                  </div>
                  <button className="text-[#94a3b8] hover:text-[#0b2b43]">⋯</button>
                </div>
                <div className="mt-4 space-y-3 text-sm text-[#4b5563]">
                  <div className="border border-[#e2e8f0] rounded-lg p-3 bg-[#f8fafc]">
                    Case review: readiness is {readiness}%. {blockingItems.length} blocking items remain.
                  </div>
                  <Button variant="outline" fullWidth>
                    Draft urgent reminder for Profile
                  </Button>
                  <Button variant="outline" fullWidth>
                    What’s blocking {fullName.split(' ')[0]}'s profile completion?
                  </Button>
                  <Button variant="outline" fullWidth>
                    What documents are needed for {origin && destination ? `${origin} → ${destination}` : 'this route'}?
                  </Button>
                </div>
                <div className="mt-4 flex gap-2">
                  <input
                    value={assistantInput}
                    onChange={(event) => setAssistantInput(event.target.value)}
                    placeholder="Ask about this case..."
                    className="flex-1 rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
                  />
                  <Button variant="outline">Send</Button>
                </div>
                <div className="text-[11px] text-[#94a3b8] mt-3">
                  ReloPass AI can make mistakes. Verify key details.
                </div>
              </Card>
            </div>
          </div>
        </div>
      )}

      {isNudgeOpen && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <Card padding="lg" className="w-full max-w-lg">
            <div className="flex items-center justify-between mb-4">
              <div className="text-sm font-semibold text-[#0b2b43]">Send nudge</div>
              <button
                onClick={() => setIsNudgeOpen(false)}
                className="text-sm text-[#6b7280] hover:text-[#0b2b43]"
              >
                Close
              </button>
            </div>
            <textarea
              value={nudgeMessage}
              onChange={(event) => setNudgeMessage(event.target.value)}
              rows={4}
              className="w-full border border-[#d1d5db] rounded-md p-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0b2b43]"
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
