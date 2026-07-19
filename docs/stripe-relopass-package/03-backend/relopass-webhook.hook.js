/**
 * Server function: relopass-webhook
 * POST /api/workspaces/776786/hooks/relopass-webhook/execute
 *
 * Stripe webhook receiver for ReloPass Case Command payments. Register this
 * URL in the Stripe Dashboard (event: checkout.session.completed):
 *   https://audos.com/api/workspaces/776786/hooks/relopass-webhook/execute
 *
 * Ported from the spec's webhook-extension.ts handleReloPassCasePayment():
 *   - only processes sessions with metadata.source === 'relopass_case_command'
 *   - updates the case row: payment_status='roadmap_paid',
 *     access_tier='roadmap', stripe_payment_intent_id, paid_at,
 *     paid amount (column amount_cents) WHERE id = caseId AND
 *     stripe_session_id = session.id
 *   - sends the confirmation/receipt email
 *
 * SECURITY (layered):
 *   1. Stripe-Signature gate — every request must carry a well-formed
 *      Stripe-Signature header (t=<unix ts>, v1=<64-hex HMAC>) whose
 *      timestamp is within 5 minutes; anything else is rejected 400 before
 *      any processing. NOTE: full cryptographic verification
 *      (stripe.webhooks.constructEvent) is NOT possible in the hook
 *      sandbox: there is no raw request body (only parsed JSON), no crypto
 *      primitives, no module loading, and no process.env — the
 *      STRIPE_WEBHOOK_SECRET workspace secret cannot be read here. The
 *      header is therefore validated structurally and for freshness.
 *   2. The payload is STILL never trusted: the session is re-verified
 *      against GET /api/payments/status/:sessionId before anything is
 *      written, so even a forged-but-well-formed request cannot unlock a
 *      case. Idempotent: rows already in a paid status are skipped, so
 *      webhook replays cannot double-unlock or double-send the receipt
 *      email.
 *
 * Table note: caseId = case_access.id (the sidecar payment table —
 * relocation_cases has no payment columns and cannot be ALTERed).
 */

const PAID_STATUSES = ['paid', 'roadmap_paid', 'essentials_paid'];

function corridorLabel(corridor) {
  if (corridor === 'france-norway') return 'France \u2192 Norway';
  return String(corridor || 'relocation corridor');
}

function formatEur(cents) {
  const whole = (cents || 0) / 100;
  return '\u20ac' + (Number.isInteger(whole) ? whole.toLocaleString('en-GB') : whole.toFixed(2));
}

async function sendConfirmationEmail(row) {
  if (!row.customer_email) return;
  const html = [
    '<h2>ReloPass \u2014 Roadmap unlocked</h2>',
    '<p>Your full relocation roadmap and vendor shortlist for case #' + row.id +
      ' (' + corridorLabel(row.corridor) + ') is now unlocked.</p>',
    '<h3>Receipt</h3>',
    '<p>Amount: <strong>' + formatEur(row.amount_cents) + '</strong> (one-time)<br/>',
    'Case reference: #' + row.id + '<br/>',
    row.billing_company ? 'Company: ' + row.billing_company + '<br/>' : '',
    row.billing_vat ? 'VAT: ' + row.billing_vat + '<br/>' : '',
    '</p>',
    '<p>This receipt is expensable as a professional service. Stripe also sends its own payment confirmation.</p>',
  ].join('\n');
  await platform.sendEmail({
    to: row.customer_email,
    subject: 'ReloPass \u2014 Roadmap unlocked (receipt enclosed)',
    html: html,
  });
}

// ---------------------------------------------------------------------------
// Stripe-Signature verification gate (see SECURITY note above). Runs before
// any other processing. Full HMAC recomputation is impossible in this
// sandbox (no raw body / crypto / STRIPE_WEBHOOK_SECRET access), so the
// header is checked for presence, well-formedness, and timestamp freshness.
// ---------------------------------------------------------------------------
const SIGNATURE_TOLERANCE_SECONDS = 300; // Stripe's own default tolerance

function checkStripeSignature(headerValue) {
  if (!headerValue || typeof headerValue !== 'string') {
    return { ok: false, reason: 'missing stripe-signature header' };
  }
  let timestamp = null;
  let v1Count = 0;
  const parts = headerValue.split(',');
  for (let i = 0; i < parts.length; i++) {
    const eq = parts[i].indexOf('=');
    if (eq === -1) continue;
    const key = parts[i].slice(0, eq).trim();
    const value = parts[i].slice(eq + 1).trim();
    if (key === 't') timestamp = parseInt(value, 10);
    if (key === 'v1' && /^[0-9a-f]{64}$/.test(value)) v1Count++;
  }
  if (!timestamp || !isFinite(timestamp)) {
    return { ok: false, reason: 'no timestamp (t=) in stripe-signature header' };
  }
  if (v1Count === 0) {
    return { ok: false, reason: 'no v1 signature in stripe-signature header' };
  }
  const ageSeconds = Math.abs(Date.now() / 1000 - timestamp);
  if (ageSeconds > SIGNATURE_TOLERANCE_SECONDS) {
    return { ok: false, reason: 'signature timestamp outside tolerance (' + Math.round(ageSeconds) + 's)' };
  }
  return { ok: true };
}

const sigCheck = checkStripeSignature(request.headers['stripe-signature']);

const event = request.body || {};

// Accept a full Stripe event envelope or a bare session object.
const session =
  (event.data && event.data.object) ||
  (event.object === 'checkout.session' ? event : null) ||
  (event.id && String(event.id).indexOf('cs_') === 0 ? event : null);

if (!sigCheck.ok) {
  console.error('[relopass-webhook] Signature verification failed:', sigCheck.reason);
  respond(400, { error: 'Invalid signature' });
} else if (event.type && event.type !== 'checkout.session.completed') {
  respond(200, { received: true, processed: 'ignored', reason: 'not checkout.session.completed' });
} else if (!session || !session.id) {
  respond(400, { error: 'no checkout session in payload' });
} else if (!session.metadata || session.metadata.source !== 'relopass_case_command') {
  // Not a ReloPass Case Command payment — leave it to other consumers.
  respond(200, { received: true, processed: 'ignored', reason: 'source mismatch' });
} else {
  const caseId = parseInt(session.metadata.caseId, 10);
  const tier = session.metadata.tier === 'essentials' ? 'essentials' : 'roadmap';

  const found = await db.query('case_access', {
    where: [
      { column: 'id', operator: '=', value: caseId },
      { column: 'stripe_session_id', operator: '=', value: session.id },
    ],
    limit: 1,
  });
  const row = found.rows[0];

  if (!caseId || !row) {
    respond(200, { received: true, matched: false });
  } else if (PAID_STATUSES.indexOf(row.payment_status) !== -1) {
    respond(200, { received: true, alreadyPaid: true });
  } else {
    // NEVER trust the payload — re-verify the session with Stripe.
    const res = await fetch('https://audos.com/api/payments/status/' + session.id);
    const status = res.ok ? await res.json() : null;

    if (!status || status.paymentStatus !== 'paid') {
      console.log('Session not paid per Stripe \u2014 no unlock', session.id, status && status.paymentStatus);
      respond(200, { received: true, verified: false });
    } else {
      const paymentIntentId =
        typeof session.payment_intent === 'string'
          ? session.payment_intent
          : (session.payment_intent && session.payment_intent.id) || null;

      const updated = await db.update('case_access',
        [
          { column: 'id', operator: '=', value: caseId },
          { column: 'stripe_session_id', operator: '=', value: session.id },
        ],
        {
          payment_status: tier + '_paid', // 'roadmap_paid' per spec
          access_tier: tier,
          stripe_payment_intent_id: paymentIntentId,
          paid_at: new Date().toISOString(),
          amount_cents: status.amountTotal || session.amount_total || row.amount_cents,
          customer_email:
            status.customerEmail ||
            (session.customer_details && session.customer_details.email) ||
            row.customer_email,
          updated_at: new Date().toISOString(),
        }
      );
      const fresh = (updated.updatedRows && updated.updatedRows[0]) || row;

      await sendConfirmationEmail(fresh);

      respond(200, { received: true, verified: true, caseId: fresh.id, accessTier: fresh.access_tier });
    }
  }
}
