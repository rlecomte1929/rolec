// case-payment-confirmation.ts
// ReloPass — Stripe Integration v1.0
//
// Confirmation + expensable receipt email, sent by the webhook extension
// (03-backend/webhook-extension.ts) after the FIRST transition of a case to
// a paid status. Idempotency is guaranteed upstream: the webhook's
// conditional UPDATE only succeeds once per case, so this function can never
// double-send.

import Stripe from 'stripe';
import { sendEmail } from './mailer'; // existing transactional mailer

const TIER_LABEL: Record<string, string> = {
  roadmap: 'M1 Roadmap + Verified Vendor Shortlist',
  essentials: 'Essentials — Immigration assurance',
};

export interface CasePaymentConfirmationParams {
  workspaceId: string;
  caseId: string;
  session: Stripe.Checkout.Session;
}

function customField(session: Stripe.Checkout.Session, key: string): string | null {
  const field = session.custom_fields?.find((f) => f.key === key);
  return field?.text?.value ?? null;
}

function formatAmount(session: Stripe.Checkout.Session): string {
  const cents = session.amount_total ?? 0;
  const currency = (session.currency ?? 'eur').toUpperCase();
  const whole = cents / 100;
  const amount = Number.isInteger(whole) ? whole.toLocaleString('en-GB') : whole.toFixed(2);
  return currency === 'EUR' ? `€${amount}` : `${amount} ${currency}`;
}

export async function sendCasePaymentConfirmation({
  workspaceId,
  caseId,
  session,
}: CasePaymentConfirmationParams): Promise<void> {
  const to = session.customer_details?.email;
  if (!to) {
    console.warn('[case-payment-confirmation] no customer email on session', session.id);
    return;
  }

  const tier = session.metadata?.tier ?? 'roadmap';
  const tierLabel = TIER_LABEL[tier] ?? tier;
  const amount = formatAmount(session);
  const company = customField(session, 'company_name');
  const vat = customField(session, 'vat_number');

  const appUrl = process.env.APP_URL ?? '';
  const caseUrl = `${appUrl}/case-command/cases/${caseId}`;

  // Hosted invoice link — available because the checkout session was created
  // with invoice_creation: { enabled: true }. May lag session completion by a
  // few seconds; omit the line rather than fail if it isn't expanded yet.
  const invoiceUrl =
    typeof session.invoice === 'object' && session.invoice !== null
      ? (session.invoice as Stripe.Invoice).hosted_invoice_url ?? null
      : null;

  const receiptRows = [
    `<tr><td>Item</td><td><strong>${tierLabel}</strong></td></tr>`,
    `<tr><td>Amount</td><td><strong>${amount}</strong> (one-time)</td></tr>`,
    `<tr><td>Case reference</td><td>#${caseId}</td></tr>`,
    company ? `<tr><td>Company</td><td>${company}</td></tr>` : '',
    vat ? `<tr><td>VAT number</td><td>${vat}</td></tr>` : '',
  ]
    .filter(Boolean)
    .join('\n');

  await sendEmail({
    to,
    subject: 'ReloPass — Your roadmap is unlocked (receipt enclosed)',
    html: `
      <h2>Your roadmap is unlocked</h2>
      <p>
        The full relocation roadmap and verified vendor shortlist for your
        France → Norway case is now available — every requirement in
        chronological order, with deadlines, owners and feasibility flags.
      </p>
      <p><a href="${caseUrl}">Open your case</a></p>

      <h3>Receipt</h3>
      <table>${receiptRows}</table>
      ${invoiceUrl ? `<p><a href="${invoiceUrl}">Download your Stripe invoice</a></p>` : ''}

      <p>
        This receipt is expensable as a professional service. Stripe also
        sends its own payment confirmation separately.
      </p>
    `,
  });

  console.log('[case-payment-confirmation] sent for case', caseId, 'to', to);
}
