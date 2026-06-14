import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card } from '../antigravity';
import type { EmployeeLinkedOverviewRow } from '../../types/employeeAssignmentOverview';
import { formatCorridorLabel, formatCaseReference } from '../../types/employeeAssignmentOverview';
import { setPreferredEmployeeAssignmentId, withAssignmentQuery } from '../../utils/employeeAssignmentScope';
import { buildRoute } from '../../navigation/routes';

type Props = {
  title: string;
  subtitle?: string;
  linkedSummaries: EmployeeLinkedOverviewRow[];
  /** Path to navigate to with `?assignment=` set (e.g. `/services` or `/quotes`). */
  targetBasePath: string;
};

export function EmployeeScopedAssignmentPicker({
  title,
  subtitle,
  linkedSummaries,
  targetBasePath,
}: Props): React.ReactElement {
  const navigate = useNavigate();
  return (
    <Card padding="lg" className="mb-6 border border-[#e2e8f0]">
      <h2 className="text-lg font-semibold text-[#0b2b43]">{title}</h2>
      {subtitle ? <p className="text-sm text-[#4b5563] mt-2">{subtitle}</p> : null}
      <ul className="mt-4 space-y-2">
        {linkedSummaries.map((row) => (
          <li key={row.assignment_id}>
            <Button
              variant="outline"
              className="w-full justify-start !text-left h-auto py-3 whitespace-normal"
              onClick={() => {
                setPreferredEmployeeAssignmentId(row.assignment_id);
                navigate(withAssignmentQuery(targetBasePath, row.assignment_id));
              }}
            >
              {/* EMP-1: title the card by the MOVE (corridor), not the constant
                  company name. Company + ref are muted metadata below it, so 8
                  cases under one employer are distinguishable at a glance. */}
              <span className="block font-medium text-[#0b2b43]">{formatCorridorLabel(row.destination)}</span>
              <span className="block text-sm text-[#64748b] font-normal">
                {row.company?.name || 'Company'}
                {formatCaseReference(row) ? (
                  <span className="text-[#94a3b8]"> · Ref {formatCaseReference(row)}</span>
                ) : null}
              </span>
            </Button>
          </li>
        ))}
      </ul>
      <Button variant="outline" className="mt-4" onClick={() => navigate(buildRoute('employeeDashboard'))}>
        Back to dashboard
      </Button>
    </Card>
  );
}
