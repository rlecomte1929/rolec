import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Alert, Button, Card, Input } from '../components/antigravity';
import { employeeAPI } from '../api/client';
import { getAuthItem } from '../utils/demo';
import type { AssignmentStatus, EmployeeJourneyResponse } from '../types';
import { safeNavigate } from '../navigation/safeNavigate';

const INTAKE_STATUSES: AssignmentStatus[] = ['DRAFT', 'IN_PROGRESS', 'CHANGES_REQUESTED'];
const SUBMITTED_STATUSES: AssignmentStatus[] = ['EMPLOYEE_SUBMITTED', 'HR_REVIEW', 'HR_APPROVED'];

function statusLabel(status?: AssignmentStatus) {
  if (status === 'HR_APPROVED') return 'Approved';
  if (status === 'HR_REVIEW') return 'Under HR review';
  if (status === 'EMPLOYEE_SUBMITTED') return 'Submitted to HR';
  if (status === 'CHANGES_REQUESTED') return 'Changes requested';
  return 'In intake';
}

export const EmployeeJourney: React.FC = () => {
  const [assignmentId, setAssignmentId] = useState<string | null>(null);
  const [journey, setJourney] = useState<EmployeeJourneyResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [claimId, setClaimId] = useState('');
  const [claimEmail, setClaimEmail] = useState(getAuthItem('relopass_email') || '');

  const navigate = useNavigate();

  const loadAssignment = async () => {
    setIsLoading(true);
    setError('');
    try {
      const response = await employeeAPI.getCurrentAssignment();
      if (!response.assignment) {
        setAssignmentId(null);
        setJourney(null);
        return;
      }
      setAssignmentId(response.assignment.id);
      const data = await employeeAPI.getNextQuestion(response.assignment.id);
      setJourney(data);
    } catch (err: any) {
      if (err.response?.status === 401) {
        safeNavigate(navigate, 'landing');
      } else {
        setError('Unable to load your case.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAssignment();
  }, []);

  const status = journey?.assignmentStatus as AssignmentStatus | undefined;
  const isIntake = status ? INTAKE_STATUSES.includes(status) : false;
  const isSubmitted = status ? SUBMITTED_STATUSES.includes(status) : false;

  // Wizard-first, dashboard-later:
  // - before submission: force the wizard
  // - after submission: force the dashboard (read-only)
  useEffect(() => {
    if (!assignmentId || !journey || !status) return;
    if (status === 'CHANGES_REQUESTED' && journey.hrNotes) {
      sessionStorage.setItem('relopass_hr_notes', journey.hrNotes);
    }
    if (isIntake) {
      navigate(`/employee/case/${assignmentId}/wizard/1`, { replace: true });
      return;
    }
    if (isSubmitted) {
      // If they came via /employee/journey, keep them here (this page is also /employee/dashboard).
      return;
    }
  }, [assignmentId, journey, status, isIntake, isSubmitted, navigate]);

  const answeredCount = journey?.progress?.answeredCount || 0;
  const totalQuestions = journey?.progress?.totalQuestions || 0;
  const requiredDone = Math.min(answeredCount, totalQuestions);
  const progressPercent = totalQuestions > 0 ? Math.round((requiredDone / totalQuestions) * 100) : 0;
  const progressPercentCapped = Math.max(0, Math.min(100, progressPercent));

  const profile = journey?.profile;

  const family = useMemo(() => {
    const spouseName = profile?.spouse?.fullName || '';
    const children = profile?.dependents?.filter((child) => child.firstName) || [];
    return { spouseName, children };
  }, [profile?.spouse?.fullName, profile?.dependents]);

  const handleClaimAssignment = async () => {
    if (!claimId.trim() || !claimEmail.trim()) {
      setError('Enter your email and the assignment ID provided by HR.');
      return;
    }
    setError('');
    try {
      await employeeAPI.claimAssignment(claimId.trim(), claimEmail.trim());
      await loadAssignment();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to claim assignment.');
    }
  };

  return (
    <AppShell title="Employee Journey" subtitle="Complete your relocation profile for HR review.">
      {isLoading && <div className="text-sm text-[#6b7280]">Loading...</div>}

      {!isLoading && error && (
        <Alert variant="error">{error}</Alert>
      )}

      {!isLoading && !assignmentId && (
        <Card padding="lg">
          <div className="space-y-3">
            <div className="text-lg font-semibold text-[#0b2b43]">No relocation case assigned yet</div>
            <div className="text-sm text-[#4b5563]">
              When HR assigns your relocation case, you’ll complete a short 5-step wizard. If you already received an assignment ID, enter it below.
            </div>
            <div className="pt-2 space-y-3">
              <Input
                type="email"
                value={claimEmail}
                onChange={setClaimEmail}
                label="Email"
                placeholder="you@example.com"
                fullWidth
              />
              <Input
                value={claimId}
                onChange={setClaimId}
                label="Assignment ID"
                placeholder="Paste the assignment ID from HR"
                fullWidth
              />
              <div className="flex flex-wrap gap-2">
                <Button onClick={handleClaimAssignment}>Start</Button>
                <Button variant="outline" onClick={loadAssignment}>Refresh</Button>
              </div>
              <Button variant="outline" onClick={() => safeNavigate(navigate, 'messages')}>Contact HR / Support</Button>
            </div>
          </div>
        </Card>
      )}

      {!isLoading && assignmentId && journey && isIntake && (
        <Card padding="lg">
          <Alert variant="info">
            <div className="space-y-2">
              <div className="font-semibold text-[#0b2b43]">Continue your case intake</div>
              <div className="text-sm text-[#4b5563]">
                Complete your relocation details in the Case Wizard. Redirecting now.
              </div>
              <div className="flex flex-wrap gap-2 pt-2">
                <Button onClick={() => navigate(`/employee/case/${assignmentId}/wizard/1`)}>Open case wizard</Button>
                <Button variant="outline" onClick={loadAssignment}>Refresh</Button>
              </div>
            </div>
          </Alert>
        </Card>
      )}

      {!isLoading && assignmentId && journey && isSubmitted && (
        <div className="space-y-6">
          <Card padding="lg">
            <div className="flex flex-wrap items-start justify-between gap-6">
              <div>
                <div className="text-2xl font-semibold text-[#0b2b43]">
                  {profile?.primaryApplicant?.fullName || 'Employee'}
                </div>
                <div className="text-sm text-[#6b7280] mt-2">
                  {profile?.movePlan?.origin || '—'} → {profile?.movePlan?.destination || '—'}
                </div>
                <div className="text-xs text-[#6b7280] mt-1">
                  Target move: {profile?.movePlan?.targetArrivalDate || '—'}
                </div>
                <div className="mt-3 inline-flex items-center rounded-full bg-[#eef4f8] text-[#0b2b43] px-3 py-1 text-xs font-semibold">
                  {statusLabel(status)}
                </div>
              </div>

              <div className="w-full max-w-xs space-y-3">
                <div className="rounded-lg border border-[#e2e8f0] bg-white p-3">
                  <div className="text-xs text-[#6b7280] mb-2">Progress</div>
                  <div className="flex items-center justify-between text-xs text-[#6b7280]">
                    <span>{requiredDone} of {totalQuestions} required items completed</span>
                    <span className="font-semibold text-[#0b2b43]">{progressPercentCapped}%</span>
                  </div>
                  <div className="mt-2 h-1.5 w-full rounded-full bg-[#e2e8f0]">
                    <div className="h-1.5 rounded-full bg-[#0b2b43]" style={{ width: `${progressPercentCapped}%` }} />
                  </div>
                </div>
                <div className="rounded-lg border border-[#e2e8f0] bg-white p-3">
                  <div className="text-xs text-[#6b7280] mb-1">Edits</div>
                  <div className="text-xs text-[#4b5563]">
                    This case is read-only during HR review. If HR requests changes, you’ll be guided back into the wizard.
                  </div>
                </div>
                <div className="rounded-lg border border-[#e2e8f0] bg-white p-3">
                  <div className="text-xs text-[#6b7280] mb-1">Next steps</div>
                  <div className="text-xs text-[#4b5563]">
                    You can continue exploring relocation Providers while HR reviews your submission.
                  </div>
                  <div className="mt-3">
                    <Button variant="outline" onClick={() => safeNavigate(navigate, 'providers')}>
                      Open Providers
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card padding="lg">
              <div className="text-sm font-semibold text-[#0b2b43]">Relocation Basics</div>
              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div className="border border-[#e2e8f0] rounded-lg p-3">
                  <div className="text-xs uppercase tracking-wide text-[#6b7280]">Origin</div>
                  <div className="text-[#0b2b43] font-medium mt-1">{profile?.movePlan?.origin || '—'}</div>
                </div>
                <div className="border border-[#e2e8f0] rounded-lg p-3">
                  <div className="text-xs uppercase tracking-wide text-[#6b7280]">Destination</div>
                  <div className="text-[#0b2b43] font-medium mt-1">{profile?.movePlan?.destination || '—'}</div>
                </div>
                <div className="border border-[#e2e8f0] rounded-lg p-3">
                  <div className="text-xs uppercase tracking-wide text-[#6b7280]">Target move date</div>
                  <div className="text-[#0b2b43] font-medium mt-1">{profile?.movePlan?.targetArrivalDate || '—'}</div>
                </div>
                <div className="border border-[#e2e8f0] rounded-lg p-3">
                  <div className="text-xs uppercase tracking-wide text-[#6b7280]">Purpose</div>
                  <div className="text-[#0b2b43] font-medium mt-1">Employment</div>
                </div>
              </div>
            </Card>

            <Card padding="lg">
              <div className="text-sm font-semibold text-[#0b2b43]">Employee Profile</div>
              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div className="border border-[#e2e8f0] rounded-lg p-3">
                  <div className="text-xs uppercase tracking-wide text-[#6b7280]">Nationality</div>
                  <div className="text-[#0b2b43] font-medium mt-1">{profile?.primaryApplicant?.nationality || '—'}</div>
                </div>
                <div className="border border-[#e2e8f0] rounded-lg p-3">
                  <div className="text-xs uppercase tracking-wide text-[#6b7280]">Role title</div>
                  <div className="text-[#0b2b43] font-medium mt-1">{profile?.primaryApplicant?.employer?.roleTitle || '—'}</div>
                </div>
                <div className="border border-[#e2e8f0] rounded-lg p-3">
                  <div className="text-xs uppercase tracking-wide text-[#6b7280]">Passport expiry</div>
                  <div className="text-[#0b2b43] font-medium mt-1">{profile?.primaryApplicant?.passport?.expiryDate || '—'}</div>
                </div>
                <div className="border border-[#e2e8f0] rounded-lg p-3">
                  <div className="text-xs uppercase tracking-wide text-[#6b7280]">Job level</div>
                  <div className="text-[#0b2b43] font-medium mt-1">{profile?.primaryApplicant?.employer?.jobLevel || '—'}</div>
                </div>
              </div>
            </Card>

            <Card padding="lg">
              <div className="text-sm font-semibold text-[#0b2b43] mb-3">Family Members</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="border border-[#e2e8f0] rounded-lg p-3">
                  <div className="text-xs uppercase tracking-wide text-[#6b7280]">Spouse</div>
                  <div className="text-sm font-medium text-[#0b2b43] mt-1">{family.spouseName || 'Not included'}</div>
                </div>
                <div className="border border-[#e2e8f0] rounded-lg p-3">
                  <div className="text-xs uppercase tracking-wide text-[#6b7280]">Children</div>
                  <div className="text-sm font-medium text-[#0b2b43] mt-1">{family.children.length}</div>
                </div>
              </div>
              {family.children.length > 0 ? (
                <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
                  {family.children.map((child, idx) => (
                    <div key={`${child.firstName}-${idx}`} className="border border-[#e2e8f0] rounded-lg p-3">
                      <div className="text-xs uppercase tracking-wide text-[#6b7280]">Child</div>
                      <div className="text-sm font-medium text-[#0b2b43] mt-1">{child.firstName}</div>
                      <div className="text-xs text-[#6b7280]">{child.dateOfBirth || 'DOB not set'}</div>
                    </div>
                  ))}
                </div>
              ) : null}
            </Card>

            <Card padding="lg">
              <div className="text-sm font-semibold text-[#0b2b43]">Assignment / Context</div>
              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div className="border border-[#e2e8f0] rounded-lg p-3">
                  <div className="text-xs uppercase tracking-wide text-[#6b7280]">Employer</div>
                  <div className="text-[#0b2b43] font-medium mt-1">{profile?.primaryApplicant?.employer?.name || '—'}</div>
                </div>
                <div className="border border-[#e2e8f0] rounded-lg p-3">
                  <div className="text-xs uppercase tracking-wide text-[#6b7280]">Contract start</div>
                  <div className="text-[#0b2b43] font-medium mt-1">{profile?.primaryApplicant?.assignment?.startDate || '—'}</div>
                </div>
              </div>
              <div className="mt-4">
                <Button variant="outline" onClick={() => safeNavigate(navigate, 'messages')}>
                  Contact HR / Support
                </Button>
              </div>
            </Card>
          </div>
        </div>
      )}
    </AppShell>
  );
};

