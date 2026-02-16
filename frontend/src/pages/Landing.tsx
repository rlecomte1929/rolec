import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Button, Card } from '../components/antigravity';
import { buildRoute } from '../navigation/routes';
import { useRegisterNav } from '../navigation/registry';
import { API_BASE_URL } from '../api/client';

export const Landing: React.FC = () => {
  const navigate = useNavigate();
  const [connStatus, setConnStatus] = useState<{
    state: 'idle' | 'loading' | 'ok' | 'error';
    latency?: number;
    data?: any;
    error?: string;
  }>({ state: 'idle' });

  const testConnection = async () => {
    setConnStatus({ state: 'loading' });
    const t0 = performance.now();
    try {
      const url = `${API_BASE_URL}/health`;
      const res = await fetch(url);
      const latency = Math.round(performance.now() - t0);
      if (!res.ok) {
        setConnStatus({ state: 'error', latency, error: `HTTP ${res.status} ${res.statusText}` });
        return;
      }
      const data = await res.json();
      setConnStatus({ state: 'ok', latency, data });
    } catch (err: any) {
      const latency = Math.round(performance.now() - t0);
      const msg = err?.message?.includes('Failed to fetch')
        ? 'CORS error or backend unreachable — check browser console for details'
        : err?.message || 'Unknown error';
      setConnStatus({ state: 'error', latency, error: msg });
    }
  };

  useRegisterNav('Landing', [
    { label: 'Create account', routeKey: 'auth' },
    { label: 'Sign in', routeKey: 'auth' },
  ]);


  return (
    <AppShell>
      <div className="space-y-14">
        <section className="grid grid-cols-1 lg:grid-cols-[1.1fr,0.9fr] gap-10 items-center">
          <div className="space-y-6">
            <h1 className="text-4xl md:text-5xl font-semibold text-[#0b2b43] leading-tight">
              International relocations, under control.
            </h1>
            <p className="text-[#4b5563] text-lg">
              Coordinate employee moves with structured intake, compliance checks, and clear HR decisions.
              ReloPass keeps every case audit-ready without extra tools.
            </p>
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => navigate(`${buildRoute('auth')}?mode=register`)}>Create account</Button>
              <Button variant="outline" onClick={() => navigate(`${buildRoute('auth')}?mode=login`)}>
                Sign in
              </Button>
            </div>
            <div className="text-sm text-[#6b7280]">
              Designed for SME HR leaders managing sensitive relocation data.
            </div>
          </div>
          <Card padding="lg" className="bg-white">
            <div className="space-y-4">
              <div className="text-sm text-[#6b7280] uppercase tracking-wide">Demo-ready highlights</div>
              <div className="grid grid-cols-1 gap-3">
                {[
                  'Single assignment view with readiness, compliance, and blockers.',
                  'Employee journey with visible progress and submission checkpoint.',
                  'HR review with compliance checks and decision logging.',
                  'Audit-friendly data capture for internal mobility teams.',
                ].map((item) => (
                  <div key={item} className="flex gap-3 items-start">
                    <span className="mt-1 h-2 w-2 rounded-full bg-[#0b2b43]" />
                    <span className="text-[#374151] text-sm">{item}</span>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </section>

        <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            { label: 'Average intake time', value: '12 min' },
            { label: 'Compliance rules tracked', value: '10+ checks' },
            { label: 'Visibility on case status', value: 'Real-time' },
          ].map((stat) => (
            <Card key={stat.label} padding="md">
              <div className="text-3xl font-semibold text-[#0b2b43]">{stat.value}</div>
              <div className="text-sm text-[#6b7280]">{stat.label}</div>
            </Card>
          ))}
        </section>

        <section className="border border-[#e2e8f0] rounded-2xl p-6 bg-white">
          <div className="text-xs uppercase tracking-wide text-[#6b7280] mb-3">Trusted by operations teams</div>
          <div className="flex flex-wrap gap-6 text-sm text-[#4b5563]">
            <span>Northwind Logistics</span>
            <span>Blue Harbor Group</span>
            <span>Skylane Mobility</span>
            <span>Nordic Retail Partners</span>
          </div>
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          <Card padding="lg" className="bg-white">
            <div className="text-sm text-[#6b7280] uppercase tracking-wide mb-2">Program visibility</div>
            <div className="text-2xl font-semibold text-[#0b2b43]">
              Track progress, compliance, and approvals in one view.
            </div>
            <p className="text-sm text-[#4b5563] mt-3">
              HR can see readiness and pending actions without digging through emails or spreadsheets.
            </p>
          </Card>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {['Case intake', 'Employee journey', 'Compliance checks', 'Decision logging'].map((label) => (
              <Card key={label} padding="md">
                <div className="text-sm text-[#6b7280]">Module</div>
                <div className="text-lg font-semibold text-[#0b2b43]">{label}</div>
              </Card>
            ))}
          </div>
        </section>

        <section className="space-y-6">
          <div className="text-2xl font-semibold text-[#0b2b43]">A simple and streamlined process</div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                title: 'HR prepares the case',
                description: 'Create a relocation case and assign an employee identifier.',
              },
              {
                title: 'Employee completes intake',
                description: 'Guided questions capture required data with progress tracking.',
              },
              {
                title: 'HR reviews and decides',
                description: 'Run compliance checks and approve or request changes.',
              },
            ].map((step, idx) => (
              <Card key={step.title} padding="md">
                <div className="text-sm text-[#6b7280]">Step {idx + 1}</div>
                <div className="text-lg font-semibold text-[#0b2b43]">{step.title}</div>
                <div className="text-sm text-[#4b5563] mt-2">{step.description}</div>
              </Card>
            ))}
          </div>
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-center">
          <Card padding="lg">
            <div className="text-sm text-[#6b7280] uppercase tracking-wide mb-2">Platform coverage</div>
            <div className="text-2xl font-semibold text-[#0b2b43]">
              Purpose-built for HR relocation operations.
            </div>
            <p className="text-sm text-[#4b5563] mt-3">
              Standardize relocation data, review compliance against policy, and keep HR decisions transparent.
            </p>
          </Card>
          <Card padding="lg" className="bg-[#f6f9fb] border border-[#e2e8f0]">
            <div className="text-sm text-[#6b7280] uppercase tracking-wide mb-2">Security posture</div>
            <div className="text-2xl font-semibold text-[#0b2b43]">
              Designed for sensitive employee data.
            </div>
            <p className="text-sm text-[#4b5563] mt-3">
              Controlled access, clear audit trails, and compliance documentation in one secure workspace.
            </p>
          </Card>
        </section>

        <section className="bg-white border border-[#e2e8f0] rounded-2xl p-8 flex flex-col md:flex-row items-center justify-between gap-6">
          <div>
            <div className="text-2xl font-semibold text-[#0b2b43]">Ready to see the workflow?</div>
            <div className="text-sm text-[#4b5563] mt-2">
              Launch the demo environment or connect to your HR workspace.
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button onClick={() => navigate('/auth?mode=register')}>Create account</Button>
            <Button variant="outline" onClick={() => navigate(`${buildRoute('auth')}?mode=login`)}>
              Sign in
            </Button>
          </div>
        </section>

        <section className="border border-[#e2e8f0] rounded-2xl p-6 bg-[#f9fafb]">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <div className="text-xs uppercase tracking-wide text-[#6b7280] mb-1">Backend connection</div>
              <div className="text-sm text-[#4b5563]">
                API: <code className="bg-[#e2e8f0] px-1.5 py-0.5 rounded text-xs">{API_BASE_URL || '(same-origin)'}</code>
              </div>
            </div>
            <Button
              variant="outline"
              onClick={testConnection}
              disabled={connStatus.state === 'loading'}
            >
              {connStatus.state === 'loading' ? 'Testing...' : 'Test connection'}
            </Button>
          </div>
          {connStatus.state === 'ok' && (
            <div className="mt-3 bg-green-50 border border-green-200 rounded-lg p-3 text-sm">
              <span className="font-medium text-green-800">Connected</span>
              <span className="text-green-700 ml-2">{connStatus.latency}ms</span>
              <pre className="mt-1 text-xs text-green-700 overflow-auto">{JSON.stringify(connStatus.data, null, 2)}</pre>
            </div>
          )}
          {connStatus.state === 'error' && (
            <div className="mt-3 bg-red-50 border border-red-200 rounded-lg p-3 text-sm">
              <span className="font-medium text-red-800">Failed</span>
              {connStatus.latency !== undefined && <span className="text-red-600 ml-2">{connStatus.latency}ms</span>}
              <div className="mt-1 text-xs text-red-700">{connStatus.error}</div>
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
};
