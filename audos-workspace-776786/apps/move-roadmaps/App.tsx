import { useState, useMemo } from 'react';
import {
  Route, Plane, Search, Filter, ChevronRight, ChevronLeft,
  Calendar, Shield, Briefcase, User, Building2, Users, AlertTriangle,
  CheckCircle2, Clock, Circle, XCircle, ArrowUpRight, FileText,
  Globe, Package, Scale, Home, GraduationCap, ArrowRight,
  ClipboardList, Luggage,
} from 'lucide-react';
import { tw } from '../../lib/colors';
import {
  DEMO_ROADMAPS,
  SARAH_CHEN_ROADMAP,
  PHASE_ORDER,
  PHASE_META,
  phaseProgress,
  overallProgress,
  countByStatus,
  countRoadmapsByStatus,
  complianceForPhase,
  vendorsForPhase,
  getRoadmapDetail,
  daysUntil,
  formatDate,
  type MoveRoadmap,
  type RoadmapSummary,
  type RoadmapStatus,
  type PhaseId,
  type MilestoneStatus,
  type Milestone,
  type ComplianceCheckpoint,
  type VendorSlot,
} from './sample-data';

// ─── Status styles ───────────────────────────────────────────────────────────

const ROADMAP_STATUS: Record<RoadmapStatus, { badge: string; dot: string }> = {
  'On track': { badge: 'bg-[var(--space-brand-primary-50)] text-[var(--space-text-brand)] border-[var(--space-border-strong)]', dot: 'bg-[var(--space-brand-primary)]' },
  'At risk': { badge: 'bg-amber-500/15 text-amber-300 border-amber-500/30', dot: 'bg-amber-400' },
  Completed: { badge: 'bg-green-500/15 text-green-300 border-green-500/30', dot: 'bg-[var(--space-semantic-success)]' },
};

const MILESTONE_STATUS: Record<MilestoneStatus, { label: string; badge: string; icon: typeof CheckCircle2 }> = {
  completed: { label: 'Done', badge: 'bg-green-500/15 text-green-300 border-green-500/30', icon: CheckCircle2 },
  in_progress: { label: 'In progress', badge: 'bg-[var(--space-brand-primary-50)] text-[var(--space-text-brand)] border-[var(--space-border-strong)]', icon: Clock },
  pending: { label: 'Pending', badge: 'bg-[var(--space-surface-muted)] text-[var(--space-text-secondary)] border-[var(--space-border-default)]', icon: Circle },
  blocked: { label: 'Blocked', badge: 'bg-red-500/15 text-red-300 border-red-500/30', icon: XCircle },
};

const CHECKPOINT_STATUS: Record<string, { label: string; badge: string }> = {
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

const CATEGORY_ICON: Record<string, typeof Globe> = {
  immigration: Globe,
  tax: Scale,
  logistics: Package,
  compliance: Shield,
  housing: Home,
  vendor: Briefcase,
};

const PHASE_ICON: Record<PhaseId, typeof ClipboardList> = {
  'pre-move': ClipboardList,
  'in-transit': Luggage,
  'post-arrival': Home,
};

// ─── Sub-components ──────────────────────────────────────────────────────────

function DaysToMove({ date, status }: { date: string; status: RoadmapStatus }) {
  const days = daysUntil(date);
  if (status === 'Completed') {
    return <span className="text-xs text-[var(--space-semantic-success)] font-medium">Closed</span>;
  }
  if (days === null) return <span className="text-xs text-[var(--space-text-muted)]">—</span>;
  if (days < 0) {
    return (
      <span className="text-xs font-semibold text-[var(--space-brand-primary)] flex items-center gap-1">
        In transit
      </span>
    );
  }
  if (days <= 14) {
    return <span className="text-xs font-semibold text-amber-400">{days}d to move</span>;
  }
  return <span className="text-xs font-medium text-[var(--space-text-secondary)]">{days}d to move</span>;
}

function RoadmapRow({
  r,
  selected,
  onSelect,
}: {
  r: RoadmapSummary;
  selected: boolean;
  onSelect: () => void;
}) {
  const style = ROADMAP_STATUS[r.status];
  const phaseLabel = PHASE_META[r.currentPhase].shortLabel;

  return (
    <button
      onClick={onSelect}
      className={`w-full text-left px-4 py-3.5 border-b border-[var(--space-border-default)] transition-all hover:bg-[var(--space-surface-card-hover)] ${
        selected ? 'bg-[var(--space-brand-primary-50)] border-l-[3px] border-l-[var(--space-brand-primary)]' : 'border-l-[3px] border-l-transparent'
      }`}
    >
      <div className="flex items-center gap-3">
        <div className={`w-2 h-2 rounded-full flex-shrink-0 ${style.dot}`} />
        <div className="flex-1 min-w-0 grid grid-cols-1 sm:grid-cols-[1.4fr_1.2fr_0.7fr_0.8fr_0.6fr] gap-1 sm:gap-3 items-center">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-[var(--space-text-primary)] truncate">{r.employeeName}</p>
            <p className="text-xs text-[var(--space-text-muted)] truncate hidden sm:block">{r.role}</p>
          </div>
          <p className="text-xs text-[var(--space-text-secondary)] flex items-center gap-1 min-w-0">
            <span className="font-medium">{r.originCode}</span>
            <Plane className="w-3 h-3 flex-shrink-0 text-[var(--space-brand-primary)]" />
            <span className="font-medium">{r.destinationCode}</span>
            <span className="text-[var(--space-text-muted)] hidden md:inline truncate">{r.origin} → {r.destination}</span>
          </p>
          <span className={`inline-flex w-fit px-2 py-0.5 rounded-full text-[10px] font-semibold border ${style.badge}`}>
            {r.status}
          </span>
          <p className="text-xs text-[var(--space-text-secondary)] truncate hidden sm:block">{phaseLabel}</p>
          <div className="hidden sm:block">
            <DaysToMove date={r.moveDate} status={r.status} />
            <p className="text-[10px] text-[var(--space-text-muted)]">{r.progress}% done</p>
          </div>
        </div>
        <ChevronRight className={`w-4 h-4 flex-shrink-0 ${selected ? 'text-[var(--space-brand-primary)]' : 'text-[var(--space-text-muted)]'}`} />
      </div>
      {r.riskNote && r.status === 'At risk' && (
        <p className="text-[10px] text-amber-300 mt-1.5 ml-5 flex items-center gap-1">
          <AlertTriangle className="w-3 h-3 flex-shrink-0" /> {r.riskNote}
        </p>
      )}
    </button>
  );
}

function PhaseStepper({
  roadmap,
  activePhase,
  onSelect,
}: {
  roadmap: MoveRoadmap;
  activePhase: PhaseId;
  onSelect: (id: PhaseId) => void;
}) {
  const currentIdx = PHASE_ORDER.indexOf(roadmap.currentPhase);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-3">
      {PHASE_ORDER.map((phaseId, idx) => {
        const phase = roadmap.phases.find((p) => p.id === phaseId)!;
        const meta = PHASE_META[phaseId];
        const PhaseIcon = PHASE_ICON[phaseId];
        const progress = phaseProgress(phase);
        const isActive = activePhase === phaseId;
        const isCurrent = roadmap.currentPhase === phaseId;
        const isPast = idx < currentIdx;
        const complianceCount = complianceForPhase(roadmap, phaseId).length;
        const vendorCount = vendorsForPhase(roadmap, phaseId).length;

        return (
          <button
            key={phaseId}
            onClick={() => onSelect(phaseId)}
            className={`text-left px-3 sm:px-4 py-3 rounded-xl border transition-all ${
              isActive
                ? 'border-[var(--space-brand-primary)] bg-[var(--space-brand-primary-50)] ring-1 ring-[var(--space-brand-primary)] shadow-sm'
                : 'border-[var(--space-border-default)] bg-[var(--space-surface-card)] hover:border-[var(--space-border-strong)]'
            }`}
          >
            <div className="flex items-center gap-2 mb-2">
              <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${
                isActive ? 'bg-[var(--space-brand-primary)]' : 'bg-[var(--space-surface-muted)]'
              }`}>
                <PhaseIcon className={`w-3.5 h-3.5 ${isActive ? 'text-[var(--space-text-on-primary)]' : 'text-[var(--space-text-brand)]'}`} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className={`text-xs sm:text-sm font-semibold truncate ${isActive ? 'text-[var(--space-text-brand)]' : 'text-[var(--space-text-primary)]'}`}>
                    {meta.label}
                  </span>
                  {isCurrent && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-[var(--space-brand-highlight)] text-[var(--space-text-on-highlight)]">
                      Current
                    </span>
                  )}
                  {isPast && progress === 100 && (
                    <CheckCircle2 className="w-3.5 h-3.5 text-[var(--space-semantic-success)] flex-shrink-0" />
                  )}
                </div>
              </div>
            </div>
            <div className="h-1.5 rounded-full bg-[var(--space-surface-muted)] overflow-hidden mb-1.5">
              <div
                className={`h-full rounded-full transition-all ${isPast && progress === 100 ? 'bg-[var(--space-semantic-success)]' : 'bg-[var(--space-brand-primary)]'}`}
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-[10px] text-[var(--space-text-muted)]">
              {progress}% · {phase.milestones.length} milestones · {complianceCount} compliance · {vendorCount} vendors
            </p>
          </button>
        );
      })}
    </div>
  );
}

function MilestoneCard({ milestone }: { milestone: Milestone }) {
  const style = MILESTONE_STATUS[milestone.status];
  const StatusIcon = style.icon;
  const CatIcon = CATEGORY_ICON[milestone.category] || FileText;
  const days = daysUntil(milestone.dueDate);
  const urgent = days !== null && days <= 7 && days >= 0 && milestone.status !== 'completed';
  const overdue = days !== null && days < 0 && milestone.status !== 'completed';

  return (
    <div className={`p-3.5 rounded-xl border ${
      milestone.status === 'in_progress' ? 'border-amber-500/30 bg-amber-500/10' :
      milestone.status === 'blocked' ? 'border-red-500/30 bg-red-500/10' :
      milestone.status === 'completed' ? 'border-[var(--space-border-default)] bg-[var(--space-surface-card)]' :
      overdue ? 'border-red-500/30' : urgent ? 'border-amber-500/30' : 'border-[var(--space-border-default)] bg-[var(--space-surface-card)]'
    }`}>
      <div className="flex items-start gap-3">
        <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 ${
          milestone.status === 'completed' ? 'bg-green-500/15' : 'bg-[var(--space-surface-muted)]'
        }`}>
          <StatusIcon className={`w-3.5 h-3.5 ${
            milestone.status === 'completed' ? 'text-green-400' :
            milestone.status === 'in_progress' ? 'text-amber-400' :
            milestone.status === 'blocked' ? 'text-red-400' : 'text-[var(--space-text-muted)]'
          }`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-1">
            <h4 className={`text-sm font-semibold leading-snug ${
              milestone.status === 'completed' ? 'text-[var(--space-text-muted)]' : 'text-[var(--space-text-primary)]'
            }`}>
              {milestone.title}
            </h4>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium border flex-shrink-0 ${style.badge}`}>
              {style.label}
            </span>
          </div>
          <p className="text-xs text-[var(--space-text-secondary)] leading-relaxed mb-2">{milestone.description}</p>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-[var(--space-text-muted)]">
            <span className="flex items-center gap-1">
              <Calendar className="w-3 h-3" />
              <span className={overdue ? 'text-red-400 font-medium' : urgent ? 'text-amber-400 font-medium' : ''}>
                {formatDate(milestone.dueDate)}
                {overdue && ` · ${Math.abs(days!)}d overdue`}
                {urgent && !overdue && ` · ${days}d left`}
              </span>
            </span>
            <span className="flex items-center gap-1"><User className="w-3 h-3" /> {milestone.owner}</span>
            <span className={`flex items-center gap-1 px-1.5 py-0.5 rounded ${tw.badge.neutral}`}>
              <CatIcon className="w-3 h-3" /> {milestone.category}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function ComplianceCard({ checkpoint }: { checkpoint: ComplianceCheckpoint }) {
  const style = CHECKPOINT_STATUS[checkpoint.status] || CHECKPOINT_STATUS.pending;

  return (
    <div className={`p-3 rounded-xl border ${
      checkpoint.status === 'at_risk' ? 'border-amber-500/30 bg-amber-500/10' :
      checkpoint.status === 'passed' ? 'border-green-500/30 bg-green-500/10' :
      'border-[var(--space-border-default)] bg-[var(--space-surface-card)]'
    }`}>
      <div className="flex items-start justify-between gap-2 mb-1">
        <div className="flex items-center gap-2 min-w-0">
          <Shield className={`w-4 h-4 flex-shrink-0 ${
            checkpoint.status === 'passed' ? 'text-green-400' :
            checkpoint.status === 'at_risk' ? 'text-amber-400' : 'text-[var(--space-text-muted)]'
          }`} />
          <h5 className="text-sm font-medium text-[var(--space-text-primary)] leading-snug">{checkpoint.title}</h5>
        </div>
        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold flex-shrink-0 ${style.badge}`}>
          {style.label}
        </span>
      </div>
      <p className="text-xs text-[var(--space-text-secondary)] leading-relaxed ml-6 mb-1.5">{checkpoint.description}</p>
      <div className="flex flex-wrap gap-3 ml-6 text-[10px] text-[var(--space-text-muted)]">
        {checkpoint.regulation && <span className="flex items-center gap-1"><Scale className="w-3 h-3" /> {checkpoint.regulation}</span>}
        {checkpoint.dueDate && <span className="flex items-center gap-1"><Calendar className="w-3 h-3" /> Due {formatDate(checkpoint.dueDate)}</span>}
        {checkpoint.linkedMilestone && <span className="flex items-center gap-1"><ArrowRight className="w-3 h-3" /> {checkpoint.linkedMilestone}</span>}
      </div>
    </div>
  );
}

function VendorCard({ vendor }: { vendor: VendorSlot }) {
  const style = VENDOR_STATUS[vendor.vendorStatus] || VENDOR_STATUS.pending;
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

function RoadmapDetailPanel({
  roadmap,
  activePhase,
  onPhaseChange,
  onBack,
}: {
  roadmap: MoveRoadmap;
  activePhase: PhaseId;
  onPhaseChange: (id: PhaseId) => void;
  onBack?: () => void;
}) {
  const { employee: emp } = roadmap;
  const statusStyle = ROADMAP_STATUS[roadmap.status];
  const daysToMove = daysUntil(emp.moveDate);
  const progress = overallProgress(roadmap);
  const counts = countByStatus(roadmap);
  const activePhaseData = roadmap.phases.find((p) => p.id === activePhase)!;
  const phaseCompliance = complianceForPhase(roadmap, activePhase);
  const phaseVendors = vendorsForPhase(roadmap, activePhase);
  const atRiskCompliance = phaseCompliance.filter((c) => c.status === 'at_risk' || c.status === 'blocked').length;

  return (
    <div className="flex flex-col h-full">
      {/* Detail header */}
      <div className="px-5 py-4 border-b border-[var(--space-border-default)] bg-gradient-to-br from-[var(--space-brand-primary-50)] via-[var(--space-surface-card)] to-[var(--space-brand-highlight-50)]">
        {onBack && (
          <button onClick={onBack} className="flex items-center gap-1 text-xs text-[var(--space-text-brand)] font-medium mb-3 sm:hidden">
            <ChevronLeft className="w-4 h-4" /> Back to roadmaps
          </button>
        )}
        <div className="flex flex-col sm:flex-row sm:items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-[var(--space-brand-primary)] flex items-center justify-center flex-shrink-0 shadow-md">
            <span className="text-base font-bold text-[var(--space-text-on-primary)]">
              {emp.name.split(' ').map((n) => n[0]).join('').slice(0, 2)}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <h2 className="text-lg font-bold text-[var(--space-text-primary)]">{emp.name}</h2>
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${statusStyle.badge}`}>{roadmap.status}</span>
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${tw.badge.primary}`}>{emp.policyTier}</span>
            </div>
            <p className="text-sm text-[var(--space-text-secondary)] mb-2">{emp.role} · {emp.department}</p>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-[var(--space-text-muted)]">
              <span className="flex items-center gap-1.5 font-medium text-[var(--space-text-primary)]">
                <span className="px-1.5 py-0.5 rounded border border-[var(--space-border-default)] bg-[var(--space-surface-card)] text-[10px] font-bold">{emp.originCode}</span>
                {emp.origin}
                <Plane className="w-3.5 h-3.5 text-[var(--space-brand-primary)]" />
                <span className="px-1.5 py-0.5 rounded border border-[var(--space-border-default)] bg-[var(--space-surface-card)] text-[10px] font-bold">{emp.destinationCode}</span>
                {emp.destination}
              </span>
            </div>
            <div className="flex flex-wrap gap-4 mt-2.5 text-xs">
              <span className="flex items-center gap-1 text-[var(--space-text-muted)]">
                <Calendar className="w-3.5 h-3.5" />
                Move {formatDate(emp.moveDate)}
                {daysToMove !== null && daysToMove > 0 && <span className="text-[var(--space-brand-primary)] font-medium">· {daysToMove}d away</span>}
              </span>
              <span className="flex items-center gap-1 text-[var(--space-text-muted)]">
                <User className="w-3.5 h-3.5" /> Coordinator: <strong className="text-[var(--space-text-secondary)]">{emp.coordinator}</strong>
              </span>
              <span className="flex items-center gap-1 text-[var(--space-text-muted)]">
                <Users className="w-3.5 h-3.5" /> {emp.dependents} dependants
              </span>
              <span className="flex items-center gap-1 text-[var(--space-text-muted)]">
                <Building2 className="w-3.5 h-3.5" /> {emp.policyTier} policy
              </span>
            </div>
          </div>
          <div className="flex-shrink-0 px-4 py-3 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)] text-center">
            <p className="text-2xl font-bold text-[var(--space-text-primary)]">{progress}%</p>
            <p className="text-[10px] text-[var(--space-text-muted)] uppercase tracking-wide">journey complete</p>
            <p className="text-[10px] text-[var(--space-text-muted)] mt-0.5">{counts.completed}/{counts.total} milestones</p>
          </div>
        </div>
        <p className="text-sm text-[var(--space-text-secondary)] leading-relaxed mt-3">{roadmap.summary}</p>
        {roadmap.riskFlags.length > 0 && (
          <div className="mt-3 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/30">
            {roadmap.riskFlags.map((flag, i) => (
              <p key={i} className="text-xs text-amber-200 font-medium flex items-start gap-2">
                <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" /> {flag}
              </p>
            ))}
          </div>
        )}
      </div>

      {/* Phase stepper */}
      <div className="px-5 py-4 border-b border-[var(--space-border-default)] bg-[var(--space-surface-card)]">
        <p className="text-xs font-semibold uppercase tracking-wider text-[var(--space-text-secondary)] mb-3">
          Relocation phases
        </p>
        <PhaseStepper roadmap={roadmap} activePhase={activePhase} onSelect={onPhaseChange} />
      </div>

      {/* Detail body */}
      <div className="flex-1 overflow-y-auto px-5 py-5">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Milestones — 2 cols */}
          <div className="lg:col-span-2 space-y-5">
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--space-text-secondary)] flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5" /> {activePhaseData.name} milestones
                </h3>
                <span className="text-xs text-[var(--space-text-muted)]">{phaseProgress(activePhaseData)}% complete</span>
              </div>
              <p className="text-xs text-[var(--space-text-muted)] mb-3 -mt-2">{activePhaseData.description}</p>
              <div className="space-y-2.5">
                {activePhaseData.milestones.map((m) => (
                  <MilestoneCard key={m.id} milestone={m} />
                ))}
              </div>
            </div>

            {/* Key dates */}
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--space-text-secondary)] mb-3 flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5" /> Key dates
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {roadmap.keyDates.map((kd, i) => (
                  <div key={i} className={`px-3 py-2.5 rounded-xl ${tw.card.flat}`}>
                    <p className="text-xs font-medium text-[var(--space-text-primary)]">{kd.label}</p>
                    <p className="text-xs text-[var(--space-text-muted)] mt-0.5">{formatDate(kd.date)}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Sidebar — phase-linked compliance + vendors */}
          <div className="space-y-5">
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--space-text-secondary)] flex items-center gap-1.5">
                  <Shield className="w-3.5 h-3.5" /> {PHASE_META[activePhase].label} compliance
                </h3>
                {atRiskCompliance > 0 && (
                  <span className="text-[10px] font-semibold text-amber-300 bg-amber-500/15 px-2 py-0.5 rounded-full">
                    {atRiskCompliance} at risk
                  </span>
                )}
              </div>
              <div className="space-y-2.5">
                {phaseCompliance.length > 0 ? (
                  phaseCompliance.map((cc) => <ComplianceCard key={cc.id} checkpoint={cc} />)
                ) : (
                  <p className="text-xs text-[var(--space-text-muted)] italic p-3 rounded-xl border border-dashed border-[var(--space-border-default)]">
                    No compliance checkpoints for this phase.
                  </p>
                )}
              </div>
            </div>

            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--space-text-secondary)] mb-3 flex items-center gap-1.5">
                <Briefcase className="w-3.5 h-3.5" /> {PHASE_META[activePhase].label} vendors
              </h3>
              <div className="space-y-2.5">
                {phaseVendors.length > 0 ? (
                  phaseVendors.map((v) => <VendorCard key={v.id} vendor={v} />)
                ) : (
                  <p className="text-xs text-[var(--space-text-muted)] italic p-3 rounded-xl border border-dashed border-[var(--space-border-default)]">
                    No vendor slots for this phase.
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

export default function MoveRoadmaps() {
  const [roadmaps] = useState(DEMO_ROADMAPS);
  const [selectedId, setSelectedId] = useState(SARAH_CHEN_ROADMAP.id);
  const [filterStatus, setFilterStatus] = useState<'all' | RoadmapStatus>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [mobileShowDetail, setMobileShowDetail] = useState(false);
  const [activePhase, setActivePhase] = useState<PhaseId>('pre-move');

  const metrics = useMemo(() => countRoadmapsByStatus(roadmaps), [roadmaps]);

  const filteredRoadmaps = useMemo(() => {
    let result = roadmaps;
    if (filterStatus !== 'all') {
      result = result.filter((r) => r.status === filterStatus);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (r) =>
          r.employeeName.toLowerCase().includes(q) ||
          r.origin.toLowerCase().includes(q) ||
          r.destination.toLowerCase().includes(q) ||
          r.coordinator.toLowerCase().includes(q) ||
          r.role.toLowerCase().includes(q),
      );
    }
    return result;
  }, [roadmaps, filterStatus, searchQuery]);

  const selectedRoadmap = useMemo(() => getRoadmapDetail(selectedId), [selectedId]);

  const handleSelectRoadmap = (id: string) => {
    setSelectedId(id);
    setMobileShowDetail(true);
    const detail = getRoadmapDetail(id);
    if (detail) setActivePhase(detail.currentPhase);
  };

  return (
    <div className="min-h-full flex flex-col w-full bg-transparent">
      {/* App header */}
      <div className="px-5 py-4 border-b border-[var(--space-border-default)] bg-[var(--space-surface-card)]">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-[var(--space-brand-primary-50)] flex items-center justify-center flex-shrink-0">
              <Route className={`w-5 h-5 ${tw.icon.primary}`} />
            </div>
            <div className="min-w-0">
              <h2 className="font-semibold text-base text-[var(--space-text-primary)]">Move Roadmaps</h2>
              <p className="text-xs text-[var(--space-text-secondary)] truncate">
                End-to-end relocation journey planning for mobility coordinators
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
            { label: 'On track', value: metrics.onTrack, color: 'text-[var(--space-brand-primary)]' },
            { label: 'At risk', value: metrics.atRisk, color: 'text-amber-400' },
            { label: 'Completed', value: metrics.completed, color: 'text-[var(--space-semantic-success)]' },
            { label: 'Total roadmaps', value: metrics.total, color: 'text-[var(--space-text-primary)]' },
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
        {/* Roadmap list panel */}
        <div className={`${
          mobileShowDetail ? 'hidden lg:flex' : 'flex'
        } flex-col w-full lg:w-[42%] xl:w-[38%] border-r border-[var(--space-border-default)] bg-[var(--space-surface-card)]`}>
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
              {(['all', 'On track', 'At risk', 'Completed'] as const).map((f) => (
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

          <div className="hidden sm:grid grid-cols-[1.4fr_1.2fr_0.7fr_0.8fr_0.6fr] gap-3 px-4 py-2 border-b border-[var(--space-border-default)] bg-[var(--space-surface-muted)]">
            {['Employee', 'Corridor', 'Status', 'Phase', 'Progress'].map((h) => (
              <p key={h} className="text-[10px] font-semibold uppercase tracking-wider text-[var(--space-text-muted)]">{h}</p>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto">
            {filteredRoadmaps.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center px-4">
                <Search className="w-8 h-8 text-[var(--space-text-muted)] mb-2" />
                <p className="text-sm text-[var(--space-text-secondary)]">No roadmaps match your filters.</p>
              </div>
            ) : (
              filteredRoadmaps.map((r) => (
                <RoadmapRow
                  key={r.id}
                  r={r}
                  selected={selectedId === r.id}
                  onSelect={() => handleSelectRoadmap(r.id)}
                />
              ))
            )}
          </div>

          <div className="px-4 py-2.5 border-t border-[var(--space-border-default)] bg-[var(--space-surface-muted)] flex items-center justify-between">
            <p className="text-[10px] text-[var(--space-text-muted)]">
              {filteredRoadmaps.length} of {roadmaps.length} roadmaps
            </p>
            <button className="text-[10px] font-medium flex items-center gap-1 text-[var(--space-text-brand)]">
              <ArrowUpRight className="w-3 h-3" /> Export
            </button>
          </div>
        </div>

        {/* Detail panel */}
        <div className={`${
          mobileShowDetail ? 'flex' : 'hidden lg:flex'
        } flex-col flex-1 min-w-0 bg-[var(--space-surface-muted)]`}>
          {selectedRoadmap ? (
            <RoadmapDetailPanel
              roadmap={selectedRoadmap}
              activePhase={activePhase}
              onPhaseChange={setActivePhase}
              onBack={() => setMobileShowDetail(false)}
            />
          ) : (
            <div className="flex-1 flex items-center justify-center text-center p-8">
              <p className="text-sm text-[var(--space-text-secondary)]">Select a roadmap to view the relocation journey.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
