import React, { useCallback, useEffect, useState } from 'react';
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
  const [employees, setEmployees] = useState<HrCompanyEmployee[]>([]);
  const [hasCompany, setHasCompany] = useState<boolean | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const loadEmployees = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const { employees: list, has_company } = await hrAPI.listCompanyEmployees();
      setEmployees(list || []);
      setHasCompany(has_company ?? true);
    } catch (err: any) {
      if (err?.response?.status === 401) {
        safeNavigate(navigate, 'landing');
      } else {
        setError('Unable to load employees.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    void loadEmployees();
  }, [location.key, loadEmployees]);

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
          <HrTeamList employees={employees} isLoading={isLoading} onReload={loadEmployees} />
        )}
      </div>
    </AppShell>
  );
};
