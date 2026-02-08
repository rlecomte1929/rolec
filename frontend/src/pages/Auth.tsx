import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card, Button, Input, Select, Alert } from '../components/antigravity';
import { AppShell } from '../components/AppShell';
import type { UserRole } from '../types';
import { clearAuthItems } from '../utils/demo';
import { useAuth } from '../hooks/useAuth';

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


  useEffect(() => {
    const nextMode = searchParams.get('mode');
    if (nextMode === 'register' || nextMode === 'login') {
      setMode(nextMode);
    }
  }, [searchParams]);


  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login({ identifier, password });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
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
      setError(err.response?.data?.detail || 'Registration failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetTest = () => {
    clearAuthItems();
    setIdentifier('');
    setPassword('');
    setUsername('');
    setEmail('');
    setName('');
    setError('');
  };

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
                Sign In
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

            {mode === 'login' && (
              <form onSubmit={handleLogin} className="space-y-4">
                <Input
                  value={identifier}
                  onChange={setIdentifier}
                  label="Username or Email"
                  placeholder="username or you@example.com"
                  fullWidth
                />
                <Input
                  type="password"
                  value={password}
                  onChange={setPassword}
                  label="Password"
                  placeholder="Enter your password"
                  fullWidth
                />
                <Button type="submit" fullWidth disabled={!identifier || !password || isLoading}>
                  {isLoading ? 'Signing in...' : 'Sign In'}
                </Button>
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
                  fullWidth
                />
                <Input
                  type="email"
                  value={email}
                  onChange={setEmail}
                  label="Email"
                  placeholder="you@example.com"
                  fullWidth
                />
                <Input
                  type="password"
                  value={password}
                  onChange={setPassword}
                  label="Password"
                  placeholder="Create a password"
                  fullWidth
                />
                <Select
                  value={role}
                  onChange={(value) => setRole(value as UserRole)}
                  label="Role"
                  options={[
                    { value: 'HR', label: 'HR manager' },
                    { value: 'EMPLOYEE', label: 'Employee' },
                  ]}
                  fullWidth
                />
                <Button type="submit" fullWidth disabled={isLoading}>
                  {isLoading ? 'Creating account...' : 'Create Account'}
                </Button>
              </form>
            )}
          </div>
        </Card>
      </div>
      <button
        onClick={handleResetTest}
        className="fixed bottom-6 right-6 text-xs bg-slate-900 text-white px-3 py-2 rounded-full shadow-lg hover:bg-slate-800"
      >
        Reset test data
      </button>
    </AppShell>
  );
};
