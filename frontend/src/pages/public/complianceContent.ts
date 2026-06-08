/**
 * Content for the public /compliance page (AIQ-828 · DIGEST-2).
 *
 * Edit copy here without touching layout. Two hard rules from the brief:
 *   1. Say "EU AI Act Ready" — never "Certified" (no certification scheme
 *      exists yet under the EU AI Act).
 *   2. The Human Oversight section must accurately reflect ReloPass's real
 *      flow: AI produces recommendations; a human (HR/Admin) explicitly
 *      accepts / overrides / rejects each one; the decision and the original
 *      AI output are written to an immutable audit log (EU AI Act Art. 14).
 *      This mirrors backend/app/routers/ai_decisions.py.
 *
 * ⚠️ Romain to confirm before production publish: data-residency wording
 * ("EU-hosted"), the contact address, and the simplified-documentation
 * threshold figures. Sources are linked in the AI Work Queue task.
 */

export const PDF_ONEPAGER_PATH = '/relopass-eu-ai-act-ready.pdf';
export const ENTERPRISE_CONTACT_EMAIL = 'contact@relopass.com';

export const complianceContent = {
  hero: {
    badge: 'EU AI Act Ready',
    eyebrow: 'Compliance',
    headline: 'Mobility AI your auditor will trust.',
    subheadline:
      'ReloPass is built for the EU AI Act: every AI recommendation is reviewed by a human, every decision is logged with the AI output that informed it, and every answer is grounded in your own policy — and cited.',
    trustMicrocopy:
      '“Ready,” not “certified” — there is no EU AI Act certification scheme yet. Here is exactly what readiness means at ReloPass.',
  },

  // What "Ready" honestly means — sets expectations and avoids overclaiming.
  readiness: {
    sectionHeader: 'What “EU AI Act Ready” means',
    title: 'Readiness is a posture, not a certificate.',
    body:
      'The EU AI Act phases in obligations for high-risk HR AI systems over the coming years. No certification body issues an “EU AI Act certificate” today. “EU AI Act Ready” means ReloPass already operates the controls the Act asks for — human oversight, transparency, record-keeping, and data governance — so your compliance team can document them now, as the obligations phase in.',
    checklist: [
      'Human oversight on every AI recommendation (accept / override / reject).',
      'A complete, timestamped record of each decision and the AI output behind it.',
      'Source-grounded answers: the AI cites your policy and declines when it is not covered.',
      'Documentation built in: the record-keeping the Act expects is produced as you operate, not bolted on later.',
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

  // Audit trail.
  audit: {
    sectionHeader: 'Record-keeping',
    title: 'An audit trail you can hand to a regulator.',
    body:
      'Decisions, document changes, and AI-assisted actions are recorded with actor, timestamp, and the data they touched. The AI-decision log pairs each human decision with the AI output that informed it — the Art. 14 evidence high-risk HR systems are expected to keep.',
  },

  // Final CTA + the explicit enterprise contact + PDF.
  finalCta: {
    headline: 'Building your EU AI Act file?',
    microCopy:
      'Download the one-page summary for your compliance and procurement teams, or book a walkthrough of the oversight and audit trail.',
    pdfCtaLabel: 'Download the one-pager (PDF)',
    demoCtaLabel: 'Book a demo',
    enterpriseLine: 'For EU enterprise inquiries:',
  },

  // Footer disclaimer — load-bearing for "Ready not Certified".
  disclaimer:
    '“EU AI Act Ready” describes ReloPass’s readiness posture and documentation. It is not a certification or a legal compliance guarantee — no EU AI Act certification scheme exists yet, and obligations depend on your own deployment and use. This page is informational, not legal advice.',
};
