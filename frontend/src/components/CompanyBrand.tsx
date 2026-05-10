import React from 'react';
import { useLocation } from 'react-router-dom';
import { useCompany } from '../hooks/useCompany';
import { useHrCompanyContext } from '../contexts/HrCompanyContext';
import { useEmployeeAssignment } from '../contexts/EmployeeAssignmentContext';
import { getAuthItem } from '../utils/demo';

const MAX_NAME_LENGTH = 24;

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export const CompanyBrand: React.FC = () => {
  const location = useLocation();
  const role = getAuthItem('relopass_role');
  const isOnHrRoute = location.pathname.startsWith('/hr');
  const isHrUser = role === 'HR' || role === 'ADMIN';
  const hrContext = useHrCompanyContext();
  const { primaryAssignmentCompany, isLoading: employeeAssignmentLoading } = useEmployeeAssignment();
  const preferAssignmentCompany =
    (role === 'EMPLOYEE' || role === 'ADMIN') && !isOnHrRoute && Boolean(primaryAssignmentCompany?.name);
  const companyAPI = useCompany({
    skip: (isHrUser && isOnHrRoute) || preferAssignmentCompany,
  });

  const assignmentCompany = preferAssignmentCompany
    ? {
        id: primaryAssignmentCompany!.id ?? undefined,
        name: primaryAssignmentCompany!.name!,
        logo_url: null as string | null | undefined,
      }
    : null;

  // HR on HR routes: context. Employee (or admin on employee-style routes) with linked assignment: overview company. Else: /api/company.
  const company =
    isHrUser && isOnHrRoute ? hrContext.company : assignmentCompany ?? companyAPI.company;
  const loading =
    isHrUser && isOnHrRoute
      ? hrContext.loading
      : preferAssignmentCompany && employeeAssignmentLoading
        ? true
        : assignmentCompany
          ? false
          : companyAPI.loading;

  if (loading || !company) {
    return null;
  }

  const name = String((company as Record<string, unknown>).name ?? '');
  const displayName =
    name.length > MAX_NAME_LENGTH
      ? `${name.slice(0, MAX_NAME_LENGTH - 1)}…`
      : name;
  const initials = getInitials(name);
  const logoUrl = (company as Record<string, unknown>).logo_url as string | undefined;

  return (
    <div className="flex items-center gap-2 shrink-0" title={name}>
      {logoUrl ? (
        <img
          src={logoUrl}
          alt=""
          className="h-7 w-7 rounded-full object-cover border border-[#e2e8f0]"
        />
      ) : (
        <div
          className="h-7 w-7 rounded-full flex items-center justify-center text-xs font-semibold bg-[#eef4f8] text-[#0b2b43] border border-[#e2e8f0]"
          aria-hidden
        >
          {initials}
        </div>
      )}
      <span className="text-sm font-medium text-[#0f172a] truncate max-w-[140px]">
        {displayName}
      </span>
      <span className="text-[#e2e8f0]" aria-hidden>|</span>
    </div>
  );
};
