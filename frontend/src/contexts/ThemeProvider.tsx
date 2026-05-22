/**
 * ThemeProvider.tsx — ReloPass platform theme management
 * ─────────────────────────────────────────────────────────────────────────────
 * Reads localStorage['rp-theme'], applies data-theme attribute to <html>,
 * and provides a context for toggling/reading the current theme.
 *
 * Token source: relopass-design-tokens.json (theme_toggle_key: 'rp-theme')
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { createContext, useCallback, useContext, useEffect, useState } from 'react';

// ─── Types ────────────────────────────────────────────────────────────────────

export type ThemePreference = 'light' | 'dark' | 'system';

interface ThemeContextValue {
  /** Current resolved theme ('light' | 'dark') — never 'system' */
  theme: 'light' | 'dark';
  /** User preference including 'system' option */
  preference: ThemePreference;
  /** Toggle between light and dark (skips system) */
  toggle: () => void;
  /** Set a specific preference */
  setPreference: (pref: ThemePreference) => void;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const STORAGE_KEY = 'rp-theme' as const;

function getSystemTheme(): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function resolveTheme(preference: ThemePreference): 'light' | 'dark' {
  if (preference === 'system') return getSystemTheme();
  return preference;
}

function readStoredPreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(STORAGE_KEY) as ThemePreference | null;
    if (stored === 'light' || stored === 'dark' || stored === 'system') return stored;
  } catch {
    // localStorage blocked (private browsing)
  }
  return 'light'; // default per design-tokens.json theme_default
}

function applyTheme(resolved: 'light' | 'dark'): void {
  const html = document.documentElement;
  html.setAttribute('data-theme', resolved);
}

// ─── Context ──────────────────────────────────────────────────────────────────

const ThemeContext = createContext<ThemeContextValue | null>(null);

// ─── Provider ─────────────────────────────────────────────────────────────────

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>(() =>
    readStoredPreference()
  );

  const resolved = resolveTheme(preference);

  // Apply theme to <html> and persist on change
  useEffect(() => {
    applyTheme(resolved);
    try {
      localStorage.setItem(STORAGE_KEY, preference);
    } catch {
      // ignore
    }
  }, [preference, resolved]);

  // Listen for system theme changes when preference is 'system'
  useEffect(() => {
    if (preference !== 'system') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = () => applyTheme(getSystemTheme());
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [preference]);

  const setPreference = useCallback((pref: ThemePreference) => {
    setPreferenceState(pref);
  }, []);

  const toggle = useCallback(() => {
    setPreferenceState(prev => {
      const current = resolveTheme(prev);
      return current === 'dark' ? 'light' : 'dark';
    });
  }, []);

  return (
    <ThemeContext.Provider value={{ theme: resolved, preference, toggle, setPreference }}>
      {children}
    </ThemeContext.Provider>
  );
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used inside <ThemeProvider>');
  return ctx;
}

// ─── Standalone initialiser (run before React hydrates to avoid FOUC) ─────────
// Insert this as an inline script in index.html <head> to eliminate flash:
//
// <script>
//   (function() {
//     var pref = localStorage.getItem('rp-theme') || 'light';
//     var resolved = pref === 'system'
//       ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
//       : pref;
//     document.documentElement.setAttribute('data-theme', resolved);
//   })();
// </script>
