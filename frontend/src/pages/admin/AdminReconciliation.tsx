import React, { useCallback, useEffect, useState } from 'react';
import { AdminLayout } from './AdminLayout';
import { Card, Button, Alert } from '../../components/antigravity';
import { adminAPI } from '../../api/client';

type Report = {
  companies: Array<{ id: string; name: string; country?: string }>;
  people: Array<{ id: string; role?: string; email?: string; full_name?: string; company_id?: string }>;
  people_without_company: Array<{ id: string; role?: string; email?: string; full_name?: string }>;
  assignments: Array<{
    id: string;
    case_id?: string;
    employee_identifier?: string;
    status?: string;
    case_company_id?: string;
    hr_company_id?: string;
    employee_user_id?: string;
  }>;
  assignments_without_company: Array<{ id: string; case_id?: string; employee_identifier?: string; status?: string }>;
  assignments_without_person: Array<{ id: string; case_id?: string; employee_identifier?: string; status?: string }>;
  policies: Array<{ id: string; company_id: string; title?: string; extraction_status?: string }>;
  policies_without_company: Array<{ id: string; company_id: string; title?: string }>;
  summary: {
    companies_count: number;
    people_count: number;
    people_without_company_count: number;
    assignments_count: number;
    assignments_without_company_count: number;
    assignments_without_person_count: number;
    policies_count: number;
    policies_without_company_count: number;
  };
};

export const AdminReconciliation: React.FC = () => {
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [linking, setLinking] = useState<string | null>(null);
  const [reason, setReason] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await adminAPI.getReconciliationReport();
      setReport(data);
    } catch (e) {
      setError((e as Error)?.message || 'Failed to load report');
      setReport(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleLinkPersonCompany = async (profileId: string, companyId: string) => {
    setLinking(`person-${profileId}`);
    try {
      await adminAPI.reconciliationLinkPersonCompany(profileId, companyId);
      await load();
    } catch (e) {
      setError((e as Error)?.message || 'Link failed');
    } finally {
      setLinking(null);
    }
  };

  const handleLinkAssignmentCompany = async (assignmentId: string, companyId: string) => {
    if (!reason.trim()) {
      setError('Reason is required for assignment–company link');
      return;
    }
    setLinking(`assignment-company-${assignmentId}`);
    try {
      await adminAPI.reconciliationLinkAssignmentCompany(assignmentId, companyId, reason.trim());
      setReason('');
      await load();
    } catch (e) {
      setError((e as Error)?.message || 'Link failed');
    } finally {
      setLinking(null);
    }
  };

  const handleLinkAssignmentPerson = async (assignmentId: string, profileId: string) => {
    setLinking(`assignment-person-${assignmentId}`);
    try {
      await adminAPI.reconciliationLinkAssignmentPerson(assignmentId, profileId);
      await load();
    } catch (e) {
      setError((e as Error)?.message || 'Link failed');
    } finally {
      setLinking(null);
    }
  };

  const handleLinkPolicyCompany = async (policyId: string, companyId: string) => {
    setLinking(`policy-${policyId}`);
    try {
      await adminAPI.reconciliationLinkPolicyCompany(policyId, companyId);
      await load();
    } catch (e) {
      setError((e as Error)?.message || 'Link failed');
    } finally {
      setLinking(null);
    }
  };

  if (loading && !report) {
    return (
      <AdminLayout title="Reconciliation" subtitle="Repair missing links">
        <Card padding="lg">Loading report…</Card>
      </AdminLayout>
    );
  }

  const s = report?.summary;
  const companies = report?.companies ?? [];

  return (
    <AdminLayout
      title="Reconciliation"
      subtitle="Repair missing links between companies, people, assignments, and policies — no data deleted"
    >
      {error && (
        <Alert variant="error" className="mb-4">
          {error}
          <Button variant="outline" size="sm" className="ml-2" onClick={() => setError(null)}>Dismiss</Button>
        </Alert>
      )}

      <Card padding="lg" className="mb-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h2 className="text-lg font-semibold text-[#0b2b43]">Summary</h2>
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            {loading ? 'Refreshing…' : 'Refresh'}
          </Button>
        </div>
        {s && (
          <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3 text-sm">
            <div><dt className="text-[#6b7280]">Companies</dt><dd className="font-medium">{s.companies_count}</dd></div>
            <div><dt className="text-[#6b7280]">People</dt><dd className="font-medium">{s.people_count}</dd></div>
            <div><dt className="text-[#6b7280]">Assignments</dt><dd className="font-medium">{s.assignments_count}</dd></div>
            <div><dt className="text-[#6b7280]">Policies</dt><dd className="font-medium">{s.policies_count}</dd></div>
            <div><dt className="text-amber-700">People without company</dt><dd className="font-medium">{s.people_without_company_count}</dd></div>
            <div><dt className="text-amber-700">Assignments without company</dt><dd className="font-medium">{s.assignments_without_company_count}</dd></div>
            <div><dt className="text-amber-700">Assignments without person</dt><dd className="font-medium">{s.assignments_without_person_count}</dd></div>
            <div><dt className="text-amber-700">Policies without company</dt><dd className="font-medium">{s.policies_without_company_count}</dd></div>
          </dl>
        )}
      </Card>

      {!report ? (
        <Card padding="lg">No report data. Check backend and try again.</Card>
      ) : (
        <div className="space-y-6">
          {report.people_without_company.length > 0 && (
            <Card padding="lg">
              <h3 className="text-base font-semibold text-[#0b2b43] mb-2">People without company</h3>
              <p className="text-sm text-[#6b7280] mb-3">Attach a profile to a company so they appear in company-scoped views.</p>
              <ul className="space-y-2">
                {report.people_without_company.map((p) => (
                  <li key={p.id} className="flex flex-wrap items-center gap-2 py-2 border-b border-[#e5e7eb] last:border-0">
                    <span className="font-medium text-[#0b2b43]">{p.full_name || p.email || p.id}</span>
                    <span className="text-xs text-[#6b7280]">{p.role} · {p.id.slice(0, 8)}…</span>
                    <select
                      className="border border-[#d1d5db] rounded px-2 py-1 text-sm"
                      id={`person-company-${p.id}`}
                    >
                      <option value="">Select company</option>
                      {companies.map((c) => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!!linking}
                      onClick={() => {
                        const sel = document.getElementById(`person-company-${p.id}`) as HTMLSelectElement;
                        const cid = sel?.value;
                        if (cid) handleLinkPersonCompany(p.id, cid);
                      }}
                    >
                      {linking === `person-${p.id}` ? 'Linking…' : 'Attach'}
                    </Button>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {report.assignments_without_company.length > 0 && (
            <Card padding="lg">
              <h3 className="text-base font-semibold text-[#0b2b43] mb-2">Assignments without company</h3>
              <p className="text-sm text-[#6b7280] mb-3">Set the case company so the assignment appears under the correct company.</p>
              <div className="mb-3">
                <label className="block text-sm text-[#6b7280] mb-1">Reason (required for audit)</label>
                <input
                  type="text"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="e.g. Backfill test data"
                  className="border border-[#d1d5db] rounded px-2 py-1.5 text-sm w-64"
                />
              </div>
              <ul className="space-y-2">
                {report.assignments_without_company.map((a) => (
                  <li key={a.id} className="flex flex-wrap items-center gap-2 py-2 border-b border-[#e5e7eb] last:border-0">
                    <span className="font-medium text-[#0b2b43]">{a.id.slice(0, 8)}…</span>
                    <span className="text-xs text-[#6b7280]">{a.employee_identifier} · {a.status}</span>
                    <select className="border border-[#d1d5db] rounded px-2 py-1 text-sm" id={`assign-company-${a.id}`}>
                      <option value="">Select company</option>
                      {companies.map((c) => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!!linking || !reason.trim()}
                      onClick={() => {
                        const sel = document.getElementById(`assign-company-${a.id}`) as HTMLSelectElement;
                        const cid = sel?.value;
                        if (cid) handleLinkAssignmentCompany(a.id, cid);
                      }}
                    >
                      {linking === `assignment-company-${a.id}` ? 'Linking…' : 'Attach'}
                    </Button>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {report.assignments_without_person.length > 0 && (
            <Card padding="lg">
              <h3 className="text-base font-semibold text-[#0b2b43] mb-2">Assignments without person</h3>
              <p className="text-sm text-[#6b7280] mb-3">Attach an employee profile so the assignment is linked to a person.</p>
              <ul className="space-y-2">
                {report.assignments_without_person.map((a) => (
                  <li key={a.id} className="flex flex-wrap items-center gap-2 py-2 border-b border-[#e5e7eb] last:border-0">
                    <span className="font-medium text-[#0b2b43]">{a.id.slice(0, 8)}…</span>
                    <span className="text-xs text-[#6b7280]">{a.employee_identifier} · {a.status}</span>
                    <select className="border border-[#d1d5db] rounded px-2 py-1 text-sm" id={`assign-person-${a.id}`}>
                      <option value="">Select person</option>
                      {report.people.filter((p) => p.role === 'EMPLOYEE' || !p.role).map((p) => (
                        <option key={p.id} value={p.id}>{p.full_name || p.email || p.id.slice(0, 8)}</option>
                      ))}
                    </select>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!!linking}
                      onClick={() => {
                        const sel = document.getElementById(`assign-person-${a.id}`) as HTMLSelectElement;
                        const pid = sel?.value;
                        if (pid) handleLinkAssignmentPerson(a.id, pid);
                      }}
                    >
                      {linking === `assignment-person-${a.id}` ? 'Linking…' : 'Attach'}
                    </Button>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {report.policies_without_company.length > 0 && (
            <Card padding="lg">
              <h3 className="text-base font-semibold text-[#0b2b43] mb-2">Policies without company</h3>
              <p className="text-sm text-[#6b7280] mb-3">Reassign a policy to a company (company_id missing or invalid).</p>
              <ul className="space-y-2">
                {report.policies_without_company.map((p) => (
                  <li key={p.id} className="flex flex-wrap items-center gap-2 py-2 border-b border-[#e5e7eb] last:border-0">
                    <span className="font-medium text-[#0b2b43]">{p.title || p.id}</span>
                    <span className="text-xs text-[#6b7280]">company_id: {p.company_id || '—'}</span>
                    <select className="border border-[#d1d5db] rounded px-2 py-1 text-sm" id={`policy-company-${p.id}`}>
                      <option value="">Select company</option>
                      {companies.map((c) => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!!linking}
                      onClick={() => {
                        const sel = document.getElementById(`policy-company-${p.id}`) as HTMLSelectElement;
                        const cid = sel?.value;
                        if (cid) handleLinkPolicyCompany(p.id, cid);
                      }}
                    >
                      {linking === `policy-${p.id}` ? 'Linking…' : 'Attach'}
                    </Button>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {report.people_without_company.length === 0 &&
            report.assignments_without_company.length === 0 &&
            report.assignments_without_person.length === 0 &&
            report.policies_without_company.length === 0 && (
              <Card padding="lg">
                <p className="text-[#0b2b43] font-medium">No missing links detected</p>
                <p className="text-sm text-[#6b7280] mt-1">
                  Companies, people, assignments, and policies are linked. Use Refresh to re-run the report.
                </p>
              </Card>
            )}
        </div>
      )}
    </AdminLayout>
  );
};
