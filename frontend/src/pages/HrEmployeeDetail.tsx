import React, { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
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
  const queryClient = useQueryClient();
  // `band`/`assignmentType`/`status` are form-local: seeded from the loaded
  // employee, then edited freely until Save.
  const [band, setBand] = useState('');
  const [assignmentType, setAssignmentType] = useState('');
  const [status, setStatus] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isRemoving, setIsRemoving] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  // `error` is also written by handleSave, so keep it local and fold the read
  // error into what we render below.
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  const employeeQuery = useQuery({
    queryKey: ['hr', 'employee', id],
    queryFn: async () => {
      const { employee: emp } = await hrAPI.getEmployee(id!);
      return emp;
    },
    enabled: !!id,
  });
  const employee: HrCompanyEmployee | null = employeeQuery.data ?? null;
  // Original kept isLoading=true until a load resolved; with no id it never
  // flips false.
  const isLoading = id ? employeeQuery.isLoading : true;

  const loadStatus =
    (employeeQuery.error as { response?: { status?: number } } | null)?.response?.status;
  const load401 = loadStatus === 401;
  const readError = employeeQuery.isError
    ? load401
      ? '' // handled by the redirect below
      : loadStatus === 404
        ? 'Employee not found.'
        : 'Unable to load employee.'
    : '';
  const displayedError = error || readError;

  // Seed the form fields from the loaded employee. Back-compat: absorb legacy
  // Band1..Band4 (and L1..L4, job-title synonyms) into the canonical slug so
  // the select shows the right option instead of an empty "Select…".
  useEffect(() => {
    const emp = employeeQuery.data;
    if (!emp) return;
    setBand(normalizeEmployeeLevel(emp.band || '') ?? '');
    setAssignmentType(emp.assignment_type || '');
    setStatus(emp.status || '');
  }, [employeeQuery.data]);

  // Preserve the 401 → landing redirect from the read.
  useEffect(() => {
    if (employeeQuery.isError && load401) {
      safeNavigate(navigate, 'landing');
    }
  }, [employeeQuery.isError, load401, navigate]);

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
      // Refetch re-seeds the form from the saved server state.
      await queryClient.invalidateQueries({ queryKey: ['hr', 'employee', id] });
    } catch (err) {
      const e = err as { response?: { status?: number } };
      if (e.response?.status === 404) {
        setError('Employee not found.');
      } else {
        setError('Failed to save.');
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handleRemove = async () => {
    if (!id) return;
    setIsRemoving(true);
    setError('');
    try {
      await hrAPI.deleteEmployee(id);
      await queryClient.invalidateQueries({ queryKey: ['hr', 'company-employees'] });
      safeNavigate(navigate, 'hrEmployees');
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string }; status?: number } };
      if (e.response?.status === 404) {
        setError('Employee not found.');
      } else {
        const detail = e.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Failed to remove employee.');
      }
      setConfirmRemove(false);
    } finally {
      setIsRemoving(false);
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
          <span className="text-gray-500">·</span>
          <Link to={buildRoute('hrPolicy')} className="text-sm text-[#6b7280] hover:text-[#0b2b43]">
            Policy
          </Link>
        </div>

        {displayedError && (
          <Alert variant="error" className="mb-4">
            {displayedError}
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
              {/* Name and email are NOT editable here, and are labelled as such rather than
                  made to look like inputs. PATCH /api/hr/employees/{id} accepts only band /
                  assignment_type / status (backend/main.py), and the email is the account's
                  auth identifier under the hybrid auth model — changing it is an identity
                  operation needing verification, not an inline field edit. Presenting these
                  as plain text beside three editable selects read as "everything here is
                  editable"; the caption removes that expectation. */}
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
              <p className="text-xs text-slate-500">
                Name and email come from the employee&rsquo;s own account and can&rsquo;t be changed
                here. The fields below are editable.
              </p>
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
              <div className="pt-2 flex flex-wrap items-center gap-2">
                <Button onClick={handleSave} disabled={isSaving || isRemoving}>
                  {isSaving ? 'Saving…' : 'Save changes'}
                </Button>
                {!confirmRemove ? (
                  <Button variant="outline" onClick={() => setConfirmRemove(true)} disabled={isRemoving}>
                    Remove from company
                  </Button>
                ) : (
                  <>
                    <Button
                      unstyled
                      className="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 disabled:opacity-50"
                      onClick={handleRemove}
                      disabled={isRemoving}
                    >
                      {isRemoving ? 'Removing…' : 'Confirm remove'}
                    </Button>
                    <Button variant="outline" onClick={() => setConfirmRemove(false)} disabled={isRemoving}>
                      Cancel
                    </Button>
                  </>
                )}
              </div>
              <p className="text-xs text-[#6b7280]">
                Removing them from the company roster does not delete their ReloPass account or active cases.
              </p>
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
};
