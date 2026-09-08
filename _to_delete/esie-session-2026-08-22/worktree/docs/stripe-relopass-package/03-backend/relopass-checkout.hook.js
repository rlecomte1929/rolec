/**
 * Server function: relopass-checkout
 * POST /api/workspaces/776786/hooks/relopass-checkout/execute
 *
 * Creates the Stripe Checkout session for a ReloPass Case Command tier
 * unlock. Accepts { caseId, tier } (tier: 'roadmap' | 'essentials'; optional
 * successUrl / cancelUrl) and returns { checkoutUrl, sessionId }.
 *
 * Converted from docs/stripe-relopass-package/03-backend/
 * relopass-payments.routes.ts (POST /:caseId/checkout) to Audos hook style:
 *   - stripeForWorkspace(workspaceId)  → platform endpoint
 *     POST https://audos.com/api/payments/checkout (Stripe keys are
 *     platform-managed; sessions are priced by cents amount, there are no
 *     STRIPE_PRICE_* env price IDs on Audos)
 *   - getWorkspaceDb(workspaceId)      → the sandbox `db` global (already
 *     scoped to this workspace's WorkspaceDB)
 *   - relocation_cases                 → sidecar table `case_access`
 *     (payment columns cannot be added to relocation_cases; caseId =
 *     case_access.id)
 *
 * Pricing is fixed HERE, server-side — the client never sends an amount.
 * Display mirror: lib/pricing.ts. Per the routes reference, access_tier /
 * payment_status are NOT touched here — only the webhook / server-side
 * verification may write them. Only stripe_session_id (+ amount/currency
 * metadata for the receipt) is stored so the webhook can match the completed
 * session back to this case.
 */

const TIER_PRICES_CENTS = { roadmap: 80000, essentials: 200000 }; // €800 / €2,000
const CURRENCY = 'eur';
const SPACE_ID = 'workspace-776786';

const body = request.body || {};
const caseId = parseInt(body.caseId, 10);
const tier = body.tier;

function corridorLabel(corridor) {
  if (corridor === 'france-norway') return 'France \u2192 Norway';
  return String(corridor || 'relocation corridor');
}

if (!caseId) {
  respond(400, { error: 'caseId is required' });
} else if (tier !== 'roadmap' && tier !== 'essentials') {
  respond(400, { error: 'invalid tier — must be roadmap or essentials' });
} else {
  const found = await db.query('case_access', { where: { id: caseId }, limit: 1 });
  const caseRow = found.rows[0];

  if (!caseRow) {
    respond(404, { error: 'case not found' });
  } else if (tier === 'roadmap' && caseRow.access_tier !== 'free') {
    respond(400, { error: 'case already unlocked at this tier' });
  } else if (tier === 'essentials' && caseRow.access_tier === 'essentials') {
    respond(400, { error: 'case already unlocked at this tier' });
  } else {
    const amountCents = TIER_PRICES_CENTS[tier];
    const successUrl =
      typeof body.successUrl === 'string' && body.successUrl
        ? body.successUrl
        : 'https://audos.com/space/' + SPACE_ID + '?app=case-command&payment=success&caseId=' + caseId;
    const cancelUrl =
      typeof body.cancelUrl === 'string' && body.cancelUrl
        ? body.cancelUrl
        : successUrl.split('?')[0] + '?app=case-command';

    const productName =
      tier === 'roadmap'
        ? 'ReloPass \u2014 Full relocation roadmap + vendor shortlist'
        : 'ReloPass \u2014 Immigration assurance (Essentials)';

    const res = await fetch('https://audos.com/api/payments/checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-App-Id': SPACE_ID },
      body: JSON.stringify({
        amount: amountCents,
        currency: CURRENCY,
        productName: productName,
        productDescription:
          corridorLabel(caseRow.corridor) +
          ' corridor case #' + caseId +
          '. One-time unlock. Expensable as a professional service.',
        successUrl: successUrl,
        cancelUrl: cancelUrl,
        metadata: {
          workspaceId: workspaceId,
          caseId: String(caseId),
          tier: tier,
          source: 'relopass_case_command',
          corridor: caseRow.corridor || 'france-norway',
        },
      }),
    });
    const data = await res.json();

    if (!res.ok || !data.checkoutUrl) {
      console.error('Stripe checkout creation failed', JSON.stringify(data).slice(0, 500));
      respond(502, { error: 'could not create checkout session' });
    } else {
      // Store the session id so the webhook / lazy verification can match the
      // completed session back to this case. amount/currency are receipt
      // metadata; access_tier and payment_status stay untouched here.
      await db.update('case_access', { id: caseId }, {
        stripe_session_id: data.sessionId,
        amount_cents: amountCents,
        currency: CURRENCY,
        updated_at: new Date().toISOString(),
      });

      respond(200, { checkoutUrl: data.checkoutUrl, sessionId: data.sessionId });
    }
  }
}
