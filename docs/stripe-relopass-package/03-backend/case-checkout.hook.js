/**
 * Server function: case-checkout
 * POST /api/workspaces/workspace-776786/hooks/case-checkout/execute
 *
 * Creates the Stripe Checkout session for a Tier 1 roadmap unlock (€800
 * one-time). The amount is FIXED HERE, server-side — the client never sends
 * a price. Runs in the Audos hook sandbox (globals: request, respond, fetch,
 * db, platform, workspaceId).
 *
 * REFERENCE IMPLEMENTATION reconstructed from the as-built spec — the
 * authoritative deployed code lives in the platform hooks registry
 * (GET /api/workspaces/776786/hooks).
 */

// Authoritative Tier 1 price. Display mirror: lib/pricing.ts PRICE_ROADMAP_CENTS.
const PRICE_ROADMAP_CENTS = 80000; // €800.00
const CURRENCY = 'eur';

const { caseId, customerEmail, company, vat, successUrl, cancelUrl } = request.body || {};

if (!caseId || !customerEmail || !successUrl) {
  respond(400, { error: 'caseId, customerEmail and successUrl are required' });
} else {
  const existing = await db.query('case_access', { where: { id: caseId }, limit: 1 });
  const row = existing.rows[0];

  if (!row) {
    respond(404, { error: 'Unknown case' });
  } else if (row.payment_status === 'paid') {
    // Already unlocked — nothing to charge.
    respond(200, { alreadyPaid: true });
  } else {
    // Create the one-time Stripe Checkout session via the platform endpoint.
    // Stripe keys are platform-managed; the session is priced by cents amount.
    const res = await fetch('https://audos.com/api/payments/checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-App-Id': 'workspace-776786' },
      body: JSON.stringify({
        amount: PRICE_ROADMAP_CENTS,
        currency: CURRENCY,
        productName: 'ReloPass \u2014 Full relocation roadmap + vendor shortlist',
        productDescription: `France \u2192 Norway corridor case #${caseId}. One-time unlock. Expensable as a professional service.`,
        customerEmail,
        successUrl,
        cancelUrl: cancelUrl || successUrl,
        metadata: { caseId: String(caseId), product: 'case-roadmap-unlock', corridor: 'france-norway' },
      }),
    });
    const data = await res.json();

    if (!res.ok || !data.checkoutUrl) {
      console.error('Stripe checkout creation failed', data);
      respond(502, { error: 'Could not create checkout session' });
    } else {
      await db.update('case_access', { id: caseId }, {
        payment_status: 'pending',
        stripe_session_id: data.sessionId,
        amount_cents: PRICE_ROADMAP_CENTS,
        currency: CURRENCY,
        billing_company: (company || '').slice(0, 200) || null,
        billing_vat: (vat || '').slice(0, 50) || null,
        customer_email: customerEmail,
        updated_at: new Date().toISOString(),
      });

      respond(200, { url: data.checkoutUrl, sessionId: data.sessionId });
    }
  }
}
