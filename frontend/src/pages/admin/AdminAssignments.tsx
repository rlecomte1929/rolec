import React, { useEffect, useState, useCallback } from 'react';
import { Card, Button, Badge, Input, Select } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';
import { adminAPI } from '../../api/client';
import type { AdminAssignment, AdminAssignmentDetail, AdminCompany } from '../../types';
import { buildRoute } from '../../navigation/routes';
import { Link } from 'react-router-dom';

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'assigned', label: 'Assigned' },
  { value: 'awaiting_intake', label: 'Awaiting intake' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'approved', label: 'Approved' },
  { value: 'completed', label: 'Completed' },
];

const employeeName = (a: AdminAssignment) =>
  a.employee_full_name || [a.employee_first_name, a.employee_last_name].filter(Boolean).join(' ') || a.employee_identifier || '—';

const destination = (a: AdminAssignment) =>
  a.host_country || a.destination_from_profile || '—';

const origin = (a: AdminAssignment) => a.home_country || '—';

export const AdminAssignments: React.FC = () => {
  const [assignments, setAssignments] = useState<AdminAssignment[]>([]);
  const [companies, setCompanies] = useState<AdminCompany[]>([]);
  const [filters, setFilters] = useState({
    company_id: '',
    employee_search: '',
    status: '',
    destination_country: '',
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AdminAssignmentDetail | null>(null);
  const [loading, setLoading] = useState(false);

  const loadAssignments = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminAPI.listAssignments({
        company_id: filters.company_id || undefined,
        employee_search: filters.employee_search || undefined,
        status: filters.status || undefined,
        destination_country: filters.destination_country || undefined,
      });
      setAssignments(res.assignments);
    } finally {
      setLoading(false);
    }
  }, [filters.company_id, filters.employee_search, filters.status, filters.destination_country]);

  const loadCompanies = useCallback(async () => {
    const res = await adminAPI.listCompanies();
    setCompanies(res.companies);
  }, []);

  const loadDetail = useCallback(async (id: string) => {
    const res = await adminAPI.getAssignmentDetail(id);
    setDetail(res.assignment);
  }, []);

  useEffect(() => {
    loadCompanies().catch(() => undefined);
  }, [loadCompanies]);

  useEffect(() => {
    if (filters.company_id) {
      loadAssignments().catch(() => undefined);
    } else {
      setAssignments([]);
    }
  }, [filters.company_id, loadAssignments]);

  useEffect(() => {
    if (selectedId) {
      loadDetail(selectedId).catch(() => setDetail(null));
    } else {
      setDetail(null);
    }
  }, [selectedId, loadDetail]);

  const applyFilters = () => {
    loadAssignments().catch(() => undefined);
  };

  const isLinkageConsistent = (d: AdminAssignmentDetail | null): { ok: boolean; issues: string[] } => {
    if (!d) return { ok: true, issues: [] };
    const issues: string[] = [];
    const caseCo = d.case_company_id ?? d.company_id;
    const empCo = d.employee_company_id ?? d.employee_profile_company_id;
    const hrCo = d.hr_company_id ?? d.hr_profile_company_id;
    if (caseCo && empCo && caseCo !== empCo) issues.push('Employee company differs from assignment company');
    if (caseCo && hrCo && caseCo !== hrCo) issues.push('HR company differs from assignment company');
    if (empCo && hrCo && empCo !== hrCo) issues.push('Employee and HR belong to different companies');
    return { ok: issues.length === 0, issues };
  };

  const linkage = isLinkageConsistent(detail);

  return (
    <AdminLayout
      title="Assignments"
      subtitle="Select a company to view and manage assignments"
    >
      <Card padding="lg" className="mb-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end">
          <Select
            label="Company"
            value={filters.company_id}
            onChange={(v) => setFilters((f) => ({ ...f, company_id: v }))}
            options={[{ value: '', label: 'Select company' }, ...companies.map((c) => ({ value: c.id, label: c.name }))]}
            placeholder="Select company"
          />
          <Input
            label="Employee search"
            value={filters.employee_search}
            onChange={(v) => setFilters((f) => ({ ...f, employee_search: v }))}
            placeholder="Name or identifier"
          />
          <Select
            label="Status"
            value={filters.status}
            onChange={(v) => setFilters((f) => ({ ...f, status: v }))}
            options={STATUS_OPTIONS}
          />
          <Input
            label="Destination country"
            value={filters.destination_country}
            onChange={(v) => setFilters((f) => ({ ...f, destination_country: v }))}
            placeholder="e.g. Singapore"
          />
          <Button onClick={applyFilters} disabled={loading}>
            {loading ? 'Loading…' : 'Apply'}
          </Button>
        </div>
      </Card>

      <Card padding="lg">
        {!filters.company_id ? (
          <div className="py-12 text-center text-[#6b7280] border border-dashed border-[#e5e7eb] rounded-lg bg-[#f9fafb]">
            Select a company above to view and manage assignments.
          </div>
        ) : (
          <>
            <div className="text-sm text-[#6b7280] mb-2">Assignments ({assignments.length})</div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#e2e8f0] text-left text-[#6b7280]">
                    <th className="py-2 pr-2">Employee</th>
                    <th className="py-2 pr-2">Company</th>
                    <th className="py-2 pr-2">Destination</th>
                    <th className="py-2 pr-2">Origin</th>
                    <th className="py-2 pr-2">Type</th>
                    <th className="py-2 pr-2">Family</th>
                    <th className="py-2 pr-2">Move date</th>
                    <th className="py-2 pr-2">Policy</th>
                    <th className="py-2 pr-2">Status</th>
                    <th className="py-2 pr-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {assignments.map((a) => (
                    <tr
                      key={a.id}
                      className="border-b border-[#e2e8f0] hover:bg-[#f8fafc]"
                    >
                      <td className="py-2 pr-2 font-medium text-[#0b2b43]">{employeeName(a)}</td>
                      <td className="py-2 pr-2">{a.company_name || '—'}</td>
                      <td className="py-2 pr-2">{destination(a)}</td>
                      <td className="py-2 pr-2">{origin(a)}</td>
                      <td className="py-2 pr-2">{a.assignment_type || '—'}</td>
                      <td className="py-2 pr-2">{a.family_status || '—'}</td>
                      <td className="py-2 pr-2">{a.move_date || '—'}</td>
                      <td className="py-2 pr-2">
                        {a.policy_resolved ? (
                          <Badge variant="success" size="sm">Resolved</Badge>
                        ) : a.company_has_policy ? (
                          <Badge variant="neutral" size="sm">Available</Badge>
                        ) : (
                          <Badge variant="neutral" size="sm">None</Badge>
                        )}
                      </td>
                      <td className="py-2 pr-2">
                        <Badge variant="neutral" size="sm">{(a.status || '—').replace(/_/g, ' ')}</Badge>
                      </td>
                      <td className="py-2 pr-2">
                        <Button size="sm" onClick={() => setSelectedId(a.id)}>
                          Detail
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {assignments.length === 0 && (
              <div className="text-sm text-[#6b7280] py-6 text-center">No assignments found for this company.</div>
            )}
          </>
        )}
      </Card>

      {selectedId && (
        <AdminAssignmentDetailDrawer
          assignmentId={selectedId}
          detail={detail}
          linkage={linkage}
          onClose={() => setSelectedId(null)}
          onRefresh={() => {
            loadAssignments();
            loadDetail(selectedId);
          }}
        />
      )}
    </AdminLayout>
  );
};

interface AdminAssignmentDetailDrawerProps {
  assignmentId: string;
  detail: AdminAssignmentDetail | null;
  linkage: { ok: boolean; issues: string[] };
  onClose: () => void;
  onRefresh: () => void;
}

const AdminAssignmentDetailDrawer: React.FC<AdminAssignmentDetailDrawerProps> = ({
  assignmentId,
  detail,
  linkage,
  onClose,
  onRefresh,
}) => {
  const [reason, setReason] = useState('');
  const [reassignCompanyId, setReassignCompanyId] = useState('');
  const [reassignHrId, setReassignHrId] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [companies, setCompanies] = useState<AdminCompany[]>([]);
  const [hrUsers, setHrUsers] = useState<Array<{ id: string; label: string }>>([]);
  const [fixCompanyId, setFixCompanyId] = useState('');

  useEffect(() => {
    adminAPI.listCompanies().then((r) => setCompanies(r.companies)).catch(() => {});
  }, []);

  useEffect(() => {
    const cid = detail?.case_company_id || detail?.hr_company_id;
    if (cid) {
      adminAPI.listHrUsers(cid).then((r) => {
        setHrUsers(r.hr_users.map((h) => ({ id: h.profile_id, label: (h as { full_name?: string }).full_name || h.profile_id })));
      }).catch(() => setHrUsers([]));
    } else {
      setHrUsers([]);
    }
  }, [detail?.case_company_id, detail?.hr_company_id]);

  const doReassignEmployee = async () => {
    if (!reason.trim() || !reassignCompanyId) return;
    setActionLoading(true);
    try {
      await adminAPI.reassignEmployeeCompany(assignmentId, { reason: reason.trim(), company_id: reassignCompanyId });
      onRefresh();
      setReason('');
      setReassignCompanyId('');
    } finally {
      setActionLoading(false);
    }
  };

  const doReassignHr = async () => {
    if (!reason.trim() || !reassignHrId) return;
    setActionLoading(true);
    try {
      await adminAPI.reassignHrOwner(assignmentId, { reason: reason.trim(), hr_user_id: reassignHrId });
      onRefresh();
      setReason('');
      setReassignHrId('');
    } finally {
      setActionLoading(false);
    }
  };

  const doFixLinkage = async () => {
    if (!reason.trim() || !fixCompanyId) return;
    setActionLoading(true);
    try {
      await adminAPI.fixAssignmentCompanyLinkage(assignmentId, { reason: reason.trim(), company_id: fixCompanyId });
      onRefresh();
      setReason('');
      setFixCompanyId('');
    } finally {
      setActionLoading(false);
    }
  };

  const empId = detail?.employee_user_id;
  const hrId = detail?.hr_user_id;

  return (
    <div className="fixed inset-0 z-50 flex items-stretch">
      <div className="flex-1 bg-black/30" onClick={onClose} aria-hidden="true" />
      <div className="w-full max-w-xl bg-white shadow-xl overflow-y-auto flex flex-col">
        <div className="p-4 border-b border-[#e2e8f0] flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[#0b2b43]">Assignment detail</h2>
          <Button size="sm" variant="outline" onClick={onClose}>Close</Button>
        </div>
        <div className="p-4 space-y-4">
          {!detail ? (
            <div className="text-sm text-[#6b7280]">Loading…</div>
          ) : (
            <>
              <section>
                <h3 className="text-sm font-medium text-[#374151] mb-2">Employee</h3>
                <div className="text-sm text-[#0b2b43]">
                  {detail.employee_full_name || [detail.employee_first_name, detail.employee_last_name].filter(Boolean).join(' ') || detail.employee_identifier || '—'}
                </div>
                {detail.employee_email && <div className="text-xs text-[#6b7280]">{detail.employee_email}</div>}
                {empId && (
                  <Link to={buildRoute('employeeJourney') + `?assignment=${assignmentId}`} className="text-xs text-[#0b2b43] hover:underline mt-1 inline-block">
                    Open employee view →
                  </Link>
                )}
              </section>

              <section>
                <h3 className="text-sm font-medium text-[#374151] mb-2">Company & HR</h3>
                <div className="text-sm">Company: {detail.company_name || '—'}</div>
                <div className="text-sm">Assigned HR: {detail.hr_full_name || '—'} {detail.hr_email && `(${detail.hr_email})`}</div>
                {hrId && (
                  <Link to={buildRoute('hrDashboard')} className="text-xs text-[#0b2b43] hover:underline mt-1 inline-block">
                    Open HR dashboard →
                  </Link>
                )}
              </section>

              <section>
                <h3 className="text-sm font-medium text-[#374151] mb-2">Relocation</h3>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <span className="text-[#6b7280]">Destination:</span><span>{detail.host_country || detail.destination_from_profile || '—'}</span>
                  <span className="text-[#6b7280]">Origin:</span><span>{detail.home_country || '—'}</span>
                  <span className="text-[#6b7280]">Type:</span><span>{detail.assignment_type || '—'}</span>
                  <span className="text-[#6b7280]">Move date:</span><span>{detail.move_date || '—'}</span>
                </div>
              </section>

              <section>
                <h3 className="text-sm font-medium text-[#374151] mb-2">Service selections</h3>
                {detail.case_services && detail.case_services.length > 0 ? (
                  <ul className="text-sm space-y-1">
                    {detail.case_services.filter((s) => s.selected).map((s) => (
                      <li key={s.service_key}>{s.service_key} ({s.category})</li>
                    ))}
                  </ul>
                ) : (
                  <div className="text-sm text-[#6b7280]">None</div>
                )}
              </section>

              <section>
                <h3 className="text-sm font-medium text-[#374151] mb-2">Policy linkage</h3>
                <div className="text-sm">
                  Resolved: {detail.resolved_policy ? 'Yes' : 'No'} · Company policy: {detail.company_has_published_policy ? 'Yes' : 'No'}
                </div>
              </section>

              {!linkage.ok && (
                <section className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
                  <h3 className="text-sm font-medium text-amber-800 mb-1">Linkage issues</h3>
                  <ul className="text-sm text-amber-800 list-disc list-inside">
                    {linkage.issues.map((i) => (
                      <li key={i}>{i}</li>
                    ))}
                  </ul>
                </section>
              )}

              <section className="border-t border-[#e2e8f0] pt-4">
                <h3 className="text-sm font-medium text-[#374151] mb-2">Admin corrections</h3>
                <Input
                  label="Reason (required for any change)"
                  value={reason}
                  onChange={setReason}
                  placeholder="Brief reason for change"
                />
                <div className="mt-3 space-y-2">
                  {detail.employee_user_id && (
                    <div className="flex flex-wrap gap-2 items-center">
                      <Select
                        value={reassignCompanyId}
                        onChange={setReassignCompanyId}
                        options={[{ value: '', label: 'Select company' }, ...companies.map((c) => ({ value: c.id, label: c.name }))]}
                        placeholder="Reassign employee company"
                      />
                      <Button size="sm" onClick={doReassignEmployee} disabled={!reason.trim() || !reassignCompanyId || actionLoading}>
                        Reassign employee company
                      </Button>
                    </div>
                  )}
                  <div className="flex flex-wrap gap-2 items-center">
                    <Select
                      value={reassignHrId}
                      onChange={setReassignHrId}
                      options={[{ value: '', label: 'Select HR' }, ...hrUsers.map((h) => ({ value: h.id, label: h.label }))]}
                      placeholder="Reassign HR owner"
                    />
                    <Button size="sm" onClick={doReassignHr} disabled={!reason.trim() || !reassignHrId || actionLoading}>
                      Reassign HR owner
                    </Button>
                  </div>
                  <div className="flex flex-wrap gap-2 items-center">
                    <Select
                      value={fixCompanyId}
                      onChange={setFixCompanyId}
                      options={[{ value: '', label: 'Select company' }, ...companies.map((c) => ({ value: c.id, label: c.name }))]}
                      placeholder="Fix assignment–company linkage"
                    />
                    <Button size="sm" variant="outline" onClick={doFixLinkage} disabled={!reason.trim() || !fixCompanyId || actionLoading}>
                      Fix assignment–company linkage
                    </Button>
                  </div>
                </div>
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
