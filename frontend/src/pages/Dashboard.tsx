import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Container, Card, Badge, Button, ProgressBar, Alert } from '../components/antigravity';
import { RecommendationPanel } from '../components/RecommendationPanel';
import { dashboardAPI } from '../api/client';
import type { DashboardResponse, TimelinePhase } from '../types';

export const Dashboard: React.FC = () => {
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'timeline' | 'housing' | 'schools' | 'movers' | 'documents'>('overview');
  const navigate = useNavigate();

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const data = await dashboardAPI.get();
      setDashboard(data);
    } catch (err: any) {
      if (err.response?.status === 401) {
        navigate('/');
      }
    } finally {
      setIsLoading(false);
    }
  };

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
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading your dashboard...</p>
        </div>
      </div>
    );
  }

  if (!dashboard) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Card padding="lg">
          <Alert variant="info">
            <p className="mb-4">No profile data yet. Start your journey first.</p>
            <Button onClick={() => navigate('/journey')}>Start Journey</Button>
          </Alert>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 shadow-sm">
        <Container maxWidth="xl" className="py-6">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">
                Your Relocation Dashboard
              </h1>
              <p className="text-gray-600">
                Oslo, Norway → Singapore
              </p>
            </div>
            <Button onClick={() => navigate('/journey')} variant="outline">
              Continue Profile
            </Button>
          </div>

          {/* Disclaimer */}
          <Alert variant="warning" title="Informational Guidance Only">
            This dashboard provides informational guidance only, not legal advice. 
            Consult an immigration professional for eligibility assessment.
          </Alert>
        </Container>
      </div>

      {/* Stats Cards */}
      <Container maxWidth="xl" className="py-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {/* Profile Completeness */}
          <Card padding="md">
            <div className="space-y-3">
              <div className="flex justify-between items-start">
                <h3 className="font-semibold text-gray-900">Profile Completeness</h3>
                <Badge variant="info">{dashboard.profileCompleteness}%</Badge>
              </div>
              <ProgressBar value={dashboard.profileCompleteness} showLabel={false} />
              <p className="text-sm text-gray-600">
                {dashboard.profileCompleteness >= 80 
                  ? 'Profile is well-detailed'
                  : 'Continue adding details for better recommendations'}
              </p>
            </div>
          </Card>

          {/* Immigration Readiness */}
          <Card padding="md">
            <div className="space-y-3">
              <div className="flex justify-between items-start">
                <h3 className="font-semibold text-gray-900">Immigration Readiness</h3>
                <Badge variant={getReadinessColor(dashboard.immigrationReadiness.status)}>
                  {dashboard.immigrationReadiness.status}
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
            <h3 className="font-semibold text-gray-900 mb-3">Next Actions</h3>
            <ul className="space-y-2">
              {dashboard.nextActions.map((action, idx) => (
                <li key={idx} className="flex items-start gap-3">
                  <span className="text-indigo-600 font-semibold">{idx + 1}.</span>
                  <span className="text-gray-700">{action}</span>
                </li>
              ))}
            </ul>
          </Card>
        )}

        {/* Tabs */}
        <div className="mb-6">
          <div className="border-b border-gray-200">
            <nav className="flex -mb-px space-x-8">
              {[
                { id: 'overview', label: 'Overview' },
                { id: 'timeline', label: 'Timeline' },
                { id: 'housing', label: 'Housing', count: dashboard.recommendations.housing?.length },
                { id: 'schools', label: 'Schools', count: dashboard.recommendations.schools?.length },
                { id: 'movers', label: 'Movers', count: dashboard.recommendations.movers?.length },
                { id: 'documents', label: 'Documents' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                    activeTab === tab.id
                      ? 'border-indigo-600 text-indigo-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  {tab.label}
                  {tab.count !== undefined && tab.count > 0 && (
                    <span className="ml-2 bg-gray-200 text-gray-700 py-0.5 px-2 rounded-full text-xs">
                      {tab.count}
                    </span>
                  )}
                </button>
              ))}
            </nav>
          </div>
        </div>

        {/* Tab Content */}
        <div>
          {activeTab === 'overview' && (
            <div className="space-y-8">
              {/* Immigration Readiness Details */}
              <Card padding="lg">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">
                  Immigration Readiness Details
                </h2>
                
                <div className="space-y-4">
                  <div>
                    <h3 className="font-semibold text-gray-900 mb-2">Current Status</h3>
                    <ul className="space-y-1">
                      {dashboard.immigrationReadiness.reasons.map((reason, idx) => (
                        <li key={idx} className="text-sm text-gray-700">{reason}</li>
                      ))}
                    </ul>
                  </div>

                  {dashboard.immigrationReadiness.missingDocs.length > 0 && (
                    <div>
                      <h3 className="font-semibold text-gray-900 mb-2">Missing Documents</h3>
                      <ul className="space-y-1">
                        {dashboard.immigrationReadiness.missingDocs.map((doc, idx) => (
                          <li key={idx} className="text-sm text-red-700">• {doc}</li>
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
                  <h3 className="text-xl font-bold text-gray-900 mb-4">{phase.phase}</h3>
                  <ul className="space-y-3">
                    {phase.tasks.map((task, idx) => (
                      <li key={idx} className="flex items-start gap-3">
                        <span className={`text-lg ${
                          task.status === 'done' ? 'text-green-600' :
                          task.status === 'in_progress' ? 'text-yellow-600' :
                          'text-gray-400'
                        }`}>
                          {getTaskStatusIcon(task.status)}
                        </span>
                        <div className="flex-1">
                          <div className={`text-gray-900 ${task.status === 'done' ? 'line-through' : ''}`}>
                            {task.title}
                          </div>
                          {task.dueDate && (
                            <div className="text-xs text-gray-500">Due: {task.dueDate}</div>
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
              <h2 className="text-2xl font-bold text-gray-900 mb-4">Document Checklist</h2>
              <div className="space-y-4">
                <Alert variant="info">
                  These are the core documents you'll need for your relocation.
                </Alert>
                
                <div className="space-y-3">
                  {[
                    { label: 'Passport scans (all family members)', checked: dashboard.immigrationReadiness.missingDocs.indexOf('Passport scans') === -1 },
                    { label: 'Marriage certificate', checked: dashboard.immigrationReadiness.missingDocs.indexOf('Marriage certificate') === -1 },
                    { label: 'Birth certificates (children)', checked: dashboard.immigrationReadiness.missingDocs.indexOf('Birth certificates') === -1 },
                    { label: 'Employment letter', checked: dashboard.immigrationReadiness.missingDocs.indexOf('Employment letter') === -1 },
                    { label: 'Educational certificates', checked: false },
                    { label: 'Bank statements (optional)', checked: false },
                  ].map((item, idx) => (
                    <div key={idx} className="flex items-center gap-3 p-3 border rounded-lg">
                      <div className={`w-6 h-6 rounded border-2 flex items-center justify-center ${
                        item.checked ? 'bg-green-100 border-green-600' : 'border-gray-300'
                      }`}>
                        {item.checked && <span className="text-green-600 text-sm">✓</span>}
                      </div>
                      <span className={item.checked ? 'text-gray-600' : 'text-gray-900'}>
                        {item.label}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          )}
        </div>
      </Container>
    </div>
  );
};
