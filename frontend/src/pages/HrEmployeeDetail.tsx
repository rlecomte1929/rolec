import React, { useEffect, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Card, Button, Alert } from '../components/antigravity';
import { hrAPI } from '../api/client';
import type { HrCompanyEmployee } from '../types';
import { buildRoute } from '../navigation/routes';
import { safeNavigate } from '../navigation/safeNavigate';
import {
  POLICY_EMPLOYEE_LEVEL_OPTIONS,
  normalizeEmployeeLevel,
} from '../features/policy-config/policyTargeting';

// Canonical employee-level options mirror the admin Policy Workspace
// row editor so HR uses the same vocabulary everywhere. The previous
// "Band1..Band4" values are absorbed through normalizeEmployeeLevel so
// a profile saved before this rename still resolves to the right option
// on load — the employee's existing band is not lost, it's just
// re-labelled.
const ASSIGNMENT_TYPES = ['Long-Term', 'Permanent', 'Short-Term'];
const STATUSES = ['active', 'inactive', 'on_assignment'];

export const HrEmployeeDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [employee, setEmployee] = useState<HrCompanyEmployee | null>(null);
  const [band, setBand] = useState('');
  const [assignmentType, setAssignmentType] = useState('');
  const [status, setStatus] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  const loadEmployee = async () => {
    if (!id) return;
    setIsLoading(true);
    setError('');
    try {
      const { employee: emp } = await hrAPI.getEmployee(id);
      setEmployee(emp);
      // Back-compat: absorb legacy Band1..Band4 (and L1..L4, job-title
      // synonyms) into the canonical slug so the select shows the right
      // option instead of an empty "Select…" for pre-existing rows.
      const storedBand = emp.band || '';
      setBand(normalizeEmployeeLevel(storedBand) ?? '');
      setAssignmentType(emp.assignment_type || '');
      setStatus(emp.status || '');
    } catch (err: any) {
      if (err?.response?.status === 401) {
        safeNavigate(navigate, 'landing');
      } else if (err?.response?.status === 404) {
        setError('Employee not found.');
      } else {
        setError('Unable to load employee.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadEmployee();
  }, [id, navigate]);

  const handleSave = async () => {
    if (!id) return;
    setIsSaving(true);
    setError('');
    setSaved(false);
    try {
      await hrAPI.updateEmployee(id, {
        band: band || undefined,
        assignment_type: assignmentType || undefined,
        status: status || undefined,
      });
      setSaved(true);
      void loadEmployee();
    } catch (err: any) {
      if (err?.response?.status === 404) {
        setError('Employee not found.');
      } else {
        setError('Failed to save.');
      }
    } finally {
      setIsSaving(false);
    }
  };

  const displayName = employee?.full_name || employee?.email || employee?.profile_id || 'Employee';

  return (
    <AppShell title={displayName} subtitle="Profile and assignments">
      <div className="max-w-2xl">
        <div className="flex items-center gap-2 mb-4">
          <Link
            to={buildRoute('hrEmployees')}
            className="text-sm text-[#6b7280] hover:text-[#0b2b43]"
          >
            ← Employees
          </Link>
          <span className="text-[#9ca3af]">·</span>
          <Link to={buildRoute('hrPolicy')} className="text-sm text-[#6b7280] hover:text-[#0b2b43]">
            Policy
          </Link>
        </div>

        {error && (
          <Alert variant="error" className="mb-4">
            {error}
          </Alert>
        )}
        {saved && (
          <Alert variant="success" className="mb-4">
            Saved.
          </Alert>
        )}

        {isLoading ? (
          <Card padding="lg">
            <div className="text-sm text-[#6b7280]">Loading…</div>
          </Card>
        ) : !employee ? (
          <Card padding="lg">
            <div className="text-sm text-[#6b7280]">Employee not found.</div>
          </Card>
        ) : (
          <Card padding="lg">
            <div className="space-y-4">
              <div>
                <div className="text-xs text-[#6b7280] uppercase tracking-wide">Name</div>
                <div className="font-medium text-[#0b2b43]">
                  {employee.full_name || '-'}
                </div>
              </div>
              <div>
                <div className="text-xs text-[#6b7280] uppercase tracking-wide">Email</div>
                <div className="text-[#0b2b43]">{employee.email || '-'}</div>
              </div>
              <div>
                <div className="text-xs text-[#6b7280] uppercase tracking-wide">Employee level</div>
                <select
                  value={band}
                  onChange={(e) => setBand(e.target.value)}
                  className="mt-1 block w-full max-w-xs rounded-lg border border-[#d1d5db] px-3 py-2 text-sm"
                >
                  <option value="">Select…</option>
                  {POLICY_EMPLOYEE_LEVEL_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-[#6b7280]">
                  Used by the compensation matrix to apply level-specific caps (e.g. different
                  relocation allowance for Directors vs Entry Level).
                </p>
              </div>
              <div>
                <div className="text-xs text-[#6b7280] uppercase tracking-wide">Assignment type</div>
                <select
                  value={assignmentType}
                  onChange={(e) => setAssignmentType(e.target.value)}
                  className="mt-1 block w-full max-w-xs rounded-lg border border-[#d1d5db] px-3 py-2 text-sm"
                >
                  <option value="">Select…</option>
                  {ASSIGNMENT_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div>
                <div className="text-xs text-[#6b7280] uppercase tracking-wide">Status</div>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  className="mt-1 block w-full max-w-xs rounded-lg border border-[#d1d5db] px-3 py-2 text-sm"
                >
                  <option value="">Select…</option>
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
              <div className="pt-2">
                <Button onClick={handleSave} disabled={isSaving}>
                  {isSaving ? 'Saving…' : 'Save changes'}
                </Button>
              </div>
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
};
