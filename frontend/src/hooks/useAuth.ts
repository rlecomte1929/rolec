import { useNavigate } from 'react-router-dom';
import { authAPI } from '../api/client';
import { signInSupabase } from '../api/supabaseAuth';
import type { LoginRequest, RegisterRequest, UserRole } from '../types';
import { setAuthItem } from '../utils/demo';
import { safeNavigate } from '../navigation/safeNavigate';
import { trackAuthPerf } from '../perf/authPerf';
import type { PostSignupReconciliation } from '../types';

function shouldPersistReconciliation(rec: PostSignupReconciliation | null | undefined): boolean {
  if (!rec) return false;
  const has = (s?: string | null) => Boolean(s && String(s).trim());
  if (has(rec.headline) || has(rec.message)) return true;
  if (rec.attachedAssignmentIds && rec.attachedAssignmentIds.length > 0) return true;
  if (rec.linkedContactIds && rec.linkedContactIds.length > 0) return true;
  if ((rec.skippedRevokedInvites ?? 0) > 0) return true;
  if ((rec.skippedContactsLinkedToOtherUser ?? 0) > 0) return true;
  if ((rec.skippedAssignmentsLinkedToOtherUser ?? 0) > 0) return true;
  return false;
}

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
    const loginRec = response.reconciliation;
    if (shouldPersistReconciliation(loginRec)) {
      try {
        sessionStorage.setItem('post_auth_claim_reconciliation', JSON.stringify(loginRec));
      } catch {
        /* ignore */
      }
    }

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
    const t0 = typeof performance !== 'undefined' ? performance.now() : Date.now();
    trackAuthPerf({ stage: 'auth_request_start' });
    const response = await authAPI.register(payload);
    const authDur = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - t0;
    trackAuthPerf({ stage: 'auth_request_end', durationMs: authDur });
    setSession(response.token, response.user);
    const rec = response.reconciliation;
    if (shouldPersistReconciliation(rec)) {
      try {
        sessionStorage.setItem('post_auth_claim_reconciliation', JSON.stringify(rec));
      } catch {
        /* ignore */
      }
    }
    const emailForSb = response.user.email ?? payload.email?.trim() ?? null;
    redirectByRole(response.user.role);
    if (emailForSb && payload.password) {
      void signInSupabase(emailForSb, payload.password);
    }
    return response;
  };

  return { login, register };
};
