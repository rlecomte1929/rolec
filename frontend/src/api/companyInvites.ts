/**
 * [AIQ-2189] Colleague-invite acceptance — the frontend half of AIQ-2094.
 *
 * The accept call is AUTHENTICATED: it goes through ./client (which attaches the ReloPass
 * session token), and the backend matches the caller's email to the invited address,
 * 403-ing on a mismatch. Pairs with backend/app/routers/hr_company_invites.py::accept.
 *
 * The pending-invite helpers stash the raw token in sessionStorage so it survives the
 * register/login round trip a logged-out invitee must make (the accept route has no
 * unauthenticated surface). sessionStorage — not localStorage — so it is scoped to the
 * tab and never mixed into the auth cache; and never console-logged or sent to analytics.
 */
import { apiPost } from './client';

export interface AcceptCompanyInviteResponse {
  id: string;
  status: string;
  company_id: string;
}

export const companyInvitesAPI = {
  accept: (token: string) =>
    apiPost<AcceptCompanyInviteResponse>(
      `/api/company-invites/${encodeURIComponent(token)}/accept`,
      {},
    ),
};

const PENDING_INVITE_KEY = 'relopass_pending_invite';

/** Carry the token across the register/login round trip a logged-out invitee makes. */
export function stashPendingInvite(token: string): void {
  try {
    sessionStorage.setItem(PENDING_INVITE_KEY, token);
  } catch {
    /* private mode / storage disabled — the URL token still works within this page */
  }
}

/** The token to redeem after auth, if the user arrived from an invite link. */
export function readPendingInvite(): string | null {
  try {
    return sessionStorage.getItem(PENDING_INVITE_KEY);
  } catch {
    return null;
  }
}

export function clearPendingInvite(): void {
  try {
    sessionStorage.removeItem(PENDING_INVITE_KEY);
  } catch {
    /* nothing to clear */
  }
}
