// ChangelogBell.tsx — AIQ-407-followup / changelog announcement stub.
//
// Replaces the Beta/NEW badges that P3 (AIQ-407) removed from the primary
// nav. The bell sits in the AppShell topbar; clicking it reveals the last
// N changelog entries from a static /changelog.json file in /public.
//
// Named "Changelog" to avoid collision with the existing NotificationBell
// component which handles unread *message* notifications.
//
// V1 design:
//   - Static JSON (fetched once, cached in component state)
//   - Unread state: localStorage key 'relopass_changelog_seen' stores the
//     ISO date of the most recent entry the user has seen
//   - Badge with red dot appears when any entry is newer than the seen date
//   - Keyboard: Tab to focus, Enter/Space to open, Esc to close
//   - Match the topbar's calm visual register (no emoji, no playful colors)

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { Button } from './antigravity/Button';
const SEEN_KEY = 'relopass_changelog_seen';

interface ChangelogEntry {
  id: string;
  /** ISO 8601 date (YYYY-MM-DD). */
  date: string;
  title: string;
  description: string;
}

function loadSeenDate(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage.getItem(SEEN_KEY);
  } catch {
    return null;
  }
}

function saveSeenDate(date: string): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(SEEN_KEY, date);
  } catch {
    /* ignore quota / private-mode errors */
  }
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return iso;
  }
}

export const ChangelogBell: React.FC = () => {
  const [entries, setEntries] = useState<ChangelogEntry[] | null>(null);
  const [open, setOpen] = useState(false);
  const [seenDate, setSeenDate] = useState<string | null>(() => loadSeenDate());
  const containerRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Fetch the static changelog once on mount. Silent failure — if the file
  // is missing in some environment, the bell just shows zero entries.
  useEffect(() => {
    let cancelled = false;
    fetch('/changelog.json', { cache: 'no-store' })
      .then((res) => (res.ok ? res.json() : []))
      .then((data: ChangelogEntry[]) => {
        if (cancelled) return;
        if (Array.isArray(data)) setEntries(data);
        else setEntries([]);
      })
      .catch(() => {
        if (!cancelled) setEntries([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const mostRecentDate = useMemo(() => {
    if (!entries || entries.length === 0) return null;
    return entries[0]?.date ?? null;
  }, [entries]);

  const hasUnread = useMemo(() => {
    if (!mostRecentDate) return false;
    if (!seenDate) return true;
    return mostRecentDate > seenDate;
  }, [mostRecentDate, seenDate]);

  const markAllRead = useCallback(() => {
    if (mostRecentDate) {
      saveSeenDate(mostRecentDate);
      setSeenDate(mostRecentDate);
    }
  }, [mostRecentDate]);

  // Close on outside click + Escape.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      const t = e.target as Node;
      if (containerRef.current && !containerRef.current.contains(t)) {
        setOpen(false);
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  const handleToggle = useCallback(() => {
    setOpen((prev) => {
      const next = !prev;
      if (next) markAllRead();
      return next;
    });
  }, [markAllRead]);

  return (
    <div ref={containerRef} className="relative">
      <Button unstyled
        ref={buttonRef}
        type="button"
        onClick={handleToggle}
        aria-label={
          hasUnread
            ? "What's new (new updates available)"
            : "What's new"
        }
        aria-haspopup="dialog"
        aria-expanded={open}
        className="relative grid h-8 w-8 place-items-center rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
      >
        {/* Sparkles-free megaphone-ish icon — clean lucide-style stroke */}
        <svg
          className="w-4 h-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M3 11l18-5v12L3 14v-3z M11.6 16.8a3 3 0 11-5.8-1.6"
          />
        </svg>
        {hasUnread && (
          <span
            aria-hidden="true"
            className="absolute right-1 top-1 inline-block h-1.5 w-1.5 rounded-full bg-rose-500"
            data-testid="changelog-bell-unread-dot"
          />
        )}
      </Button>

      {open && (
        <div
          role="dialog"
          aria-label="What's new"
          className="absolute right-0 top-full mt-1 w-80 max-w-[calc(100vw-2rem)] rounded-lg border border-slate-200 bg-white shadow-lg z-40"
        >
          <div className="px-4 py-2.5 border-b border-slate-100 flex items-center justify-between">
            <span className="text-sm font-semibold text-slate-900">What's new</span>
            <Button unstyled
              type="button"
              onClick={() => setOpen(false)}
              className="text-xs text-slate-400 hover:text-slate-600"
              aria-label="Close"
            >
              Close
            </Button>
          </div>

          {!entries && (
            <div className="px-4 py-4 text-sm text-slate-500">Loading…</div>
          )}

          {entries && entries.length === 0 && (
            <div className="px-4 py-4 text-sm text-slate-500">
              No updates yet. New releases and improvements will appear here.
            </div>
          )}

          {entries && entries.length > 0 && (
            <ul className="divide-y divide-slate-100 max-h-80 overflow-y-auto">
              {entries.slice(0, 8).map((entry) => (
                <li key={entry.id} className="px-4 py-3">
                  <div className="flex items-baseline justify-between gap-2">
                    <h3 className="text-sm font-medium text-slate-900">{entry.title}</h3>
                    <span className="text-[11px] text-slate-400 shrink-0">
                      {formatDate(entry.date)}
                    </span>
                  </div>
                  <p className="mt-1 text-[12.5px] text-slate-600 leading-relaxed">
                    {entry.description}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};

export default ChangelogBell;
