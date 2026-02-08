import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { GuidedQuestionCard } from '../components/GuidedQuestionCard';
import { Alert, Button, Card, Input } from '../components/antigravity';
import { employeeAPI } from '../api/client';
import { getAuthItem } from '../utils/demo';
import type { EmployeeJourneyResponse, AssignmentStatus } from '../types';
import { useRegisterNav } from '../navigation/registry';
import { safeNavigate } from '../navigation/safeNavigate';

export const EmployeeJourney: React.FC = () => {
  const [assignmentId, setAssignmentId] = useState<string | null>(null);
  const [journey, setJourney] = useState<EmployeeJourneyResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [claimId, setClaimId] = useState('');
  const [claimEmail, setClaimEmail] = useState(getAuthItem('relopass_email') || '');
  const [isPhotoSaving, setIsPhotoSaving] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    loadAssignment();
  }, []);

  useRegisterNav('EmployeeJourney', [
    { label: 'Submit relocation details to HR', routeKey: 'hrAssignmentReview' },
  ]);


  const loadAssignment = async () => {
    setIsLoading(true);
    try {
      const response = await employeeAPI.getCurrentAssignment();
      if (!response.assignment) {
        setAssignmentId(null);
        setJourney(null);
        setClaimId('');
        setClaimEmail(getAuthItem('relopass_email') || '');
      } else {
        setAssignmentId(response.assignment.id);
        await loadJourney(response.assignment.id);
      }
    } catch (err: any) {
      if (err.response?.status === 401) {
        safeNavigate(navigate, 'landing');
      } else {
        setError('Unable to load assignment.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const loadJourney = async (currentAssignmentId: string) => {
    try {
      const data = await employeeAPI.getNextQuestion(currentAssignmentId);
      setJourney(data);
    } catch (err: any) {
      if (err.response?.status === 401) {
        safeNavigate(navigate, 'landing');
      } else {
        setError(err.response?.data?.detail || 'Failed to load journey.');
      }
    }
  };

  const handleAnswer = async (answer: any, isUnknown: boolean) => {
    if (!journey?.question || !assignmentId) return;
    setError('');
    try {
      const payload = isUnknown ? 'unknown' : answer;
      const next = await employeeAPI.submitAnswer(assignmentId, journey.question.id, payload);
      setJourney(next);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save answer.');
    }
  };

  const handleSubmitToHR = async () => {
    if (!assignmentId) return;
    setError('');
    try {
      await employeeAPI.submitAssignment(assignmentId);
      const next = await employeeAPI.getNextQuestion(assignmentId);
      setJourney(next);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to submit to HR.');
    }
  };

  const handlePhotoChange = async (file?: File | null) => {
    if (!file || !assignmentId) return;
    if (!file.type.startsWith('image/')) {
      setError('Please select an image file.');
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setError('Image must be smaller than 2MB.');
      return;
    }
    setError('');
    setIsPhotoSaving(true);
    try {
      const reader = new FileReader();
      const dataUrl = await new Promise<string>((resolve, reject) => {
        reader.onerror = () => reject(new Error('Unable to read image'));
        reader.onload = () => resolve(String(reader.result));
        reader.readAsDataURL(file);
      });
      await employeeAPI.updateProfilePhoto(assignmentId, dataUrl);
      const next = await employeeAPI.getNextQuestion(assignmentId);
      setJourney(next);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to save profile photo.');
    } finally {
      setIsPhotoSaving(false);
    }
  };

  const handleClaimAssignment = async () => {
    if (!claimId.trim() || !claimEmail.trim()) {
      setError('Enter your email and assignment ID provided by HR.');
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

  const status = journey?.assignmentStatus as AssignmentStatus | undefined;
  const isSubmitted = status === 'EMPLOYEE_SUBMITTED' || status === 'HR_REVIEW' || status === 'HR_APPROVED';
  const canSubmit = (journey?.completeness || 0) >= 90 && (status === 'IN_PROGRESS' || status === 'CHANGES_REQUESTED');
  const answeredCount = journey?.progress?.answeredCount || 0;
  const totalQuestions = journey?.progress?.totalQuestions || 0;
  const immediateActions = [
    journey?.question?.title,
    journey?.missingItems?.[0],
    journey?.missingItems?.[1],
  ].filter(Boolean) as string[];
  const requiredDocs = [
    { label: 'Passport Scan', done: Boolean(journey?.profile?.complianceDocs?.hasPassportScans) },
    { label: 'Work Contract', done: Boolean(journey?.profile?.complianceDocs?.hasEmploymentLetter) },
    { label: 'Birth Certificate', done: Boolean(journey?.profile?.complianceDocs?.hasBirthCertificates) },
  ];
  const hasBasics = Boolean(journey?.profile?.movePlan?.origin && journey?.profile?.movePlan?.destination);
  const hasEmployeeProfile = Boolean(journey?.profile?.primaryApplicant?.fullName && journey?.profile?.primaryApplicant?.nationality);
  const hasFamilyMembers = Boolean(
    journey?.profile?.spouse?.fullName ||
      (journey?.profile?.dependents?.filter((d) => d.firstName).length || 0) > 0
  );
  const hasAssignmentContext = Boolean(
    journey?.profile?.primaryApplicant?.employer?.name || journey?.profile?.primaryApplicant?.assignment?.startDate
  );
  const firstName = (journey?.profile?.primaryApplicant?.fullName || 'Employee').split(' ')[0];
  const stepStatuses = [
    { label: 'Relocation Basics', done: hasBasics },
    { label: 'Employee Profile', done: hasEmployeeProfile },
    { label: 'Family Members', done: hasFamilyMembers },
    { label: 'Assignment / Context', done: hasAssignmentContext },
    { label: 'Review & Create Case', done: journey?.completeness ? journey.completeness >= 90 : false },
  ];

  return (
    <AppShell title="Employee Journey" subtitle="Complete your relocation profile for HR review.">
      {isLoading && <div className="text-sm text-[#6b7280]">Loading assignment...</div>}

      {!isLoading && !assignmentId && (
        <Card padding="lg">
          <Alert variant="info">
            <div className="space-y-2">
              <div className="font-semibold text-[#0b2b43]">Start your relocation case</div>
              <div className="text-sm text-[#4b5563]">
                Enter the assignment ID from HR to begin your journey.
              </div>
              <div className="text-xs text-[#6b7280]">
                You can find the assignment ID in the email invite or HR message.
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
                  <Button onClick={handleClaimAssignment}>Start case</Button>
                  <Button variant="outline" onClick={loadAssignment}>Refresh</Button>
                </div>
              </div>
            </div>
          </Alert>
        </Card>
      )}

      {assignmentId && journey && (
        <div className="space-y-6">
          {journey.profile && (
            <Card padding="lg">
              <div className="flex flex-wrap items-start justify-between gap-6">
                <div className="flex items-start gap-4">
                  <div className="h-16 w-16 rounded-full bg-[#e2e8f0] overflow-hidden flex items-center justify-center text-[#0b2b43] font-semibold">
                    {journey.profile.primaryApplicant?.photoUrl ? (
                      <img
                        src={journey.profile.primaryApplicant.photoUrl}
                        alt="Profile"
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      (journey.profile.primaryApplicant?.fullName || '—')
                        .split(' ')
                        .map((part) => part[0])
                        .slice(0, 2)
                        .join('')
                        .toUpperCase() || '—'
                    )}
                  </div>
                  <div>
                    <div className="text-2xl font-semibold text-[#0b2b43]">
                      Welcome, {firstName}
                    </div>
                    <div className="text-sm text-[#6b7280] mt-2">
                      {journey.profile.movePlan?.origin || '—'} → {journey.profile.movePlan?.destination || '—'}
                    </div>
                    <div className="text-xs text-[#6b7280] mt-1">
                      Target move: {journey.profile.movePlan?.targetArrivalDate || '—'}
                    </div>
                    <div className="mt-3 text-xs text-[#6b7280]">
                      Your Visa Path:{" "}
                      <span className="inline-flex items-center rounded-full bg-[#eef4ff] text-[#1d4ed8] px-3 py-1 text-xs font-semibold">
                        L-1B Specialized Knowledge
                      </span>
                    </div>
                  </div>
                </div>
                <div className="w-full max-w-xs space-y-3">
                  <div className="rounded-lg border border-[#e2e8f0] bg-white p-3">
                    <div className="text-xs text-[#6b7280] mb-2">Profile photo</div>
                    <label className="inline-flex items-center gap-2 text-xs text-[#0b2b43] cursor-pointer">
                      <input
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={(event) => handlePhotoChange(event.target.files?.[0])}
                        disabled={isPhotoSaving}
                      />
                      <span className="px-3 py-1 rounded-full border border-[#e2e8f0]">
                        {isPhotoSaving ? 'Uploading...' : 'Upload photo'}
                      </span>
                    </label>
                  </div>
                  <div className="rounded-lg border border-[#e2e8f0] bg-white p-3">
                    <div className="flex items-center justify-between text-xs text-[#6b7280]">
                      <div className="flex items-center gap-2">
                        <span>Current Stage:</span>
                        <span className="font-semibold text-[#0b2b43]">Intake</span>
                      </div>
                      <span className="px-2 py-0.5 rounded-full bg-[#eaf5f4] text-[#1f8e8b] text-[10px] uppercase tracking-wide">
                        On track
                      </span>
                    </div>
                    <div className="mt-3 flex items-center justify-between text-xs text-[#6b7280]">
                      <span>Overall Progress</span>
                      <span className="font-semibold text-[#0b2b43]">{Math.round(journey.completeness)}%</span>
                    </div>
                    <div className="mt-2 h-1.5 w-full rounded-full bg-[#e2e8f0]">
                      <div
                        className="h-1.5 rounded-full bg-[#0b2b43]"
                        style={{ width: `${Math.min(Math.max(journey.completeness, 0), 100)}%` }}
                      />
                    </div>
                    <div className="mt-3 text-xs text-[#6b7280] flex items-center gap-2">
                      <span className="text-[#0b2b43]">Next milestone:</span>
                      <span className="font-semibold text-[#0b2b43]">
                        {journey.missingItems?.[0] || 'Profile completion'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          )}

          {journey.profile && (
            <Card padding="lg">
              <div className="text-sm font-semibold text-[#0b2b43] mb-3">Family members</div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="border border-[#e2e8f0] rounded-lg p-3">
                  <div className="text-xs uppercase tracking-wide text-[#6b7280]">Primary applicant</div>
                  <div className="text-sm font-medium text-[#0b2b43] mt-1">
                    {journey.profile.primaryApplicant?.fullName || 'Not set'}
                  </div>
                  <div className="text-xs text-[#6b7280]">
                    {journey.profile.primaryApplicant?.nationality || 'Nationality not set'}
                  </div>
                </div>
                {journey.profile.spouse?.fullName && (
                  <div className="border border-[#e2e8f0] rounded-lg p-3">
                    <div className="text-xs uppercase tracking-wide text-[#6b7280]">Spouse</div>
                    <div className="text-sm font-medium text-[#0b2b43] mt-1">
                      {journey.profile.spouse.fullName}
                    </div>
                    <div className="text-xs text-[#6b7280]">
                      {journey.profile.spouse.nationality || 'Nationality not set'}
                    </div>
                  </div>
                )}
                {journey.profile.dependents
                  ?.filter((child) => child.firstName)
                  .map((child, idx) => (
                    <div key={`${child.firstName}-${idx}`} className="border border-[#e2e8f0] rounded-lg p-3">
                      <div className="text-xs uppercase tracking-wide text-[#6b7280]">Child</div>
                      <div className="text-sm font-medium text-[#0b2b43] mt-1">
                        {child.firstName}
                      </div>
                      <div className="text-xs text-[#6b7280]">
                        {child.dateOfBirth || 'DOB not set'}
                      </div>
                    </div>
                  ))}
              </div>
            </Card>
          )}

          {journey.profile && (
            <div className="grid grid-cols-1 xl:grid-cols-[0.9fr,2.1fr] gap-6">
              <Card padding="lg">
                <div className="text-xs uppercase tracking-wide text-[#6b7280] mb-3">Case wizard</div>
                <div className="space-y-3 text-sm">
                  {stepStatuses.map((step, idx) => (
                    <div key={step.label} className="flex items-start gap-3">
                      <div
                        className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-semibold ${
                          step.done ? 'bg-[#eaf5f4] text-[#1f8e8b]' : 'bg-[#f3f4f6] text-[#6b7280]'
                        }`}
                      >
                        {idx + 1}
                      </div>
                      <div>
                        <div className="font-medium text-[#0b2b43]">{step.label}</div>
                        <div className="text-xs text-[#6b7280]">{step.done ? 'Completed' : 'In progress'}</div>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-4">
                  <Button onClick={() => navigate(`/employee/case/${assignmentId}/wizard/1`)}>
                    Open case wizard
                  </Button>
                </div>
              </Card>

              <div className="space-y-5">
                <Card padding="lg">
                  <div className="text-lg font-semibold text-[#0b2b43]">Relocation Basics</div>
                  <div className="text-sm text-[#6b7280] mt-1">
                    Why this step is needed: We need core move details to tailor your relocation plan.
                  </div>
                  <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div className="border border-[#e2e8f0] rounded-lg p-3">
                      <div className="text-xs uppercase tracking-wide text-[#6b7280]">Origin</div>
                      <div className="text-[#0b2b43] font-medium mt-1">
                        {journey.profile.movePlan?.origin || 'Select country'}
                      </div>
                    </div>
                    <div className="border border-[#e2e8f0] rounded-lg p-3">
                      <div className="text-xs uppercase tracking-wide text-[#6b7280]">Destination</div>
                      <div className="text-[#0b2b43] font-medium mt-1">
                        {journey.profile.movePlan?.destination || 'Select country'}
                      </div>
                    </div>
                    <div className="border border-[#e2e8f0] rounded-lg p-3">
                      <div className="text-xs uppercase tracking-wide text-[#6b7280]">Target move date</div>
                      <div className="text-[#0b2b43] font-medium mt-1">
                        {journey.profile.movePlan?.targetArrivalDate || 'mm/dd/yyyy'}
                      </div>
                    </div>
                    <div className="border border-[#e2e8f0] rounded-lg p-3">
                      <div className="text-xs uppercase tracking-wide text-[#6b7280]">Purpose</div>
                      <div className="text-[#0b2b43] font-medium mt-1">Employment</div>
                    </div>
                  </div>
                </Card>

                <Card padding="lg">
                  <div className="text-lg font-semibold text-[#0b2b43]">Employee Profile</div>
                  <div className="text-sm text-[#6b7280] mt-1">
                    Why this step is needed: We collect identity details for immigration and policy checks.
                  </div>
                  <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div className="border border-[#e2e8f0] rounded-lg p-3">
                      <div className="text-xs uppercase tracking-wide text-[#6b7280]">Full name</div>
                      <div className="text-[#0b2b43] font-medium mt-1">
                        {journey.profile.primaryApplicant?.fullName || 'Not set'}
                      </div>
                    </div>
                    <div className="border border-[#e2e8f0] rounded-lg p-3">
                      <div className="text-xs uppercase tracking-wide text-[#6b7280]">Nationality</div>
                      <div className="text-[#0b2b43] font-medium mt-1">
                        {journey.profile.primaryApplicant?.nationality || 'Select nationality'}
                      </div>
                    </div>
                    <div className="border border-[#e2e8f0] rounded-lg p-3">
                      <div className="text-xs uppercase tracking-wide text-[#6b7280]">Role title</div>
                      <div className="text-[#0b2b43] font-medium mt-1">
                        {journey.profile.primaryApplicant?.employer?.roleTitle || 'Not set'}
                      </div>
                    </div>
                    <div className="border border-[#e2e8f0] rounded-lg p-3">
                      <div className="text-xs uppercase tracking-wide text-[#6b7280]">Job level</div>
                      <div className="text-[#0b2b43] font-medium mt-1">
                        {journey.profile.primaryApplicant?.employer?.jobLevel || 'Not set'}
                      </div>
                    </div>
                  </div>
                </Card>

                <Card padding="lg">
                  <div className="text-lg font-semibold text-[#0b2b43]">Family Members</div>
                  <div className="text-sm text-[#6b7280] mt-1">
                    Why this step is needed: Family details support visas and school planning.
                  </div>
                  <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div className="border border-[#e2e8f0] rounded-lg p-3">
                      <div className="text-xs uppercase tracking-wide text-[#6b7280]">Spouse</div>
                      <div className="text-[#0b2b43] font-medium mt-1">
                        {journey.profile.spouse?.fullName || 'Not provided'}
                      </div>
                    </div>
                    <div className="border border-[#e2e8f0] rounded-lg p-3">
                      <div className="text-xs uppercase tracking-wide text-[#6b7280]">Dependents</div>
                      <div className="text-[#0b2b43] font-medium mt-1">
                        {journey.profile.dependents?.filter((d) => d.firstName).length || 0} listed
                      </div>
                    </div>
                  </div>
                </Card>

                <Card padding="lg">
                  <div className="text-lg font-semibold text-[#0b2b43]">Assignment / Context</div>
                  <div className="text-sm text-[#6b7280] mt-1">
                    Why this step is needed: Assignment details drive policy caps and recommendations.
                  </div>
                  <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div className="border border-[#e2e8f0] rounded-lg p-3">
                      <div className="text-xs uppercase tracking-wide text-[#6b7280]">Employer</div>
                      <div className="text-[#0b2b43] font-medium mt-1">
                        {journey.profile.primaryApplicant?.employer?.name || 'Not set'}
                      </div>
                    </div>
                    <div className="border border-[#e2e8f0] rounded-lg p-3">
                      <div className="text-xs uppercase tracking-wide text-[#6b7280]">Contract start</div>
                      <div className="text-[#0b2b43] font-medium mt-1">
                        {journey.profile.primaryApplicant?.assignment?.startDate || 'mm/dd/yyyy'}
                      </div>
                    </div>
                  </div>
                </Card>

                <Card padding="lg">
                  <div className="text-lg font-semibold text-[#0b2b43]">Review & Create Case</div>
                  <div className="text-sm text-[#6b7280] mt-1">
                    Please verify the collected information. HR will generate compliance checks and timelines.
                  </div>
                  <div className="mt-4 flex flex-wrap gap-3">
                    <Button variant="outline">Save as draft</Button>
                    <Button>Continue</Button>
                  </div>
                </Card>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 xl:grid-cols-[2.1fr,1fr,1fr] gap-6">
          <div className="space-y-6">
            {error && <Alert variant="error">{error}</Alert>}

            {status === 'CHANGES_REQUESTED' && journey.hrNotes && (
              <Alert variant="warning" title="HR feedback received">
                {journey.hrNotes}
              </Alert>
            )}

            {isSubmitted && (
              <Card padding="lg">
                <div className="space-y-2">
                  <div className="text-xl font-semibold text-[#0b2b43]">Submitted to HR for review</div>
                  <div className="text-sm text-[#4b5563]">
                    Your relocation details are locked for review. HR will update the status once checks are complete.
                  </div>
                </div>
              </Card>
            )}

            <Card padding="lg">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <div className="text-sm font-semibold text-[#0b2b43]">Your Next Steps</div>
                  <div className="text-xs text-[#6b7280]">
                    {answeredCount} of {totalQuestions || 0} completed
                  </div>
                </div>
              </div>
              <div className="space-y-3">
                {immediateActions.length === 0 && (
                  <div className="text-sm text-[#6b7280]">No immediate actions.</div>
                )}
                {immediateActions.map((action, idx) => (
                  <div key={`${action}-${idx}`} className="border border-[#fbd5d5] bg-[#fff5f5] rounded-lg p-4 flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-[#0b2b43]">{action}</div>
                      <div className="text-xs text-[#6b7280]">Owner: Employee</div>
                      <div className="text-xs text-[#7a2a2a] mt-2">Action required</div>
                    </div>
                    <Button
                      variant="outline"
                      onClick={() => {
                        document.getElementById('current-question')?.scrollIntoView({ behavior: 'smooth' });
                      }}
                    >
                      Start
                    </Button>
                  </div>
                ))}
              </div>
            </Card>

            {!isSubmitted && journey.question && (
              <div id="current-question">
                <GuidedQuestionCard question={journey.question} onAnswer={handleAnswer} />
              </div>
            )}

            {!isSubmitted && !journey.question && (
              <Card padding="lg">
                <div className="space-y-3">
                  <div className="text-lg font-semibold text-[#0b2b43]">Profile ready for review</div>
                  <div className="text-sm text-[#4b5563]">
                    All required information is captured. Submit to HR to begin compliance checks.
                  </div>
                  <Button size="lg" onClick={handleSubmitToHR}>
                    Submit relocation details to HR
                  </Button>
                </div>
              </Card>
            )}

            {!isSubmitted && journey.question && canSubmit && (
              <Card padding="md">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="text-sm font-medium text-[#0b2b43]">Ready for HR review</div>
                    <div className="text-xs text-[#6b7280]">Completeness: {journey.completeness}%</div>
                  </div>
                  <Button size="lg" onClick={handleSubmitToHR}>
                    Submit relocation details to HR
                  </Button>
                </div>
              </Card>
            )}
          </div>

          <div className="space-y-4">
            <Card padding="lg">
              <div className="flex items-center justify-between mb-3">
                <div className="text-sm font-semibold text-[#0b2b43]">Required Docs</div>
                <button className="text-xs text-[#2563eb]" onClick={() => safeNavigate(navigate, 'resources')}>
                  View all
                </button>
              </div>
              <div className="space-y-3">
                {requiredDocs.map((doc) => (
                  <div key={doc.label} className="flex items-center justify-between border border-[#e2e8f0] rounded-lg p-3">
                    <div>
                      <div className="text-sm font-medium text-[#0b2b43]">{doc.label}</div>
                      <div className="text-xs text-[#6b7280]">{doc.done ? 'Uploaded' : 'Not uploaded'}</div>
                    </div>
                    <Button variant="outline" onClick={() => safeNavigate(navigate, 'resources')}>
                      {doc.done ? 'View' : 'Upload'}
                    </Button>
                  </div>
                ))}
              </div>
            </Card>

            <Card padding="lg">
              <div className="text-sm font-semibold text-[#0b2b43] mb-2">Need a human?</div>
              <div className="text-xs text-[#6b7280]">
                Your dedicated case manager is just a message away.
              </div>
              <Button variant="outline" fullWidth onClick={() => safeNavigate(navigate, 'messages')}>
                Contact support
              </Button>
            </Card>

            <Card padding="md">
              <div className="text-sm text-[#6b7280] uppercase tracking-wide">Profile photo</div>
              <div className="mt-3 flex items-center gap-4">
                <div className="h-16 w-16 rounded-full bg-[#e2e8f0] overflow-hidden flex items-center justify-center text-[#0b2b43] font-semibold">
                  {journey.profile?.primaryApplicant?.photoUrl ? (
                    <img
                      src={journey.profile.primaryApplicant.photoUrl}
                      alt="Profile"
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    '—'
                  )}
                </div>
                <label className="text-sm text-[#0b2b43] cursor-pointer">
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(event) => handlePhotoChange(event.target.files?.[0])}
                    disabled={isPhotoSaving || isSubmitted}
                  />
                  <span className="inline-flex items-center gap-2 rounded-full border border-[#e2e8f0] px-4 py-2 text-xs uppercase tracking-wide">
                    {isPhotoSaving ? 'Uploading...' : 'Upload photo'}
                  </span>
                </label>
              </div>
              <div className="text-xs text-[#6b7280] mt-2">PNG or JPG up to 2MB.</div>
            </Card>
          </div>

          <div className="space-y-4">
            <Card padding="lg">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-semibold text-[#0b2b43]">ReloPass Assistant</div>
                  <div className="text-xs text-[#6b7280]">Context aware</div>
                </div>
                <span className="text-xs px-2 py-1 rounded-full bg-[#eef4f8] text-[#0b2b43]">AI Guidance</span>
              </div>
              <div className="mt-4 text-sm text-[#4b5563] border border-[#e2e8f0] rounded-lg p-3 bg-[#f8fafc]">
                Hi {journey.profile?.primaryApplicant?.fullName?.split(' ')[0] || 'there'}! I see you're moving to{" "}
                {journey.profile?.movePlan?.destination || 'your destination'}. What can I clarify for you today?
              </div>
              <div className="mt-4 space-y-2">
                {['What documents do I need?', 'How long does the L-1B take?', 'Housing options in destination'].map((suggestion) => (
                  <Button key={suggestion} variant="outline" fullWidth>
                    {suggestion}
                  </Button>
                ))}
              </div>
              <div className="mt-4 border border-[#e2e8f0] rounded-lg px-3 py-2 text-xs text-[#6b7280]">
                Ask anything about your move...
              </div>
            </Card>
          </div>
          </div>
        </div>
      )}
    </AppShell>
  );
};
