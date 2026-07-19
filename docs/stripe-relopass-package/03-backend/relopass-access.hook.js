/**
 * Server function: relopass-access
 * GET /api/workspaces/776786/hooks/relopass-access/execute?caseId=<id>
 *
 * Access state for a ReloPass Case Command case. Returns
 *   { caseId, accessTier, paymentStatus, accountTier, availableAddons }
 * (+ employeeType / moveDate / unlockedAt so the frontend can restore the
 * case inputs after the Stripe redirect).
 *
 * Converted from docs/stripe-relopass-package/03-backend/
 * relopass-payments.routes.ts (GET /:caseId/access) to Audos hook style
 * (getWorkspaceDb → sandbox `db`, relocation_cases → sidecar `case_access`,
 * caseId = case_access.id).
 *
 * LAZY VERIFICATION (platform reality): the real Stripe webhook terminates at
 * the Audos platform, so until the relopass-webhook hook is registered in the
 * Stripe Dashboard no event reaches this workspace. Any row with a
 * stripe_session_id that is not yet paid is therefore re-verified against
 * GET /api/payments/status/:sessionId on every read — the unlock lands even
 * without a webhook. Idempotent: the upgrade (and the receipt email) only
 * fires on the row's first transition to a paid status.
 *
 * accountTier: the routes reference reads contacts.metadata->>'planTier' for
 * the authenticated user. Hooks have no authenticated user, so the caller may
 * pass &email=<contact email>; the CRM contact's metadata.planTier is
 * returned, else null.
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

/** Re-verify an unpaid row that has a Stripe session; upgrade it if paid. */
async function verifyPending(row) {
  if (!row.stripe_session_id || PAID_STATUSES.indexOf(row.payment_status) !== -1) return row;
  try {
    const res = await fetch('https://audos.com/api/payments/status/' + row.stripe_session_id);
    if (!res.ok) return row;
    const status = await res.json();
    if (status.paymentStatus === 'paid') {
      const tier = (status.amountTotal || row.amount_cents) >= 200000 ? 'essentials' : 'roadmap';
      const updated = await db.update('case_access', { id: row.id }, {
        access_tier: tier,
        payment_status: tier + '_paid',
        paid_at: new Date().toISOString(),
        amount_cents: status.amountTotal || row.amount_cents,
        customer_email: status.customerEmail || row.customer_email,
        updated_at: new Date().toISOString(),
      });
      const fresh = (updated.updatedRows && updated.updatedRows[0]) || row;
      await sendConfirmationEmail(fresh);
      return fresh;
    }
  } catch (e) {
    console.error('Lazy Stripe verification failed', e && e.message);
  }
  return row;
}

const caseId = parseInt((request.query && request.query.caseId) || (request.body && request.body.caseId), 10);
const email = (request.query && request.query.email) || (request.body && request.body.email) || null;

if (!caseId) {
  respond(400, { error: 'caseId is required' });
} else {
  const found = await db.query('case_access', { where: { id: caseId }, limit: 1 });
  let row = found.rows[0];

  if (!row) {
    respond(404, { error: 'case not found' });
  } else {
    row = await verifyPending(row);

    // accountTier: retainer plan for the identified contact, if any.
    let accountTier = null;
    if (email) {
      try {
        const result = await platform.getContacts({ limit: 100 });
        const contacts = (result && result.contacts) || [];
        const match = contacts.find(function (c) {
          return c.email && String(c.email).toLowerCase() === String(email).toLowerCase();
        });
        accountTier = (match && match.metadata && match.metadata.planTier) || null;
      } catch (e) {
        console.error('accountTier lookup failed', e && e.message);
      }
    }

    // Paid add-ons for this case (v1 scaffold — empty until add-ons ship).
    const addons = await db.query('case_addons', {
      where: [
        { column: 'case_access_id', operator: '=', value: caseId },
        { column: 'payment_status', operator: '=', value: 'paid' },
      ],
    });

    respond(200, {
      caseId: row.id,
      accessTier: row.access_tier,
      paymentStatus: row.payment_status,
      accountTier: accountTier,
      availableAddons: addons.rows.map(function (r) { return r.addon_type; }),
      employeeType: row.employee_type || null,
      moveDate: row.move_date ? new Date(row.move_date).toISOString().slice(0, 10) : null,
      unlockedAt: row.paid_at || null,
    });
  }
}
