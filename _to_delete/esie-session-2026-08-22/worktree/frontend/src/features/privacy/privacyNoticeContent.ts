/**
 * Art. 13 privacy notice — point-of-collection copy (PRIV-005 / AIQ-473).
 *
 * Ship-ready copy from audit/gdpr/priv-005_privacy_notice_v1.md §2.1, with the
 * Art. 13(2)(e) consequence clause folded in (flagged for v1.1 in §3 of the spec).
 *
 * PRIVACY_NOTICE_VERSION is the source of truth for re-acknowledgement: bump it
 * whenever the copy below changes materially (scope, retention, recipients) and
 * every data subject is re-prompted on their next point of collection.
 */

/** Bump on any material copy change → triggers re-acknowledgement. */
export const PRIVACY_NOTICE_VERSION = '2026-06-03-v1.0';

export type NoticeSection = {
  title: string;
  body: string;
};

export const privacyNoticeContent = {
  /** One-line headline + lede shown above the fold. */
  headline: 'Your data, in plain English.',
  lede: 'Before we ask you anything, here’s what we’ll do with your answers.',

  /** Full Art. 13 detail — revealed under "Read the full notice". */
  sections: [
    {
      title: 'Who we are',
      body:
        'ReloPass SAS (registered in France) is the company processing your data. We’re acting on behalf of your employer to help with your international move. Your employer asked us to do this work, and we both follow EU data protection law (GDPR).',
    },
    {
      title: 'What we collect',
      body:
        'Documents you upload (passports, employment contracts, certificates), the answers you give in this workspace, and your contact details. If you tell us about your family, we also collect their data — with your confirmation that you’re authorised to share it.',
    },
    {
      title: 'Why we collect it',
      body:
        'To file the immigration applications, register your address, set up your payroll, and coordinate the services your move requires. We do not use your data for anything else.',
    },
    {
      title: 'The legal basis',
      body:
        'Most of what we do is to perform the contract between you, your employer, and ReloPass (GDPR Article 6(1)(b)). Some processing of sensitive data (family records, health insurance proof) is necessary under employment and social-security law (Article 9(2)(b)). Providing the required data is a contractual necessity — failure to provide it may delay or prevent your relocation.',
    },
    {
      title: 'Who else sees it',
      body:
        'Your HR team at your employer sees what we extract. The immigration authorities receive the formal applications. Specialised vendors (translators, notaries) see only the documents they need to do their work — and only after you approve their involvement. We do not sell or share your data with anyone else.',
    },
    {
      title: 'Where your data lives',
      body:
        'Inside the European Union. We use European cloud providers (Supabase, Render, Cloudflare) for storage and compute. Our AI tools — for reading your documents and pre-filling your forms — run on European infrastructure provided by Mistral AI, Microsoft Azure, Anthropic, and OpenAI. Each provider is bound by a data processing agreement that forbids using your data to train their models.',
    },
    {
      title: 'How long we keep it',
      body:
        'Your active case data is kept while your move is in progress and for 12 months after the case closes. Audit records — proof that we followed the rules — are kept for 6 years to meet our legal obligations under the EU AI Act and accounting law.',
    },
    {
      title: 'Your rights',
      body:
        'You can see your data (ask for a copy in machine-readable format), correct it, delete it (except where law requires us to keep audit records), restrict processing, object to any processing not strictly necessary for the contract, and withdraw consent where processing is based on consent. You can also complain to a regulator — in France, the CNIL (cnil.fr).',
    },
    {
      title: 'AI-assisted decisions',
      body:
        'Our AI extracts values from your documents and surfaces possible contradictions. Every value is shown to you for confirmation before we file anything. No AI makes terminal decisions about your move — your HR team does, with you. You can review the audit trail of any AI decision on request.',
    },
    {
      title: 'Contact us',
      body:
        'dpo@relopass.com for any privacy question. We answer within 72 hours; complete handling within 1 month per GDPR Article 12(3).',
    },
  ] as NoticeSection[],

  /** Label on the acknowledgement checkbox. */
  acknowledgement: 'I have read and understood how my data will be used.',
};
