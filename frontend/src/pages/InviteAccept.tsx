import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Card, Button, Alert } from '../components/antigravity';
import { authAPI } from '../api/client';
import {
  companyInvitesAPI,
  stashPendingInvite,
  clearPendingInvite,
} from '../api/companyInvites';
import { getAuthItem, clearAuthItems } from '../utils/demo';
import { homeRouteKeyForRole } from '../navigation/routes';
import { safeNavigate } from '../navigation/safeNavigate';

/**
 * [AIQ-2189] Landing for a colleague-invite accept link (/invite/:token).
 *
 * AIQ-2094 built the accept endpoint but nothing that reaches it: the endpoint is
 * authenticated and email-matched, so a colleague with no ReloPass account cannot simply
 * POST the token — they must create an account with the invited email first. Nothing in
 * the product said so; a hand-made link just bounced them to a bare login screen. This
 * page branches on auth state so the link always explains the next step:
 *
 *   - logged out                       → "create your account with the invited email
 *                                         first" (token stashed so it survives the
 *                                         register/login round trip)
 *   - logged in as the invited person  → redeems automatically, then goes to the app
 *   - logged in as someone else        → readable 403 + switch-account affordance
 *
 * The raw token only ever travels in the API path and sessionStorage — never a log line
 * and never analytics.
 */
type Phase = 'checking' | 'loggedOut' | 'accepting' | 'success' | 'error';

export function InviteAccept() {
  const { token = '' } = useParams();
  const navigate = useNavigate();
  const [phase, setPhase] = useState<Phase>('checking');
  const [message, setMessage] = useState('');
  const [mismatch, setMismatch] = useState(false);
  const started = useRef(false);

  const goToApp = () => safeNavigate(navigate, homeRouteKeyForRole(getAuthItem('relopass_role')));

  useEffect(() => {
    if (started.current) return; // redeem at most once per mount
    started.current = true;

    if (!token) {
      setMessage("This invite link isn't valid. Ask your administrator to send a new one.");
      setPhase('error');
      return;
    }

    if (!getAuthItem('relopass_token')) {
      stashPendingInvite(token); // carry the token across the register/login round trip
      setPhase('loggedOut');
      return;
    }

    setPhase('accepting');
    companyInvitesAPI
      .accept(token)
      .then(() => {
        clearPendingInvite();
        setPhase('success');
      })
      .catch((err: unknown) => {
        const status = (err as { status?: number })?.status;
        if (status === 403) {
          // Wrong account. Keep the token so re-auth as the invited email finishes the trip.
          stashPendingInvite(token);
          setMismatch(true);
          setMessage(
            'This invite was sent to a different email address. Sign out and sign back in ' +
              'with the email address your invite was sent to.',
          );
        } else {
          clearPendingInvite();
          if (status === 404) {
            setMessage("This invite link isn't valid. Ask your administrator to send a new one.");
          } else if (status === 409) {
            setMessage('This invite has already been used. If that is unexpected, ask your administrator.');
          } else if (status === 410) {
            setMessage('This invite has expired. Ask your administrator to send you a new one.');
          } else {
            setMessage(
              (err as { message?: string })?.message ||
                'We could not accept this invite right now. Please try again.',
            );
          }
        }
        setPhase('error');
      });
  }, [token]);

  useEffect(() => {
    if (phase === 'success') goToApp();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  const goRegister = () => navigate('/auth?mode=register');

  const switchAccount = async () => {
    stashPendingInvite(token); // survives the logout (sessionStorage, not cleared by it)
    try {
      await authAPI.logout();
    } catch {
      /* best effort — the local clear below is what matters */
    }
    clearAuthItems();
    window.location.assign('/auth?mode=login');
  };

  return (
    <div className="min-h-[70vh] flex items-center justify-center p-6">
      <Card className="max-w-md w-full">
        <div className="p-6 space-y-4 text-center">
          <h1 className="text-xl font-semibold text-navy-800">Join your team on ReloPass</h1>

          {(phase === 'checking' || phase === 'accepting') && (
            <p className="text-slate-600">Checking your invite&hellip;</p>
          )}

          {phase === 'loggedOut' && (
            <>
              <p className="text-slate-600">
                You&rsquo;ve been invited to join a company on ReloPass. To accept, sign in
                &mdash; or create your account using the email address this invite was sent
                to &mdash; and you&rsquo;ll be added automatically.
              </p>
              <Button onClick={goRegister} className="w-full">
                Create your account
              </Button>
              <p className="text-sm text-slate-500">
                Already have an account?{' '}
                <button
                  type="button"
                  onClick={goRegister}
                  className="text-accent-700 underline underline-offset-2"
                >
                  Sign in
                </button>
              </p>
            </>
          )}

          {phase === 'success' && (
            <>
              <p className="text-slate-600">You&rsquo;re all set &mdash; taking you to your dashboard&hellip;</p>
              <Button onClick={goToApp} className="w-full">
                Continue
              </Button>
            </>
          )}

          {phase === 'error' && (
            <>
              <Alert variant={mismatch ? 'warning' : 'error'}>{message}</Alert>
              {mismatch && (
                <Button onClick={switchAccount} className="w-full">
                  Sign out and switch account
                </Button>
              )}
            </>
          )}
        </div>
      </Card>
    </div>
  );
}
