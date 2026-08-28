import React, { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Alert } from '../components/antigravity';
import { hrAPI } from '../api/client';
import type { HrCompanyEmployee } from '../types';
import { buildRoute } from '../navigation/routes';
import { safeNavigate } from '../navigation/safeNavigate';
import { HrTeamList } from '../features/hr/HrTeamList';

export const HrEmployees: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const employeesQuery = useQuery({
    queryKey: ['hr', 'company-employees', location.key],
    queryFn: () => hrAPI.listCompanyEmployees(),
  });

  const employees: HrCompanyEmployee[] = employeesQuery.data?.employees ?? [];
  const hasCompany: boolean | undefined = employeesQuery.data
    ? (employeesQuery.data.has_company ?? true)
    : undefined;
  const isLoading = employeesQuery.isLoading;
  const is401 = (employeesQuery.error as { response?: { status?: number } } | null)?.response?.status === 401;
  const error = employeesQuery.isError && !is401 ? 'Unable to load employees.' : '';

  useEffect(() => {
    if (employeesQuery.isError && is401) {
      safeNavigate(navigate, 'landing');
    }
  }, [employeesQuery.isError, is401, navigate]);

  return (
    <AppShell title="Team" subtitle="People at your company on ReloPass">
      <div className="max-w-5xl">
        <div className="flex items-center justify-between gap-4 mb-5">
          <p className="text-sm text-[#6b7280]">
            View and manage employees. Click a row to expand details.
          </p>
          {/* Styled Link, not <Link><Button>. A <button> inside an <a> is invalid HTML
              and axe flags it as nested-interactive: the button swallows the click and
              screen readers announce two nested controls. Classes mirror
              Button variant="outline" size="sm". */}
          <Link to={buildRoute('hrPolicy')} className="inline-block font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 border-2 border-[#0b2b43] text-[#0b2b43] hover:bg-[#e6f2f4] focus:ring-[#0b2b43] px-3 py-1.5 text-sm">
            Policy
          </Link>
        </div>

        {error && (
          <Alert variant="error" className="mb-4">
            {error}
          </Alert>
        )}

        {!isLoading && employees.length === 0 && hasCompany === false ? (
          <div className="border border-[#e5e7eb] rounded-xl p-6">
            <div className="text-sm text-[#6b7280]">
              Complete your company profile to view employees.
            </div>
            <div className="mt-3">
              <Link to={buildRoute('hrCompanyProfile')} className="inline-block font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 bg-[#0b2b43] text-white hover:bg-[#123651] focus:ring-[#0b2b43] px-3 py-1.5 text-sm">
                Set up company profile
              </Link>
            </div>
          </div>
        ) : (
          <HrTeamList
            employees={employees}
            isLoading={isLoading}
            onReload={() => employeesQuery.refetch()}
          />
        )}
      </div>
    </AppShell>
  );
};
