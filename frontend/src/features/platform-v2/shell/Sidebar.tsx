/**
 * Sidebar.tsx — ReloPass Platform App Shell Sidebar
 * ─────────────────────────────────────────────────────────────────────────────
 * - 4 nav sections, 24 NavItems from design-tokens nav_items
 * - Drag-to-reorder sections via HTML5 drag API
 * - Collapse toggle: 232px ↔ 58px (icon-only mode)
 * - Role/plan_tier gating (items hidden below min_tier)
 * - Active route highlight
 * - Badge support (count, dot, status)
 * - State persisted in localStorage['rp-sidebar']
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { PlanTier } from '../../../types/relopass-api-contracts';

// ─── Nav data (from design-tokens.json nav_items) ─────────────────────────────

export interface NavItemDef {
  id: string;
  label: string;
  icon: string;
  route: string;
  min_tier: PlanTier;
  badge_key?: string;
}

export interface NavSectionDef {
  key: string;
  label: string;
  min_tier: PlanTier;
  items: NavItemDef[];
}

const NAV_SECTIONS: NavSectionDef[] = [
  {
    key: 'my_case',
    label: 'My Relocation',
    min_tier: 'basic',
    items: [
      { id: 'profile',   label: 'My Profile',   icon: 'UserCircle',     route: '/profile',    min_tier: 'basic' },
      { id: 'roadmap',   label: 'Roadmap',       icon: 'Map',            route: '/roadmap',    min_tier: 'basic' },
      { id: 'discovery', label: 'Requirements',  icon: 'Search',         route: '/discovery',  min_tier: 'basic' },
      { id: 'dossier',   label: 'My Dossier',    icon: 'FileText',       route: '/dossier',    min_tier: 'basic' },
      { id: 'documents', label: 'Documents',     icon: 'Folder',         route: '/documents',  min_tier: 'basic' },
      { id: 'policy',    label: 'My Policy',     icon: 'Shield',         route: '/policy',     min_tier: 'basic' },
      { id: 'vendors',   label: 'Service Hub',   icon: 'Store',          route: '/marketplace',min_tier: 'basic' },
      { id: 'inbox',     label: 'Inbox',         icon: 'Inbox',          route: '/inbox',      min_tier: 'basic', badge_key: 'unread_messages' },
    ],
  },
  {
    key: 'team',
    label: 'HR Control',
    min_tier: 'hr',
    items: [
      { id: 'hr_dashboard', label: 'Control Panel',  icon: 'LayoutDashboard', route: '/hr',             min_tier: 'hr' },
      { id: 'hr_profile',   label: 'HR Profile',     icon: 'Settings',        route: '/hr/profile',     min_tier: 'hr' },
      { id: 'policy_mgmt',  label: 'Policy Builder', icon: 'Edit3',           route: '/policy/builder', min_tier: 'hr' },
    ],
  },
  {
    key: 'admin',
    label: 'Platform Admin',
    min_tier: 'admin',
    items: [
      { id: 'admin_dash',  label: 'Admin Dashboard', icon: 'BarChart2',   route: '/admin',             min_tier: 'admin' },
      { id: 'admin_co',    label: 'Companies',       icon: 'Building',    route: '/admin/companies',   min_tier: 'admin' },
      { id: 'admin_users', label: 'Users',           icon: 'Users',       route: '/admin/users',       min_tier: 'admin' },
      { id: 'admin_exc',   label: 'Exceptions',      icon: 'AlertCircle', route: '/admin/exceptions',  min_tier: 'admin', badge_key: 'pending_exceptions' },
    ],
  },
];

const TIER_ORDER: Record<PlanTier, number> = { basic: 0, hr: 1, admin: 2 };

function tierAllows(userTier: PlanTier, minTier: PlanTier): boolean {
  return TIER_ORDER[userTier] >= TIER_ORDER[minTier];
}

// ─── Persistence ──────────────────────────────────────────────────────────────

interface SidebarPersistedState {
  is_collapsed: boolean;
  section_order: string[]; // section keys in display order
}

function loadState(): SidebarPersistedState {
  try {
    const raw = localStorage.getItem('rp-sidebar');
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return { is_collapsed: false, section_order: NAV_SECTIONS.map(s => s.key) };
}

function saveState(state: SidebarPersistedState): void {
  try {
    localStorage.setItem('rp-sidebar', JSON.stringify(state));
  } catch { /* ignore */ }
}

// ─── Icon stub (lucide-react symbols rendered as text for portability) ─────────
// In production: import { Map, Search, ... } from 'lucide-react'
// Here we use a minimal inline icon proxy so the shell works without the import.

const ICON_MAP: Record<string, string> = {
  UserCircle: '○', Map: '⊞', Search: '⌕', FileText: '≡', Folder: '⊡',
  Shield: '⊕', Store: '⊠', Inbox: '⊟', LayoutDashboard: '⊞', Settings: '⚙',
  Edit3: '✏', BarChart2: '▦', Building: '⊟', Users: '⊕', AlertCircle: '⊗',
  Sparkles: '✦', ChevronRight: '›', ChevronLeft: '‹', X: '×', PanelLeft: '◫',
};

function Icon({ name, size = 16 }: { name: string; size?: number }) {
  return (
    <span
      aria-hidden="true"
      style={{ fontSize: size, lineHeight: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: size, height: size }}
    >
      {ICON_MAP[name] ?? '•'}
    </span>
  );
}

// ─── Badge ─────────────────────────────────────────────────────────────────────

function NavBadge({ value }: { value: number }) {
  if (!value) return null;
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      minWidth: 18,
      height: 18,
      padding: '0 5px',
      borderRadius: 'var(--radius-full)',
      background: value > 0 ? 'var(--danger)' : 'var(--border)',
      color: 'var(--text-inverse)',
      fontSize: 'var(--text-xs)',
      fontWeight: 'var(--fw-semibold)',
      lineHeight: 1,
      marginLeft: 'auto',
    }}>
      {value > 99 ? '99+' : value}
    </span>
  );
}

// ─── NavItem ───────────────────────────────────────────────────────────────────

interface NavItemProps {
  item: NavItemDef;
  isActive: boolean;
  collapsed: boolean;
  badges?: Record<string, number>;
  onClick: (route: string) => void;
}

function NavItemRow({ item, isActive, collapsed, badges, onClick }: NavItemProps) {
  const badgeValue = item.badge_key ? (badges?.[item.badge_key] ?? 0) : 0;

  return (
    <button
      type="button"
      title={collapsed ? item.label : undefined}
      aria-current={isActive ? 'page' : undefined}
      onClick={() => onClick(item.route)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        width: '100%',
        padding: collapsed ? '8px 0' : '7px 12px',
        justifyContent: collapsed ? 'center' : 'flex-start',
        border: 'none',
        borderRadius: 'var(--radius-md)',
        cursor: 'pointer',
        background: isActive ? 'var(--accent-soft)' : 'transparent',
        color: isActive ? 'var(--accent-text)' : 'var(--text-secondary)',
        fontFamily: 'var(--font-ui)',
        fontSize: 'var(--text-sm)',
        fontWeight: isActive ? 'var(--fw-semibold)' : 'var(--fw-regular)',
        borderLeft: isActive ? '3px solid var(--accent)' : '3px solid transparent',
        transition: 'background var(--transition-fast), color var(--transition-fast)',
        position: 'relative',
        overflow: 'hidden',
        whiteSpace: 'nowrap',
        textOverflow: 'ellipsis',
      }}
      onMouseEnter={e => {
        if (!isActive) (e.currentTarget as HTMLElement).style.background = 'var(--surface-hover)';
      }}
      onMouseLeave={e => {
        if (!isActive) (e.currentTarget as HTMLElement).style.background = 'transparent';
      }}
    >
      <Icon name={item.icon} size={15} />
      {!collapsed && (
        <>
          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.label}</span>
          {badgeValue > 0 && <NavBadge value={badgeValue} />}
        </>
      )}
      {collapsed && badgeValue > 0 && (
        <span style={{
          position: 'absolute',
          top: 4,
          right: 4,
          width: 6,
          height: 6,
          borderRadius: 'var(--radius-full)',
          background: 'var(--danger)',
        }} />
      )}
    </button>
  );
}

// ─── Props ─────────────────────────────────────────────────────────────────────

export interface SidebarProps {
  /** Current active route (e.g. '/roadmap') */
  activeRoute: string;
  /** User's plan tier for visibility gating */
  planTier: PlanTier;
  /** Live badge values keyed by badge_key */
  badges?: Record<string, number>;
  /** Navigate to route */
  onNavigate: (route: string) => void;
  /** Open/close the AI panel */
  onToggleAIPanel: () => void;
  /** Whether AI panel has a suggestion dot */
  hasAISuggestion?: boolean;
  /** User display info */
  user?: { name: string; role: string; avatarUrl?: string };
}

// ─── Component ─────────────────────────────────────────────────────────────────

export function Sidebar({
  activeRoute,
  planTier,
  badges,
  onNavigate,
  onToggleAIPanel,
  hasAISuggestion = false,
  user,
}: SidebarProps) {
  const [state, setState] = useState<SidebarPersistedState>(loadState);
  const dragSrcRef = useRef<string | null>(null);

  const collapsed = state.is_collapsed;

  // Persist on change
  useEffect(() => { saveState(state); }, [state]);

  const toggleCollapse = useCallback(() => {
    setState(s => ({ ...s, is_collapsed: !s.is_collapsed }));
  }, []);

  // Filter sections by tier
  const visibleSections = state.section_order
    .map(key => NAV_SECTIONS.find(s => s.key === key)!)
    .filter(Boolean)
    .filter(section => tierAllows(planTier, section.min_tier));

  // Drag-to-reorder sections
  const onDragStart = (key: string) => { dragSrcRef.current = key; };
  const onDragOver = (e: React.DragEvent, key: string) => {
    e.preventDefault();
    if (!dragSrcRef.current || dragSrcRef.current === key) return;
    setState(s => {
      const order = [...s.section_order];
      const srcIdx = order.indexOf(dragSrcRef.current!);
      const dstIdx = order.indexOf(key);
      if (srcIdx === -1 || dstIdx === -1) return s;
      order.splice(srcIdx, 1);
      order.splice(dstIdx, 0, dragSrcRef.current!);
      return { ...s, section_order: order };
    });
  };

  return (
    <nav
      aria-label="Platform navigation"
      style={{
        width: collapsed ? 'var(--sidebar-w-collapsed)' : 'var(--sidebar-w)',
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--surface)',
        borderRight: '1px solid var(--border)',
        transition: 'width var(--transition-sidebar)',
        overflow: 'hidden',
        position: 'fixed',
        top: 0,
        left: 0,
        zIndex: 'var(--z-sticky)',
        flexShrink: 0,
      }}
    >
      {/* Logo */}
      <div style={{
        height: 'var(--topbar-h)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: collapsed ? 'center' : 'flex-start',
        padding: collapsed ? 0 : '0 16px',
        borderBottom: '1px solid var(--border)',
        flexShrink: 0,
      }}>
        <button
          type="button"
          onClick={() => onNavigate(planTier === 'basic' ? '/my-move' : '/dashboard')}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--accent)',
            fontFamily: 'var(--font-ui)',
            fontWeight: 'var(--fw-bold)',
            fontSize: 'var(--text-lg)',
            letterSpacing: '-0.02em',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
          aria-label="ReloPass home"
        >
          <span style={{
            width: 28,
            height: 28,
            background: 'var(--accent)',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontSize: 'var(--text-sm)',
            fontWeight: 'var(--fw-bold)',
            flexShrink: 0,
          }}>R</span>
          {!collapsed && <span>ReloPass</span>}
        </button>
      </div>

      {/* Nav sections */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 8px 0' }}>
        {visibleSections.map((section) => (
          <div
            key={section.key}
            draggable={!collapsed}
            onDragStart={() => onDragStart(section.key)}
            onDragOver={(e) => onDragOver(e, section.key)}
            style={{ marginBottom: 8 }}
          >
            {/* Section label */}
            {!collapsed && (
              <div style={{
                padding: '4px 12px 2px',
                fontSize: 'var(--text-xs)',
                fontWeight: 'var(--fw-semibold)',
                color: 'var(--text-muted)',
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                userSelect: 'none',
              }}>
                {section.label}
              </div>
            )}
            {collapsed && <div style={{ height: 1, background: 'var(--border)', margin: '4px 8px' }} />}

            {/* Items */}
            {section.items
              .filter(item => tierAllows(planTier, item.min_tier))
              .map(item => (
                <NavItemRow
                  key={item.id}
                  item={item}
                  isActive={activeRoute === item.route || activeRoute.startsWith(item.route + '/')}
                  collapsed={collapsed}
                  badges={badges}
                  onClick={onNavigate}
                />
              ))}
          </div>
        ))}
      </div>

      {/* AI Panel toggle */}
      <div style={{ padding: '8px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
        <button
          type="button"
          onClick={onToggleAIPanel}
          title={collapsed ? 'AI Assistant' : undefined}
          aria-label="Toggle AI Assistant panel"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            width: '100%',
            padding: collapsed ? '8px 0' : '7px 12px',
            justifyContent: collapsed ? 'center' : 'flex-start',
            border: 'none',
            borderRadius: 'var(--radius-md)',
            cursor: 'pointer',
            background: 'transparent',
            color: 'var(--accent)',
            fontFamily: 'var(--font-ui)',
            fontSize: 'var(--text-sm)',
            fontWeight: 'var(--fw-medium)',
            position: 'relative',
            transition: 'background var(--transition-fast)',
          }}
          onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'var(--accent-soft)'; }}
          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
        >
          <span style={{ position: 'relative' }}>
            <Icon name="Sparkles" size={15} />
            {hasAISuggestion && (
              <span style={{
                position: 'absolute',
                top: -2,
                right: -2,
                width: 6,
                height: 6,
                borderRadius: 'var(--radius-full)',
                background: 'var(--accent)',
                animation: 'rp-pulse 2s infinite',
              }} />
            )}
          </span>
          {!collapsed && <span>AI Assistant</span>}
        </button>
      </div>

      {/* User row */}
      {user && (
        <div style={{ padding: '8px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
          <button
            type="button"
            onClick={() => onNavigate('/profile')}
            title={collapsed ? user.name : undefined}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              width: '100%',
              padding: collapsed ? '8px 0' : '7px 12px',
              justifyContent: collapsed ? 'center' : 'flex-start',
              border: 'none',
              borderRadius: 'var(--radius-md)',
              cursor: 'pointer',
              background: 'transparent',
              fontFamily: 'var(--font-ui)',
              transition: 'background var(--transition-fast)',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'var(--surface-hover)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
          >
            {/* Avatar */}
            <span style={{
              width: 28,
              height: 28,
              borderRadius: 'var(--radius-full)',
              background: 'var(--accent-soft)',
              color: 'var(--accent-text)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 'var(--text-xs)',
              fontWeight: 'var(--fw-semibold)',
              flexShrink: 0,
              overflow: 'hidden',
            }}>
              {user.avatarUrl
                ? <img src={user.avatarUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                : user.name.split(' ').map(n => n[0]).slice(0, 2).join('')}
            </span>
            {!collapsed && (
              <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', minWidth: 0 }}>
                <span style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--fw-medium)', color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 130 }}>
                  {user.name}
                </span>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', textTransform: 'capitalize' }}>
                  {user.role}
                </span>
              </span>
            )}
          </button>
        </div>
      )}

      {/* Collapse toggle */}
      <div style={{ padding: '8px', flexShrink: 0 }}>
        <button
          type="button"
          onClick={toggleCollapse}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '100%',
            padding: '6px',
            border: 'none',
            borderRadius: 'var(--radius-md)',
            cursor: 'pointer',
            background: 'transparent',
            color: 'var(--text-muted)',
            transition: 'background var(--transition-fast), color var(--transition-fast)',
          }}
          onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'var(--surface-hover)'; }}
          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
        >
          <Icon name={collapsed ? 'ChevronRight' : 'ChevronLeft'} size={14} />
        </button>
      </div>
    </nav>
  );
}

// ─── Pulse keyframes (injected once) ─────────────────────────────────────────

if (typeof document !== 'undefined') {
  const styleId = 'rp-sidebar-styles';
  if (!document.getElementById(styleId)) {
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      @keyframes rp-pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.6; transform: scale(1.3); }
      }
    `;
    document.head.appendChild(style);
  }
}

export default Sidebar;
