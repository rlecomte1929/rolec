import React from 'react';
import { AppShell } from '../components/AppShell';
import { Card } from '../components/antigravity';
import { getNavRegistry } from '../navigation/registry';
import { ROUTE_DEFS, routeKeys } from '../navigation/routes';

export const NavigationAudit: React.FC = () => {
  const registry = getNavRegistry();
  const usedRouteKeys = new Set(registry.flatMap((page) => page.items.map((item) => item.routeKey)));
  const missingRoutes = registry.flatMap((page) =>
    page.items.filter((item) => !(item.routeKey in ROUTE_DEFS)).map((item) => ({
      page: page.pageId,
      label: item.label,
      routeKey: item.routeKey,
    }))
  );
  const unusedRoutes = routeKeys.filter((key) => !usedRouteKeys.has(key) && key !== 'auditNavigation');

  return (
    <AppShell title="Navigation Audit" subtitle="Routes and CTA integrity for demo readiness.">
      <div className="space-y-6">
        <Card padding="lg">
          <div className="text-sm font-semibold text-[#0b2b43] mb-3">Registered routes</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
            {routeKeys.map((key) => (
              <div key={key} className="border border-[#e2e8f0] rounded-lg p-3">
                <div className="font-medium text-[#0b2b43]">{key}</div>
                <div className="text-xs text-[#6b7280]">{ROUTE_DEFS[key].path}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card padding="lg">
          <div className="text-sm font-semibold text-[#0b2b43] mb-3">Buttons & links by page</div>
          <div className="space-y-4">
            {registry.map((page) => (
              <div key={page.pageId} className="border border-[#e2e8f0] rounded-lg p-4">
                <div className="text-sm font-semibold text-[#0b2b43]">{page.pageId}</div>
                <ul className="text-sm text-[#4b5563] mt-2 space-y-1">
                  {page.items.map((item) => (
                    <li key={`${item.label}-${item.routeKey}`}>
                      {item.label} → {item.routeKey}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Card>

        <Card padding="lg">
          <div className="text-sm font-semibold text-[#0b2b43] mb-3">Audit flags</div>
          <div className="space-y-3 text-sm text-[#4b5563]">
            <div>Missing routes: {missingRoutes.length}</div>
            {missingRoutes.length > 0 && (
              <ul className="list-disc pl-5">
                {missingRoutes.map((item) => (
                  <li key={`${item.page}-${item.label}`}>{item.page}: {item.label} → {item.routeKey}</li>
                ))}
              </ul>
            )}
            <div>Unused routes: {unusedRoutes.length}</div>
            {unusedRoutes.length > 0 && (
              <ul className="list-disc pl-5">
                {unusedRoutes.map((key) => (
                  <li key={key}>{key}</li>
                ))}
              </ul>
            )}
          </div>
        </Card>

        <Card padding="lg">
          <div className="text-sm font-semibold text-[#0b2b43] mb-3">Demo flows</div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-[#4b5563]">
            <div className="border border-[#e2e8f0] rounded-lg p-3">
              HR happy path: landing → auth → hrDashboard → hrAssignmentReview
            </div>
            <div className="border border-[#e2e8f0] rounded-lg p-3">
              Employee happy path: landing → auth → employeeJourney → submit
            </div>
            <div className="border border-[#e2e8f0] rounded-lg p-3">
              Employee submit → HR review: employeeJourney → hrAssignmentReview
            </div>
          </div>
        </Card>
      </div>
    </AppShell>
  );
};
