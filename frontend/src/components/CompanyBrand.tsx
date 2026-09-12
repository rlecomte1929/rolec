import React from 'react';
import { useLocation } from 'react-router-dom';
import { useCompany } from '../hooks/useCompany';
import { useHrCompanyContext } from '../contexts/HrCompanyContext';
import { useEmployeeAssignment } from '../contexts/EmployeeAssignmentContext';
import { getAuthItem } from '../utils/demo';

const MAX_NAME_LENGTH = 24;

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const first = parts[0];
  const last = parts[parts.length - 1];
  if (!first || !last) return '?';
  if (parts.length === 1) return first.slice(0, 2).toUpperCase();
  return (first.charAt(0) + last.charAt(0)).toUpperCase();
}

export interface CompanyBrandProps {
  /** Logo/initials only, no company name — for the collapsed (64px) sidebar rail. */
  compact?: boolean;
}

export const CompanyBrand: React.FC<CompanyBrandProps> = ({ compact = false }) => {
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
    // Hold the row's height instead of collapsing it. PlatformShellSidebar always renders
    // the wrapper (px-3 py-2 + border), so returning null made it 17px tall and it jumped
    // to 45px once the avatar (h-7 = 28px) mounted — pushing all 15 nav links down by
    // exactly 28px after the company-profile response landed.
    return <div className="h-7" aria-hidden />;
  }

  const nameRaw = (company as Record<string, unknown>).name;
  const name = typeof nameRaw === 'string' ? nameRaw : '';
  const displayName =
    name.length > MAX_NAME_LENGTH
      ? `${name.slice(0, MAX_NAME_LENGTH - 1)}…`
      : name;
  const initials = getInitials(name);
  const logoUrl = (company as Record<string, unknown>).logo_url as string | undefined;

  const mark = logoUrl ? (
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
  );

  // Collapsed sidebar: the mark alone. Previously the whole slot was hidden when
  // collapsed, so the company disappeared entirely — the page said the logo "appears in
  // the header on every page" and then it did not. The name would not fit in 64px; the
  // mark does, and `title` keeps it discoverable on hover.
  if (compact) {
    return (
      <div className="flex items-center justify-center shrink-0" title={name}>
        {mark}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 shrink-0" title={name}>
      {mark}
      <span className="text-sm font-medium text-[#0f172a] truncate max-w-[140px]">
        {displayName}
      </span>
    </div>
  );
};
