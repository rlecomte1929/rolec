import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Card, Badge, Button, ProgressBar, Alert } from '../components/antigravity';
import { RecommendationPanel } from '../components/RecommendationPanel';
import { dashboardAPI } from '../api/client';
import type { DashboardResponse } from '../types';
import { AppShell } from '../components/AppShell';
import { statusLabel } from '../lib/statusLabel';

export const Dashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'overview' | 'timeline' | 'housing' | 'schools' | 'movers' | 'documents'>('overview');
  const navigate = useNavigate();

  const dashboardQuery = useQuery({
    queryKey: ['employee', 'dashboard'],
    queryFn: () => dashboardAPI.get(),
  });
  const dashboard: DashboardResponse | null = dashboardQuery.data ?? null;
  const isLoading = dashboardQuery.isLoading;

  // Preserve the original 401 -> home redirect (the axios interceptor also fires).
  useEffect(() => {
    const status = (dashboardQuery.error as { response?: { status?: number } } | null)?.response?.status;
    if (dashboardQuery.isError && status === 401) navigate('/');
  }, [dashboardQuery.isError, dashboardQuery.error, navigate]);

  const getReadinessColor = (status: string) => {
    switch (status) {
      case 'GREEN': return 'success';
      case 'AMBER': return 'warning';
      case 'RED': return 'error';
      default: return 'neutral';
    }
  };

  const getTaskStatusIcon = (status: string) => {
    switch (status) {
      case 'done': return '✓';
      case 'in_progress': return '⋯';
      default: return '○';
    }
  };

  if (isLoading) {
    return (
      <AppShell title="Relocation Dashboard">
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-accent-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading your dashboard...</p>
        </div>
      </AppShell>
    );
  }

  if (!dashboard) {
    return (
      <AppShell title="Relocation Dashboard">
        <Card padding="lg">
          {/* Stage 6 (audit): empty-state copy per docs/product-copy-rules.md
              ("No X yet. [Reason or guidance] → [CTA]"). */}
          <Alert variant="info">
            <p className="font-medium text-[#0b2b43] mb-1">No relocation plan yet</p>
            <p className="mb-4">
              Tell us your origin, destination, and target move date — we&apos;ll build a tailored
              plan with documents, milestones, and provider recommendations.
            </p>
            <Button onClick={() => navigate('/journey')}>Start your profile</Button>
          </Alert>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell title="Relocation Dashboard" subtitle="Oslo, Norway → Singapore">
      <div className="flex justify-end mb-4">
        <Button onClick={() => navigate('/journey')} variant="outline">
          Continue Profile
        </Button>
      </div>
      <Alert variant="warning" title="Informational Guidance Only">
        This dashboard provides informational guidance only, not legal advice.
        Consult an immigration professional for eligibility assessment.
      </Alert>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8 mt-6">
          {/* Profile Completeness */}
          <Card padding="md">
            <div className="space-y-3">
              <div className="flex justify-between items-start">
                <h3 className="font-semibold text-gray-900">Profile Completeness</h3>
                <Badge variant="info">{dashboard.profileCompleteness}%</Badge>
              </div>
              <ProgressBar value={dashboard.profileCompleteness} showLabel={false} />
              <p className="text-sm text-[#4b5563]">
                {dashboard.profileCompleteness >= 80
                  ? 'Profile is complete enough for tailored recommendations.'
                  : 'Add more profile details to unlock housing and school recommendations.'}
              </p>
            </div>
          </Card>

          {/* Immigration Readiness */}
          <Card padding="md">
            <div className="space-y-3">
              <div className="flex justify-between items-start">
                <h3 className="font-semibold text-gray-900">Immigration Readiness</h3>
                <Badge variant={getReadinessColor(dashboard.immigrationReadiness.status)}>
                  {statusLabel(dashboard.immigrationReadiness.status)}
                </Badge>
              </div>
              <div className="text-3xl font-bold text-gray-900">
                {dashboard.immigrationReadiness.score}/100
              </div>
              <p className="text-sm text-gray-600">
                {dashboard.immigrationReadiness.reasons[0] || 'Building readiness...'}
              </p>
            </div>
          </Card>

          {/* Overall Status */}
          <Card padding="md">
            <div className="space-y-3">
              <div className="flex justify-between items-start">
                <h3 className="font-semibold text-gray-900">Overall Status</h3>
                <Badge variant={dashboard.overallStatus === 'On track' ? 'success' : 'warning'}>
                  {dashboard.overallStatus}
                </Badge>
              </div>
              <div className="text-lg font-semibold text-gray-900">
                {dashboard.nextActions.length} actions needed
              </div>
              <p className="text-sm text-gray-600">
                {dashboard.overallStatus === 'On track' 
                  ? 'You\'re making good progress'
                  : 'Some items need attention'}
              </p>
            </div>
          </Card>
        </div>

      {/* Next Actions */}
      {dashboard.nextActions.length > 0 && (
        <Card padding="md" className="mb-8">
            <h3 className="font-semibold text-[#0b2b43] mb-3">Next Actions</h3>
            <ul className="space-y-2">
              {dashboard.nextActions.map((action, idx) => (
                <li key={idx} className="flex items-start gap-3">
                  <span className="text-[#0b2b43] font-semibold">{idx + 1}.</span>
                  <span className="text-[#4b5563]">{action}</span>
                </li>
              ))}
            </ul>
        </Card>
      )}

      <div className="mb-6">
        <div className="border-b border-[#e2e8f0]">
          <div role="tablist" aria-label="Dashboard sections" className="flex -mb-px space-x-8">
            {[
              { id: 'overview', label: 'Overview' },
              { id: 'timeline', label: 'Timeline' },
              { id: 'housing', label: 'Housing', count: dashboard.recommendations.housing?.length },
              { id: 'schools', label: 'Schools', count: dashboard.recommendations.schools?.length },
              { id: 'movers', label: 'Movers', count: dashboard.recommendations.movers?.length },
              { id: 'documents', label: 'Documents' },
            ].map((tab) => (
              <Button unstyled
                key={tab.id}
                id={`dashboard-tab-${tab.id}`}
                role="tab"
                aria-selected={activeTab === tab.id}
                aria-controls={`dashboard-panel-${tab.id}`}
                onClick={() => setActiveTab(tab.id as any)}
                className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === tab.id
                    ? 'border-[#0b2b43] text-[#0b2b43]'
                    : 'border-transparent text-[#6b7280] hover:text-[#374151] hover:border-[#d1d5db]'
                }`}
              >
                {tab.label}
                {tab.count !== undefined && tab.count > 0 && (
                  <span className="ml-2 bg-[#f3f4f6] text-[#4b5563] py-0.5 px-2 rounded-full text-xs">
                    {tab.count}
                  </span>
                )}
              </Button>
            ))}
          </div>
        </div>
      </div>

      <div
        role="tabpanel"
        id={`dashboard-panel-${activeTab}`}
        aria-labelledby={`dashboard-tab-${activeTab}`}
      >
        {activeTab === 'overview' && (
          <div className="space-y-8">
              {/* Immigration Readiness Details */}
              <Card padding="lg">
                <h2 className="text-2xl font-bold text-[#0b2b43] mb-4">
                  Immigration Readiness Details
                </h2>
                
                <div className="space-y-4">
                  <div>
                    <h3 className="font-semibold text-[#0b2b43] mb-2">Current Status</h3>
                    <ul className="space-y-1">
                      {dashboard.immigrationReadiness.reasons.map((reason, idx) => (
                        <li key={idx} className="text-sm text-[#4b5563]">{reason}</li>
                      ))}
                    </ul>
                  </div>

                  {dashboard.immigrationReadiness.missingDocs.length > 0 && (
                    <div>
                      <h3 className="font-semibold text-[#0b2b43] mb-2">Missing Documents</h3>
                      <ul className="space-y-1">
                        {dashboard.immigrationReadiness.missingDocs.map((doc, idx) => (
                          <li key={idx} className="text-sm text-[#7a2a2a]">• {doc}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </Card>

              {/* Quick Recommendations Preview */}
              <RecommendationPanel
                housing={dashboard.recommendations.housing?.slice(0, 4)}
                schools={dashboard.recommendations.schools?.slice(0, 4)}
                movers={dashboard.recommendations.movers?.slice(0, 3)}
              />
          </div>
        )}

        {activeTab === 'timeline' && (
          <div className="space-y-6">
            {dashboard.timeline.map((phase) => (
              <Card key={phase.phase} padding="lg">
                <h3 className="text-xl font-bold text-[#0b2b43] mb-4">{phase.phase}</h3>
                <ul className="space-y-3">
                  {phase.tasks.map((task, idx) => (
                    <li key={idx} className="flex items-start gap-3">
                      <span className={`text-lg ${
                        task.status === 'done' ? 'text-[#1f8e8b]' :
                        task.status === 'in_progress' ? 'text-[#7a5e2a]' :
                        'text-[#9ca3af]'
                      }`}>
                        {getTaskStatusIcon(task.status)}
                      </span>
                      <div className="flex-1">
                        <div className={`text-[#0b2b43] ${task.status === 'done' ? 'line-through' : ''}`}>
                          {task.title}
                        </div>
                        {task.dueDate && (
                          <div className="text-xs text-[#6b7280]">Due: {task.dueDate}</div>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            ))}
          </div>
        )}

        {activeTab === 'housing' && (
          <RecommendationPanel housing={dashboard.recommendations.housing} />
        )}

        {activeTab === 'schools' && (
          <RecommendationPanel schools={dashboard.recommendations.schools} />
        )}

        {activeTab === 'movers' && (
          <RecommendationPanel movers={dashboard.recommendations.movers} />
        )}

        {activeTab === 'documents' && (
          <Card padding="lg">
            <h2 className="text-2xl font-bold text-[#0b2b43] mb-4">Document Checklist</h2>
            <div className="space-y-4">
              <Alert variant="info">Core documents for this relocation.</Alert>

              <div className="space-y-3">
                {[
                  { label: 'Passport scans (all family members)', checked: dashboard.immigrationReadiness.missingDocs.indexOf('Passport scans') === -1 },
                  { label: 'Marriage certificate', checked: dashboard.immigrationReadiness.missingDocs.indexOf('Marriage certificate') === -1 },
                  { label: 'Birth certificates (children)', checked: dashboard.immigrationReadiness.missingDocs.indexOf('Birth certificates') === -1 },
                  { label: 'Employment letter', checked: dashboard.immigrationReadiness.missingDocs.indexOf('Employment letter') === -1 },
                  { label: 'Educational certificates', checked: false },
                  { label: 'Bank statements (optional)', checked: false },
                ].map((item, idx) => (
                  <div key={idx} className="flex items-center gap-3 p-3 border border-[#e2e8f0] rounded-lg">
                    <div className={`w-6 h-6 rounded border-2 flex items-center justify-center ${
                      item.checked ? 'bg-[#eaf5f4] border-[#1f8e8b]' : 'border-[#d1d5db]'
                    }`}>
                      {item.checked && <span className="text-[#1f8e8b] text-sm">✓</span>}
                    </div>
                    <span className={item.checked ? 'text-[#6b7280]' : 'text-[#0b2b43]'}>
                      {item.label}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
};
