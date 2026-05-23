/**
 * analytics.ts — ReloPass structured event tracking
 * ─────────────────────────────────────────────────────────────────────────────
 * Sends typed events to the `capture-event` Supabase Edge Function which
 * writes them to the `public.events` table (FOUNDATION-1A schema).
 *
 * Usage:
 *   import { initRelopassAnalytics, trackEvent } from './lib/analytics';
 *
 *   // Once at app startup (after auth resolves):
 *   initRelopassAnalytics({ userId: user.id, companyId: user.company_id });
 *
 *   // Anywhere in the app:
 *   trackEvent('page_view', { page: '/hr/dashboard' });
 *   trackEvent('assignment_created', { entity_id: assignmentId });
 *
 * Privacy:
 *   - user_id is SHA-256 hashed before transmission — raw UUIDs/emails never leave the browser
 *   - No PII fields (email, name, passport, etc.) are permitted in `properties`
 *
 * Rate limiting:
 *   - Client-side: max 100 events/minute per session (drops silently)
 *   - Server-side: enforced again in the Edge Function
 * ─────────────────────────────────────────────────────────────────────────────
 */

import type { EventType, EventSource, EventInsert } from '../types/analytics';

// ─── Session state ────────────────────────────────────────────────────────────

/** Randomly generated once per page load, stable for the session. */
const SESSION_ID: string = (() => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for environments without crypto.randomUUID
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
})();

interface AnalyticsContext {
  hashedUserId: string | null;
  companyId: string | null;
  enabled: boolean;
}

const ctx: AnalyticsContext = {
  hashedUserId: null,
  companyId: null,
  enabled: false,
};

// ─── Rate limiter — sliding window ───────────────────────────────────────────

const RATE_LIMIT = 100;
const RATE_WINDOW_MS = 60_000;
let rateWindowStart = Date.now();
let rateCount = 0;

function withinRateLimit(): boolean {
  const now = Date.now();
  if (now - rateWindowStart > RATE_WINDOW_MS) {
    rateWindowStart = now;
    rateCount = 0;
  }
  if (rateCount >= RATE_LIMIT) return false;
  rateCount += 1;
  return true;
}

// ─── SHA-256 hashing (Web Crypto API) ────────────────────────────────────────

async function sha256(value: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(value);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Call once at app startup after the authenticated user is known.
 * Hashes the userId so it never travels in plaintext.
 */
export async function initRelopassAnalytics(opts: {
  userId: string | null;
  companyId: string | null;
}): Promise<void> {
  ctx.hashedUserId = opts.userId ? await sha256(opts.userId) : null;
  ctx.companyId = opts.companyId ?? null;
  ctx.enabled = true;
}

/**
 * Call when the user signs out to clear the identity context.
 */
export function resetRelopassAnalytics(): void {
  ctx.hashedUserId = null;
  ctx.companyId = null;
  ctx.enabled = false;
}

/**
 * Track a structured platform event.
 *
 * @param eventType   The event name (use the EventType union for autocomplete)
 * @param properties  Optional event-specific payload — must contain NO PII
 * @param overrides   Optional per-call overrides (entity_type, entity_id, source)
 */
export function trackEvent(
  eventType: EventType,
  properties?: Record<string, unknown>,
  overrides?: {
    entity_type?: string;
    entity_id?: string;
    source?: EventSource;
    company_id?: string;
  }
): void {
  if (!ctx.enabled) return;
  if (!withinRateLimit()) return;

  const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
  if (!supabaseUrl) return;

  const payload: Omit<EventInsert, 'id' | 'created_at'> = {
    event_type:  eventType,
    entity_type: overrides?.entity_type ?? null,
    entity_id:   overrides?.entity_id ?? null,
    user_id:     ctx.hashedUserId,
    company_id:  overrides?.company_id ?? ctx.companyId,
    session_id:  SESSION_ID,
    source:      overrides?.source ?? 'web',
    properties:  properties ?? {},
  };

  // Fire-and-forget — analytics must never block UI interactions
  fetch(`${supabaseUrl}/functions/v1/capture-event`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    // keepalive allows the request to complete even if the page unloads
    keepalive: true,
  }).catch(() => {
    // Silently drop — analytics failures must never surface to the user
  });
}

/**
 * Convenience: track a page view with the current pathname.
 */
export function trackPageView(path: string): void {
  trackEvent('page_view', { page: path });
}

export { SESSION_ID };
