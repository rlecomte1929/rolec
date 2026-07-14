/**
 * Content for the public /compliance page (AIQ-828 · DIGEST-2).
 *
 * ⚠️ HARD RULE — [AIQ-1513] DO NOT MAKE AN EU AI ACT STATUS CLAIM HERE.
 *
 * No "EU AI Act Ready", "compliant", "certified", or equivalent. Per
 * docs/compliance/AIQ-1487_eu_ai_act_assessment.md:
 *
 *   "Do not ship an 'EU AI Act Ready' / 'Compliant' badge. For a limited-risk
 *    system there is no certification to be 'ready' for, and the phrasing
 *    implies a formal status we don't hold."
 *   "A false or premature compliance claim is itself a legal liability."
 *
 * That assessment also found ReloPass's AI is **limited-risk, NOT high-risk** —
 * so copy must never imply we are a high-risk HR system either.
 *
 * What this page MAY say: what our controls actually do — human review on every
 * AI recommendation, an audit log pairing each decision with the AI output that
 * informed it, source-grounded answers, PII masked before any LLM call. Those are
 * verifiable product facts, not a legal status. Describe the controls; claim no
 * status. Any NEW compliance claim needs legal sign-off before it ships.
 *
 * scripts/check_compliance_claims.py enforces this in CI.
 */

export const ENTERPRISE_CONTACT_EMAIL = 'contact@relopass.com';

export const complianceContent = {
  hero: {
    badge: 'Human oversight by design',
    eyebrow: 'Trust',
    headline: 'Mobility AI your auditor will trust.',
    subheadline:
      'Every AI recommendation is reviewed by a human. Every decision is logged with the AI output that informed it. Every answer is grounded in your own policy — and cited.',
    trustMicrocopy:
      'We make no compliance certification claim. Below is exactly how the AI works, and what we record — so your compliance team can assess it themselves.',
  },

  // How the AI actually works. Controls, not status claims — see the hard rule above.
  readiness: {
    sectionHeader: 'How AI works at ReloPass',
    title: 'Controls you can inspect, not a badge.',
    body:
      'ReloPass AI answers policy questions, estimates costs, and suggests service providers. It does not make hiring, promotion, or termination decisions, and it does not score or rank people. A human accepts, overrides, or rejects every recommendation it produces. Here is what that means in practice.',
    checklist: [
      'Human oversight on every AI recommendation (accept / override / reject).',
      'A complete, timestamped record of each decision and the AI output behind it.',
      'Source-grounded answers: the AI cites your policy and declines when it is not covered.',
      'Personal details are masked before any text is sent to an AI sub-processor.',
    ],
  },

  // AIQ-1240: explicit AI-systems inventory (EU AI Act transparency, Art. 13).
  // Every claim here is scoped to what is verifiable in the codebase. The
  // text-LLM paths (policy assistant, policy extraction) provably receive only
  // policy text + the question — not passport/identity/DOB/family data
  // (see docs/privacy/data-residency-and-gdpr.md "What we send to OpenAI").
  // Document OCR is described honestly as processing uploaded document content.
  aiSystems: {
    sectionHeader: 'AI systems we use',
    title: 'Every AI system, named — and what it works on.',
    body:
      'The EU AI Act expects transparency about which AI systems run and on what data. This is the full inventory. The policy AI receives your policy text and the question being asked — not passport numbers, dates of birth, or family data.',
    cards: [
      {
        title: 'Policy assistant (Q&A)',
        body: 'Answers HR and employee questions from your published policy only — grounded, cited, and declines when something is out of policy. Receives the question and the matching policy text.',
      },
      {
        title: 'Policy document extraction',
        body: 'Turns an uploaded corporate policy document into structured benefit rules for a human to review. Reads the policy document text — a corporate document, not employee identity data.',
      },
      {
        title: 'Case guidance & roadmaps',
        body: 'Proposes relocation steps and provider or corridor matches for a person to confirm. Operates on case structure and your policy rules; nothing is applied without human review.',
      },
      {
        title: 'Document text recognition (OCR)',
        body: 'Reads text from documents you upload to reduce manual data entry. Civil-status documents (e.g. birth or marriage certificates) use an EU-hosted provider (Mistral AI, France); identity documents such as passports use OpenAI vision (US) under standard contractual clauses.',
      },
    ],
  },

  // The substance: the REAL oversight flow (Art. 14).
  oversight: {
    sectionHeader: 'Human oversight',
    title: 'A person decides. Every time.',
    body:
      'No AI recommendation is applied without a human decision. ReloPass surfaces a recommendation; a named HR or admin user reviews it and records an explicit decision. The platform stores that decision next to the exact AI output it was based on, so an auditor can reconstruct who decided what, when, and why.',
    steps: [
      {
        number: '01',
        title: 'AI recommends',
        body: 'The platform proposes — a policy insight, an exception assessment, a provider or corridor match — and shows the reasoning and the policy it relied on.',
      },
      {
        number: '02',
        title: 'A human reviews',
        body: 'A named HR or admin user reads the recommendation in context. Override and reject require a written reason; nothing is auto-applied.',
      },
      {
        number: '03',
        title: 'The decision is logged',
        body: 'Accept, override, or reject — the choice, the reviewer, the timestamp, and the original AI output are written to an immutable audit record.',
      },
      {
        number: '04',
        title: 'Auditors can replay it',
        body: 'Every AI-assisted decision is queryable and exportable, so your compliance team can evidence effective oversight on demand.',
      },
    ],
  },

  // Transparency + data processing.
  transparency: {
    sectionHeader: 'Transparency & data processing',
    title: 'Grounded answers, not guesses.',
    cards: [
      {
        title: 'Cited, not invented',
        body: 'The policy assistant answers only from your company’s published policy and shows the source for each claim. If something isn’t covered, it says so instead of guessing.',
      },
      {
        title: 'Purpose-bound data',
        body: 'Personal data is processed to run the relocation case it belongs to — scoped to the employee’s company, never pooled across tenants.',
      },
      {
        title: 'EU-hosted infrastructure',
        body: 'Case data is stored on EU-region infrastructure, with row-level tenant isolation enforced at the database.',
      },
    ],
  },

  // AIQ-1240: data governance + GDPR. Wording is deliberately conservative —
  // every line maps to docs/security/PRIV-004_sub-processor_register.md and
  // docs/privacy/data-residency-and-gdpr.md. "Available on request" is used
  // rather than "in place" for the DPA, since sub-processor DPA signatures are
  // still pending (see PRIV-004 §"Actions still requiring human sign-off").
  dataGovernance: {
    sectionHeader: 'Data governance & GDPR',
    title: 'EU-resident by default. Disclosed where it isn’t.',
    cards: [
      {
        title: 'EU data residency',
        body: 'Your case data — cases, profiles, uploaded documents, and audit logs — is stored in the EU (Supabase, Ireland), with row-level tenant isolation enforced at the database.',
      },
      {
        title: 'Named sub-processors',
        body: 'We keep a current sub-processor register (Supabase, Anthropic, OpenAI, Mistral, Render, Resend). Where a provider processes data outside the EU, it is covered by standard contractual clauses. A DPA is available for enterprise customers on request.',
      },
      {
        title: 'Minimised before AI',
        body: 'Personal data is minimised before it reaches a language model: the policy assistant masks direct identifiers, and the policy AI receives policy text and questions — not identity-document or family data.',
      },
      {
        title: 'Your rights (GDPR)',
        body: 'Erasure requests (Article 17) are actioned per case — identifying fields are redacted and the case removed from every view. Data-residency details and our sub-processor list are available to your DPO on request.',
      },
    ],
  },

  // Audit trail.
  audit: {
    sectionHeader: 'Record-keeping',
    title: 'An audit trail you can hand to a regulator.',
    body:
      'Decisions, document changes, and AI-assisted actions are recorded with actor, timestamp, and the data they touched. The AI-decision log pairs each human decision with the AI output that informed it, so the reasoning behind a case can be reconstructed after the fact.',
  },

  // Final CTA + the explicit enterprise contact.
  finalCta: {
    headline: 'Assessing AI in your mobility stack?',
    microCopy:
      'Book a walkthrough of the oversight flow and the audit trail. Your compliance team can review the controls directly.',
    demoCtaLabel: 'Book a demo',
    enterpriseLine: 'For EU enterprise inquiries:',
  },

  // Footer disclaimer. [AIQ-1513] States what we do NOT claim — no status, no certification.
  disclaimer:
    'This page describes how ReloPass’s AI features work and what we record. It is not a certification, a compliance guarantee, or a statement of regulatory status — and it is not legal advice. Your own obligations depend on how you deploy and use the product.',
};
