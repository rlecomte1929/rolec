import { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import type { SpaceConfig } from '@shared/schema';

export type SpaceMode = 'entrepreneur' | 'customer';

export interface FileInfo {
  path: string;
  size: number;
  isDirectory: boolean;
}

/**
 * Subscription state fetched from /api/space/:spaceId/subscription-status.
 * CRM contact metadata is the single source of truth.
 *
 * planTier: The workspace-specific plan identifier (e.g., "essentials", "companion", "guide").
 *   - Set via Stripe subscription metadata, manual CRM override, or direct metadata update.
 *   - null when the contact has no explicit plan set (workspace app should apply its own default).
 *   - Workspace apps that define custom tiers in lib/plans.ts should check planTier
 *     against their own tier definitions for app access gating.
 */
export interface SubscriptionState {
  status: 'loading' | 'not_registered' | 'registered' | 'trial' | 'trialing' | 'trial_expired' | 'active' | 'manual_override' | 'canceled' | 'past_due' | 'incomplete';
  planTier: string | null;
  email: string | null;
  stripeCustomerId: string | null;
  subscriptionId: string | null;
  trialDaysRemaining: number;
  trialDays: number;
  trialExpired: boolean;
  hasPaymentMethod: boolean;
  contactId: string | null;
  manualOverride: { tier: string; grantedBy: string; reason: string; expiresAt: string | null } | null;
}

interface SpaceRuntimeContextValue {
  mode: SpaceMode;
  spaceId: string;
  sessionId?: string;
  setSessionId: (sessionId: string) => void;
  visitorId?: string;
  isBootstrappingSession: boolean;
  
  config: SpaceConfig | null;
  isLoading: boolean;
  error: Error | null;
  
  readFile: (path: string) => Promise<string>;
  readTemplateFile: (path: string) => Promise<string>;
  writeFile: (path: string, content: string) => Promise<void>;
  listFiles: (dirPath?: string) => Promise<FileInfo[]>;
  
  trackEvent: (eventType: string, metadata?: Record<string, any>) => Promise<void>;
  
  refetchConfig: () => Promise<void>;

  subscription: SubscriptionState | null;
  subscriptionReady: boolean;
  updateSubscription: (updates: Partial<SubscriptionState>) => void;
  refreshSubscription: () => Promise<void>;
  checkAppAccess: (requiredTier?: string) => boolean;

  sessionMetadata: Record<string, unknown>;
  userRole: string | null;
  checkRoleAccess: (allowedRoles?: string[]) => boolean;

  waitForResolvedSession: (timeoutMs?: number) => Promise<string>;
}

const SpaceRuntimeContext = createContext<SpaceRuntimeContextValue | null>(null);

interface SpaceRuntimeProviderProps {
  children: ReactNode;
  spaceId: string;
  mode?: SpaceMode;
  sessionId?: string;
  config?: SpaceConfig | null; // Optional pre-loaded config
}

// Get or create persistent visitor ID from cookie (same as landing pages for cross-site tracking)
const VISITOR_COOKIE = 'audos_vid';

function getPaymentAppId(spaceId: string) {
  const runtimeWindow = window as Window & {
    __APP_ID__?: string;
    __SPACE_ID__?: string;
  };
  return runtimeWindow.__APP_ID__ || runtimeWindow.__SPACE_ID__ || spaceId;
}

// Comprehensive list of second-level TLDs (country-code SLDs) that require 3-part domain
const MULTI_LEVEL_TLDS = [
  // UK
  'co.uk', 'org.uk', 'me.uk', 'net.uk', 'ac.uk', 'gov.uk', 'ltd.uk', 'plc.uk', 'sch.uk',
  // Anguilla (.ai is treated as standard TLD but some registrars use second-level)
  'com.ai', 'net.ai', 'org.ai', 'off.ai',
  // Australia  
  'com.au', 'net.au', 'org.au', 'edu.au', 'gov.au', 'asn.au', 'id.au',
  // New Zealand
  'co.nz', 'net.nz', 'org.nz', 'govt.nz', 'ac.nz', 'school.nz', 'geek.nz', 'gen.nz',
  // Brazil
  'com.br', 'net.br', 'org.br', 'gov.br', 'edu.br', 'art.br', 'blog.br',
  // Japan
  'co.jp', 'or.jp', 'ne.jp', 'ac.jp', 'ad.jp', 'ed.jp', 'go.jp', 'gr.jp',
  // India
  'co.in', 'net.in', 'org.in', 'gen.in', 'firm.in', 'ind.in',
  // Singapore
  'com.sg', 'net.sg', 'org.sg', 'edu.sg', 'gov.sg', 'per.sg',
  // South Africa
  'co.za', 'org.za', 'web.za', 'net.za', 'gov.za',
  // Mexico
  'com.mx', 'org.mx', 'gob.mx', 'edu.mx', 'net.mx',
  // South Korea
  'co.kr', 'or.kr', 'ne.kr', 'ac.kr', 'go.kr',
  // Hong Kong
  'com.hk', 'org.hk', 'net.hk', 'edu.hk', 'gov.hk',
  // Taiwan
  'com.tw', 'org.tw', 'net.tw', 'edu.tw', 'gov.tw',
  // China
  'com.cn', 'net.cn', 'org.cn', 'gov.cn', 'ac.cn', 'edu.cn',
  // Germany (special)
  'co.de',
  // USA state-level
  'co.us', 'k12.us', 'ci.us', 'state.us',
  // Other common ones
  'com.tr', 'org.tr', 'net.tr', 'biz.tr', 'gov.tr',
  'co.il', 'org.il', 'net.il', 'ac.il', 'gov.il',
  'com.ar', 'org.ar', 'net.ar', 'gov.ar',
  'com.pl', 'org.pl', 'net.pl', 'gov.pl',
  'com.pt', 'org.pt', 'net.pt', 'gov.pt',
  'co.id', 'or.id', 'go.id', 'ac.id', 'sch.id',
  'co.th', 'or.th', 'ac.th', 'go.th',
  'com.ph', 'org.ph', 'net.ph', 'gov.ph',
  'com.my', 'org.my', 'net.my', 'gov.my', 'edu.my',
  'com.vn', 'net.vn', 'org.vn', 'gov.vn', 'edu.vn',
  // Platform/hosting domains in Public Suffix List (browsers block cookies on root)
  'replit.dev', 'replit.app', 'repl.co',
  'github.io', 'herokuapp.com', 'netlify.app', 'vercel.app',
  'pages.dev', 'workers.dev', 'web.app', 'firebaseapp.com',
  'azurewebsites.net', 'cloudfront.net', 'amazonaws.com',
  'ngrok.io', 'ngrok.app', 'railway.app', 'render.com',
  'fly.dev', 'deno.dev', 'glitch.me'
];

// Platform domains where we should NOT set a cross-subdomain cookie (Safari ITP blocks it)
const PLATFORM_DOMAINS = [
  'replit.dev', 'replit.app', 'repl.co',
  'github.io', 'herokuapp.com', 'netlify.app', 'vercel.app',
  'pages.dev', 'workers.dev', 'web.app', 'firebaseapp.com',
  'azurewebsites.net', 'cloudfront.net', 'amazonaws.com',
  'ngrok.io', 'ngrok.app', 'railway.app', 'render.com',
  'fly.dev', 'deno.dev', 'glitch.me'
];

function isPlatformDomain(hostname: string): boolean {
  for (const platform of PLATFORM_DOMAINS) {
    if (hostname.endsWith('.' + platform) || hostname === platform) {
      return true;
    }
  }
  return false;
}

function getVisitorId(): string {
  if (typeof document === 'undefined') return '';
  
  const cookies = document.cookie.split(';');
  for (let i = 0; i < cookies.length; i++) {
    const cookie = cookies[i].trim();
    if (cookie.startsWith(VISITOR_COOKIE + '=')) {
      const value = cookie.substring(VISITOR_COOKIE.length + 1);
      console.log('[SpaceRuntime] Found existing visitor ID:', value);
      return value;
    }
  }
  
  // Create new visitor ID and set cookie for 1 year
  const visitorId = 'vid_' + Date.now() + '_' + Math.random().toString(36).substring(2, 15);
  const expires = new Date();
  expires.setFullYear(expires.getFullYear() + 1);
  
  // Determine cookie domain for cross-subdomain tracking
  const hostname = window.location.hostname;
  let cookieDomain = '';
  
  // Skip domain for localhost, IP addresses, AND platform domains (Safari ITP compatibility)
  const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1' || hostname.endsWith('.localhost');
  const isIP = /^\d+\.\d+\.\d+\.\d+$/.test(hostname);
  const isPlatform = isPlatformDomain(hostname);
  
  // For platform domains (like replit.dev), DON'T set a domain - use host-only cookie
  // Safari ITP blocks JavaScript-set cookies with cross-subdomain domain settings
  if (!isLocalhost && !isIP && !isPlatform) {
    const domainParts = hostname.split('.');
    const lastTwo = domainParts.slice(-2).join('.');
    
    // Check if this is a multi-level TLD requiring 3-part domain
    if (MULTI_LEVEL_TLDS.includes(lastTwo) && domainParts.length >= 3) {
      cookieDomain = '; domain=.' + domainParts.slice(-3).join('.');
    } else if (domainParts.length >= 2) {
      // For standard TLDs like example.com, example.io, example.app
      cookieDomain = '; domain=.' + domainParts.slice(-2).join('.');
    }
  }
  
  // Set cookie with SameSite=Lax for Safari ITP compatibility
  const isSecure = window.location.protocol === 'https:';
  const secureFlag = isSecure ? '; Secure' : '';
  const cookieString = VISITOR_COOKIE + '=' + visitorId + '; expires=' + expires.toUTCString() + '; path=/' + cookieDomain + '; SameSite=Lax' + secureFlag;
  document.cookie = cookieString;
  console.log('[SpaceRuntime] Created new visitor ID:', visitorId, 'domain:', cookieDomain || '(host-only)', 'isPlatform:', isPlatform, 'cookie:', cookieString);
  return visitorId;
}

export function SpaceRuntimeProvider({ 
  children, 
  spaceId, 
  mode = 'customer',
  sessionId: initialSessionId,
  config: initialConfig = null
}: SpaceRuntimeProviderProps) {
  const [config, setConfig] = useState<SpaceConfig | null>(initialConfig);
  const [isLoading, setIsLoading] = useState(!initialConfig);
  const [error, setError] = useState<Error | null>(null);
  const [sessionId, setSessionIdRaw] = useState<string | undefined>(() => {
    let resolved: string | undefined;
    if (initialSessionId) {
      resolved = initialSessionId;
    } else {
      try {
        const stored = localStorage.getItem(`space_session_${spaceId}`);
        if (stored) {
          const session = JSON.parse(stored);
          const recoveredId = session.workspaceSessionId || session.sessionId || session.id;
          if (recoveredId) resolved = recoveredId;
        }
        if (!resolved) {
          const ssId = sessionStorage.getItem('space_session_id');
          if (ssId) resolved = ssId;
        }
      } catch {
        resolved = `ephemeral_${Date.now()}_${Math.random().toString(36).substring(2, 10)}`;
      }
    }
    if (resolved && typeof window !== 'undefined') {
      (window as any).__spaceSessionId = resolved;
    }
    return resolved;
  });
  const [visitorId] = useState<string>(() => getVisitorId());
  // True while post-checkout auto-session bootstrap is in flight — suppresses EmailGate render
  const [isBootstrappingSession, setIsBootstrappingSession] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    if (mode !== 'customer') return false;
    const params = new URLSearchParams(window.location.search);
    const isPostPayment = params.has('payment_success') || params.has('subscription_success');
    const stripeSessionId = params.get('session_id');
    if (!isPostPayment || !stripeSessionId) return false;
    try {
      const stored = localStorage.getItem(`space_session_${spaceId}`);
      if (stored) {
        const session = JSON.parse(stored);
        if (session.workspaceSessionId || session.sessionId || session.id) return false;
      }
    } catch {}
    return true;
  });
  const [subscription, setSubscription] = useState<SubscriptionState | null>(null);
  const [subscriptionReady, setSubscriptionReady] = useState(false);
  const subscriptionRef = useRef<SubscriptionState | null>(null);
  const [sessionMetadata, setSessionMetadata] = useState<Record<string, unknown>>(() => {
    try {
      const stored = localStorage.getItem(`space_session_${spaceId}`);
      if (stored) {
        const session = JSON.parse(stored);
        if (session.metadata && typeof session.metadata === 'object') {
          return session.metadata;
        }
      }
    } catch {}
    return {};
  });

  const setSessionId = useCallback((newSessionId: string) => {
    setSessionIdRaw(newSessionId);
    if (typeof window !== 'undefined') {
      (window as any).__spaceSessionId = newSessionId;
    }
    try {
      const stored = localStorage.getItem(`space_session_${spaceId}`);
      if (stored) {
        const session = JSON.parse(stored);
        if (session.metadata && typeof session.metadata === 'object') {
          setSessionMetadata(session.metadata);
        }
      }
    } catch {}
  }, [spaceId]);

  // Keep window.__spaceSessionId in sync with the current sessionId so workspace
  // components that poll (e.g. saveAndContinue in GardenVisualizer) can read the
  // latest value without depending on stale React props.
  useEffect(() => {
    if (typeof window !== 'undefined') {
      (window as any).__spaceSessionId = sessionId;
    }
  }, [sessionId]);

  const waitForResolvedSession = useCallback(
    (timeoutMs = 8000): Promise<string> => {
      const current = sessionId || (typeof window !== 'undefined' ? (window as any).__spaceSessionId : undefined);
      if (current && typeof current === 'string' && current.startsWith('wses_')) {
        return Promise.resolve(current);
      }

      return new Promise<string>((resolve, reject) => {
        const start = Date.now();
        const interval = setInterval(() => {
          const val = (typeof window !== 'undefined' ? (window as any).__spaceSessionId : undefined) as string | undefined;
          if (val && typeof val === 'string' && val.startsWith('wses_')) {
            clearInterval(interval);
            resolve(val);
            return;
          }
          if (Date.now() - start >= timeoutMs) {
            clearInterval(interval);
            reject(new Error('Session initialization timed out — no wses_ session available'));
          }
        }, 200);
      });
    },
    [sessionId],
  );

  // Auto-session: When the page loads from a Stripe payment_success redirect with no existing session,
  // pull the customer email from the Stripe session, register a workspace session, and bypass the EmailGate.
  useEffect(() => {
    if (mode !== 'customer') return;

    const params = new URLSearchParams(window.location.search);
    const isPostPayment = params.has('payment_success') || params.has('subscription_success');
    const stripeSessionId = params.get('session_id');

    if (!isPostPayment || !stripeSessionId) return;

    // If there's already a session in localStorage, the existing flow handles it
    try {
      const stored = localStorage.getItem(`space_session_${spaceId}`);
      if (stored) {
        const session = JSON.parse(stored);
        if (session.workspaceSessionId || session.sessionId || session.id) return;
      }
    } catch {}

    // No existing session — auto-create one from the Stripe session customer email
    const autoCreateSession = async () => {
      try {
        console.log('[SpaceRuntime] Post-checkout landing detected — auto-creating session from Stripe session:', stripeSessionId);

        // Fetch payment status to get the customer email
        const statusRes = await fetch(`/api/space/${spaceId}/payment-status?session_id=${encodeURIComponent(stripeSessionId)}`);
        if (!statusRes.ok) {
          console.warn('[SpaceRuntime] Could not fetch payment status for auto-session creation');
          setIsBootstrappingSession(false);
          return;
        }
        const statusData = await statusRes.json();
        const customerEmail = statusData.customerEmail;

        // Only auto-create session for completed, paid sessions — reject unpaid / pending ones
        if (!statusData.countsAsPurchase) {
          console.warn('[SpaceRuntime] Stripe session not yet paid (countsAsPurchase=false) — skipping auto-session creation');
          setIsBootstrappingSession(false);
          return;
        }

        if (!customerEmail) {
          console.warn('[SpaceRuntime] No customer email in Stripe session — cannot auto-create session');
          setIsBootstrappingSession(false);
          return;
        }

        // Register workspace session using the email from Stripe
        const visitorId = getVisitorId();
        const registerRes = await fetch(`/api/space/${spaceId}/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: customerEmail,
            sessionId: `post_pay_${Date.now()}_${Math.random().toString(36).substring(2, 10)}`,
            visitorId,
            attribution: null,
            metadata: { source: 'landing_page_checkout', stripeSessionId },
            workspaceId: (window as any).__WORKSPACE_ID__ || null,
          }),
        });

        if (!registerRes.ok) {
          console.warn('[SpaceRuntime] Auto-session registration failed');
          setIsBootstrappingSession(false);
          return;
        }

        const registerData = await registerRes.json();
        const effectiveSessionId = registerData.workspaceSessionId || registerData.sessionId;
        if (!effectiveSessionId) {
          console.warn('[SpaceRuntime] Auto-session registration returned no session ID');
          setIsBootstrappingSession(false);
          return;
        }

        // Persist to localStorage like EmailGate does
        const sessionKey = `space_session_${spaceId}`;
        const session = {
          id: effectiveSessionId,
          workspaceSessionId: effectiveSessionId,
          email: customerEmail,
          contactId: registerData.contactId || null,
          timestamp: Date.now(),
          isReturningUser: !!registerData.isReturningUser,
          metadata: registerData.metadata || { source: 'landing_page_checkout' },
        };
        localStorage.setItem(sessionKey, JSON.stringify(session));

        try {
          window.dispatchEvent(new CustomEvent('audos:session-established', {
            detail: { workspaceSessionId: effectiveSessionId, email: customerEmail },
          }));
        } catch {}

        console.log('[SpaceRuntime] Auto-session established from post-checkout for:', customerEmail);
        setSessionId(effectiveSessionId);
        setIsBootstrappingSession(false);
      } catch (err) {
        console.error('[SpaceRuntime] Auto-session creation failed:', err);
        setIsBootstrappingSession(false);
      }
    };

    autoCreateSession();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spaceId, mode]);

  useEffect(() => {
    if (!isBootstrappingSession) return;
    const timeout = setTimeout(() => {
      console.warn('[SpaceRuntime] Bootstrap session timeout — clearing spinner after 10s');
      setIsBootstrappingSession(false);
    }, 10000);
    return () => clearTimeout(timeout);
  }, [isBootstrappingSession]);

  // Cross-device / logged-out email resume: a workspace-side "Save your
  // conversation" pill (or any other component) can register an email via
  // POST /api/space/:spaceId/register and dispatch `audos:session-established`
  // with the resolved workspaceSessionId. The standard platform EmailGate
  // also calls setSessionId() itself, but custom workspace components may
  // only dispatch the event. Without this listener, sessionId would stay on
  // the visitor's fresh anonymous id and the AgentChat history useEffect
  // (deps: [spaceId, sessionId]) would never re-fetch the resumed session's
  // transcript — the page would stay on the empty "Welcome" greeting.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const onSessionEstablished = (event: Event) => {
      const detail = (event as CustomEvent).detail || {};
      const resumedSessionId =
        detail.workspaceSessionId || detail.sessionId || detail.id;
      if (!resumedSessionId || typeof resumedSessionId !== 'string') return;
      if (resumedSessionId === sessionId) return;
      console.log(
        '[SpaceRuntime] audos:session-established → adopting resumed sessionId:',
        resumedSessionId,
      );
      setSessionId(resumedSessionId);
    };
    window.addEventListener('audos:session-established', onSessionEstablished);
    return () =>
      window.removeEventListener('audos:session-established', onSessionEstablished);
  }, [sessionId, setSessionId]);

  const resolveSessionId = (): string | undefined => {
    if (sessionId) return sessionId;
    try {
      const stored = localStorage.getItem(`space_session_${spaceId}`);
      if (stored) {
        const session = JSON.parse(stored);
        const recoveredId = session.workspaceSessionId || session.sessionId || session.id;
        if (recoveredId) {
          setSessionId(recoveredId);
          return recoveredId;
        }
      }
      const ssId = sessionStorage.getItem('space_session_id');
      if (ssId) {
        setSessionId(ssId);
        return ssId;
      }
    } catch {
      // Storage unavailable — generate ephemeral session ID for this page visit
      const ephemeral = `ephemeral_${Date.now()}_${Math.random().toString(36).substring(2, 10)}`;
      setSessionId(ephemeral);
      return ephemeral;
    }
    return undefined;
  };

  const getApiBasePath = () => {
    if (mode === 'entrepreneur') {
      return `/api/space/${spaceId}`;
    }
    const resolvedId = resolveSessionId();
    if (!resolvedId) {
      throw new Error('Session not initialized - cannot perform file operations without login');
    }
    return `/api/space/${spaceId}/user/${resolvedId}`;
  };

  // Load space config
  const fetchConfig = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`/api/space/${spaceId}/config`);
      
      if (!response.ok) {
        throw new Error(`Failed to load config: ${response.statusText}`);
      }
      
      const data = await response.json();
      setConfig(data);
    } catch (err) {
      setError(err as Error);
      console.error('[SpaceRuntime] Config load error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Initial config load (only if not pre-loaded)
  useEffect(() => {
    if (!initialConfig) {
      fetchConfig();
    }
  }, [spaceId]);

  // Validate path security - multiple layers
  const validatePath = (logicalPath: string): void => {
    // Security layer 1: Prevent path traversal with ..
    if (logicalPath.includes('..')) {
      throw new Error('Invalid path: path traversal detected');
    }
    
    // Security layer 2: Reject absolute paths (/, //, etc.)
    if (logicalPath.startsWith('/')) {
      throw new Error('Invalid path: absolute paths not allowed');
    }
    
    // Security layer 3: Reject protocol-prefixed paths
    if (logicalPath.includes(':')) {
      throw new Error('Invalid path: protocol-prefixed paths not allowed');
    }
    
    // Security layer 4: Reject backslashes (Windows path separators)
    if (logicalPath.includes('\\')) {
      throw new Error('Invalid path: backslashes not allowed');
    }
  };

  // Storage operations with mode-aware routing
  const readFile = async (logicalPath: string): Promise<string> => {
    validatePath(logicalPath);
    
    try {
      const apiPath = `${getApiBasePath()}/file/${logicalPath}`;
      const response = await fetch(apiPath);
      
      if (!response.ok) {
        // Return empty object for non-existent files (initial state)
        if (response.status === 404) {
          return JSON.stringify({});
        }
        throw new Error(`Failed to read file: ${response.statusText}`);
      }
      
      const data = await response.json();
      return data.content || '';
    } catch (err) {
      console.error('[SpaceRuntime] Read file error:', logicalPath, err);
      throw err;
    }
  };

  const readTemplateFile = async (logicalPath: string): Promise<string> => {
    validatePath(logicalPath);
    
    try {
      const apiPath = `/api/space/${spaceId}/file/${logicalPath}`;
      const response = await fetch(apiPath);
      
      if (!response.ok) {
        if (response.status === 404) {
          return JSON.stringify({});
        }
        throw new Error(`Failed to read template file: ${response.statusText}`);
      }
      
      const data = await response.json();
      return data.content || '';
    } catch (err) {
      console.error('[SpaceRuntime] Read template file error:', logicalPath, err);
      throw err;
    }
  };

  const writeFile = async (logicalPath: string, content: string): Promise<void> => {
    validatePath(logicalPath);
    
    try {
      const apiPath = `${getApiBasePath()}/file/${logicalPath}`;
      const response = await fetch(apiPath, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });
      
      if (!response.ok) {
        throw new Error(`Failed to write file: ${response.statusText}`);
      }
    } catch (err) {
      console.error('[SpaceRuntime] Write file error:', logicalPath, err);
      throw err;
    }
  };

  const listFiles = async (dirPath: string = ''): Promise<FileInfo[]> => {
    try {
      const apiPath = `${getApiBasePath()}/files${dirPath ? `?path=${dirPath}` : ''}`;
      const response = await fetch(apiPath);
      
      if (!response.ok) {
        throw new Error(`Failed to list files: ${response.statusText}`);
      }
      
      const data = await response.json();
      return data.files || [];
    } catch (err) {
      console.error('[SpaceRuntime] List files error:', dirPath, err);
      throw err;
    }
  };
  
  const getAttribution = (): Record<string, string> | null => {
    const params = new URLSearchParams(window.location.search);
    const attr: Record<string, string | null> = {
      utm_source: params.get('utm_source'),
      utm_medium: params.get('utm_medium'),
      utm_campaign: params.get('utm_campaign'),
      utm_content: params.get('utm_content'),
      utm_term: params.get('utm_term'),
      fbclid: params.get('fbclid'),
      gclid: params.get('gclid'),
      ref: params.get('ref'),
    };
    const filtered: Record<string, string> = {};
    for (const key in attr) {
      if (attr[key] !== null) { filtered[key] = attr[key]!; }
    }
    return Object.keys(filtered).length > 0 ? filtered : null;
  };

  const trackEvent = async (eventType: string, metadata: Record<string, any> = {}): Promise<void> => {
    if (!sessionId) {
      console.warn('[SpaceRuntime] Cannot track event without sessionId');
      return;
    }
    
    try {
      const response = await fetch(`/api/space/${spaceId}/track`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId,
          visitorId,
          eventType,
          metadata,
          attribution: getAttribution(),
        }),
      });
      
      if (!response.ok) {
        console.warn('[SpaceRuntime] Failed to track event:', eventType);
        return;
      }
      
      // Get the eventId from the response and link to recording (like landing pages do)
      const data = await response.json();
      if (data.eventId && (window as any).__RECORDING_ID__) {
        try {
          await fetch(`/api/crm/session-recordings/${(window as any).__RECORDING_ID__}/link`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ funnelEventId: data.eventId }),
          });
          console.log('[SpaceRuntime] Recording linked to event:', data.eventId);
        } catch (linkErr) {
          console.warn('[SpaceRuntime] Failed to link recording to event:', linkErr);
        }
      }
    } catch (err) {
      console.warn('[SpaceRuntime] Track event error:', err);
    }
  };

  const getEmailFromSession = useCallback((): string | null => {
    try {
      const sessionKey = `space_session_${spaceId}`;
      const stored = localStorage.getItem(sessionKey);
      if (!stored) return null;
      const session = JSON.parse(stored);
      return session.email || null;
    } catch {
      return null;
    }
  }, [spaceId]);

  useEffect(() => {
    subscriptionRef.current = subscription;
  }, [subscription]);

  const readCachedSubscription = useCallback((): SubscriptionState | null => {
    try {
      const cachedSub = localStorage.getItem(`space_subscription_${spaceId}`);
      if (!cachedSub) return null;
      return JSON.parse(cachedSub) as SubscriptionState;
    } catch {
      return null;
    }
  }, [spaceId]);

  const buildSafeNonEntitledSubscription = useCallback((
    email: string,
    fallback?: SubscriptionState | null,
  ): SubscriptionState => ({
    status: 'registered',
    planTier: fallback?.planTier ?? null,
    email,
    stripeCustomerId: null,
    subscriptionId: null,
    trialDaysRemaining: 0,
    trialDays: 0,
    trialExpired: true,
    hasPaymentMethod: false,
    contactId: fallback?.contactId ?? null,
    manualOverride: null,
  }), []);

  const getSafeFallbackSubscription = useCallback((
    email: string,
    fallback?: SubscriptionState | null,
  ): SubscriptionState | null => {
    if (!fallback) return null;

    if ([
      'registered',
      'not_registered',
      'canceled',
      'trial_expired',
      'past_due',
      'incomplete',
    ].includes(fallback.status)) {
      return { ...fallback, email };
    }

    const hasVerifiedEntitlement = !!fallback.subscriptionId || !!fallback.manualOverride;
    if (
      hasVerifiedEntitlement &&
      (fallback.status === 'trialing' || fallback.status === 'trial' || fallback.status === 'active' || fallback.status === 'manual_override')
    ) {
      return { ...fallback, email };
    }

    return buildSafeNonEntitledSubscription(email, fallback);
  }, [buildSafeNonEntitledSubscription]);

  const refreshSubscription = useCallback(async () => {
    const email = getEmailFromSession();
    if (!email) {
      console.log('[SpaceRuntime] No email in session, skipping subscription check');
      setSubscription(null);
      setSubscriptionReady(true);
      return;
    }

    const restoreSafeFallback = (source: string) => {
      const cachedFallback = getSafeFallbackSubscription(email, readCachedSubscription());
      const previousFallback = getSafeFallbackSubscription(email, subscriptionRef.current);
      const fallbackState = cachedFallback || previousFallback || buildSafeNonEntitledSubscription(email, subscriptionRef.current);
      console.warn(`[SpaceRuntime] Subscription status fetch failed, restoring safe fallback from ${source}:`, fallbackState.status);
      setSubscription(fallbackState);
      setSubscriptionReady(true);
    };

    // Only block the UI on the very first check. Once we've resolved a real
    // subscription state, subsequent refreshes (Stripe return, force-refresh
    // from inside an app) must not flip `subscriptionReady` back to `false` —
    // doing so causes SubscriptionReadyGate to flash the full-screen loader
    // every time the bundle decides to revalidate.
    const hasPriorResolved = subscriptionRef.current !== null
      && subscriptionRef.current.status !== 'loading';

    try {
      if (!hasPriorResolved) {
        setSubscriptionReady(false);
        setSubscription({
          status: 'loading' as const, planTier: null, email, stripeCustomerId: null,
          subscriptionId: null, trialDaysRemaining: 0, trialDays: 0, trialExpired: false,
          hasPaymentMethod: false, contactId: null, manualOverride: null,
        });
      }

      const response = await fetch(
        `/api/space/${spaceId}/subscription-status?email=${encodeURIComponent(email)}`,
        {
          cache: 'no-store',
          headers: {
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
          },
        },
      );

      if (!response.ok) {
        console.warn('[SpaceRuntime] Subscription status fetch failed:', response.status);
        restoreSafeFallback(`http_${response.status}`);
        return;
      }

      const data = await response.json();
      console.log('[SpaceRuntime] Subscription status:', data.status);

      const newState: SubscriptionState = {
        status: data.status || 'not_registered',
        planTier: data.planTier || null,
        email,
        stripeCustomerId: data.hasPaymentMethod ? 'exists' : null,
        subscriptionId: data.subscriptionId || null,
        trialDaysRemaining: data.trialDaysRemaining || 0,
        trialDays: data.trialDays || 0,
        trialExpired: data.trialExpired || false,
        hasPaymentMethod: data.hasPaymentMethod || false,
        contactId: data.contactId || null,
        manualOverride: data.manualOverride || null,
      };

      setSubscription(newState);
      localStorage.setItem(`space_subscription_${spaceId}`, JSON.stringify(newState));
      setSubscriptionReady(true);
    } catch (err) {
      console.error('[SpaceRuntime] Subscription check error:', err);
      restoreSafeFallback('network_error');
    }
  }, [spaceId, getEmailFromSession, buildSafeNonEntitledSubscription, getSafeFallbackSubscription, readCachedSubscription]);

  const updateSubscription = useCallback((updates: Partial<SubscriptionState>) => {
    setSubscription(prev => {
      const updated = prev
        ? { ...prev, ...updates }
        : {
            status: 'not_registered' as const, planTier: null, email: null,
            stripeCustomerId: null, subscriptionId: null, trialDaysRemaining: 0,
            trialDays: 0, trialExpired: false, hasPaymentMethod: false,
            contactId: null, manualOverride: null, ...updates,
          };
      localStorage.setItem(`space_subscription_${spaceId}`, JSON.stringify(updated));
      return updated;
    });
  }, [spaceId]);

  const checkAppAccess = useCallback((requiredTier?: string): boolean => {
    if (mode === 'entrepreneur') return true;
    if (!subscription) return false;
    if (subscription.status === 'active') return true;
    if (subscription.manualOverride) return true;
    if ((subscription.status === 'trialing' || subscription.status === 'trial') && !subscription.trialExpired) return true;
    return false;
  }, [mode, subscription]);

  const userRole = (sessionMetadata.role as string) || null;

  const checkRoleAccess = useCallback((allowedRoles?: string[]): boolean => {
    if (mode === 'entrepreneur') return true;
    if (!allowedRoles || allowedRoles.length === 0) return true;
    if (!userRole) return false;
    return allowedRoles.includes(userRole);
  }, [mode, userRole]);

  const purchaseFiredRef = useRef(false);

  const firePurchaseEvent = (email: string | null, amount?: number, currency?: string, stripeSessionId?: string | null): boolean => {
    let fbqFired = false;
    if (typeof (window as any).fbq === 'function') {
      const eventParams: Record<string, any> = {
        content_name: 'Subscription Purchase',
        content_category: 'space',
        value: amount ?? 0,
        currency: (currency || 'usd').toUpperCase(),
      };
      const advancedMatching = email
        ? { em: email.toLowerCase().trim() }
        : undefined;
      (window as any).fbq('track', 'Purchase', eventParams, advancedMatching);
      console.log(`[SpaceRuntime] Meta Pixel Purchase event fired (value=${eventParams.value}, currency=${eventParams.currency})`);
      fbqFired = true;
    }

    // Task #1480: parallel Reddit Pixel Purchase. Keyed on the Stripe session id
    // for client↔server CAPI dedupe. Caller wraps this in purchaseFiredRef so a
    // refresh won't re-fire either pixel. Calls window.rdt directly — the
    // queue stub installed by the live PageVisit snippet (Task #1456) handles
    // late pixel.js loads.
    try {
      const rdt = (window as any).rdt;
      const pixelId = (window as any).__REDDIT_PIXEL_ID__;
      if (typeof rdt === 'function') {
        if (pixelId && email) {
          rdt('init', pixelId, { email: email.toLowerCase().trim() });
        }
        const conversionId = stripeSessionId || `purchase_${spaceId}_${Date.now()}`;
        rdt('track', 'Purchase', {
          value: amount ?? 0,
          currency: (currency || 'usd').toUpperCase(),
          conversionId,
        });
        console.log(`[SpaceRuntime] Reddit Pixel Purchase event fired (value=${amount ?? 0}, currency=${(currency || 'usd').toUpperCase()}, conversionId=${conversionId})`);
      }
    } catch (e) {
      console.warn('[SpaceRuntime] Reddit Pixel Purchase failed:', e);
    }

    return fbqFired;
  };

  const firePurchaseEventWithRetry = async (email: string | null, stripeSessionId?: string | null) => {
    if (!stripeSessionId) {
      console.log('[SpaceRuntime] No session_id in URL — skipping Purchase event (cannot confirm payment)');
      return;
    }

    let amount: number | undefined;
    let currency: string | undefined;

    try {
      const baseUrl = window.location.origin;
      const resp = await fetch(`${baseUrl}/api/payments/status/${stripeSessionId}`, {
        headers: { 'X-App-Id': getPaymentAppId(spaceId) },
      });
      if (!resp.ok) {
        console.warn(`[SpaceRuntime] Failed to verify payment status (HTTP ${resp.status}) — skipping Purchase event`);
        return;
      }

      const data = await resp.json();

      if (!data.countsAsPurchase) {
        console.log(`[SpaceRuntime] Skipping Purchase event — session not qualified (status: ${data.status}, paymentStatus: ${data.paymentStatus}, mode: ${data.mode})`);
        return;
      }

      amount = (data.purchaseValueCents ?? 0) / 100;
      currency = data.currency || 'usd';
      console.log(`[SpaceRuntime] Purchase qualified: ${amount} ${currency.toUpperCase()} (mode: ${data.mode}, paymentStatus: ${data.paymentStatus})`);

      await trackEvent('purchase', {
        value: amount,
        currency,
        stripeSessionId,
        mode: data.mode,
        paymentStatus: data.paymentStatus,
      });
    } catch (e) {
      console.warn('[SpaceRuntime] Error fetching payment status — skipping Purchase event', e);
      return;
    }

    if (!firePurchaseEvent(email, amount, currency, stripeSessionId)) {
      const maxRetries = 5;
      const delays = [100, 200, 400, 800, 1600];
      const retryWithBackoff = (attempt: number) => {
        if (attempt >= maxRetries) return;
        setTimeout(() => {
          if (!firePurchaseEvent(email, amount, currency, stripeSessionId)) {
            retryWithBackoff(attempt + 1);
          }
        }, delays[attempt]);
      };
      retryWithBackoff(0);
    }
  };

  useEffect(() => {
    if (!sessionId) return;

    const cachedSub = localStorage.getItem(`space_subscription_${spaceId}`);
    if (cachedSub) {
      try {
        setSubscription(JSON.parse(cachedSub));
      } catch {}
    }

    const params = new URLSearchParams(window.location.search);
    const isReturnFromStripe = params.has('subscription_success') || params.has('payment_success');
    const stripeSessionId = params.get('session_id');

    if (isReturnFromStripe) {
      console.log('[SpaceRuntime] Detected return from Stripe, refreshing subscription with retry...');

      if (!purchaseFiredRef.current) {
        purchaseFiredRef.current = true;
        const email = getEmailFromSession();
        firePurchaseEventWithRetry(email, stripeSessionId);
      }

      const retryDelays = [2000, 5000, 10000];
      let attempt = 0;
      const tryRefresh = async () => {
        await refreshSubscription();
        const sub = JSON.parse(localStorage.getItem(`space_subscription_${spaceId}`) || '{}');
        if (sub.status && sub.status !== 'active' && sub.status !== 'manual_override' && sub.status !== 'loading' && attempt < retryDelays.length - 1) {
          attempt++;
          console.log(`[SpaceRuntime] Subscription not yet active (${sub.status}), retrying in ${retryDelays[attempt]}ms...`);
          setTimeout(tryRefresh, retryDelays[attempt]);
        }
      };
      setTimeout(tryRefresh, retryDelays[0]);

      const url = new URL(window.location.href);
      url.searchParams.delete('subscription_success');
      url.searchParams.delete('payment_success');
      url.searchParams.delete('plan');
      url.searchParams.delete('session_id');
      window.history.replaceState({}, '', url.toString());
    } else {
      refreshSubscription();
    }
  }, [sessionId, spaceId, refreshSubscription]);

  const value: SpaceRuntimeContextValue = {
    mode,
    spaceId,
    sessionId,
    setSessionId,
    visitorId,
    isBootstrappingSession,
    config,
    isLoading,
    error,
    readFile,
    readTemplateFile,
    writeFile,
    listFiles,
    trackEvent,
    refetchConfig: fetchConfig,
    subscription,
    subscriptionReady,
    updateSubscription,
    refreshSubscription,
    checkAppAccess,
    sessionMetadata,
    userRole,
    checkRoleAccess,
    waitForResolvedSession,
  };

  return (
    <SpaceRuntimeContext.Provider value={value}>
      {children}
    </SpaceRuntimeContext.Provider>
  );
}

export function useSpaceRuntime() {
  const context = useContext(SpaceRuntimeContext);
  
  if (!context) {
    throw new Error('useSpaceRuntime must be used within SpaceRuntimeProvider');
  }
  
  return context;
}

export function useSubscription() {
  const { subscription, subscriptionReady, updateSubscription, refreshSubscription, checkAppAccess, mode } = useSpaceRuntime();
  
  const isPremium = mode === 'entrepreneur' || (subscription?.status === 'active') || !!subscription?.manualOverride;
  const isTrial = (subscription?.status === 'trialing' || subscription?.status === 'trial') && !subscription?.trialExpired;
  const isExpired = subscription?.status === 'trial_expired' || subscription?.status === 'canceled';
  const loading = !subscriptionReady || (!!subscription && subscription.status === 'loading');
  
  return {
    subscription,
    isPremium,
    isTrial,
    isExpired,
    loading,
    trialDaysRemaining: subscription?.trialDaysRemaining || 0,
    updateSubscription,
    refreshSubscription,
    checkAppAccess,
  };
}
