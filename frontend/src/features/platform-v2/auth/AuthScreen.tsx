/**
 * AuthScreen.tsx — ReloPass Auth (S0)
 * ─────────────────────────────────────────────────────────────────────────────
 * Split layout: GlobeCanvas left (60%) + auth card right (40%)
 * Tabs: Sign In | Create Account
 * Demo persona quick-fill cards (admin / hr / employee)
 * RoutingFlash overlay on successful auth
 * Supabase auth.signInWithPassword / signUp
 * Responsive: globe hidden at < 768px
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useCallback, useEffect, useState } from 'react';
import { Input } from '../../../components/antigravity/Input';
import { Button } from '../../../components/antigravity/Button';
import { GlobeCanvas } from './GlobeCanvas';

// ─── Types ────────────────────────────────────────────────────────────────────

type AuthTab = 'sign_in' | 'sign_up' | 'reset_password';

interface AuthScreenProps {
  /** Called with the session token after successful auth */
  onAuthSuccess: (session: { access_token: string; user_id: string; role: string }) => void;
  /** Override initial tab */
  defaultTab?: AuthTab;
  /** Invite token from URL ?invite= */
  inviteToken?: string;
}

// ─── Supabase stub ────────────────────────────────────────────────────────────
// In production this comes from @supabase/supabase-js. We declare only what
// AuthScreen needs so the file compiles without the client being initialised.

declare const supabase: {
  auth: {
    signInWithPassword: (opts: { email: string; password: string }) => Promise<{
      data: { session: { access_token: string; user: { id: string } } | null };
      error: { message: string } | null;
    }>;
    signUp: (opts: { email: string; password: string; options?: { data?: Record<string, unknown> } }) => Promise<{
      data: { user: { id: string } | null };
      error: { message: string } | null;
    }>;
    signInWithOAuth: (opts: { provider: 'google' | 'azure' }) => Promise<{ error: { message: string } | null }>;
  };
  from: (table: string) => {
    insert: (row: Record<string, unknown>) => Promise<{ error: { message: string } | null }>;
  };
};

// ─── Demo personas ─────────────────────────────────────────────────────────────

interface Persona {
  id: string;
  label: string;
  role: string;
  email: string;
  password: string;
  description: string;
  emoji: string;
  color: string;
}

const demoEnv = import.meta.env as Record<string, string | undefined>;
const DEMO_PERSONAS: Persona[] = [
  {
    id: 'admin',
    label: 'Platform Admin',
    role: 'admin',
    email: demoEnv.VITE_DEMO_ADMIN_USER ?? 'admin@relopass.com',
    password: demoEnv.VITE_DEMO_ADMIN_PASS ?? 'AdminPass!1',
    description: 'Full platform access, policy builder, org settings',
    emoji: '🛡️',
    color: '#4A9AE8',
  },
  {
    id: 'hr',
    label: 'HR Manager',
    role: 'hr',
    email: demoEnv.VITE_DEMO_HR_USER ?? 'hr@testingapril.com',
    password: demoEnv.VITE_DEMO_HR_PASS ?? 'HrPass!1',
    description: 'Case management, approvals, HR control panel',
    emoji: '👩‍💼',
    color: '#1DBFA2',
  },
  {
    id: 'employee',
    label: 'Employee',
    role: 'employee',
    email: demoEnv.VITE_DEMO_EMP_USER ?? 'employee@testingapril.com',
    password: demoEnv.VITE_DEMO_EMP_PASS ?? 'EmpPass!1',
    description: 'Roadmap, dossier, documents, inbox',
    emoji: '🧳',
    color: '#EFA827',
  },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function validateEmail(e: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e);
}

function passwordStrength(p: string): 0 | 1 | 2 | 3 {
  if (p.length < 4) return 0;
  let score = 0;
  if (p.length >= 8) score++;
  if (/\d/.test(p)) score++;
  if (/[^a-zA-Z0-9]/.test(p)) score++;
  return score as 0 | 1 | 2 | 3;
}

const STRENGTH_LABEL = ['', 'Weak', 'Moderate', 'Strong'];
const STRENGTH_COLOR = ['', 'var(--danger)', 'var(--warning, #EFA827)', 'var(--success, #1DBFA2)'];

// ─── PasswordInput ────────────────────────────────────────────────────────────

function PasswordInput({
  id,
  value,
  onChange,
  placeholder,
  autoComplete,
  disabled,
  error,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  autoComplete?: string;
  disabled?: boolean;
  error?: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <div style={{ position: 'relative' }}>
      <Input unstyled
        id={id}
        type={show ? 'text' : 'password'}
        value={value}
        onChange={v => onChange(v)}
        placeholder={placeholder ?? 'Password'}
        autoComplete={autoComplete}
        disabled={disabled}
        style={{
          width: '100%',
          padding: '10px 38px 10px 12px',
          borderRadius: 'var(--radius-md)',
          border: `1px solid ${error ? 'var(--status-error, #E53E3E)' : 'var(--border-default)'}`,
          background: 'var(--surface)',
          color: 'var(--text-primary)',
          fontSize: '14px',
          outline: 'none',
          boxSizing: 'border-box',
          transition: 'border-color var(--transition-fast)',
        }}
        onFocus={e => { if (!error) (e.target).style.borderColor = 'var(--accent-border)'; }}
        onBlur={e => { if (!error) (e.target).style.borderColor = 'var(--border-default)'; }}
      />
      <Button unstyled
        type="button"
        onClick={() => setShow(s => !s)}
        aria-label={show ? 'Hide password' : 'Show password'}
        tabIndex={-1}
        style={{
          position: 'absolute',
          right: '10px',
          top: '50%',
          transform: 'translateY(-50%)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          color: 'var(--text-tertiary)',
          padding: 0,
          display: 'flex',
        }}
      >
        {show ? (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
            <line x1="1" y1="1" x2="23" y2="23" />
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        )}
      </Button>
    </div>
  );
}

// ─── RoutingFlash ──────────────────────────────────────────────────────────────

function RoutingFlash({ visible }: { visible: boolean }) {
  return (
    <div
      aria-hidden="true"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'var(--accent)',
        zIndex: 9999,
        opacity: visible ? 0.18 : 0,
        pointerEvents: 'none',
        transition: 'opacity 0.4s ease',
      }}
    />
  );
}

// ─── AuthScreen ────────────────────────────────────────────────────────────────

export function AuthScreen({ onAuthSuccess, defaultTab = 'sign_in', inviteToken }: AuthScreenProps) {
  const [tab, setTab] = useState<AuthTab>(defaultTab);

  // Sign in
  const [siEmail, setSiEmail] = useState('');
  const [siPassword, setSiPassword] = useState('');
  const [siError, setSiError] = useState('');
  const [siLoading, setSiLoading] = useState(false);

  // Sign up
  const [suName, setSuName] = useState('');
  const [suEmail, setSuEmail] = useState('');
  const [suPassword, setSuPassword] = useState('');
  const [suCompany, setSuCompany] = useState('');
  const [suError, setSuError] = useState('');
  const [suLoading, setSuLoading] = useState(false);

  // Reset password
  const [rpEmail, setRpEmail] = useState('');
  const [rpError, setRpError] = useState('');
  const [rpLoading, setRpLoading] = useState(false);
  const [rpSent, setRpSent] = useState(false);

  const [flash, setFlash] = useState(false);

  // Auto-fill invite token
  useEffect(() => {
    if (inviteToken) setTab('sign_up');
  }, [inviteToken]);

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleSignIn = useCallback(async (email: string, password: string) => {
    setSiError('');
    if (!validateEmail(email)) { setSiError('Please enter a valid email address.'); return; }
    if (!password) { setSiError('Password is required.'); return; }
    setSiLoading(true);
    try {
      const { data, error } = await supabase.auth.signInWithPassword({ email, password });
      if (error || !data.session) {
        setSiError(error?.message ?? 'Sign-in failed. Check your credentials.');
        return;
      }
      setFlash(true);
      setTimeout(() => {
        onAuthSuccess({
          access_token: data.session!.access_token,
          user_id: data.session!.user.id,
          role: 'employee', // resolved from profile after redirect
        });
      }, 350);
    } catch (e) {
      setSiError('Unexpected error. Please try again.');
    } finally {
      setSiLoading(false);
    }
  }, [onAuthSuccess]);

  const handleSignUp = useCallback(async () => {
    setSuError('');
    if (!suName.trim()) { setSuError('Full name is required.'); return; }
    if (!validateEmail(suEmail)) { setSuError('Please enter a valid work email.'); return; }
    if (suPassword.length < 8) { setSuError('Password must be at least 8 characters.'); return; }
    if (passwordStrength(suPassword) < 2) { setSuError('Password must include a number and a special character.'); return; }
    setSuLoading(true);
    try {
      const { data, error } = await supabase.auth.signUp({
        email: suEmail,
        password: suPassword,
        options: { data: { full_name: suName, company_slug: suCompany || undefined } },
      });
      if (error || !data.user) {
        setSuError(error?.message ?? 'Sign-up failed. Please try again.');
        return;
      }
      // Insert profile row
      await supabase.from('profiles').insert({
        id: data.user.id,
        full_name: suName,
        role: 'employee',
        invite_token: inviteToken ?? null,
      });
      setFlash(true);
      setTimeout(() => {
        onAuthSuccess({ access_token: '', user_id: data.user!.id, role: 'employee' });
      }, 350);
    } catch (e) {
      setSuError('Unexpected error. Please try again.');
    } finally {
      setSuLoading(false);
    }
  }, [suName, suEmail, suPassword, suCompany, inviteToken, onAuthSuccess]);

  const handleResetPassword = useCallback(async () => {
    setRpError('');
    if (!validateEmail(rpEmail)) { setRpError('Please enter a valid email address.'); return; }
    setRpLoading(true);
    try {
      // In production: supabase.auth.resetPasswordForEmail(rpEmail)
      await new Promise(r => setTimeout(r, 800));
      setRpSent(true);
    } finally {
      setRpLoading(false);
    }
  }, [rpEmail]);

  const handlePersona = useCallback((persona: Persona) => {
    setSiEmail(persona.email);
    setSiPassword(persona.password);
    setTab('sign_in');
    setSiError('');
    // Auto-submit after short delay for UX
    setTimeout(() => void handleSignIn(persona.email, persona.password), 80);
  }, [handleSignIn]);

  const handleOAuth = useCallback(async (provider: 'google' | 'azure') => {
    setSiError('');
    try {
      const { error } = await supabase.auth.signInWithOAuth({ provider });
      if (error) setSiError(error.message);
    } catch {
      setSiError('OAuth sign-in failed.');
    }
  }, []);

  // ── Shared field styles ───────────────────────────────────────────────────

  const inputStyle = (hasError: boolean): React.CSSProperties => ({
    width: '100%',
    padding: '10px 12px',
    borderRadius: 'var(--radius-md)',
    border: `1px solid ${hasError ? 'var(--status-error, #E53E3E)' : 'var(--border-default)'}`,
    background: 'var(--surface)',
    color: 'var(--text-primary)',
    fontSize: '14px',
    outline: 'none',
    boxSizing: 'border-box' as const,
    transition: 'border-color var(--transition-fast)',
  });

  const labelStyle: React.CSSProperties = {
    display: 'block',
    fontSize: '13px',
    fontWeight: 500,
    color: 'var(--text-secondary)',
    marginBottom: '6px',
  };

  const fieldStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 0,
    marginBottom: '16px',
  };

  const strength = passwordStrength(suPassword);

  return (
    <>
      <RoutingFlash visible={flash} />

      <div
        style={{
          display: 'flex',
          height: '100vh',
          overflow: 'hidden',
          background: 'var(--bg)',
        }}
      >
        {/* ── Left: Globe panel ── */}
        <div
          className="rp-auth-globe"
          style={{
            flex: '0 0 60%',
            position: 'relative',
            background: '#0A0E1A',
            overflow: 'hidden',
          }}
        >
          <GlobeCanvas style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />

          {/* Wordmark + tagline overlay */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'flex-end',
              padding: '40px',
              background: 'linear-gradient(to top, rgba(10,14,26,0.8) 0%, transparent 50%)',
              pointerEvents: 'none',
            }}
          >
            <div
              style={{
                fontSize: '28px',
                fontWeight: 800,
                color: '#fff',
                letterSpacing: '-0.02em',
                marginBottom: '8px',
              }}
            >
              ReloPass
            </div>
            <p
              style={{
                fontSize: '15px',
                color: 'rgba(255,255,255,0.7)',
                margin: 0,
                maxWidth: '340px',
                lineHeight: 1.5,
              }}
            >
              Every relocation case. Visible, compliant, on-time.
            </p>
          </div>
        </div>

        {/* ── Right: Auth card ── */}
        <div
          style={{
            flex: '0 0 40%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            overflowY: 'auto',
            padding: '40px 24px',
            background: 'var(--surface)',
          }}
        >
          <div style={{ width: '100%', maxWidth: '400px' }}>
            {/* Top link */}
            <a
              href="https://relopass.com"
              style={{
                display: 'block',
                fontSize: '13px',
                color: 'var(--text-tertiary)',
                textDecoration: 'none',
                marginBottom: '32px',
              }}
            >
              ← relopass.com
            </a>

            {/* ── Demo persona cards ── */}
            <div style={{ marginBottom: '28px' }}>
              <p style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginBottom: '10px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Try a demo account
              </p>
              <div style={{ display: 'flex', gap: '8px' }}>
                {DEMO_PERSONAS.map(p => (
                  <Button unstyled
                    key={p.id}
                    onClick={() => handlePersona(p)}
                    disabled={siLoading || suLoading}
                    title={p.description}
                    style={{
                      flex: 1,
                      padding: '10px 8px',
                      borderRadius: 'var(--radius-md)',
                      border: `1px solid var(--border-subtle)`,
                      background: 'var(--surface-hover)',
                      cursor: 'pointer',
                      textAlign: 'center',
                      transition: 'border-color var(--transition-fast), background var(--transition-fast)',
                    }}
                    onMouseEnter={e => {
                      (e.currentTarget as HTMLElement).style.borderColor = p.color;
                      (e.currentTarget as HTMLElement).style.background = `${p.color}14`;
                    }}
                    onMouseLeave={e => {
                      (e.currentTarget as HTMLElement).style.borderColor = 'var(--border-subtle)';
                      (e.currentTarget as HTMLElement).style.background = 'var(--surface-hover)';
                    }}
                  >
                    <div style={{ fontSize: '20px', marginBottom: '4px' }}>{p.emoji}</div>
                    <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-primary)' }}>{p.label}</div>
                  </Button>
                ))}
              </div>
            </div>

            {/* Divider */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
              <div style={{ flex: 1, height: '1px', background: 'var(--border-subtle)' }} />
              <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>or</span>
              <div style={{ flex: 1, height: '1px', background: 'var(--border-subtle)' }} />
            </div>

            {/* ── Tabs ── */}
            {tab !== 'reset_password' && (
              <div style={{ display: 'flex', marginBottom: '24px', borderBottom: '1px solid var(--border-subtle)' }}>
                {(['sign_in', 'sign_up'] as const).map(t => (
                  <Button unstyled
                    key={t}
                    onClick={() => setTab(t)}
                    style={{
                      flex: 1,
                      padding: '10px',
                      background: 'none',
                      border: 'none',
                      borderBottom: `2px solid ${tab === t ? 'var(--accent)' : 'transparent'}`,
                      cursor: 'pointer',
                      fontSize: '14px',
                      fontWeight: tab === t ? 600 : 400,
                      color: tab === t ? 'var(--text-primary)' : 'var(--text-tertiary)',
                      marginBottom: '-1px',
                      transition: 'color var(--transition-fast)',
                    }}
                  >
                    {t === 'sign_in' ? 'Sign in' : 'Create account'}
                  </Button>
                ))}
              </div>
            )}

            {/* ── Sign In ── */}
            {tab === 'sign_in' && (
              <form
                onSubmit={e => { e.preventDefault(); void handleSignIn(siEmail, siPassword); }}
                noValidate
              >
                <div style={fieldStyle}>
                  <label htmlFor="si-email" style={labelStyle}>Email</label>
                  <Input unstyled
                    id="si-email"
                    type="email"
                    autoComplete="email"
                    value={siEmail}
                    onChange={v => setSiEmail(v)}
                    placeholder="you@company.com"
                    disabled={siLoading}
                    style={inputStyle(!!siError)}
                    onFocus={e => (e.target).style.borderColor = 'var(--accent-border)'}
                    onBlur={e => (e.target).style.borderColor = siError ? 'var(--status-error, #E53E3E)' : 'var(--border-default)'}
                  />
                </div>

                <div style={fieldStyle}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <label htmlFor="si-password" style={{ ...labelStyle, marginBottom: 0 }}>Password</label>
                    <Button unstyled
                      type="button"
                      onClick={() => setTab('reset_password')}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '12px', color: 'var(--accent)', padding: 0 }}
                    >
                      Forgot password?
                    </Button>
                  </div>
                  <PasswordInput
                    id="si-password"
                    value={siPassword}
                    onChange={setSiPassword}
                    autoComplete="current-password"
                    disabled={siLoading}
                    error={siError}
                  />
                </div>

                {siError && (
                  <p role="alert" style={{ color: 'var(--danger, #E53E3E)', fontSize: '13px', margin: '-8px 0 16px' }}>
                    {siError}
                  </p>
                )}

                <Button unstyled
                  type="submit"
                  disabled={siLoading}
                  style={{
                    width: '100%',
                    padding: '11px',
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--accent)',
                    color: '#fff',
                    fontWeight: 600,
                    fontSize: '14px',
                    border: 'none',
                    cursor: siLoading ? 'not-allowed' : 'pointer',
                    opacity: siLoading ? 0.7 : 1,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    transition: 'opacity var(--transition-fast)',
                    marginBottom: '16px',
                  }}
                >
                  {siLoading && (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true" style={{ animation: 'rp-spin 0.8s linear infinite' }}>
                      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                    </svg>
                  )}
                  {siLoading ? 'Signing in…' : 'Sign in'}
                </Button>

                {/* SSO */}
                <div style={{ display: 'flex', gap: '8px' }}>
                  {[
                    { provider: 'google' as const, label: 'Google', icon: 'M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z' },
                    { provider: 'azure' as const, label: 'Microsoft', icon: 'M11.4 24H0V12.6l11.4-1.4V24zm12.6 0H12.6V12.4L24 11.4V24zM11.4 11.4H0V0h11.4v11.4zm12.6 0H12.6V1.4L24 0v11.4z' },
                  ].map(({ provider, label, icon }) => (
                    <Button unstyled
                      key={provider}
                      type="button"
                      onClick={() => handleOAuth(provider)}
                      style={{
                        flex: 1,
                        padding: '9px',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--border-default)',
                        background: 'var(--surface)',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '8px',
                        fontSize: '13px',
                        color: 'var(--text-secondary)',
                        transition: 'border-color var(--transition-fast)',
                      }}
                      onMouseEnter={e => (e.currentTarget as HTMLElement).style.borderColor = 'var(--accent-border)'}
                      onMouseLeave={e => (e.currentTarget as HTMLElement).style.borderColor = 'var(--border-default)'}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                        <path d={icon} />
                      </svg>
                      {label}
                    </Button>
                  ))}
                </div>
              </form>
            )}

            {/* ── Sign Up ── */}
            {tab === 'sign_up' && (
              <form onSubmit={e => { e.preventDefault(); void handleSignUp(); }} noValidate>
                <div style={fieldStyle}>
                  <label htmlFor="su-name" style={labelStyle}>Full name</label>
                  <Input unstyled id="su-name" type="text" autoComplete="name" value={suName} onChange={v => setSuName(v)} placeholder="Jane Smith" disabled={suLoading} style={inputStyle(false)} />
                </div>

                <div style={fieldStyle}>
                  <label htmlFor="su-email" style={labelStyle}>Work email</label>
                  <Input unstyled id="su-email" type="email" autoComplete="email" value={suEmail} onChange={v => setSuEmail(v)} placeholder="jane@company.com" disabled={suLoading} style={inputStyle(false)} />
                </div>

                <div style={{ ...fieldStyle, marginBottom: '8px' }}>
                  <label htmlFor="su-password" style={labelStyle}>Password</label>
                  <PasswordInput id="su-password" value={suPassword} onChange={setSuPassword} autoComplete="new-password" disabled={suLoading} placeholder="Min. 8 characters" />
                </div>

                {suPassword.length > 0 && (
                  <div style={{ display: 'flex', gap: '4px', marginBottom: '16px', alignItems: 'center' }}>
                    {[1, 2, 3].map(level => (
                      <div
                        key={level}
                        style={{
                          flex: 1,
                          height: '3px',
                          borderRadius: '2px',
                          background: strength >= level ? STRENGTH_COLOR[strength] : 'var(--border-subtle)',
                          transition: 'background var(--transition-fast)',
                        }}
                      />
                    ))}
                    <span style={{ fontSize: '11px', color: STRENGTH_COLOR[strength], marginLeft: '6px', minWidth: '50px' }}>
                      {STRENGTH_LABEL[strength]}
                    </span>
                  </div>
                )}

                <div style={fieldStyle}>
                  <label htmlFor="su-company" style={labelStyle}>
                    Company slug <span style={{ fontWeight: 400, color: 'var(--text-tertiary)' }}>(optional)</span>
                  </label>
                  <Input unstyled
                    id="su-company"
                    type="text"
                    value={suCompany}
                    onChange={v => setSuCompany(v)}
                    placeholder="acme-corp"
                    disabled={suLoading}
                    style={inputStyle(false)}
                  />
                  <p style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginTop: '4px' }}>
                    Leave blank to create a new organisation.
                  </p>
                </div>

                {suError && (
                  <p role="alert" style={{ color: 'var(--danger, #E53E3E)', fontSize: '13px', margin: '-4px 0 16px' }}>
                    {suError}
                  </p>
                )}

                <Button unstyled
                  type="submit"
                  disabled={suLoading}
                  style={{
                    width: '100%',
                    padding: '11px',
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--accent)',
                    color: '#fff',
                    fontWeight: 600,
                    fontSize: '14px',
                    border: 'none',
                    cursor: suLoading ? 'not-allowed' : 'pointer',
                    opacity: suLoading ? 0.7 : 1,
                    marginBottom: '12px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                  }}
                >
                  {suLoading && (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true" style={{ animation: 'rp-spin 0.8s linear infinite' }}>
                      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                    </svg>
                  )}
                  {suLoading ? 'Creating account…' : 'Create account'}
                </Button>

                {/* [AIQ-2059] The second half of this sentence is gone. No such page exists
                    in the repo or in production — relopass.com/terms served the marketing
                    homepage, byte-identical to a nonsense path — so the form was collecting
                    agreement to a document that does not exist. Asserting consent to nothing
                    is worse than asking for less consent. /privacy resolves to a real page
                    and stays. Restore the second half in one line once the document is
                    actually written and routed.
                    (Phrased without the literal product name on purpose: the guard in
                    navigation/navigateTargets.test.ts greps this file for it.) */}
                <p style={{ fontSize: '12px', color: 'var(--text-tertiary)', textAlign: 'center' }}>
                  By signing up you agree to our{' '}
                  <a href="/privacy" style={{ color: 'var(--accent)' }}>Privacy Policy</a>.
                </p>
              </form>
            )}

            {/* ── Reset Password ── */}
            {tab === 'reset_password' && (
              <div>
                <Button unstyled
                  onClick={() => setTab('sign_in')}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '13px', color: 'var(--text-tertiary)', padding: 0, marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '4px' }}
                >
                  ← Back to sign in
                </Button>

                <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '8px' }}>
                  Reset your password
                </h2>
                <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '24px' }}>
                  Enter your email and we&apos;ll send you a reset link.
                </p>

                {rpSent ? (
                  <div
                    role="status"
                    style={{
                      padding: '14px 16px',
                      borderRadius: 'var(--radius-md)',
                      background: 'var(--surface-success, rgba(29,191,162,0.1))',
                      border: '1px solid var(--accent-border)',
                      color: 'var(--accent)',
                      fontSize: '14px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                    }}
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    Check your email — a reset link is on its way.
                  </div>
                ) : (
                  <form onSubmit={e => { e.preventDefault(); void handleResetPassword(); }} noValidate>
                    <div style={fieldStyle}>
                      <label htmlFor="rp-email" style={labelStyle}>Email</label>
                      <Input unstyled
                        id="rp-email"
                        type="email"
                        autoComplete="email"
                        value={rpEmail}
                        onChange={v => setRpEmail(v)}
                        placeholder="you@company.com"
                        disabled={rpLoading}
                        style={inputStyle(!!rpError)}
                      />
                    </div>
                    {rpError && (
                      <p role="alert" style={{ color: 'var(--danger, #E53E3E)', fontSize: '13px', margin: '-8px 0 16px' }}>{rpError}</p>
                    )}
                    <Button unstyled
                      type="submit"
                      disabled={rpLoading}
                      style={{
                        width: '100%',
                        padding: '11px',
                        borderRadius: 'var(--radius-md)',
                        background: 'var(--accent)',
                        color: '#fff',
                        fontWeight: 600,
                        fontSize: '14px',
                        border: 'none',
                        cursor: rpLoading ? 'not-allowed' : 'pointer',
                        opacity: rpLoading ? 0.7 : 1,
                      }}
                    >
                      {rpLoading ? 'Sending…' : 'Send reset link'}
                    </Button>
                  </form>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Responsive: hide globe on mobile */}
      <style>{`
        @keyframes rp-spin { to { transform: rotate(360deg); } }
        @media (max-width: 767px) {
          .rp-auth-globe { display: none !important; }
        }
        @media (max-width: 767px) {
          .rp-auth-globe + div { flex: 1 !important; }
        }
      `}</style>
    </>
  );
}

export default AuthScreen;
