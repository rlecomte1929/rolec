// relopass-payments.routes.ts
// ReloPass — Stripe Integration v1.0
//
// Exposes:
//   POST /api/relopass/cases/:caseId/checkout
//   GET  /api/relopass/cases/:caseId/access
//
// Registration — in server/routes/api/index.ts:
//   import relopassPaymentsRouter from './relopass-payments.routes';
//   router.use('/api', relopassPaymentsRouter);

import { Router, Request, Response } from 'express';
import Stripe from 'stripe';
import { authenticateDeviceTokenOrJWT } from '../middleware/auth';
import { stripeForWorkspace } from '../../services/stripe-router.service';
import { getWorkspaceDb } from '../../services/workspace-db';

const CHECKOUT_EXPIRY_MINUTES = 30;

function getPriceId(tier: string): string | null {
  switch (tier) {
    case 'roadmap':    return process.env.STRIPE_PRICE_ROADMAP_EUR ?? null;
    case 'essentials': return process.env.STRIPE_PRICE_ESSENTIALS_EUR ?? null;
    default:           return null;
  }
}

const router = Router();

// ── POST /api/relopass/cases/:caseId/checkout ─────────────────────────────
router.post(
  '/relopass/cases/:caseId/checkout',
  authenticateDeviceTokenOrJWT,
  async (req: Request, res: Response) => {
    const { caseId } = req.params;
    const { tier } = req.body as { tier: 'roadmap' | 'essentials' };
    const workspaceId = (req as any).workspaceId as string;

    if (!['roadmap', 'essentials'].includes(tier)) {
      return res.status(400).json({ error: 'invalid tier — must be roadmap or essentials' });
    }

    const wsDb = await getWorkspaceDb(workspaceId);
    const result = await wsDb.query(
      'SELECT id, access_tier FROM relocation_cases WHERE id = $1',
      [caseId]
    );
    if (!result.rows.length) return res.status(404).json({ error: 'case not found' });

    const caseRow = result.rows[0];
    if (tier === 'roadmap' && caseRow.access_tier !== 'free') {
      return res.status(400).json({ error: 'case already unlocked at this tier' });
    }
    if (tier === 'essentials' && caseRow.access_tier === 'essentials') {
      return res.status(400).json({ error: 'case already unlocked at this tier' });
    }

    const priceId = getPriceId(tier);
    if (!priceId) {
      return res.status(500).json({
        error: `Stripe price ID not configured for tier '${tier}' — set STRIPE_PRICE_${tier.toUpperCase()}_EUR`,
      });
    }

    const stripe: Stripe = await stripeForWorkspace(workspaceId);
    const appUrl = process.env.APP_URL ?? 'http://localhost:5173';

    const session = await stripe.checkout.sessions.create({
      mode: 'payment',
      line_items: [{ price: priceId, quantity: 1 }],
      success_url: `${appUrl}/case-command/cases/${caseId}?payment=success`,
      cancel_url: `${appUrl}/case-command/cases/${caseId}?payment=cancelled`,
      metadata: {
        workspaceId,
        caseId,
        tier,
        source: 'relopass_case_command',
      },
      billing_address_collection: 'required',
      custom_fields: [
        {
          key: 'company_name',
          label: { type: 'custom', custom: 'Company name (for your receipt)' },
          type: 'text',
          optional: true,
        },
        {
          key: 'vat_number',
          label: { type: 'custom', custom: 'VAT number (for your receipt)' },
          type: 'text',
          optional: true,
        },
      ],
      invoice_creation: { enabled: true },
      currency: 'eur',
      expires_at: Math.floor(Date.now() / 1000) + CHECKOUT_EXPIRY_MINUTES * 60,
    });

    // Store the session id so the webhook can match the completed session
    // back to this case. access_tier / payment_status are NOT touched here —
    // only the webhook may write them.
    await wsDb.query(
      'UPDATE relocation_cases SET stripe_session_id = $1 WHERE id = $2',
      [session.id, caseId]
    );

    return res.json({ checkoutUrl: session.url, sessionId: session.id });
  }
);

// ── GET /api/relopass/cases/:caseId/access ────────────────────────────────
router.get(
  '/relopass/cases/:caseId/access',
  authenticateDeviceTokenOrJWT,
  async (req: Request, res: Response) => {
    const { caseId } = req.params;
    const workspaceId = (req as any).workspaceId as string;

    const wsDb = await getWorkspaceDb(workspaceId);
    const result = await wsDb.query(
      `SELECT id, access_tier, payment_status, paid_at
         FROM relocation_cases
        WHERE id = $1`,
      [caseId]
    );
    if (!result.rows.length) return res.status(404).json({ error: 'case not found' });

    const caseRow = result.rows[0];

    // accountTier: retainer plan for the logged-in contact, if any
    // (contacts.metadata.planTier — 'starter' | 'growth' | null).
    const contactEmail = (req as any).userEmail as string | undefined;
    let accountTier: string | null = null;
    if (contactEmail) {
      const contact = await wsDb.query(
        `SELECT metadata->>'planTier' AS plan_tier
           FROM contacts
          WHERE lower(email) = lower($1)
          LIMIT 1`,
        [contactEmail]
      );
      accountTier = contact.rows[0]?.plan_tier ?? null;
    }

    // Paid add-ons for this case (v1 scaffold — empty until add-ons ship).
    const addons = await wsDb.query(
      `SELECT addon_type FROM case_addons
        WHERE case_id = $1 AND payment_status = 'paid'`,
      [caseId]
    );

    return res.json({
      caseId: caseRow.id,
      accessTier: caseRow.access_tier,
      paymentStatus: caseRow.payment_status,
      accountTier,
      availableAddons: addons.rows.map((r: { addon_type: string }) => r.addon_type),
    });
  }
);

export default router;
