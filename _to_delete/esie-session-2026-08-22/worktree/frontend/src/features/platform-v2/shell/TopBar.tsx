/**
 * TopBar.tsx — ReloPass Platform App Shell Top Bar
 * ─────────────────────────────────────────────────────────────────────────────
 * - Fixed top bar, 56px height, z-index var(--z-topbar)
 * - Left: breadcrumb trail (max 3 levels), animated with sidebar collapse
 * - Right: ⌘K search, ⌘J AI toggle, notifications bell, theme toggle, avatar
 * - User avatar dropdown: profile, settings, sign out
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '../../../components/antigravity/Button';
import { useTheme } from '../../../contexts/ThemeProvider';
import type { UserRole, PlanTier } from '../../../types/relopass-api-contracts';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface BreadcrumbItem {
  label: string;
  route?: string;
}

export interface TopBarUser {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  plan_tier: PlanTier;
  avatar_url?: string;
}

export interface TopBarProps {
  /** Breadcrumb items for current route (max 3) */
  breadcrumbs: BreadcrumbItem[];
  /** Current user */
  user: TopBarUser;
  /** Whether the sidebar is collapsed (shifts left edge) */
  sidebarCollapsed: boolean;
  /** Unread notification count */
  notificationCount?: number;
  /** Whether AI panel is currently open */
  aiPanelOpen: boolean;
  /** Toggle AI panel */
  onToggleAIPanel: () => void;
  /** Navigate to a route */
  onNavigate: (route: string) => void;
  /** Sign out callback */
  onSignOut: () => void;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getInitials(name: string): string {
  return name
    .split(' ')
    .map(part => part[0]?.toUpperCase() ?? '')
    .slice(0, 2)
    .join('');
}

function isMac(): boolean {
  return typeof navigator !== 'undefined' && /mac/i.test(navigator.platform);
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function Breadcrumbs({
  items,
  onNavigate,
}: {
  items: BreadcrumbItem[];
  onNavigate: (route: string) => void;
}) {
  const capped = items.slice(0, 3);
  return (
    <nav aria-label="Breadcrumb" style={{ display: 'flex', alignItems: 'center', gap: '4px', minWidth: 0 }}>
      {capped.map((item, i) => {
        const isLast = i === capped.length - 1;
        return (
          <span key={i} style={{ display: 'flex', alignItems: 'center', gap: '4px', minWidth: 0 }}>
            {i > 0 && (
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
                style={{ color: 'var(--text-tertiary)', flexShrink: 0 }}
              >
                <polyline points="9 18 15 12 9 6" />
              </svg>
            )}
            {isLast ? (
              <span
                style={{
                  fontSize: '14px',
                  fontWeight: 600,
                  color: 'var(--text-primary)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {item.label}
              </span>
            ) : item.route ? (
              <Button unstyled
                onClick={() => onNavigate(item.route!)}
                style={{
                  fontSize: '14px',
                  fontWeight: 400,
                  color: 'var(--text-secondary)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 0,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
                onMouseEnter={e => ((e.target as HTMLElement).style.color = 'var(--text-primary)')}
                onMouseLeave={e => ((e.target as HTMLElement).style.color = 'var(--text-secondary)')}
              >
                {item.label}
              </Button>
            ) : (
              <span
                style={{
                  fontSize: '14px',
                  color: 'var(--text-secondary)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {item.label}
              </span>
            )}
          </span>
        );
      })}
    </nav>
  );
}

function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <Button unstyled
      onClick={toggle}
      aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '32px',
        height: '32px',
        borderRadius: 'var(--radius-md)',
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        color: 'var(--text-secondary)',
        transition: 'background var(--transition-fast), color var(--transition-fast)',
        flexShrink: 0,
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLElement).style.background = 'var(--surface-hover)';
        (e.currentTarget as HTMLElement).style.color = 'var(--text-primary)';
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLElement).style.background = 'none';
        (e.currentTarget as HTMLElement).style.color = 'var(--text-secondary)';
      }}
    >
      {theme === 'dark' ? (
        // Sun icon
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="5" />
          <line x1="12" y1="1" x2="12" y2="3" />
          <line x1="12" y1="21" x2="12" y2="23" />
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
          <line x1="1" y1="12" x2="3" y2="12" />
          <line x1="21" y1="12" x2="23" y2="12" />
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
        </svg>
      ) : (
        // Moon icon
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      )}
    </Button>
  );
}

function NotificationBell({ count, onClick }: { count: number; onClick: () => void }) {
  return (
    <Button unstyled
      onClick={onClick}
      aria-label={count > 0 ? `${count} unread notifications` : 'Notifications'}
      title="Notifications"
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '32px',
        height: '32px',
        borderRadius: 'var(--radius-md)',
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        color: 'var(--text-secondary)',
        transition: 'background var(--transition-fast), color var(--transition-fast)',
        flexShrink: 0,
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLElement).style.background = 'var(--surface-hover)';
        (e.currentTarget as HTMLElement).style.color = 'var(--text-primary)';
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLElement).style.background = 'none';
        (e.currentTarget as HTMLElement).style.color = 'var(--text-secondary)';
      }}
    >
      {/* Bell icon */}
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>
      {count > 0 && (
        <span
          aria-hidden="true"
          style={{
            position: 'absolute',
            top: '4px',
            right: '4px',
            minWidth: '16px',
            height: '16px',
            borderRadius: '8px',
            background: 'var(--pill-danger-bg)',
            color: 'var(--pill-danger-text)',
            fontSize: '10px',
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '0 3px',
            lineHeight: 1,
          }}
        >
          {count > 99 ? '99+' : count}
        </span>
      )}
    </Button>
  );
}

function AIToggle({ open, onClick, hasSuggestion }: { open: boolean; onClick: () => void; hasSuggestion?: boolean }) {
  const modKey = isMac() ? '⌘' : 'Ctrl';
  return (
    <Button unstyled
      onClick={onClick}
      aria-label={open ? 'Close AI Assistant' : 'Open AI Assistant'}
      aria-pressed={open}
      title={`${open ? 'Close' : 'Open'} AI Assistant (${modKey}J)`}
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '32px',
        height: '32px',
        borderRadius: 'var(--radius-md)',
        background: open ? 'var(--accent-soft)' : 'none',
        border: open ? '1px solid var(--accent-border)' : '1px solid transparent',
        cursor: 'pointer',
        color: open ? 'var(--accent)' : 'var(--text-secondary)',
        transition: 'background var(--transition-fast), color var(--transition-fast), border-color var(--transition-fast)',
        flexShrink: 0,
      }}
      onMouseEnter={e => {
        if (!open) {
          (e.currentTarget as HTMLElement).style.background = 'var(--surface-hover)';
          (e.currentTarget as HTMLElement).style.color = 'var(--accent)';
        }
      }}
      onMouseLeave={e => {
        if (!open) {
          (e.currentTarget as HTMLElement).style.background = 'none';
          (e.currentTarget as HTMLElement).style.color = 'var(--text-secondary)';
        }
      }}
    >
      {/* Sparkles icon */}
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
        <path d="M5 3v4" />
        <path d="M19 17v4" />
        <path d="M3 5h4" />
        <path d="M17 19h4" />
      </svg>
      {hasSuggestion && !open && (
        <span
          aria-hidden="true"
          style={{
            position: 'absolute',
            top: '5px',
            right: '5px',
            width: '7px',
            height: '7px',
            borderRadius: '50%',
            background: 'var(--accent)',
            animation: 'rp-pulse 2s infinite',
          }}
        />
      )}
    </Button>
  );
}

// ─── Avatar Dropdown ──────────────────────────────────────────────────────────

interface AvatarDropdownProps {
  user: TopBarUser;
  onNavigate: (route: string) => void;
  onSignOut: () => void;
}

function AvatarDropdown({ user, onNavigate, onSignOut }: AvatarDropdownProps) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handler(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    function handler(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open]);

  const initials = getInitials(user.name);

  return (
    <div ref={menuRef} style={{ position: 'relative', flexShrink: 0 }}>
      <Button unstyled
        onClick={() => setOpen(v => !v)}
        aria-expanded={open}
        aria-haspopup="true"
        aria-label={`User menu for ${user.name}`}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '4px 6px',
          borderRadius: 'var(--radius-md)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          color: 'var(--text-primary)',
          transition: 'background var(--transition-fast)',
        }}
        onMouseEnter={e => ((e.currentTarget as HTMLElement).style.background = 'var(--surface-hover)')}
        onMouseLeave={e => ((e.currentTarget as HTMLElement).style.background = 'none')}
      >
        {/* Avatar */}
        <span
          aria-hidden="true"
          style={{
            width: '28px',
            height: '28px',
            borderRadius: '50%',
            background: user.avatar_url ? 'none' : 'var(--accent-soft)',
            color: 'var(--accent)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '11px',
            fontWeight: 700,
            flexShrink: 0,
            overflow: 'hidden',
          }}
        >
          {user.avatar_url ? (
            <img src={user.avatar_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            initials
          )}
        </span>
        {/* Name — hidden on narrow screens via a CSS class */}
        <span
          className="rp-topbar-username"
          style={{
            fontSize: '13px',
            fontWeight: 500,
            color: 'var(--text-primary)',
            maxWidth: '120px',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {user.name}
        </span>
        {/* Chevron down */}
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
          style={{
            color: 'var(--text-tertiary)',
            transform: open ? 'rotate(180deg)' : 'none',
            transition: 'transform var(--transition-fast)',
            flexShrink: 0,
          }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </Button>

      {open && (
        <div
          role="menu"
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            right: 0,
            width: '200px',
            background: 'var(--surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-lg)',
            overflow: 'hidden',
            zIndex: 'var(--z-dropdown)' as never,
          }}
        >
          {/* User info */}
          <div
            style={{
              padding: '12px 14px',
              borderBottom: '1px solid var(--border-subtle)',
            }}
          >
            <p style={{ margin: 0, fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
              {user.name}
            </p>
            <p style={{ margin: '2px 0 0', fontSize: '12px', color: 'var(--text-tertiary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user.email}
            </p>
          </div>

          {/* Menu items */}
          {[
            { label: 'My Profile', route: '/profile', icon: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z' },
            { label: 'Settings', route: '/settings', icon: 'M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z' },
          ].map(item => (
            <Button unstyled
              key={item.route}
              role="menuitem"
              onClick={() => { onNavigate(item.route); setOpen(false); }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                width: '100%',
                padding: '9px 14px',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: 'var(--text-secondary)',
                fontSize: '13px',
                textAlign: 'left',
                transition: 'background var(--transition-fast)',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLElement).style.background = 'var(--surface-hover)';
                (e.currentTarget as HTMLElement).style.color = 'var(--text-primary)';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLElement).style.background = 'none';
                (e.currentTarget as HTMLElement).style.color = 'var(--text-secondary)';
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d={item.icon} />
              </svg>
              {item.label}
            </Button>
          ))}

          <div style={{ borderTop: '1px solid var(--border-subtle)' }}>
            <Button unstyled
              role="menuitem"
              onClick={() => { onSignOut(); setOpen(false); }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                width: '100%',
                padding: '9px 14px',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: 'var(--danger)',
                fontSize: '13px',
                textAlign: 'left',
                transition: 'background var(--transition-fast)',
              }}
              onMouseEnter={e => ((e.currentTarget as HTMLElement).style.background = 'var(--surface-hover)')}
              onMouseLeave={e => ((e.currentTarget as HTMLElement).style.background = 'none')}
            >
              {/* LogOut icon */}
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              Sign out
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── TopBar ───────────────────────────────────────────────────────────────────

export function TopBar({
  breadcrumbs,
  user,
  sidebarCollapsed,
  notificationCount = 0,
  aiPanelOpen,
  onToggleAIPanel,
  onNavigate,
  onSignOut,
}: TopBarProps) {
  const sidebarWidth = sidebarCollapsed ? 'var(--sidebar-w-collapsed)' : 'var(--sidebar-w)';

  // ⌘J keyboard shortcut for AI panel
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      const modKey = isMac() ? e.metaKey : e.ctrlKey;
      if (modKey && e.key === 'j') {
        e.preventDefault();
        onToggleAIPanel();
      }
    }
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onToggleAIPanel]);

  const handleNotificationsClick = useCallback(() => {
    // Notifications slide-over: delegate to parent or router
    onNavigate('/notifications');
  }, [onNavigate]);

  return (
    <header
      role="banner"
      style={{
        position: 'fixed',
        top: 0,
        left: sidebarWidth,
        right: 0,
        height: 'var(--topbar-h)',
        background: 'var(--surface-topbar)',
        borderBottom: '1px solid var(--border-subtle)',
        zIndex: 'var(--z-topbar)' as never,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 var(--spacing-4)',
        gap: 'var(--spacing-3)',
        transition: 'left var(--transition-base)',
      }}
    >
      {/* Left: breadcrumb */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center' }}>
        <Breadcrumbs items={breadcrumbs} onNavigate={onNavigate} />
      </div>

      {/* Right: actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-1)', flexShrink: 0 }}>
        {/* Search ⌘K */}
        <Button unstyled
          aria-label="Search (⌘K)"
          title={`Search (${isMac() ? '⌘' : 'Ctrl'}K)`}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '32px',
            height: '32px',
            borderRadius: 'var(--radius-md)',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--text-secondary)',
            transition: 'background var(--transition-fast), color var(--transition-fast)',
          }}
          onMouseEnter={e => {
            (e.currentTarget as HTMLElement).style.background = 'var(--surface-hover)';
            (e.currentTarget as HTMLElement).style.color = 'var(--text-primary)';
          }}
          onMouseLeave={e => {
            (e.currentTarget as HTMLElement).style.background = 'none';
            (e.currentTarget as HTMLElement).style.color = 'var(--text-secondary)';
          }}
          onClick={() => {
            // Dispatch custom event; CommandPalette listens for it
            document.dispatchEvent(new CustomEvent('rp:open-command-palette'));
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </Button>

        {/* AI Panel toggle ⌘J */}
        <AIToggle open={aiPanelOpen} onClick={onToggleAIPanel} />

        {/* Notifications */}
        <NotificationBell count={notificationCount} onClick={handleNotificationsClick} />

        {/* Theme toggle */}
        <ThemeToggle />

        {/* Divider */}
        <div
          aria-hidden="true"
          style={{
            width: '1px',
            height: '20px',
            background: 'var(--border-subtle)',
            margin: '0 var(--spacing-1)',
          }}
        />

        {/* Avatar + dropdown */}
        <AvatarDropdown user={user} onNavigate={onNavigate} onSignOut={onSignOut} />
      </div>
    </header>
  );
}

export default TopBar;
