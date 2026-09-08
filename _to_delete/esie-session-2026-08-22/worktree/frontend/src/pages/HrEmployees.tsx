import React, { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Alert, Button } from '../components/antigravity';
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
          <Link to={buildRoute('hrPolicy')}>
            <Button variant="outline" size="sm">
              Policy
            </Button>
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
              <Link to={buildRoute('hrCompanyProfile')}>
                <Button variant="primary" size="sm">
                  Set up company profile
                </Button>
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
