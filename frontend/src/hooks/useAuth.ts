import { useNavigate } from 'react-router-dom';
import { authAPI } from '../api/client';
import { signInSupabase } from '../api/supabaseAuth';
import { supabase } from '../api/supabase';
import type { LoginRequest, RegisterRequest, UserRole } from '../types';
import { normalizeStoredRole, setAuthItem, setStoredRoles, setActiveRole } from '../utils/demo';
import { seedWelcomeSeenFromLogin } from '../utils/welcomeSeen';
import { safeNavigate } from '../navigation/safeNavigate';
import { homeRouteKeyForRole, type RouteKey } from '../navigation/routes';
import { heldHomeRole } from '../navigation/roleHome';
import { readPendingInvite } from '../api/companyInvites';
import { trackAuthPerf } from '../perf/authPerf';
import { trackAssignmentFlow, ASSIGNMENT_FLOW_EVENTS } from '../perf/assignmentLinkingInstrumentation';
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

  const setSession = (token: string, user: { id: string; role: UserRole; email?: string | null; username?: string | null; name?: string | null; roles?: string[] | null; primary_role?: string | null; welcome_seen?: boolean | null }) => {
    setAuthItem('relopass_token', token);
    setAuthItem('relopass_user_id', user.id);
    // AIQ-1701: the welcome dismissal is stored server-side on the profile; mirror it
    // into localStorage here, at login, so useWelcomeRedirect's mount check stays
    // SYNCHRONOUS. Making that check async would risk the role home flashing the
    // welcome page before the answer arrived. Only ever sets the flag — never clears
    // it — so a user already onboarded in this browser is unaffected if the server
    // says nothing (which is also the pre-AIQ-1701 behaviour).
    seedWelcomeSeenFromLogin(user.id, user.welcome_seen);
    if (user.email) setAuthItem('relopass_email', user.email);
    if (user.username) setAuthItem('relopass_username', user.username);
    if (user.name) setAuthItem('relopass_name', user.name);
    // SEC-FE-4: role is sourced from the SERVER login response (response.user.role).
    // This localStorage copy is a cache/UX hint only — it is NOT the access boundary
    // (the backend re-derives role + company-scope from the token on every request).
    setAuthItem('relopass_role', normalizeStoredRole(user.role));
    // AIQ-1363: multi-role — persist all held roles + the active (primary) role.
    // Falls back to the single role so single-role users are unchanged.
    const held = user.roles && user.roles.length ? user.roles : [user.role];
    setStoredRoles(held);
    setActiveRole(heldHomeRole(held, user.primary_role || user.role));
  };

  const landingRole = (user: { role: UserRole; roles?: string[] | null; primary_role?: string | null }): string => {
    const held = user.roles && user.roles.length ? user.roles : [user.role];
    return heldHomeRole(held, user.primary_role || user.role);
  };

  const postAuthRouteKey = (role: UserRole | string): RouteKey => homeRouteKeyForRole(normalizeStoredRole(role));

  const redirectByRole = (role: UserRole) => {
    // [AIQ-2189] If the user arrived via a colleague-invite link, finish the round trip on
    // the invite page (which redeems the token) rather than dropping them at their role
    // home. Guarded: only fires when an invite is actually pending, so normal auth is
    // unchanged. InviteAccept clears the stash once it redeems (or hits a terminal error).
    const pendingInvite = readPendingInvite();
    if (pendingInvite) {
      navigate(`/invite/${encodeURIComponent(pendingInvite)}`);
      return;
    }
    safeNavigate(navigate, postAuthRouteKey(role));
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
      trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.postLoginRoute, {
        role: landingRole(response.user),
        targetRouteKey: postAuthRouteKey(landingRole(response.user)),
        source: 'login',
      });
      redirectByRole(landingRole(response.user) as UserRole);
      void signInSupabase(email, payload.password).then(() => {
        const dur = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - supabaseT0;
        trackAuthPerf({ stage: 'token_refresh_end', durationMs: dur });
      });
    } else {
      trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.postLoginRoute, {
        role: landingRole(response.user),
        targetRouteKey: postAuthRouteKey(landingRole(response.user)),
        source: 'login',
      });
      redirectByRole(landingRole(response.user) as UserRole);
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
    trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.postLoginRoute, {
      role: landingRole(response.user),
      targetRouteKey: postAuthRouteKey(landingRole(response.user)),
      source: 'register',
    });
    redirectByRole(landingRole(response.user) as UserRole);
    if (emailForSb && payload.password) {
      void signInSupabase(emailForSb, payload.password);
    }
    return response;
  };

  // [AIQ-1491] Passwordless passkey sign-in (POC). Drives the WebAuthn ceremony via
  // auth-js 2.108's first-class signInWithPasskey(), which yields a SUPABASE session;
  // that JWT is then exchanged for the ReloPass session token the rest of the API needs
  // (POST /api/auth/exchange-supabase-token). Password login is untouched.
  const loginWithPasskey = async () => {
    const { data, error } = await supabase.auth.signInWithPasskey();
    if (error) throw error;
    const accessToken = data?.session?.access_token;
    if (!accessToken) {
      throw new Error('Passkey sign-in did not return a session.');
    }
    const response = await authAPI.exchangeSupabaseToken(accessToken);
    setSession(response.token, response.user);
    trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.postLoginRoute, {
      role: landingRole(response.user),
      targetRouteKey: postAuthRouteKey(landingRole(response.user)),
      source: 'login',
    });
    redirectByRole(landingRole(response.user) as UserRole);
    return response;
  };

  // [AIQ-1491] Register a passkey for the CURRENT (already-authenticated) user. Requires
  // an active Supabase session — established after password login by signInSupabase — so
  // this is offered from Settings, not the logged-out screen.
  const registerPasskey = async () => {
    const { data, error } = await supabase.auth.registerPasskey();
    if (error) throw error;
    return data;
  };

  return { login, register, loginWithPasskey, registerPasskey };
};
