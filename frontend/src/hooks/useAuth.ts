import { useNavigate } from 'react-router-dom';
import { authAPI } from '../api/client';
import { signInSupabase } from '../api/supabaseAuth';
import type { LoginRequest, RegisterRequest, UserRole } from '../types';
import { setAuthItem } from '../utils/demo';
import { safeNavigate } from '../navigation/safeNavigate';
import { trackAuthPerf } from '../perf/authPerf';

export const useAuth = () => {
  const navigate = useNavigate();

  const setSession = (token: string, user: { id: string; role: UserRole; email?: string | null; username?: string | null; name?: string | null }) => {
    setAuthItem('relopass_token', token);
    setAuthItem('relopass_user_id', user.id);
    if (user.email) setAuthItem('relopass_email', user.email);
    if (user.username) setAuthItem('relopass_username', user.username);
    if (user.name) setAuthItem('relopass_name', user.name);
    setAuthItem('relopass_role', user.role);
  };

  const redirectByRole = (role: UserRole) => {
    safeNavigate(navigate, role === 'EMPLOYEE' ? 'employeeDashboard' : 'hrDashboard');
  };

  const login = async (payload: LoginRequest) => {
    trackAuthPerf({ stage: 'sign_in_click' });
    const t0 = typeof performance !== 'undefined' ? performance.now() : Date.now();

    trackAuthPerf({ stage: 'auth_request_start' });
    const response = await authAPI.login(payload);
    const authDur = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - t0;
    trackAuthPerf({ stage: 'auth_request_end', durationMs: authDur });

    setSession(response.token, response.user);

    // Establish Supabase session so tokens auto-refresh (feedback, review, RPC).
    // Deferred to after redirect so the user sees the app immediately.
    const email = response.user.email ?? (payload.identifier?.includes('@') ? payload.identifier.trim() : null);
    if (email && payload.password) {
      const supabaseT0 = typeof performance !== 'undefined' ? performance.now() : Date.now();
      trackAuthPerf({ stage: 'token_refresh_start' });
      redirectByRole(response.user.role);
      void signInSupabase(email, payload.password).then(() => {
        const dur = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - supabaseT0;
        trackAuthPerf({ stage: 'token_refresh_end', durationMs: dur });
      });
    } else {
      redirectByRole(response.user.role);
    }
    return response;
  };

  const register = async (payload: RegisterRequest) => {
    trackAuthPerf({ stage: 'sign_in_click' });
    const response = await authAPI.register(payload);
    setSession(response.token, response.user);
    redirectByRole(response.user.role);
    return response;
  };

  return { login, register };
};
