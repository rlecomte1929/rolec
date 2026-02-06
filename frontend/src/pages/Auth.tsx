import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Input, Container, Alert } from '../components/antigravity';
import { authAPI } from '../api/client';

export const Auth: React.FC = () => {
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const response = await authAPI.login({ email, provider: 'email' });
      
      // Store token and user info
      localStorage.setItem('relopass_token', response.token);
      localStorage.setItem('relopass_user_id', response.userId);
      localStorage.setItem('relopass_email', response.email);
      
      // Navigate to journey
      navigate('/journey');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleLogin = () => {
    // Mock Google login - in production this would use OAuth
    const mockEmail = 'user@example.com';
    setEmail(mockEmail);
    // Auto-submit after a moment
    setTimeout(() => {
      const mockEvent = { preventDefault: () => {} } as React.FormEvent;
      handleLogin(mockEvent);
    }, 100);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-100 via-white to-purple-100 flex items-center justify-center py-12">
      <Container maxWidth="sm">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">ReloPass</h1>
          <p className="text-lg text-gray-600">
            Your guided journey to Singapore
          </p>
        </div>

        <Card padding="lg">
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-semibold text-gray-900 mb-2">
                Welcome
              </h2>
              <p className="text-gray-600">
                Sign in to start or continue your relocation profile.
              </p>
            </div>

            {error && (
              <Alert variant="error">{error}</Alert>
            )}

            <form onSubmit={handleLogin} className="space-y-4">
              <Input
                type="email"
                value={email}
                onChange={setEmail}
                label="Email Address"
                placeholder="you@example.com"
                fullWidth
              />

              <Button
                type="submit"
                fullWidth
                disabled={!email || isLoading}
              >
                {isLoading ? 'Signing in...' : 'Continue with Email'}
              </Button>
            </form>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-300"></div>
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white text-gray-500">Or</span>
              </div>
            </div>

            <Button
              onClick={handleGoogleLogin}
              variant="outline"
              fullWidth
            >
              <span className="flex items-center justify-center gap-2">
                <span>Continue with Google (Mock)</span>
              </span>
            </Button>

            <div className="text-xs text-gray-500 text-center">
              By continuing, you agree to our Terms of Service and Privacy Policy.
            </div>
          </div>
        </Card>

        <div className="mt-8 text-center">
          <div className="inline-flex items-center gap-4 text-sm text-gray-600">
            <span>✓ Secure & Private</span>
            <span>•</span>
            <span>✓ Progress Saved</span>
            <span>•</span>
            <span>✓ Free to Use</span>
          </div>
        </div>
      </Container>
    </div>
  );
};
