// webhook-extension.ts
// ReloPass — Stripe Integration v1.0
//
// Extension for the EXISTING Stripe webhook endpoint in misc.routes.ts.
// Add the call below inside the `checkout.session.completed` case of the
// existing event switch — BEFORE the generic handling, and return early
// when it reports the event as handled:
//
//   case 'checkout.session.completed': {
//     const session = event.data.object as Stripe.Checkout.Session;
//     const handled = await handleRelopassCaseCheckoutCompleted(session);
//     if (handled) break; // ReloPass case unlock — done
//     // ...existing handling for other products continues here...
//   }
//
// CRITICAL INVARIANT: relocation_cases.access_tier is ONLY ever written by
// this handler. Never from the client, never from the /checkout endpoint.

import Stripe from 'stripe';
import { getWorkspaceDb } from '../../services/workspace-db';
import { sendCasePaymentConfirmation } from '../../services/email/case-payment-confirmation';

const TIER_TO_PAYMENT_STATUS: Record<string, string> = {
  roadmap: 'roadmap_paid',
  essentials: 'essentials_paid',
};

/**
 * Returns true when the event belonged to ReloPass Case Command and has been
 * fully handled (including replays), false when the event is not ours and
 * the caller's existing handling should continue.
 */
export async function handleRelopassCaseCheckoutCompleted(
  session: Stripe.Checkout.Session
): Promise<boolean> {
  const meta = session.metadata ?? {};

  // 1. Only handle our own sessions — everything else falls through.
  if (meta.source !== 'relopass_case_command') return false;

  const { workspaceId, caseId, tier } = meta;
  const paymentStatus = TIER_TO_PAYMENT_STATUS[tier ?? ''];
  if (!workspaceId || !caseId || !paymentStatus) {
    console.warn('[relopass-webhook] malformed metadata on session', session.id, meta);
    return true; // ours but unusable — acknowledge, do not retry forever
  }

  // Only unlock sessions Stripe reports as actually paid.
  if (session.payment_status !== 'paid') {
    console.log('[relopass-webhook] session completed but not paid', session.id, session.payment_status);
    return true;
  }

  const wsDb = await getWorkspaceDb(workspaceId);

  // 2. Conditional UPDATE — the WHERE clause is the idempotency guard:
  //    - stripe_session_id must match what /checkout stored on the row
  //    - payment_status must still be 'unpaid' (replays affect 0 rows)
  const result = await wsDb.query(
    `UPDATE relocation_cases
        SET access_tier              = $1,
            payment_status           = $2,
            stripe_payment_intent_id = $3,
            paid_at                  = NOW(),
            paid_amount_cents        = $4,
            paid_currency            = $5
      WHERE id = $6
        AND stripe_session_id = $7
        AND payment_status = 'unpaid'
      RETURNING id, access_tier`,
    [
      tier,
      paymentStatus,
      typeof session.payment_intent === 'string'
        ? session.payment_intent
        : session.payment_intent?.id ?? null,
      session.amount_total,
      session.currency ?? 'eur',
      caseId,
      session.id,
    ]
  );

  if (!result.rows.length) {
    // Replay, or session/case mismatch — already handled; acknowledge quietly.
    console.log('[relopass-webhook] no-op (replay or mismatch) for session', session.id);
    return true;
  }

  console.log('[relopass-webhook] case unlocked', caseId, '→', tier);

  // 3. Confirmation email — fires at most once because the UPDATE above
  //    only succeeds on the first transition.
  try {
    await sendCasePaymentConfirmation({ workspaceId, caseId, session });
  } catch (err) {
    // The unlock is durable; the email is best-effort. Log and move on —
    // do NOT bubble up, or Stripe would retry and the guard would skip the
    // email anyway.
    console.error('[relopass-webhook] confirmation email failed for case', caseId, err);
  }

  return true;
}
