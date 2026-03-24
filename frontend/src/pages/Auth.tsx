import React, { useEffect, useRef, useState } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { Card, Input, Select, Alert, LoadingButton } from '../components/antigravity';
import { AppShell } from '../components/AppShell';
import type { UserRole } from '../types';
import { useAuth } from '../hooks/useAuth';
import { getApiErrorMessage, getClientTransportErrorMessage } from '../utils/apiDetail';
import { buildRoute, homeRouteKeyForRole } from '../navigation/routes';
import { getAuthItem } from '../utils/demo';

export const Auth: React.FC = () => {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<UserRole>('EMPLOYEE');
  const [name, setName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchParams] = useSearchParams();
  const { login, register } = useAuth();
  /** Blocks double-submit before React re-renders (e.g. double-click + Enter). */
  const authInFlight = useRef(false);


  useEffect(() => {
    const nextMode = searchParams.get('mode');
    if (nextMode === 'register' || nextMode === 'login') {
      setMode(nextMode);
    }
  }, [searchParams]);


  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (authInFlight.current || isLoading) return;
    setError('');
    authInFlight.current = true;
    setIsLoading(true);

    try {
      await login({ identifier, password });
    } catch (err: any) {
      const transport = getClientTransportErrorMessage(err);
      const msg = transport ?? getApiErrorMessage(err, 'Login failed. Try again.');
      try {
        localStorage.setItem('debug_last_auth_error', msg);
      } catch {
        /* ignore */
      }
      setError(msg);
    } finally {
      authInFlight.current = false;
      setIsLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (authInFlight.current || isLoading) return;
    setError('');

    const hasUsername = username.trim().length > 0;
    const hasEmail = email.trim().length > 0;
    if (!hasUsername && !hasEmail) {
      setError('Provide a username or email.');
      return;
    }

    if (hasUsername && !/^[A-Za-z0-9_]{3,30}$/.test(username.trim())) {
      setError('Username must be 3–30 characters, alphanumeric or underscore.');
      return;
    }

    if (hasEmail && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) {
      setError('Provide a valid email address.');
      return;
    }

    if (!password.trim()) {
      setError('Password is required.');
      return;
    }

    authInFlight.current = true;
    setIsLoading(true);
    try {
      await register({
        username: hasUsername ? username.trim() : undefined,
        email: hasEmail ? email.trim() : undefined,
        password,
        role,
        name: name.trim() || undefined,
      });
    } catch (err: any) {
      const transport = getClientTransportErrorMessage(err);
      if (transport) {
        try {
          localStorage.setItem('debug_last_auth_error', transport);
        } catch {
          /* ignore */
        }
        setError(transport);
        return;
      }
      const detail = err.response?.data?.detail;
      let msg: string;
      if (err.response?.status === 400 && detail && typeof detail === 'object' && !Array.isArray(detail)) {
        const code = (detail as { code?: string }).code;
        const message = (detail as { message?: string }).message;
        if (code === 'AUTH_EMAIL_TAKEN' && message) {
          msg = message;
        } else if (code === 'AUTH_USERNAME_TAKEN' && message) {
          msg = message;
        } else if (message) {
          msg = message;
        } else {
          msg = 'Registration failed. Check your details and try again.';
        }
      } else if (err.response?.status === 400 && detail) {
        msg = Array.isArray(detail) ? (detail[0]?.msg || String(detail)) : String(detail);
      } else if (!err.response) {
        msg = 'Cannot reach server. Is the backend running? Check the console for details.';
      } else {
        msg = detail ? (Array.isArray(detail) ? (detail[0]?.msg || String(detail)) : String(detail)) : 'Registration failed. Try again.';
      }
      try {
        localStorage.setItem('debug_last_auth_error', msg);
      } catch {
        /* ignore */
      }
      setError(msg);
    } finally {
      authInFlight.current = false;
      setIsLoading(false);
    }
  };

  if (getAuthItem('relopass_token')) {
    const key = homeRouteKeyForRole(getAuthItem('relopass_role'));
    if (key !== 'landing') {
      return <Navigate to={buildRoute(key)} replace />;
    }
  }

  return (
    <AppShell>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
        <div className="space-y-6">
          <div className="flex items-center gap-4">
            <img src="/relopass-logo.png?v=1" alt="ReloPass logo" className="h-11 w-11 rounded-2xl object-contain" />
            <div>
              <h1 className="text-3xl font-semibold text-[#0b2b43]">ReloPass</h1>
              <p className="text-[#4b5563]">Guided relocation management for HR and employees.</p>
            </div>
          </div>
          <div className="space-y-2 text-sm text-[#4b5563]">
            <div>• Centralized relocation intake and compliance checks.</div>
            <div>• Track readiness, housing, schooling, and movers.</div>
            <div>• HR review workflow with clear decisions.</div>
          </div>
        </div>

        <Card padding="lg">
          <div className="space-y-5">
            <div className="flex gap-2">
              <button
                onClick={() => setMode('login')}
                className={`px-3 py-2 text-sm rounded-md ${
                  mode === 'login' ? 'bg-[#0b2b43] text-white' : 'bg-[#f3f4f6] text-[#4b5563]'
                }`}
              >
                Sign in
              </button>
              <button
                onClick={() => setMode('register')}
                className={`px-3 py-2 text-sm rounded-md ${
                  mode === 'register' ? 'bg-[#0b2b43] text-white' : 'bg-[#f3f4f6] text-[#4b5563]'
                }`}
              >
                Create Account
              </button>
            </div>

            {error && <Alert variant="error">{error}</Alert>}

            {mode === 'register' && role === 'EMPLOYEE' && (
              <Alert variant="info" title="Signing up with a work email">
                <p className="text-sm text-[#374151] leading-relaxed">
                  HR can add your work email to a case before you register. You can still create an account here.
                </p>
                <p className="text-sm text-[#374151] mt-2 leading-relaxed">
                  &quot;Email already in use&quot; means that address is already a login on ReloPass. Use the same email
                  HR used and pending cases usually attach. If not, enter the assignment ID from HR on your dashboard.
                </p>
              </Alert>
            )}

            {mode === 'login' && (
              <form onSubmit={handleLogin} className="space-y-4">
                <Input
                  value={identifier}
                  onChange={setIdentifier}
                  label="Username or Email"
                  placeholder="username or you@example.com"
                  autoComplete="username"
                  fullWidth
                />
                <Input
                  type="password"
                  value={password}
                  onChange={setPassword}
                  label="Password"
                  placeholder="Password"
                  autoComplete="current-password"
                  fullWidth
                />
                <LoadingButton
                  type="submit"
                  fullWidth
                  loading={isLoading}
                  loadingLabel="Signing in…"
                  disabled={!identifier || !password}
                >
                  Sign in
                </LoadingButton>
              </form>
            )}

            {mode === 'register' && (
              <form onSubmit={handleRegister} className="space-y-4">
                <Input
                  value={name}
                  onChange={setName}
                  label="Full name (optional)"
                  placeholder="Alex Johnson"
                  fullWidth
                />
                <Input
                  value={username}
                  onChange={setUsername}
                  label="Username"
                  placeholder="username (3–30 chars, letters/numbers/_)"
                  autoComplete="username"
                  fullWidth
                />
                <Input
                  type="email"
                  value={email}
                  onChange={setEmail}
                  label="Email"
                  placeholder="you@example.com"
                  autoComplete="email"
                  fullWidth
                />
                <Input
                  type="password"
                  value={password}
                  onChange={setPassword}
                  label="Password"
                  placeholder="Create a password"
                  autoComplete="new-password"
                  fullWidth
                />
                <Select
                  value={role}
                  onChange={(value) => setRole(value as UserRole)}
                  label="Role"
                  options={[
                    { value: 'HR', label: 'HR manager' },
                    { value: 'EMPLOYEE', label: 'Employee' },
                    { value: 'ADMIN', label: 'Admin (full access)' },
                  ]}
                  fullWidth
                />
                <LoadingButton
                  type="submit"
                  fullWidth
                  loading={isLoading}
                  loadingLabel="Creating account…"
                  disabled={!password.trim() || (!username.trim() && !email.trim())}
                >
                  Create account
                </LoadingButton>
              </form>
            )}
          </div>
        </Card>
      </div>
    </AppShell>
  );
};
