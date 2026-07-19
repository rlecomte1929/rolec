/**
 * Server function: case-access
 * POST /api/workspaces/workspace-776786/hooks/case-access/execute
 *
 * Reads (and lazily creates) the access state for a corridor-check case, and
 * performs LAZY server-side payment verification: any 'pending' row with a
 * Stripe session id is re-checked against the platform Stripe status API on
 * every read, so the unlock lands even if no webhook was forwarded.
 *
 * REFERENCE IMPLEMENTATION reconstructed from the as-built spec — the
 * authoritative deployed code lives in the platform hooks registry
 * (GET /api/workspaces/776786/hooks).
 */

const { caseId, caseKey, create } = request.body || {};

function toResponse(row) {
  return {
    caseId: row.id,
    accessTier: row.access_tier,
    paymentStatus: row.payment_status,
    unlockedAt: row.paid_at || null,
    employeeType: row.employee_type || null,
    moveDate: row.move_date || null,
  };
}

async function sendReceiptEmail(row) {
  if (!row.customer_email) return;
  const amount = `\u20ac${(row.amount_cents / 100).toLocaleString('en-GB')}`;
  const lines = [
    `<h2>ReloPass \u2014 Roadmap unlocked</h2>`,
    `<p>Your full relocation roadmap and vendor shortlist for case #${row.id} (France \u2192 Norway) is now unlocked.</p>`,
    `<h3>Receipt</h3>`,
    `<p>Amount: <strong>${amount}</strong> (one-time)<br/>`,
    `Case reference: #${row.id}<br/>`,
    row.billing_company ? `Company: ${row.billing_company}<br/>` : '',
    row.billing_vat ? `VAT: ${row.billing_vat}<br/>` : '',
    `</p>`,
    `<p>This receipt is expensable as a professional service. Stripe also sends its own payment confirmation.</p>`,
  ];
  await platform.sendEmail({
    to: row.customer_email,
    subject: 'ReloPass \u2014 Roadmap unlocked (receipt enclosed)',
    html: lines.join('\n'),
  });
}

/** Re-verify a pending payment against Stripe; upgrade the row if paid. */
async function verifyPending(row) {
  if (row.payment_status !== 'pending' || !row.stripe_session_id) return row;
  try {
    const res = await fetch(`https://audos.com/api/payments/status/${row.stripe_session_id}`);
    if (!res.ok) return row;
    const status = await res.json();
    if (status.paymentStatus === 'paid') {
      const updated = await db.update('case_access', { id: row.id }, {
        access_tier: 'roadmap',
        payment_status: 'paid',
        paid_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });
      const fresh = updated.updatedRows[0] || row;
      await sendReceiptEmail(fresh);
      return fresh;
    }
  } catch (e) {
    console.error('Lazy Stripe verification failed', e && e.message);
  }
  return row;
}

let row = null;

if (caseId) {
  const byId = await db.query('case_access', { where: { id: caseId }, limit: 1 });
  row = byId.rows[0] || null;
}
if (!row && caseKey) {
  const byKey = await db.query('case_access', { where: { case_key: caseKey }, limit: 1 });
  row = byKey.rows[0] || null;
}

// First check for this caseKey — create the free row.
if (!row && caseKey && create && create.employeeType && create.moveDate) {
  const inserted = await db.insert('case_access', {
    case_key: caseKey,
    corridor: 'france-norway',
    employee_type: create.employeeType,
    move_date: create.moveDate,
    access_tier: 'free',
    payment_status: 'unpaid',
    session_id: create.sessionId || null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  });
  row = inserted.insertedRows[0];
}

if (!row) {
  respond(404, { error: 'Case not found' });
} else {
  row = await verifyPending(row);
  respond(200, toResponse(row));
}
