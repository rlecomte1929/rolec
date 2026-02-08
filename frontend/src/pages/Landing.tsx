import React from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Button, Card } from '../components/antigravity';
import { buildRoute } from '../navigation/routes';
import { useRegisterNav } from '../navigation/registry';

export const Landing: React.FC = () => {
  const navigate = useNavigate();

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
      </div>
    </AppShell>
  );
};
