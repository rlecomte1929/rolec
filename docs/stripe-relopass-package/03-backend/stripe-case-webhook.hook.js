/**
 * Server function: stripe-case-webhook
 * POST /api/workspaces/workspace-776786/hooks/stripe-case-webhook/execute
 *
 * Accepts forwarded Stripe `checkout.session.completed` payloads — but NEVER
 * trusts them. The real Stripe webhook terminates at the Audos platform
 * (keys are platform-managed), so this hook re-verifies every session
 * against the platform Stripe status API before writing anything. A forged
 * "payment succeeded" call cannot unlock a case.
 *
 * Idempotent: dedups on stripe_session_id and skips rows already 'paid', so
 * webhook replays (and the lazy path in case-access) cannot double-unlock or
 * double-send the receipt email.
 *
 * REFERENCE IMPLEMENTATION reconstructed from the as-built spec — the
 * authoritative deployed code lives in the platform hooks registry
 * (GET /api/workspaces/776786/hooks).
 */

const event = request.body || {};

// Accept either a full Stripe event envelope or a bare { sessionId }.
const sessionId =
  (event.data && event.data.object && event.data.object.id) ||
  event.sessionId ||
  null;

if (!sessionId) {
  respond(400, { error: 'No checkout session id in payload' });
} else {
  const found = await db.query('case_access', {
    where: { stripe_session_id: sessionId },
    limit: 1,
  });
  const row = found.rows[0];

  if (!row) {
    // Not one of ours (or checkout was never started through case-checkout).
    respond(200, { received: true, matched: false });
  } else if (row.payment_status === 'paid') {
    // Replay — already confirmed. Idempotent no-op.
    respond(200, { received: true, alreadyPaid: true });
  } else {
    // NEVER trust the forwarded payload — re-verify with Stripe.
    const res = await fetch(`https://audos.com/api/payments/status/${sessionId}`);
    const status = res.ok ? await res.json() : null;

    if (!status || status.paymentStatus !== 'paid') {
      console.log('Session not paid per Stripe \u2014 no unlock', sessionId, status && status.paymentStatus);
      respond(200, { received: true, verified: false });
    } else {
      const updated = await db.update('case_access', { id: row.id }, {
        access_tier: 'roadmap',
        payment_status: 'paid',
        paid_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });
      const fresh = updated.updatedRows[0] || row;

      // Receipt email — see 05-email/receipt-email.md for the contract.
      if (fresh.customer_email) {
        const amount = `\u20ac${(fresh.amount_cents / 100).toLocaleString('en-GB')}`;
        await platform.sendEmail({
          to: fresh.customer_email,
          subject: 'ReloPass \u2014 Roadmap unlocked (receipt enclosed)',
          html: [
            `<h2>ReloPass \u2014 Roadmap unlocked</h2>`,
            `<p>Your full relocation roadmap and vendor shortlist for case #${fresh.id} (France \u2192 Norway) is now unlocked.</p>`,
            `<h3>Receipt</h3>`,
            `<p>Amount: <strong>${amount}</strong> (one-time)<br/>`,
            `Case reference: #${fresh.id}<br/>`,
            fresh.billing_company ? `Company: ${fresh.billing_company}<br/>` : '',
            fresh.billing_vat ? `VAT: ${fresh.billing_vat}<br/>` : '',
            `</p>`,
            `<p>This receipt is expensable as a professional service. Stripe also sends its own payment confirmation.</p>`,
          ].join('\n'),
        });
      }

      respond(200, { received: true, verified: true, caseId: fresh.id });
    }
  }
}
