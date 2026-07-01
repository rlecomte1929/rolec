import { useState, useMemo } from 'react';
import {
  ClipboardCheck, Plane, Search, Filter, ChevronRight, ChevronLeft,
  Calendar, Shield, Briefcase, User, Building2, Users, AlertTriangle,
  CheckCircle2, Clock, Circle, XCircle, ArrowUpRight, FileCheck,
  Globe, Package, Scale, Home, GraduationCap, ArrowRight,
} from 'lucide-react';
import { tw } from '../../lib/colors';
import {
  DEMO_CASES,
  MARCUS_OBI_DETAIL,
  getCaseDetail,
  countByStatus,
  daysUntil,
  formatDate,
  type RelocationCase,
  type CaseStatus,
  type CaseDetail,
  type TimelineEvent,
  type ComplianceItem,
  type VendorAssignment,
  type ApprovalEntry,
} from './sample-data';

// ─── Status styles ───────────────────────────────────────────────────────────

const CASE_STATUS: Record<CaseStatus, { badge: string; dot: string }> = {
  Active: { badge: 'bg-[var(--space-brand-primary-50)] text-[var(--space-text-brand)] border-[var(--space-border-strong)]', dot: 'bg-[var(--space-brand-primary)]' },
  'At Risk': { badge: 'bg-amber-500/15 text-amber-300 border-amber-500/30', dot: 'bg-amber-400' },
  Completed: { badge: 'bg-green-500/15 text-green-300 border-green-500/30', dot: 'bg-[var(--space-semantic-success)]' },
};

const TIMELINE_STATUS: Record<string, { icon: typeof CheckCircle2; color: string }> = {
  completed: { icon: CheckCircle2, color: 'text-green-400 bg-green-500/15' },
  current: { icon: Clock, color: 'text-amber-400 bg-amber-500/15' },
  upcoming: { icon: Circle, color: 'text-[var(--space-text-muted)] bg-[var(--space-surface-muted)]' },
  blocked: { icon: XCircle, color: 'text-red-400 bg-red-500/15' },
};

const COMPLIANCE_STATUS: Record<string, { label: string; badge: string }> = {
  passed: { label: 'Passed', badge: 'bg-green-500/15 text-green-300' },
  pending: { label: 'Pending', badge: 'bg-[var(--space-surface-muted)] text-[var(--space-text-secondary)]' },
  at_risk: { label: 'At risk', badge: 'bg-amber-500/15 text-amber-300' },
  blocked: { label: 'Blocked', badge: 'bg-red-500/15 text-red-300' },
};

const VENDOR_STATUS: Record<string, { label: string; badge: string }> = {
  assigned: { label: 'Assigned', badge: 'bg-green-500/15 text-green-300' },
  in_progress: { label: 'Active', badge: 'bg-[var(--space-brand-primary-50)] text-[var(--space-text-brand)]' },
  pending: { label: 'Unassigned', badge: 'bg-amber-500/15 text-amber-300' },
};

const APPROVAL_STATUS: Record<string, { label: string; badge: string }> = {
  approved: { label: 'Approved', badge: 'bg-green-500/15 text-green-300' },
  pending: { label: 'Pending', badge: 'bg-amber-500/15 text-amber-300' },
  rejected: { label: 'Rejected', badge: 'bg-red-500/15 text-red-300' },
  escalated: { label: 'Escalated', badge: 'bg-orange-500/15 text-orange-300' },
};

const CATEGORY_ICON: Record<string, typeof Globe> = {
  immigration: Globe,
  tax: Scale,
  logistics: Package,
  compliance: Shield,
  housing: Home,
  hr: User,
};

// ─── Sub-components ──────────────────────────────────────────────────────────

function DaysRemaining({ date, status }: { date: string; status: CaseStatus }) {
  const days = daysUntil(date);
  if (status === 'Completed') {
    return <span className="text-xs text-[var(--space-semantic-success)] font-medium">Closed</span>;
  }
  if (days === null) return <span className="text-xs text-[var(--space-text-muted)]">—</span>;
  if (days < 0) {
    return (
      <span className="text-xs font-semibold text-red-400 flex items-center gap-1">
        <AlertTriangle className="w-3 h-3" />
        {Math.abs(days)}d overdue
      </span>
    );
  }
  if (days <= 7) {
    return (
      <span className="text-xs font-semibold text-amber-400">
        {days}d left
      </span>
    );
  }
  return (
    <span className="text-xs font-medium text-[var(--space-text-secondary)]">
      {days}d left
    </span>
  );
}

function CaseRow({
  c,
  selected,
  onSelect,
}: {
  c: RelocationCase;
  selected: boolean;
  onSelect: () => void;
}) {
  const style = CASE_STATUS[c.status];

  return (
    <button
      onClick={onSelect}
      className={`w-full text-left px-4 py-3.5 border-b border-[var(--space-border-default)] transition-all hover:bg-[var(--space-surface-card-hover)] ${
        selected ? 'bg-[var(--space-brand-primary-50)] border-l-[3px] border-l-[var(--space-brand-primary)]' : 'border-l-[3px] border-l-transparent'
      }`}
    >
      <div className="flex items-center gap-3">
        <div className={`w-2 h-2 rounded-full flex-shrink-0 ${style.dot}`} />
        <div className="flex-1 min-w-0 grid grid-cols-1 sm:grid-cols-[1.4fr_1.2fr_0.8fr_1fr_0.7fr] gap-1 sm:gap-3 items-center">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-[var(--space-text-primary)] truncate">{c.employeeName}</p>
            <p className="text-xs text-[var(--space-text-muted)] truncate hidden sm:block">{c.role}</p>
          </div>
          <p className="text-xs text-[var(--space-text-secondary)] flex items-center gap-1 min-w-0">
            <span className="font-medium">{c.originCode}</span>
            <Plane className="w-3 h-3 flex-shrink-0 text-[var(--space-brand-primary)]" />
            <span className="font-medium">{c.destinationCode}</span>
            <span className="text-[var(--space-text-muted)] hidden md:inline truncate">{c.origin} → {c.destination}</span>
          </p>
          <span className={`inline-flex w-fit px-2 py-0.5 rounded-full text-[10px] font-semibold border ${style.badge}`}>
            {c.status}
          </span>
          <p className="text-xs text-[var(--space-text-secondary)] truncate hidden sm:block">{c.coordinator}</p>
          <div className="hidden sm:block">
            <DaysRemaining date={c.deadlineDate} status={c.status} />
            <p className="text-[10px] text-[var(--space-text-muted)]">{formatDate(c.deadlineDate)}</p>
          </div>
        </div>
        <ChevronRight className={`w-4 h-4 flex-shrink-0 ${selected ? 'text-[var(--space-brand-primary)]' : 'text-[var(--space-text-muted)]'}`} />
      </div>
      {c.riskNote && c.status === 'At Risk' && (
        <p className="text-[10px] text-amber-300 mt-1.5 ml-5 flex items-center gap-1">
          <AlertTriangle className="w-3 h-3 flex-shrink-0" /> {c.riskNote}
        </p>
      )}
    </button>
  );
}

function TimelineEventCard({ event }: { event: TimelineEvent }) {
  const style = TIMELINE_STATUS[event.status] || TIMELINE_STATUS.upcoming;
  const Icon = style.icon;
  const CatIcon = CATEGORY_ICON[event.category] || FileCheck;

  return (
    <div className={`relative pl-8 pb-5 last:pb-0`}>
      <div className={`absolute left-0 top-0.5 w-6 h-6 rounded-full flex items-center justify-center ${style.color}`}>
        <Icon className="w-3.5 h-3.5" />
      </div>
      <div className={`p-3.5 rounded-xl border ${
        event.status === 'current' ? 'border-amber-500/30 bg-amber-500/10' :
        event.status === 'blocked' ? 'border-red-500/30 bg-red-500/10' :
        'border-[var(--space-border-default)] bg-[var(--space-surface-card)]'
      }`}>
        <div className="flex items-start justify-between gap-2 mb-1">
          <h4 className="text-sm font-semibold text-[var(--space-text-primary)] leading-snug">{event.title}</h4>
          <span className="text-[10px] text-[var(--space-text-muted)] flex-shrink-0">{formatDate(event.date)}</span>
        </div>
        <p className="text-xs text-[var(--space-text-secondary)] leading-relaxed mb-2">{event.description}</p>
        <div className="flex flex-wrap gap-3 text-[10px] text-[var(--space-text-muted)]">
          <span className="flex items-center gap-1"><User className="w-3 h-3" /> {event.owner}</span>
          <span className={`flex items-center gap-1 px-1.5 py-0.5 rounded ${tw.badge.neutral}`}>
            <CatIcon className="w-3 h-3" /> {event.category}
          </span>
        </div>
      </div>
    </div>
  );
}

function ComplianceCard({ item }: { item: ComplianceItem }) {
  const style = COMPLIANCE_STATUS[item.status] || COMPLIANCE_STATUS.pending;

  return (
    <div className={`p-3 rounded-xl border ${
      item.status === 'at_risk' ? 'border-amber-500/30 bg-amber-500/10' :
      item.status === 'passed' ? 'border-green-500/30 bg-green-500/10' :
      'border-[var(--space-border-default)] bg-[var(--space-surface-card)]'
    }`}>
      <div className="flex items-start justify-between gap-2 mb-1">
        <div className="flex items-center gap-2 min-w-0">
          <Shield className={`w-4 h-4 flex-shrink-0 ${
            item.status === 'passed' ? 'text-green-400' :
            item.status === 'at_risk' ? 'text-amber-400' : 'text-[var(--space-text-muted)]'
          }`} />
          <h5 className="text-sm font-medium text-[var(--space-text-primary)] leading-snug">{item.title}</h5>
        </div>
        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold flex-shrink-0 ${style.badge}`}>
          {style.label}
        </span>
      </div>
      <p className="text-xs text-[var(--space-text-secondary)] leading-relaxed ml-6 mb-1.5">{item.description}</p>
      <div className="flex flex-wrap gap-3 ml-6 text-[10px] text-[var(--space-text-muted)]">
        {item.regulation && <span className="flex items-center gap-1"><Scale className="w-3 h-3" /> {item.regulation}</span>}
        {item.dueDate && <span className="flex items-center gap-1"><Calendar className="w-3 h-3" /> Due {formatDate(item.dueDate)}</span>}
      </div>
    </div>
  );
}

function VendorCard({ vendor }: { vendor: VendorAssignment }) {
  const style = VENDOR_STATUS[vendor.status] || VENDOR_STATUS.pending;
  const isUnassigned = !vendor.vendorName;

  return (
    <div className={`p-3.5 rounded-xl border ${
      isUnassigned ? 'border-dashed border-amber-500/40 bg-amber-500/10' : 'border-[var(--space-border-default)] bg-[var(--space-surface-card)]'
    }`}>
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
            isUnassigned ? 'bg-amber-500/15' : 'bg-[var(--space-brand-primary-50)]'
          }`}>
            {vendor.category === 'Immigration' ? <Globe className="w-4 h-4 text-[var(--space-text-brand)]" /> :
             vendor.category === 'Relocation' ? <Package className="w-4 h-4 text-[var(--space-text-brand)]" /> :
             vendor.category === 'Tax Advisory' ? <Scale className="w-4 h-4 text-[var(--space-text-brand)]" /> :
             vendor.category === 'School Search' ? <GraduationCap className="w-4 h-4 text-[var(--space-text-brand)]" /> :
             <Briefcase className="w-4 h-4 text-[var(--space-text-brand)]" />}
          </div>
          <div>
            <p className="text-sm font-semibold text-[var(--space-text-primary)]">{vendor.category}</p>
            <p className="text-xs text-[var(--space-text-muted)]">{vendor.description}</p>
          </div>
        </div>
        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${style.badge}`}>{style.label}</span>
      </div>
      {vendor.vendorName ? (
        <div className="ml-10 space-y-1">
          <p className="text-sm font-medium text-[var(--space-text-primary)]">{vendor.vendorName}</p>
          {vendor.contact && <p className="text-xs text-[var(--space-text-muted)]">{vendor.contact}</p>}
          {vendor.nextMilestone && (
            <p className="text-xs text-[var(--space-text-secondary)] flex items-center gap-1 mt-1">
              <ArrowRight className="w-3 h-3" /> {vendor.nextMilestone}
            </p>
          )}
        </div>
      ) : (
        <p className="ml-10 text-xs text-amber-300 flex items-center gap-1">
          <AlertTriangle className="w-3 h-3" /> {vendor.nextMilestone || 'Vendor not yet assigned'}
        </p>
      )}
    </div>
  );
}

function ApprovalRow({ entry }: { entry: ApprovalEntry }) {
  const style = APPROVAL_STATUS[entry.status] || APPROVAL_STATUS.pending;

  return (
    <div className="flex items-start gap-3 py-3 border-b border-[var(--space-border-default)] last:border-0">
      <div className="w-8 h-8 rounded-lg bg-[var(--space-surface-muted)] flex items-center justify-center flex-shrink-0">
        <FileCheck className="w-4 h-4 text-[var(--space-text-muted)]" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2 mb-0.5">
          <p className="text-sm font-medium text-[var(--space-text-primary)] leading-snug">{entry.item}</p>
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold flex-shrink-0 ${style.badge}`}>{style.label}</span>
        </div>
        <p className="text-xs text-[var(--space-text-muted)]">
          {entry.approver} · {entry.role} · {formatDate(entry.date)}
        </p>
        {entry.notes && (
          <p className="text-xs text-[var(--space-text-secondary)] mt-1 leading-relaxed">{entry.notes}</p>
        )}
      </div>
    </div>
  );
}

function CaseDetailPanel({ detail, onBack }: { detail: CaseDetail; onBack?: () => void }) {
  const { case: c } = detail;
  const statusStyle = CASE_STATUS[c.status];
  const daysToMove = daysUntil(c.moveDate);
  const daysToDeadline = daysUntil(c.deadlineDate);
  const atRiskCompliance = detail.compliance.filter((x) => x.status === 'at_risk' || x.status === 'blocked').length;

  return (
    <div className="flex flex-col h-full">
      {/* Detail header */}
      <div className="px-5 py-4 border-b border-[var(--space-border-default)] bg-gradient-to-br from-[var(--space-brand-primary-50)] via-[var(--space-surface-card)] to-[var(--space-brand-highlight-50)]">
        {onBack && (
          <button onClick={onBack} className="flex items-center gap-1 text-xs text-[var(--space-text-brand)] font-medium mb-3 sm:hidden">
            <ChevronLeft className="w-4 h-4" /> Back to cases
          </button>
        )}
        <div className="flex flex-col sm:flex-row sm:items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-[var(--space-brand-primary)] flex items-center justify-center flex-shrink-0 shadow-md">
            <span className="text-base font-bold text-[var(--space-text-on-primary)]">
              {c.employeeName.split(' ').map((n) => n[0]).join('').slice(0, 2)}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <h2 className="text-lg font-bold text-[var(--space-text-primary)]">{c.employeeName}</h2>
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${statusStyle.badge}`}>{c.status}</span>
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${tw.badge.primary}`}>{c.policyTier}</span>
            </div>
            <p className="text-sm text-[var(--space-text-secondary)] mb-2">{c.role} · {c.department}</p>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-[var(--space-text-muted)]">
              <span className="flex items-center gap-1.5 font-medium text-[var(--space-text-primary)]">
                <span className="px-1.5 py-0.5 rounded border border-[var(--space-border-default)] bg-[var(--space-surface-card)] text-[10px] font-bold">{c.originCode}</span>
                {c.origin}
                <Plane className="w-3.5 h-3.5 text-[var(--space-brand-primary)]" />
                <span className="px-1.5 py-0.5 rounded border border-[var(--space-border-default)] bg-[var(--space-surface-card)] text-[10px] font-bold">{c.destinationCode}</span>
                {c.destination}
              </span>
            </div>
            <div className="flex flex-wrap gap-4 mt-2.5 text-xs">
              <span className="flex items-center gap-1 text-[var(--space-text-muted)]">
                <Calendar className="w-3.5 h-3.5" />
                Move {formatDate(c.moveDate)}
                {daysToMove !== null && daysToMove > 0 && <span className="text-[var(--space-brand-primary)] font-medium">· {daysToMove}d away</span>}
              </span>
              <span className="flex items-center gap-1 text-[var(--space-text-muted)]">
                <User className="w-3.5 h-3.5" /> Coordinator: <strong className="text-[var(--space-text-secondary)]">{c.coordinator}</strong>
              </span>
              <span className="flex items-center gap-1 text-[var(--space-text-muted)]">
                <Users className="w-3.5 h-3.5" /> {c.dependents} dependants
              </span>
              <span className="flex items-center gap-1 text-[var(--space-text-muted)]">
                <Building2 className="w-3.5 h-3.5" /> {c.policyTier} policy
              </span>
            </div>
          </div>
          {c.status !== 'Completed' && daysToDeadline !== null && (
            <div className={`flex-shrink-0 px-4 py-3 rounded-xl border text-center ${
              daysToDeadline < 0 ? 'border-red-500/30 bg-red-500/10' :
              daysToDeadline <= 7 ? 'border-amber-500/30 bg-amber-500/10' :
              'border-[var(--space-border-default)] bg-[var(--space-surface-card)]'
            }`}>
              <p className={`text-2xl font-bold ${
                daysToDeadline < 0 ? 'text-red-400' :
                daysToDeadline <= 7 ? 'text-amber-400' : 'text-[var(--space-text-primary)]'
              }`}>
                {daysToDeadline < 0 ? Math.abs(daysToDeadline) : daysToDeadline}
              </p>
              <p className="text-[10px] text-[var(--space-text-muted)] uppercase tracking-wide">
                {daysToDeadline < 0 ? 'days overdue' : 'days to deadline'}
              </p>
              <p className="text-[10px] text-[var(--space-text-muted)] mt-0.5">{formatDate(c.deadlineDate)}</p>
            </div>
          )}
        </div>
        <p className="text-sm text-[var(--space-text-secondary)] leading-relaxed mt-3">{c.summary}</p>
        {c.riskNote && (
          <div className="mt-3 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-amber-200 font-medium">{c.riskNote}</p>
          </div>
        )}
      </div>

      {/* Detail body */}
      <div className="flex-1 overflow-y-auto px-5 py-5">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Timeline — 2 cols */}
          <div className="lg:col-span-2 space-y-5">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--space-text-secondary)] mb-4 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5" /> Case timeline
              </h3>
              <div className="relative ml-3 border-l-2 border-[var(--space-border-strong)]">
                {detail.timeline.map((e) => (
                  <TimelineEventCard key={e.id} event={e} />
                ))}
              </div>
            </div>

            {/* Approvals log */}
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--space-text-secondary)] mb-3 flex items-center gap-1.5">
                <FileCheck className="w-3.5 h-3.5" /> Approvals log
              </h3>
              <div className={`rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)] px-4`}>
                {detail.approvals.map((a) => (
                  <ApprovalRow key={a.id} entry={a} />
                ))}
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-5">
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--space-text-secondary)] flex items-center gap-1.5">
                  <Shield className="w-3.5 h-3.5" /> Compliance
                </h3>
                {atRiskCompliance > 0 && (
                  <span className="text-[10px] font-semibold text-amber-300 bg-amber-500/15 px-2 py-0.5 rounded-full">
                    {atRiskCompliance} at risk
                  </span>
                )}
              </div>
              <div className="space-y-2.5">
                {detail.compliance.map((cp) => (
                  <ComplianceCard key={cp.id} item={cp} />
                ))}
              </div>
            </div>

            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--space-text-secondary)] mb-3 flex items-center gap-1.5">
                <Briefcase className="w-3.5 h-3.5" /> Vendor assignments
              </h3>
              <div className="space-y-2.5">
                {detail.vendors.length > 0 ? (
                  detail.vendors.map((v) => <VendorCard key={v.id} vendor={v} />)
                ) : (
                  <p className="text-xs text-[var(--space-text-muted)] italic p-3 rounded-xl border border-dashed border-[var(--space-border-default)]">
                    No vendors assigned yet.
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Main App ────────────────────────────────────────────────────────────────

export default function CaseCommand() {
  const [cases] = useState(DEMO_CASES);
  const [selectedId, setSelectedId] = useState(MARCUS_OBI_DETAIL.case.id);
  const [filterStatus, setFilterStatus] = useState<'all' | CaseStatus>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [mobileShowDetail, setMobileShowDetail] = useState(false);

  const metrics = useMemo(() => countByStatus(cases), [cases]);

  const filteredCases = useMemo(() => {
    let result = cases;
    if (filterStatus !== 'all') {
      result = result.filter((c) => c.status === filterStatus);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (c) =>
          c.employeeName.toLowerCase().includes(q) ||
          c.origin.toLowerCase().includes(q) ||
          c.destination.toLowerCase().includes(q) ||
          c.coordinator.toLowerCase().includes(q) ||
          c.role.toLowerCase().includes(q),
      );
    }
    return result;
  }, [cases, filterStatus, searchQuery]);

  const selectedDetail = useMemo(() => getCaseDetail(selectedId), [selectedId]);

  const handleSelectCase = (id: string) => {
    setSelectedId(id);
    setMobileShowDetail(true);
  };

  return (
    <div className="min-h-full flex flex-col w-full bg-transparent">
      {/* App header */}
      <div className="px-5 py-4 border-b border-[var(--space-border-default)] bg-[var(--space-surface-card)]">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-[var(--space-brand-primary-50)] flex items-center justify-center flex-shrink-0">
              <ClipboardCheck className={`w-5 h-5 ${tw.icon.primary}`} />
            </div>
            <div className="min-w-0">
              <h2 className="font-semibold text-base text-[var(--space-text-primary)]">Case Command</h2>
              <p className="text-xs text-[var(--space-text-secondary)] truncate">
                Global relocation case management hub
              </p>
            </div>
          </div>
          <span className="hidden sm:inline px-2.5 py-1 rounded-full text-xs font-medium bg-[var(--space-brand-highlight-100)] text-[var(--space-text-accent)]">
            Live demo
          </span>
        </div>
      </div>

      {/* Metrics strip */}
      <div className="px-5 py-3 border-b border-[var(--space-border-default)] bg-[var(--space-surface-panel)]">
        <div className="grid grid-cols-4 gap-3 max-w-2xl">
          {[
            { label: 'Active', value: metrics.active, color: 'text-[var(--space-brand-primary)]' },
            { label: 'At risk', value: metrics.atRisk, color: 'text-amber-400' },
            { label: 'Completed', value: metrics.completed, color: 'text-[var(--space-semantic-success)]' },
            { label: 'Total cases', value: metrics.total, color: 'text-[var(--space-text-primary)]' },
          ].map((m) => (
            <div key={m.label} className="text-center">
              <p className={`text-xl font-bold ${m.color}`}>{m.value}</p>
              <p className="text-[10px] sm:text-xs text-[var(--space-text-secondary)]">{m.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Master-detail layout */}
      <div className="flex-1 flex min-h-0">
        {/* Case list panel */}
        <div className={`${
          mobileShowDetail ? 'hidden lg:flex' : 'flex'
        } flex-col w-full lg:w-[42%] xl:w-[38%] border-r border-[var(--space-border-default)] bg-[var(--space-surface-card)]`}>
          {/* Search & filters */}
          <div className="px-4 py-3 border-b border-[var(--space-border-default)] space-y-2.5">
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--space-surface-muted)] border border-[var(--space-border-default)]">
              <Search className="w-3.5 h-3.5 text-[var(--space-text-muted)] flex-shrink-0" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search employee, corridor, coordinator…"
                className="flex-1 text-sm bg-transparent border-none outline-none text-[var(--space-text-primary)] placeholder:text-[var(--space-text-muted)]"
              />
            </div>
            <div className="flex items-center gap-1.5 flex-wrap">
              <Filter className="w-3.5 h-3.5 text-[var(--space-text-muted)]" />
              {(['all', 'Active', 'At Risk', 'Completed'] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilterStatus(f)}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium transition-all ${
                    filterStatus === f ? tw.button.primary : tw.button.secondary
                  }`}
                >
                  {f === 'all' ? 'All' : f}
                </button>
              ))}
            </div>
          </div>

          {/* Column headers */}
          <div className="hidden sm:grid grid-cols-[1.4fr_1.2fr_0.8fr_1fr_0.7fr] gap-3 px-4 py-2 border-b border-[var(--space-border-default)] bg-[var(--space-surface-muted)]">
            {['Employee', 'Corridor', 'Status', 'Coordinator', 'Deadline'].map((h) => (
              <p key={h} className="text-[10px] font-semibold uppercase tracking-wider text-[var(--space-text-muted)]">{h}</p>
            ))}
          </div>

          {/* Case rows */}
          <div className="flex-1 overflow-y-auto">
            {filteredCases.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center px-4">
                <Search className="w-8 h-8 text-[var(--space-text-muted)] mb-2" />
                <p className="text-sm text-[var(--space-text-secondary)]">No cases match your filters.</p>
              </div>
            ) : (
              filteredCases.map((c) => (
                <CaseRow
                  key={c.id}
                  c={c}
                  selected={selectedId === c.id}
                  onSelect={() => handleSelectCase(c.id)}
                />
              ))
            )}
          </div>

          <div className="px-4 py-2.5 border-t border-[var(--space-border-default)] bg-[var(--space-surface-muted)] flex items-center justify-between">
            <p className="text-[10px] text-[var(--space-text-muted)]">
              {filteredCases.length} of {cases.length} cases
            </p>
            <button className={`text-[10px] font-medium flex items-center gap-1 text-[var(--space-text-brand)]`}>
              <ArrowUpRight className="w-3 h-3" /> Export
            </button>
          </div>
        </div>

        {/* Detail panel */}
        <div className={`${
          mobileShowDetail ? 'flex' : 'hidden lg:flex'
        } flex-col flex-1 min-w-0 bg-[var(--space-surface-muted)]`}>
          {selectedDetail ? (
            <CaseDetailPanel
              detail={selectedDetail}
              onBack={() => setMobileShowDetail(false)}
            />
          ) : (
            <div className="flex-1 flex items-center justify-center text-center p-8">
              <p className="text-sm text-[var(--space-text-secondary)]">Select a case to view details.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
