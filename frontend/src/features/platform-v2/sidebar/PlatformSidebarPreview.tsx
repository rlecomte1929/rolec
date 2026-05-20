import React from 'react';
import { PlatformSidebar } from './PlatformSidebar';

/**
 * Standalone preview of the new platform sidebar. Mount at /platform-v2/sidebar
 * to see the redesign in isolation without the legacy AppShell chrome.
 */
export const PlatformSidebarPreview: React.FC = () => {
  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      <PlatformSidebar />

      <main className="flex-1 overflow-y-auto">
        <div className="border-b border-slate-200 bg-white px-8 py-4">
          <div className="flex items-center gap-2 text-[12.5px] text-slate-500">
            <span>Aurora Energy</span>
            <span className="text-slate-300">/</span>
            <span>HR Operations</span>
            <span className="text-slate-300">/</span>
            <span className="font-medium text-slate-800">Mobility control</span>
          </div>
        </div>

        <div className="mx-auto max-w-4xl px-8 py-12">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Sidebar redesign preview</h1>
          <p className="mt-2 text-[14px] text-slate-600">
            This is the new platform navigation. Click the round chevron on the right edge to fold or unfold the sidebar — the state persists in localStorage. Hover items when collapsed to see tooltips.
          </p>

          <div className="mt-8 space-y-3 text-[13.5px] text-slate-700">
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="font-medium text-slate-900">Sections</div>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-600">
                <li><strong>Employee</strong> — Intake, Detailed intake, Roadmap, Documents, Dossier &amp; forms, Service providers, Inbox</li>
                <li><strong>AI Engine</strong> — Requirements discovery</li>
                <li><strong>HR Operations</strong> — Company profile, Mobility control, Policy Builder, Policy &amp; benefits, Policy vs. Reality, Exceptions</li>
                <li><strong>Admin · ReloPass</strong> — Admin overview, Companies, Review queue, Ops analytics, Workflow analytics, Resources CMS, Prospects, Integrations</li>
              </ul>
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="font-medium text-slate-900">UX improvements vs. legacy top-nav</div>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-600">
                <li>Sectioned vertical layout — scales to 25+ destinations without wrapping.</li>
                <li>Each item carries a glyph for faster visual scanning.</li>
                <li>Collapse toggle reclaims ~190px for content; tooltips replace labels.</li>
                <li>Persistent collapse state across sessions (<code>localStorage</code>).</li>
                <li>Workspace switcher and search promoted to the top of the rail.</li>
                <li>Active route uses brand-blue tint instead of pill borders — softer at scale.</li>
                <li>Status badges differentiate <em>NEW</em>, <em>LIVE</em>, and counts via tone.</li>
              </ul>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default PlatformSidebarPreview;
