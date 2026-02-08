import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Alert, Button, Card } from '../components/antigravity';
import { hrAPI } from '../api/client';
import type { AssignmentDetail, ComplianceReport } from '../types';
import { useRegisterNav } from '../navigation/registry';
import { safeNavigate } from '../navigation/safeNavigate';

const formatCurrency = (value: number) =>
  value.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });

type CoverageItem = {
  title: string;
  used: number;
  cap: number;
  status: 'on_track' | 'near_limit' | 'over_limit';
};

export const HrAssignmentPackageReview: React.FC = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [assignment, setAssignment] = useState<AssignmentDetail | null>(null);
  const [compliance, setCompliance] = useState<ComplianceReport | null>(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  const loadAssignment = async () => {
    if (!id) return;
    setIsLoading(true);
    try {
      const data = await hrAPI.getAssignment(id);
      setAssignment(data);
      setCompliance(data.complianceReport || null);
      localStorage.setItem('relopass_last_assignment_id', data.id);
    } catch (err: any) {
      if (err.response?.status === 401) {
        safeNavigate(navigate, 'landing');
      } else {
        setError('Unable to load package review.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAssignment();
  }, [id]);

  const profile = assignment?.profile;
  const fullName = profile?.primaryApplicant?.fullName || assignment?.employeeIdentifier || 'Employee';
  const routeLabel = profile?.movePlan?.origin && profile?.movePlan?.destination
    ? `${profile.movePlan.origin} → ${profile.movePlan.destination}`
    : 'Relocation route';
  const familySize = 1 + (profile?.spouse?.fullName ? 1 : 0) + (profile?.dependents?.length || 0);

  const coverage: CoverageItem[] = useMemo(() => ([
    { title: 'Housing', used: 3200, cap: 5000, status: 'on_track' },
    { title: 'Movers & Logistics', used: 12400, cap: 10000, status: 'over_limit' },
    { title: 'Schools', used: 18500, cap: 20000, status: 'near_limit' },
  ]), []);

  const updatedLabel = new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  const exceptionPending = coverage.some((item) => item.status === 'over_limit');

  useRegisterNav('HrAssignmentPackageReview', [
    { label: 'Back to Providers', routeKey: 'providers' },
    { label: 'Continue to Submission Center', routeKey: 'submissionCenter' },
    { label: 'View rules', routeKey: 'hrPolicy' },
    { label: 'Request exception', routeKey: 'hrPolicy' },
  ]);

  return (
    <AppShell title="Assignment Package & Limits" subtitle="Review coverage, caps, and HR approvals required.">
      {error && <Alert variant="error">{error}</Alert>}
      {isLoading && <div className="text-sm text-[#6b7280]">Loading package review...</div>}

      {!isLoading && assignment && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-3">
              <span className="text-xs px-3 py-1 rounded-full border border-[#e2e8f0] text-[#4b5563]">
                {routeLabel}
              </span>
              <span className="text-xs px-3 py-1 rounded-full border border-[#e2e8f0] text-[#4b5563]">
                Family size: {familySize}
              </span>
              <span className="text-xs px-3 py-1 rounded-full border border-[#e2e8f0] text-[#4b5563]">
                Policy: v2.1
              </span>
              <span className="text-xs px-3 py-1 rounded-full border border-[#e2e8f0] text-[#4b5563]">
                HR owner: {fullName.split(' ')[0]}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={() => safeNavigate(navigate, 'providers')}>Back to Providers</Button>
              <Button variant="outline" onClick={() => safeNavigate(navigate, 'submissionCenter')}>
                Continue to Submission Center
              </Button>
            </div>
          </div>

          {exceptionPending && (
            <Card padding="md" className="bg-[#eef4ff] border border-[#c7d8ff]">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                  <div className="text-sm font-semibold text-[#0b2b43]">Policy exceptions pending</div>
                  <div className="text-xs text-[#4b5563]">
                    One or more categories exceed policy caps. HR approval required.
                  </div>
                </div>
                <Button variant="outline" onClick={() => safeNavigate(navigate, 'hrPolicy')}>View details</Button>
              </div>
            </Card>
          )}

          <div className="flex items-center justify-between">
            <div className="text-lg font-semibold text-[#0b2b43]">Your Coverage Envelope</div>
            <div className="text-xs text-[#6b7280]">Updated: Today, {updatedLabel}</div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {coverage.map((item) => {
              const remaining = Math.max(item.cap - item.used, 0);
              const statusLabel =
                item.status === 'on_track' ? 'On track' : item.status === 'near_limit' ? 'Near limit' : 'Over limit';
              const statusClasses =
                item.status === 'on_track'
                  ? 'bg-[#eaf5f4] text-[#1f8e8b]'
                  : item.status === 'near_limit'
                  ? 'bg-[#fff7ed] text-[#9a3412]'
                  : 'bg-[#fef2f2] text-[#7a2a2a]';
              const barPercent = Math.min(100, Math.round((item.used / item.cap) * 100));

              return (
                <Card key={item.title} padding="md">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-semibold text-[#0b2b43]">{item.title}</div>
                    <span className={`text-xs px-2 py-1 rounded-full ${statusClasses}`}>{statusLabel}</span>
                  </div>
                  <div className="mt-4 text-xs text-[#6b7280] flex items-center justify-between">
                    <span>Used</span>
                    <span className="text-[#0b2b43] font-semibold">{formatCurrency(item.used)}</span>
                  </div>
                  <div className="mt-2 h-2 w-full bg-[#e2e8f0] rounded-full overflow-hidden">
                    <div
                      className={`h-full ${item.status === 'over_limit' ? 'bg-[#ef4444]' : item.status === 'near_limit' ? 'bg-[#f59e0b]' : 'bg-[#1f8e8b]'}`}
                      style={{ width: `${barPercent}%` }}
                    />
                  </div>
                  <div className="mt-2 text-xs text-[#6b7280] flex items-center justify-between">
                    <span>Cap: {formatCurrency(item.cap)}</span>
                    <span>Remaining: {formatCurrency(remaining)}</span>
                  </div>
                  <div className="mt-3 flex items-center justify-between text-xs">
                    <button className="text-[#0b2b43]" onClick={() => safeNavigate(navigate, 'hrPolicy')}>
                      View rules
                    </button>
                    {item.status === 'over_limit' && (
                      <button className="text-[#7a2a2a]" onClick={() => safeNavigate(navigate, 'hrPolicy')}>
                        Request exception
                      </button>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>

          <Card padding="lg">
            <div className="flex items-center justify-between mb-4">
              <div className="text-sm font-semibold text-[#0b2b43]">Detailed Policy Rules</div>
              <div className="text-xs text-[#6b7280]">Action required</div>
            </div>
            <div className="space-y-3">
              <div className="border border-[#e2e8f0] rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-semibold text-[#0b2b43]">Movers & Logistics Rules</div>
                    <div className="text-xs text-[#6b7280]">
                      Door-to-door services, packing, and storage approvals.
                    </div>
                  </div>
                  <span className="text-xs px-2 py-1 rounded-full bg-[#fef2f2] text-[#7a2a2a]">
                    Budget exceeded
                  </span>
                </div>
                <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="text-xs text-[#4b5563] space-y-2">
                    <div>• Door-to-door move (up to 40ft container).</div>
                    <div>• Packing and unpacking services included.</div>
                    <div>• Storage beyond 30 days requires approval.</div>
                  </div>
                  <div className="border border-[#fde2e2] bg-[#fff5f5] rounded-lg p-3 text-xs text-[#7a2a2a]">
                    Request exceeds the $10,000 cap by {formatCurrency(coverage[1].used - coverage[1].cap)}.
                    <div className="mt-2 flex gap-2">
                      <Button variant="outline" onClick={() => safeNavigate(navigate, 'hrPolicy')}>
                        Request exception
                      </Button>
                      <Button variant="outline" onClick={() => safeNavigate(navigate, 'providers')}>
                        Adjust providers
                      </Button>
                    </div>
                  </div>
                </div>
                <div className="mt-3 bg-[#eef4f8] border border-[#c7d8e6] rounded-lg p-3 text-xs text-[#0b2b43]">
                  HR note: Peak season surcharges may apply. Consider shifting dates where possible.
                </div>
              </div>

              {compliance && (
                <div className="border border-[#e2e8f0] rounded-lg p-4">
                  <div className="text-sm font-semibold text-[#0b2b43]">Compliance observations</div>
                  <ul className="text-xs text-[#4b5563] mt-2 space-y-2">
                    {compliance.actions.map((action, idx) => (
                      <li key={idx}>• {action}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </Card>
        </div>
      )}
    </AppShell>
  );
};
