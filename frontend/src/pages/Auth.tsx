import React, { useEffect, useRef, useState } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { Fingerprint, Globe } from 'lucide-react';
import { Alert, Button, Input, Select, LoadingButton } from '../components/antigravity';
import type { UserRole } from '../types';
import { useAuth } from '../hooks/useAuth';
import { getApiErrorMessage, getClientTransportErrorMessage } from '../utils/apiDetail';
import { buildRoute, homeRouteKeyForRole } from '../navigation/routes';
import { getAuthItem } from '../utils/demo';
import { supabase } from '../api/supabase';
import { clearAutofillResidueIfStale } from '../utils/clearAutofillResidue';
import { env } from '../config/env';
import { swallow } from '../lib/errorTracking';
import { GlobeNetwork } from '../components/auth/GlobeNetwork';
import { useAuthPageConfig } from '../hooks/useAuthPageConfig';

// ── Icons ─────────────────────────────────────────────────────────────────────

const EyeIcon: React.FC<{ open: boolean }> = ({ open }) =>
  open ? (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
      strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
    </svg>
  ) : (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
      strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.522 10.522 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88" />
    </svg>
  );

const GoogleIcon = () => (
  <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24">
    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
  </svg>
);

const MicrosoftIcon = () => (
  <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24">
    <path fill="#f25022" d="M1 1h10.5v10.5H1z"/>
    <path fill="#00a4ef" d="M12.5 1H23v10.5H12.5z"/>
    <path fill="#7fba00" d="M1 12.5h10.5V23H1z"/>
    <path fill="#ffb900" d="M12.5 12.5H23V23H12.5z"/>
  </svg>
);

// ── Main component ────────────────────────────────────────────────────────────

export const Auth: React.FC = () => {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<UserRole>('EMPLOYEE');
  const [name, setName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [companySize, setCompanySize] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login, register, loginWithPasskey } = useAuth();
  const authInFlight = useRef(false);
  const { config: authPageConfig } = useAuthPageConfig();

  // Invite flow
  const [inviteMode, setInviteMode] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [invitePassword, setInvitePassword] = useState('');
  const [inviteConfirm, setInviteConfirm] = useState('');
  const [showInvitePassword, setShowInvitePassword] = useState(false);
  const [inviteDone, setInviteDone] = useState(false);
  // Friendly banner for an expired / already-used / malformed auth link.
  const [linkError, setLinkError] = useState('');

  useEffect(() => {
    const hash = window.location.hash;
    if (!hash) return;
    const params = new URLSearchParams(hash.slice(1));

    // Reused / expired / malformed link: Supabase has already consumed the OTP and
    // bounces back with an error fragment instead of tokens. Surface a friendly
    // banner above the sign-in form rather than the bare login screen.
    if (params.get('error')) {
      const code = params.get('error_code');
      setLinkError(
        code === 'otp_expired'
          ? 'This invite link has expired or has already been used. Ask your admin to send a new invite, or contact support if you keep seeing this.'
          : 'This sign-in link is invalid or has already been used. Ask your admin to send a new invite, or contact support if you keep seeing this.'
      );
      window.history.replaceState(null, '', '/auth?mode=login');
      return;
    }

    const accessToken = params.get('access_token');
    const refreshToken = params.get('refresh_token');
    const type = params.get('type');
    if (!accessToken || !refreshToken) return;

    // Only invite/recovery land in the set-password flow. Switch UI state up front
    // so the existing-session redirect (below) is suppressed before setSession resolves.
    if (type === 'invite' || type === 'recovery') setInviteMode(true);

    void supabase.auth
      .setSession({ access_token: accessToken, refresh_token: refreshToken })
      .then(({ data, error }) => {
        if (error) {
          setInviteMode(false);
          setLinkError(
            'We could not validate your link — it may have expired. Ask your admin to send a new invite.'
          );
          return;
        }
        if (data.user?.email) setInviteEmail(data.user.email);
      })
      .catch(() => {
        setInviteMode(false);
        setLinkError('We could not validate your link. Ask your admin to send a new invite.');
      });
    window.history.replaceState(null, '', '/auth?mode=login');
  }, []);

  // Suppress the existing-session redirect while an auth link is being processed.
  // Read live each render: the effect clears the hash, but inviteMode/linkError then
  // carry the suppression so a pre-existing session can't hijack the invite flow.
  const hashHasAuthPayload =
    typeof window !== 'undefined' && /[#&](access_token|error)=/.test(window.location.hash);

  const sessionExpired = searchParams.get('reason') === 'session_expired';

  useEffect(() => {
    const nextMode = searchParams.get('mode');
    if (nextMode === 'register' || nextMode === 'login') setMode(nextMode);
    // Pre-fill email from ?email= (assignment invite link). Only seed when the
    // field is still empty so we never clobber what the user is typing.
    const qpEmail = searchParams.get('email');
    if (qpEmail) setEmail((prev) => prev || qpEmail);
  }, [searchParams]);

  // ── Handlers ────────────────────────────────────────────────────────────────

  const handleSetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (authInFlight.current || isLoading) return;
    if (invitePassword.length < 8 || !/[A-Za-z]/.test(invitePassword) || !/[0-9]/.test(invitePassword)) {
      setError('Password must be at least 8 characters and include a letter and a number.');
      return;
    }
    if (invitePassword !== inviteConfirm) { setError('Passwords do not match.'); return; }
    setError('');
    authInFlight.current = true;
    setIsLoading(true);
    try {
      const { error: supaErr } = await supabase.auth.updateUser({ password: invitePassword });
      if (supaErr) throw new Error(supaErr.message);
      await login({ identifier: inviteEmail, password: invitePassword });
      setInviteDone(true);
      const key = homeRouteKeyForRole(getAuthItem('relopass_role'));
      navigate(buildRoute(key), { replace: true });
    } catch (err) {
      setError((err as { message?: string })?.message ?? 'Failed to set password. The invite link may have expired.');
    } finally {
      authInFlight.current = false;
      setIsLoading(false);
    }
  };

  const exitInviteMode = () => {
    setInviteMode(false);
    setError('');
    setInvitePassword('');
    setInviteConfirm('');
  };

  const doLogin = async (id: string, pw: string) => {
    if (authInFlight.current || isLoading) return;
    setError('');
    authInFlight.current = true;
    setIsLoading(true);
    try {
      await login({ identifier: id, password: pw });
    } catch (err) {
      const transport = getClientTransportErrorMessage(err);
      const msg = transport ?? getApiErrorMessage(err, 'Login failed. Check your email and password, then try again.');
      try { localStorage.setItem('debug_last_auth_error', msg); } catch (e) { swallow(e, 'Auth: persist debug breadcrumb'); }
      setError(msg);
    } finally {
      authInFlight.current = false;
      setIsLoading(false);
    }
  };

  const handleLogin = (e: React.FormEvent) => { e.preventDefault(); void doLogin(identifier, password); };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (authInFlight.current || isLoading) return;
    setError('');
    const hasUsername = username.trim().length > 0;
    const hasEmail = email.trim().length > 0;
    if (!hasUsername && !hasEmail) { setError('Provide a username or email.'); return; }
    if (hasUsername && !/^[A-Za-z0-9_]{3,30}$/.test(username.trim())) {
      setError('Username must be 3–30 characters, alphanumeric or underscore.'); return;
    }
    if (hasEmail && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) {
      setError('Provide a valid email address.'); return;
    }
    if (!password.trim()) { setError('Password is required.'); return; }
    authInFlight.current = true;
    setIsLoading(true);
    try {
      await register({
        username: hasUsername ? username.trim() : undefined,
        email: hasEmail ? email.trim() : undefined,
        password, role,
        name: name.trim() || undefined,
        company_name: role !== 'EMPLOYEE' ? (companyName.trim() || undefined) : undefined,
        company_size: role === 'HR' ? (companySize || undefined) : undefined,
      });
    } catch (err) {
      const e = err as { response?: { data?: { detail?: unknown }; status?: number } };
      const transport = getClientTransportErrorMessage(err);
      if (transport) { try { localStorage.setItem('debug_last_auth_error', transport); } catch (e) { swallow(e, 'Auth: persist debug breadcrumb'); } setError(transport); return; }
      const detail = e.response?.data?.detail;
      let msg: string;
      const detailStr = (d: unknown): string => Array.isArray(d) ? ((d[0] as { msg?: string })?.msg || JSON.stringify(d)) : (typeof d === 'string' ? d : JSON.stringify(d));
      if (e.response?.status === 400 && detail && typeof detail === 'object' && !Array.isArray(detail)) {
        const code = (detail as { code?: string }).code;
        const message = (detail as { message?: string }).message;
        msg = (code === 'AUTH_EMAIL_TAKEN' || code === 'AUTH_USERNAME_TAKEN') && message ? message : (message ?? 'Registration failed.');
      } else if (e.response?.status === 400 && detail) {
        msg = detailStr(detail);
      } else if (!e.response) {
        msg = 'Cannot reach the server. Check your connection and try again.';
      } else {
        msg = detail ? (detailStr(detail)) : 'Registration failed. Try again.';
      }
      try { localStorage.setItem('debug_last_auth_error', msg); } catch (e) { swallow(e, 'Auth: persist debug breadcrumb'); }
      setError(msg);
    } finally {
      authInFlight.current = false;
      setIsLoading(false);
    }
  };

  const handleDemoLogin = (demoRole: 'admin' | 'hr' | 'employee') => {
    // Defaults match the credentials seeded by
    // backend/scripts/seed_testingapril_accounts.py. Override per-env via
    // VITE_DEMO_*_USER / VITE_DEMO_*_PASS. If you haven't run the seed
    // script yet, login will fail with "Invalid username or email."
    const credMap: Record<string, { user: string; pass: string }> = {
      // SECURITY (UIAUDIT-G2): admin is the platform SUPERUSER (full CMS, all tenants).
      // Never embed a working admin password in the shipped bundle — no hardcoded
      // fallback. The dev-only admin one-click (below) relies on VITE_DEMO_ADMIN_PASS
      // being set locally; in production the admin button isn't rendered at all.
      admin:    { user: (import.meta.env.VITE_DEMO_ADMIN_USER as string | undefined) ?? 'admin@relopass.com',        pass: (import.meta.env.VITE_DEMO_ADMIN_PASS as string | undefined) ?? '' },
      hr:       { user: (import.meta.env.VITE_DEMO_HR_USER as string | undefined)    ?? 'hr@testingapril.com',       pass: (import.meta.env.VITE_DEMO_HR_PASS as string | undefined)    ?? '' },
      employee: { user: (import.meta.env.VITE_DEMO_EMP_USER as string | undefined)   ?? 'employee@testingapril.com', pass: (import.meta.env.VITE_DEMO_EMP_PASS as string | undefined)   ?? '' },
    };
    const creds = credMap[demoRole];
    if (!creds) return;
    const { user, pass } = creds;
    setIdentifier(user);
    setPassword(pass);
    setMode('login');
    void doLogin(user, pass);
  };

  const handleGoogleSSO = () => {
    void supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/auth?mode=login` },
    });
  };

  // [AIQ-1491] Passwordless passkey sign-in (POC). signInWithPasskey() runs the WebAuthn
  // ceremony (Face ID / Touch ID / Windows Hello / security key) → Supabase session →
  // exchanged for a ReloPass token inside loginWithPasskey. Password login is untouched.
  const handlePasskeySignIn = async () => {
    setError('');
    setIsLoading(true);
    try {
      await loginWithPasskey();
    } catch (err) {
      // Two different error shapes reach here. The token-exchange leg is axios
      // (detail in err.response.data.detail); the WebAuthn leg is a Supabase
      // AuthError, which has no `.response` at all — so getApiErrorMessage
      // silently yields its fallback. Fall back to err.message before the
      // generic hint, or a project with WebAuthn disabled reports "register a
      // passkey from Settings first" — advice that sends the user to a second
      // button that fails for the very same reason.
      const supabaseMessage =
        typeof (err as { message?: unknown })?.message === 'string'
          ? (err as { message: string }).message
          : '';
      setError(
        getApiErrorMessage(err, '') ||
          supabaseMessage ||
          'Passkey sign-in failed. Use your password instead.',
      );
    } finally {
      setIsLoading(false);
    }
  };

  // ── Redirect if already logged in ───────────────────────────────────────────
  // Skip while an invite/recovery link is being processed (inviteMode), while an
  // expired-link banner is showing (linkError), or before the mount effect has run
  // on a hash-bearing URL (hashHasAuthPayload) — otherwise a pre-existing session
  // would hijack the invite acceptance flow.
  if (getAuthItem('relopass_token') && !inviteMode && !linkError && !hashHasAuthPayload) {
    const key = homeRouteKeyForRole(getAuthItem('relopass_role'));
    if (key !== 'landing') return <Navigate to={buildRoute(key)} replace />;
  }

  // ── Invite flow ──────────────────────────────────────────────────────────────
  if (inviteMode) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
        <div className="w-full max-w-sm bg-white rounded-2xl shadow-lg p-8">
          {inviteDone ? (
            <div className="text-center space-y-3">
              <p className="text-3xl">✓</p>
              <p className="font-semibold text-[#0b2b43]">Password set — you&apos;re in!</p>
              <p className="text-sm text-slate-500">Redirecting you to your dashboard…</p>
            </div>
          ) : (
            <form onSubmit={handleSetPassword} className="space-y-5">
              <div>
                <h2 className="text-lg font-semibold text-[#0b2b43]">Set your password</h2>
                <p className="text-sm text-slate-500 mt-1">
                  Welcome to ReloPass. Choose a password to activate your account.
                </p>
              </div>
              {error && <Alert variant="error">{error}</Alert>}
              {inviteEmail && (
                <div>
                  <span className="block text-sm font-medium text-slate-700 mb-1.5">Your email</span>
                  <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3.5 py-2.5">
                    <span className="text-sm text-slate-700 truncate">{inviteEmail}</span>
                    <span className="ml-auto inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-600 border border-emerald-200">
                      ✓ Verified
                    </span>
                  </div>
                </div>
              )}
              <div className="relative">
                <Input type={showInvitePassword ? 'text' : 'password'} value={invitePassword}
                  onChange={setInvitePassword}
                  label="New password" placeholder="At least 8 characters, with a letter and a number"
                  autoComplete="new-password" fullWidth />
                <Button type="button" variant="ghost" onClick={() => setShowInvitePassword((p) => !p)}
                  aria-label={showInvitePassword ? 'Hide password' : 'Show password'}
                  className="absolute right-3 top-8 !p-0 !text-slate-500 hover:!text-slate-600 hover:!bg-transparent transition-colors">
                  <EyeIcon open={showInvitePassword} />
                </Button>
              </div>
              <Input type={showInvitePassword ? 'text' : 'password'} value={inviteConfirm}
                onChange={setInviteConfirm}
                label="Confirm password" placeholder="Repeat your password"
                autoComplete="new-password" fullWidth />
              <LoadingButton type="submit" fullWidth loading={isLoading}
                loadingLabel="Setting password…" disabled={!invitePassword || !inviteConfirm}>
                Set password and sign in
              </LoadingButton>
              <Button type="button" variant="ghost" fullWidth onClick={exitInviteMode}
                className="block text-center text-sm !p-0 !font-normal !text-slate-500 hover:!text-slate-700 hover:!bg-transparent transition-colors">
                Sign in with existing account
              </Button>
            </form>
          )}
        </div>
      </main>
    );
  }

  // ── Main layout ──────────────────────────────────────────────────────────────
  return (
    <main className="min-h-screen flex overflow-hidden">

      {/* ── Left: dark globe panel ── */}
      <div className="hidden lg:flex lg:flex-col lg:w-[58%] relative bg-[#061424] overflow-hidden select-none">

        {/* Header */}
        <div className="relative z-10 flex items-center gap-2.5 px-8 pt-7">
          <img src="/relopass-logo.png" width={122} height={128} alt="ReloPass" className="h-7 w-auto"
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
          <span className="text-white font-semibold text-base tracking-tight">ReloPass</span>
          {/* eslint-disable-next-line local/no-low-contrast-text -- light-on-dark: inside the bg-[#061424] hero panel. slate-400 is ~5.6:1 here; slate-500 measures 3.5-3.9:1 (axe). Darkening this REDUCES contrast. */}
          <span className="text-slate-400 text-base">· Platform</span>
        </div>

        {/* Globe */}
        <div className="flex-1 relative">
          <div className="absolute inset-0">
            <GlobeNetwork config={authPageConfig} />
          </div>
        </div>

        {/* What the platform does. Deliberately makes no volume, corridor-count or
            customer claim: we are pre-launch, so any figure here would be invented.
            See AIQ-1574 — the previous ticker named a fictitious customer and badged
            him LIVE. Do not reintroduce counts without a real data source. */}
        <div className="relative z-10 px-6 pb-7">
          <div className="rounded-xl bg-white/5 border border-white/10 backdrop-blur-sm px-5 py-4">
            {/* eslint-disable-next-line local/no-low-contrast-text -- light-on-dark: inside the bg-[#061424] hero panel. slate-400 is ~5.6:1 here; slate-500 measures 3.5-3.9:1 (axe). Darkening this REDUCES contrast. */}
            <p className="text-[10px] font-semibold tracking-widest text-slate-400 uppercase mb-2">
              Built for cross-border moves
            </p>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center shrink-0">
                <Globe className="w-4 h-4 text-slate-500" aria-hidden="true" />
              </div>
              <div>
                <p className="text-sm text-white font-medium">
                  One record per relocation
                </p>
                {/* eslint-disable-next-line local/no-low-contrast-text -- light-on-dark: inside the bg-[#061424] hero panel. slate-400 is ~5.6:1 here; slate-500 measures 3.5-3.9:1 (axe). Darkening this REDUCES contrast. */}
                <p className="text-xs text-slate-400">
                  Guided intake, your policy applied automatically, and suppliers in one place.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Right: auth panel ── */}
      <div className="flex-1 flex flex-col justify-center px-8 py-12 bg-white overflow-y-auto">
        <div className="w-full max-w-sm mx-auto">

          {/* Mobile logo */}
          <div className="flex items-center gap-2 mb-8 lg:hidden">
            <img src="/relopass-logo.png" width={122} height={128} alt="ReloPass" className="h-6 w-auto"
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
            <span className="font-semibold text-[#0b2b43]">ReloPass</span>
          </div>

          {/* Mode tabs */}
          <div className="flex rounded-lg bg-slate-100 p-1 mb-7">
            {(['login', 'register'] as const).map((m) => (
              <Button key={m} type="button" variant="ghost" onClick={() => { setMode(m); setError(''); }}
                className={`flex-1 !py-1.5 text-sm !rounded-md transition-all ${
                  // slate-500 on the bg-slate-100 track is 4.34:1 — under AA. slate-600 is
                  // 6.92:1 there. (Reported separately as the "Create account tab toggle"
                  // contrast bug.) The selected tab sits on white and is unaffected.
                  mode === m ? '!bg-white shadow-sm !text-slate-900' : '!text-slate-600 hover:!text-slate-800 hover:!bg-transparent'
                }`}>
                {m === 'login' ? 'Sign in' : 'Create account'}
              </Button>
            ))}
          </div>

          {/* Expired / already-used invite link banner (dismissable) */}
          {linkError && (
            <Alert variant="warning" className="mb-5">
              <div className="flex items-start gap-2">
                <span className="flex-1">{linkError}</span>
                <Button type="button" variant="ghost" onClick={() => setLinkError('')}
                  aria-label="Dismiss" className="shrink-0 !p-0 !font-normal !text-current opacity-60 hover:opacity-100 hover:!bg-transparent">
                  ✕
                </Button>
              </div>
            </Alert>
          )}

          {/* Session expired banner */}
          {sessionExpired && (
            <Alert variant="warning" className="mb-5">
              Your session has expired — please sign in again.
            </Alert>
          )}

          {/* Heading */}
          <div className="mb-6">
            {mode === 'login' ? (
              <>
                <h1 className="text-2xl font-semibold text-slate-900">Sign in to ReloPass</h1>
                <p className="text-sm text-slate-500 mt-1">Welcome back. Pick up where you left off.</p>
              </>
            ) : (
              <>
                <h1 className="text-2xl font-semibold text-slate-900">Create your account</h1>
                <p className="text-sm text-slate-500 mt-1">Join your team on ReloPass.</p>
              </>
            )}
          </div>

          {/* Reserved slot. The panel above is `flex flex-col justify-center`, so inserting
              an Alert re-centres the whole column: the heading rises and the form drops,
              measured at 34px on the password field — the user's cursor moves out from
              under them mid-typing. Holding the space means the error appears in place and
              nothing else moves. min-h matches the rendered Alert + mb-4. */}
          <div className="min-h-[3.75rem]">
            {error && <Alert variant="error" className="mb-4">{error}</Alert>}
          </div>

          {/* ── Login form ── */}
          {mode === 'login' && (
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label htmlFor="auth-login-identifier" className="block text-sm font-medium text-slate-700 mb-1.5">
                  Email
                </label>
                <Input unstyled
                  id="auth-login-identifier"
                  type="text" value={identifier}
                  onChange={(v) => setIdentifier(v)}
                  placeholder="you@company.com" autoComplete="username"
                  className="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-[#0b2b43]/25 focus:border-[#0b2b43] transition-colors"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label htmlFor="auth-login-password" className="block text-sm font-medium text-slate-700">Password</label>
                  <Button type="button" variant="ghost" className="text-xs !p-0 !font-normal !text-slate-500 hover:!text-slate-600 hover:!bg-transparent transition-colors">
                    Forgot?
                  </Button>
                </div>
                <div className="relative">
                  <Input unstyled
                    id="auth-login-password"
                    type={showPassword ? 'text' : 'password'} value={password}
                    onChange={(v) => setPassword(v)}
                    // AIQ-1628: drop stale passive-autofill residue (a value the
                    // browser dropped into the DOM without an onChange, so our
                    // `password` state is still empty) before the user types —
                    // otherwise the keystrokes concatenate onto the previous
                    // persona's password. A manager-chosen fill sets state via
                    // onChange, so this leaves it untouched.
                    onFocus={(e) => clearAutofillResidueIfStale(password, e.currentTarget)}
                    placeholder="••••••••" autoComplete="current-password"
                    className="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 pr-10 text-sm text-slate-900 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-[#0b2b43]/25 focus:border-[#0b2b43] transition-colors"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => setShowPassword((p) => !p)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    className="absolute right-3 top-1/2 -translate-y-1/2 inline-flex h-6 w-6 items-center justify-center !p-0 !text-slate-500 hover:!text-slate-600 hover:!bg-transparent transition-colors">
                    <EyeIcon open={showPassword} />
                  </Button>
                </div>
              </div>

              <Button type="submit" variant="primary" fullWidth disabled={isLoading || !identifier || !password}
                className="!py-2.5 !text-sm !font-semibold">
                {isLoading ? 'Signing in…' : 'Sign in'}
              </Button>
            </form>
          )}

          {/* ── Register form ── */}
          {mode === 'register' && (
            <>
              {role === 'EMPLOYEE' && (
                <Alert variant="info" title="Signing up with a work email" className="mb-4">
                  <p className="text-sm text-slate-700 leading-relaxed">
                    HR can add your work email to a case before you register. &quot;Email already in use&quot; means that address is already on ReloPass — use the same email HR used.
                  </p>
                </Alert>
              )}
              <form onSubmit={handleRegister} className="space-y-4">
                <Input value={name} onChange={setName} label="Full name (optional)" placeholder="Alex Johnson" fullWidth />
                <Input value={username} onChange={setUsername} label="Username"
                  placeholder="username (3–30 chars)" autoComplete="username" fullWidth />
                <Input type="email" value={email} onChange={setEmail} label="Email"
                  placeholder="you@example.com" autoComplete="email" fullWidth />
                <div className="relative">
                  <Input type={showPassword ? 'text' : 'password'} value={password}
                    onChange={setPassword} label="Password"
                    placeholder="Create a password" autoComplete="new-password" fullWidth />
                  <Button type="button" variant="ghost" onClick={() => setShowPassword((p) => !p)}
                    className="absolute right-3 top-8 !p-0 !text-slate-500 hover:!text-slate-600 hover:!bg-transparent transition-colors">
                    <EyeIcon open={showPassword} />
                  </Button>
                </div>
                {/* AIQ-829 — one routing question bifurcates onboarding. ADMIN is
                    intentionally not self-selectable: @relopass.com allowlisted users
                    are auto-promoted to admin on login (backend auth_deps._is_admin_user). */}
                <div>
                  <span id="signup-routing-label" className="block text-sm font-medium text-slate-700 mb-2">I am…</span>
                  <div role="radiogroup" aria-labelledby="signup-routing-label" className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {([
                      { value: 'HR' as UserRole, icon: '🏢', title: 'An HR or mobility manager', sub: 'Set up policies and manage relocations' },
                      { value: 'EMPLOYEE' as UserRole, icon: '✈️', title: 'An employee being relocated', sub: 'Track your move and tasks' },
                    ]).map((opt) => {
                      const selected = role === opt.value;
                      return (
                        <Button unstyled key={opt.value} type="button" role="radio" aria-checked={selected}
                          onClick={() => setRole(opt.value)}
                          className={`p-4 text-left rounded-xl border-2 transition-colors cursor-pointer ${selected ? 'border-[#0b2b43] bg-slate-50' : 'border-slate-200 bg-white hover:border-slate-300'}`}>
                          <span aria-hidden="true" className="block text-2xl mb-1">{opt.icon}</span>
                          <span className="block text-sm font-semibold text-slate-900">{opt.title}</span>
                          <span className="block text-xs text-slate-500 mt-0.5">{opt.sub}</span>
                        </Button>
                      );
                    })}
                  </div>
                </div>
                {role === 'HR' && (
                  <>
                    <Input value={companyName} onChange={setCompanyName} label="Company"
                      placeholder="Your company name" fullWidth />
                    <Select value={companySize} onChange={setCompanySize} label="Company size"
                      options={[
                        { value: '', label: 'Select company size…' },
                        { value: '1-50', label: '1–50 employees' },
                        { value: '51-500', label: '51–500 employees' },
                        { value: '500+', label: '500+ employees' },
                      ]} fullWidth />
                  </>
                )}
                <LoadingButton type="submit" fullWidth loading={isLoading}
                  loadingLabel="Creating account…"
                  disabled={!password.trim() || (!username.trim() && !email.trim())}>
                  Create account
                </LoadingButton>
              </form>
            </>
          )}

          {/* ── SSO + create account link ── */}
          {mode === 'login' && (
            <>
              <div className="flex items-center gap-3 my-5">
                <div className="flex-1 h-px bg-slate-200" />
                <span className="text-xs text-slate-500">or</span>
                <div className="flex-1 h-px bg-slate-200" />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <Button type="button" variant="ghost" onClick={handleGoogleSSO}
                  className="flex items-center justify-center gap-2 !py-2.5 border border-slate-200 text-sm !text-slate-700 hover:!bg-slate-50 transition-colors">
                  <GoogleIcon /> Google
                </Button>
                <Button type="button" variant="ghost"
                  className="flex items-center justify-center gap-2 !py-2.5 border border-slate-200 text-sm !text-slate-700 hover:!bg-slate-50 transition-colors">
                  <MicrosoftIcon /> Microsoft SSO
                </Button>
              </div>

              {/* [AIQ-1491] Passwordless passkey sign-in (POC). Dark by default:
                  passkeys also need the WebAuthn toggle enabled on the Supabase
                  project, and until that lands every click here dead-ends. Set
                  VITE_ENABLE_PASSKEYS=true to light it up on staging. */}
              {env.enablePasskeys && (
                <Button type="button" variant="ghost" onClick={() => void handlePasskeySignIn()}
                  disabled={isLoading} fullWidth
                  className="flex items-center justify-center gap-2 !py-2.5 mt-3 border border-slate-200 text-sm !text-slate-700 hover:!bg-slate-50 transition-colors">
                  <Fingerprint className="w-4 h-4" /> Sign in with a passkey
                </Button>
              )}

              <p className="text-center text-sm text-slate-500 mt-5">
                New to ReloPass?{' '}
                <Button type="button" variant="ghost" onClick={() => { setMode('register'); setError(''); }}
                  className="!p-0 text-[#0b2b43] font-medium hover:!bg-transparent hover:underline">
                  Create an account →
                </Button>
              </p>
            </>
          )}

          {/* ── One-click demo (DEV builds ONLY) ──
              SECURITY (UIAUDIT-G2 + secrets review): the entire one-click demo is gated
              behind import.meta.env.DEV, which Vite statically evaluates to false in
              production — so the demo buttons, handleDemoLogin call sites, and any demo
              credentials are dead-code-eliminated from the prod bundle. No demo creds
              (admin, HR, or employee) ship to the public site. */}
          {import.meta.env.DEV && (
          <div className="mt-7 pt-6 border-t border-slate-100">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-widest">One-click demo</span>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-600 border border-amber-200">
                DEV ONLY
              </span>
            </div>
            <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(3, minmax(0, 1fr))' }}>
              {(['admin', 'hr', 'employee'] as const).map((r) => (
                <Button key={r} type="button" variant="ghost" onClick={() => handleDemoLogin(r)} disabled={isLoading}
                  className="!px-0 border border-slate-200 !text-xs !text-slate-600 hover:!bg-slate-50 hover:border-slate-300 capitalize transition-colors">
                  {r === 'admin' ? 'Admin' : r === 'hr' ? 'HR' : 'Employee'}
                </Button>
              ))}
            </div>
          </div>
          )}

        </div>
      </div>
    </main>
  );
};
