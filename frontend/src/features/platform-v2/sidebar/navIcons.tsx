import React from 'react';
import {
  ClipboardCheck,
  Sparkles,
  UserRound,
  Activity,
  Upload,
  Files,
  Briefcase,
  MessageSquare,
  Share2,
  Globe2,
  PenSquare,
  ShieldCheck,
  TriangleAlert,
  ShieldAlert,
  Home,
  Building2,
  CheckCircle2,
  BarChart3,
  Workflow,
  BookOpen,
  Users,
  Layers,
  BrainCircuit,
  ClipboardList,
  Plane,
  Gauge,
  Radar,
  FileText,
  GitBranch,
  ListChecks,
  Palette,
  FlaskConical,
  MessagesSquare,
  Flag,
  KeyRound,
  UserCog,
  Scale,
  Fingerprint,
  ScrollText,
  Rocket,
  Megaphone,
  MessageCircleQuestion,
  Link2,
  PlaneTakeoff,
  UsersRound,
  Map,
  LifeBuoy,
  type LucideIcon,
} from 'lucide-react';

/**
 * Single source of truth for platform sidebar icons.
 *
 * `PlatformShellSidebar` (production shell) and `PlatformSidebar` (platform-v2
 * nav) read from this map. Add a new nav item: add it here once, reference its
 * id from both sidebars. Keys mirror the prototype IDs at
 * `frontend/public/design-preview/platform-shell.jsx`.
 *
 * `satisfies` (rather than a `Record<string, LucideIcon>` annotation) keeps the
 * keys literal, so `NavIconId` below is a real union and a nav item whose id has
 * no icon here fails `tsc` instead of silently rendering nothing — which is how
 * the Outreach and Immigration Q&A items shipped icon-less.
 */
export const NAV_ICONS = {
  // Employee
  intake: Sparkles,
  'detailed-intake': UserRound,
  roadmap: Activity,
  documents: Upload,
  dossier: Files,
  'service-providers': Briefcase,
  'benefit-comparison': BarChart3,
  'immigration-qa': MessageCircleQuestion,
  inbox: MessageSquare,

  // AI Engine
  'requirements-discovery': Share2,

  // HR Operations
  'company-profile': Briefcase,
  'mobility-control': Globe2,
  // [AIQ-2086] PlaneTakeoff/UsersRound, not the Plane/Users already used by
  // admin-assignments and prospects — an HR nav item that looks identical to an
  // admin one reads as the same destination.
  relocations: PlaneTakeoff,
  employees: UsersRound,
  risk: ShieldAlert,
  'duty-of-care': LifeBuoy,
  'policy-builder': PenSquare,
  'policy-benefits': ShieldCheck,
  'policy-reality': Activity,
  'provider-status': Activity,
  exceptions: TriangleAlert,
  // AIQ-1116: AI decisions audit — a brain-circuit icon conveys "AI/automation",
  // distinct from intake's Sparkles, so the nav item is no longer icon-less.
  'ai-decisions': BrainCircuit,
  requirements: ClipboardList,
  'hr-resources-preview': BookOpen,
  'resources-guide': BookOpen,

  // Admin · ReloPass
  'admin-overview': Home,
  'admin-assignments': Plane,
  'test-drive': Rocket,
  executive: Gauge,
  'mission-control': Radar,
  'admin-companies': Building2,
  'review-queue': CheckCircle2,
  'ops-analytics': BarChart3,
  'workflow-analytics': Workflow,
  'resources-cms': BookOpen,
  'form-templates': FileText,
  'admin-policies': GitBranch,
  'policy-versions': GitBranch,
  'admin-people': UserRound,
  'admin-suppliers': Link2,
  'country-requirements': Globe2,
  coverage: Map,
  'requirement-facts': ListChecks,
  'auth-page-design': Palette,
  'research-requests': FlaskConical,
  'feedback-console': MessagesSquare,
  'feature-flags': Flag,
  permissions: KeyRound,
  'admin-accounts': UserCog,
  'ai-governance': Scale,
  'data-rights': Fingerprint,
  'audit-log': ScrollText,
  prospects: Users,
  outreach: Megaphone,
  integrations: Layers,
  'vetting-queue': ShieldCheck,
  'content-review': ClipboardCheck,
  'supplier-submissions': ShieldCheck,
} satisfies Record<string, LucideIcon>;

export type NavIconId = keyof typeof NAV_ICONS;

interface NavIconProps {
  id: NavIconId;
  size?: number;
  className?: string;
  strokeWidth?: number;
}

/** Render the icon for a nav item by id. Renders nothing if the id is unknown. */
export const NavIcon: React.FC<NavIconProps> = ({ id, size = 16, className, strokeWidth = 1.75 }) => {
  const Icon = NAV_ICONS[id];
  if (!Icon) return null;
  return <Icon size={size} strokeWidth={strokeWidth} className={className} aria-hidden="true" />;
};
