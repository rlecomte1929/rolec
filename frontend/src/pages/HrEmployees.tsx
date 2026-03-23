import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Card, Button, Alert, Badge } from '../components/antigravity';
import { hrAPI } from '../api/client';
import type { HrCompanyEmployee } from '../types';
import { buildRoute } from '../navigation/routes';
import { safeNavigate } from '../navigation/safeNavigate';

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
    <AppShell title="Employees" subtitle="People at your company on ReloPass">
      <div className="max-w-4xl">
        <div className="flex items-center justify-between gap-4 mb-4">
          <p className="text-sm text-[#6b7280]">
            View and manage employees in your company. Click an employee to view or edit details.
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

        {isLoading ? (
          <Card padding="lg">
            <div className="text-sm text-[#6b7280]">Loading employees…</div>
          </Card>
        ) : employees.length === 0 ? (
          <Card padding="lg">
            {hasCompany === false ? (
              <>
                <div className="text-sm text-[#6b7280]">
                  Complete your company profile to view employees.
                </div>
                <div className="mt-2">
                  <Link to={buildRoute('hrCompanyProfile')}>
                    <Button variant="primary" size="sm">
                      Set up company profile
                    </Button>
                  </Link>
                </div>
              </>
            ) : (
              <>
                <div className="text-sm text-[#6b7280]">No employees found for your company.</div>
                <div className="mt-2 text-xs text-[#9ca3af]">
                  Employees are added when you create assignments and assign them to cases.
                </div>
              </>
            )}
          </Card>
        ) : (
          <Card padding="none">
            <div className="divide-y divide-[#e5e7eb]">
              {employees.map((emp) => (
                <Link
                  key={emp.id}
                  to={buildRoute('hrEmployeeDetail', { id: emp.id })}
                  className="block px-4 py-3 hover:bg-[#f9fafb] transition-colors"
                >
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <div className="font-medium text-[#0b2b43]">
                        {emp.full_name || emp.email || emp.profile_id || '-'}
                      </div>
                      {emp.email && (
                        <div className="text-xs text-[#6b7280]">{emp.email}</div>
                      )}
                      {(emp.band || emp.assignment_type) && (
                        <div className="text-xs text-[#9ca3af] mt-1">
                          {[emp.band, emp.assignment_type].filter(Boolean).join(' · ')}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {emp.status && (
                        <Badge variant="neutral" size="sm">
                          {emp.status}
                        </Badge>
                      )}
                      <span className="text-[#9ca3af]">→</span>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
};
