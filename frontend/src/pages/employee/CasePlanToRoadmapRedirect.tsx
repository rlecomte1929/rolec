import React from 'react';
import { Navigate, useParams } from 'react-router-dom';
import { buildRoute, ROUTE_DEFS } from '../../navigation/routes';

/**
 * [AIQ-1259b] The legacy relocation-plan page (/employee/case/:caseId/plan) was
 * consolidated into the canonical Roadmap (/employee/case/:caseId/roadmap). Both
 * rendered the same plan-view data and the Roadmap is the more capable surface
 * (hero, validation gate, generation polling, explain-term) — and the Policy
 * Assistant was ported onto it so no affordance is lost. Any remaining /plan link
 * (bookmarks, external refs) redirects here, preserving caseId.
 * See audit/ux/relocation_plan_vs_roadmap_v1.md.
 */
export const CasePlanToRoadmapRedirect: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  return (
    <Navigate
      to={caseId ? buildRoute('employeeCaseRoadmap', { caseId }) : ROUTE_DEFS.employeeDashboard.path}
      replace
    />
  );
};
