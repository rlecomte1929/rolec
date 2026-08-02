-- 20261010000000_seed_es_ie_immigration_corpus_docs.sql
-- Seed the ES_IE (Spain -> Ireland, Critical Skills) immigration corpus source docs.
--
-- Populates crawled_immigration_documents (the N1 crawl store). After this migration
-- applies, run the N2 indexer ON RENDER (where OPENAI_API_KEY is set) to chunk + embed
-- these into immigration_corpus_chunks so the roadmap retriever stops returning
-- RULE_NOT_FOUND for ES_IE:
--
--     python -m backend.app.services.immigration_chunk_indexer --corridor ES_IE
--
-- Embeddings are intentionally NOT hand-written here: every corridor's corpus is
-- embedded by the indexer with the same OpenAI model the retriever queries with
-- (HashEmbedder without a key would not match prod vectors). Idempotent on
-- (corridor, source_url, content_hash); re-running the migration is a no-op, and the
-- indexer skips already-embedded (source_doc_id, content_hash) pairs.
--
-- Lead times in the text are marked as ESTIMATES pending confirmation against recent
-- real cases (the beta tester's relocation agent is the ground-truth check).

begin;

insert into public.crawled_immigration_documents
  (corridor, source_url, trust_tier, extracted_text, content_hash, http_status, is_active)
values
  ('ES_IE', 'https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/', 1, '# Ireland Critical Skills Employment Permit (CSEP) — eligibility and salary (Spain to Ireland)

The Critical Skills Employment Permit (CSEP) is the primary route for a non-EEA national taking up an eligible tech role in Ireland, under the Employment Permits Act 2024. Either the employer or the employee may apply; in practice the employer files it through Employment Permits Online. A two-year employment contract is required and no labour market needs test applies.

2026 minimum annual salary thresholds (from 1 March 2026): approximately EUR 40,904 for occupations on the Critical Skills Occupations List (CSOL) held with a relevant degree; approximately EUR 68,911 for eligible occupations that are not on the CSOL; and approximately EUR 36,848 for a person who graduated within the previous 12 months in a CSOL role. Whether a specific job is on the CSOL determines which floor applies, and must be confirmed against the current DETE list for the exact job title — this is a determination for the employer or a qualified adviser, not an assumption.

Critical Skills holders receive immediate family reunification (a spouse or de-facto partner may live on Stamp 1G with the right to work without a separate permit) and become eligible to apply for Stamp 4 after 21 months, after which they can work without an employment permit. Source: Department of Enterprise, Trade and Employment (DETE).', '046290c03b4aaa7290b7fea93f7ce1d97d3b7ae8ead2eaada1493319419bb210', 200, true),
  ('ES_IE', 'https://emn.ie/legislation/council-directive-2003-109-ec-of-25-november-2003-concerning-the-status-of-third-country-nationals-who-are-long-term-residents/', 1, '# Long-term residence in Spain does not transfer to Ireland

A non-EEA national who holds long-term residence, or a TIE residence card, in Spain does NOT thereby gain any right to enter, reside, or work in Ireland. Ireland is not bound by the EU Long-Term Residents Directive (Council Directive 2003/109/EC), so EU long-term resident status acquired in another member state confers no intra-EU mobility right into Ireland.

The full Irish process therefore applies regardless of how many years the person has been legally resident in Spain: an Irish employment permit, an entry visa where the nationality is visa-required, and in-person immigration registration after arrival. This is one of the most common and costly misconceptions for someone who has already lived in the EU for years and assumes free movement into Ireland. Source: European Migration Network Ireland / Council Directive 2003/109/EC.', '7c93c32f0b44da3e0df2e2820b284cd8199fbd33ba32e53c0b525cdca2a61d2d', 200, true),
  ('ES_IE', 'https://www.irishimmigration.ie/coming-to-work-in-ireland/what-are-my-work-visa-options/applying-for-a-long-stay-employment-visa/', 1, '# Ireland is outside Schengen — a Venezuelan national needs a long-stay ''D'' Employment visa before travel

Ireland is not part of the Schengen area; it operates a Common Travel Area with the United Kingdom only. A Spanish residence card or a Schengen visa does not permit entry to Ireland. Venezuela is a visa-required nationality for Ireland, so a Venezuelan national must obtain a long-stay ''D'' Employment visa BEFORE travelling to take up employment for more than 90 days.

The ''D'' visa is applied for only AFTER the employment permit has been granted, through the Irish visa system handling applications from Spain. Processing-time estimate — NOT yet verified against recent real cases; confirm with the relocation agent on the ground: the long-stay employment visa commonly takes on the order of 4 to 8 weeks, but this varies by mission and season. Source: Immigration Service Delivery (ISD).', '5d9840397d77c1f8c4fb22577872990787d629855708617c5b3719163f19de93', 200, true),
  ('ES_IE', 'https://www.irishimmigration.ie/registering-your-immigration-permission/', 1, '# An employment permit is not immigration permission — register for the IRP (Stamp 1) within 90 days

An Irish employment permit issued by DETE is a labour-market authorisation, not immigration permission. After arriving in Ireland, a non-EEA worker must register their immigration permission in person and receive an Irish Residence Permit (IRP) card carrying Stamp 1. Registration must be completed within 90 days of arrival, and the registration fee is EUR 300. First-time registrations for people living in Dublin are handled at the Immigration Service Delivery registration office at Burgh Quay.

Appointment lead-time estimate — NOT yet verified against recent real cases; confirm with the relocation agent on the ground: a first Burgh Quay appointment commonly takes on the order of 6 to 8 weeks to secure, and it is a well-known bottleneck, so book as early as possible after arrival. Source: Immigration Service Delivery (ISD).', '3471a0a2a823168c30b3212d419fbde839803410a95851af45543af676c22269', 200, true),
  ('ES_IE', 'https://www.revenue.ie/en/jobs-and-pensions/starting-work/index.aspx', 1, '# PPSN and Revenue payroll registration — avoiding emergency tax

To be paid and taxed correctly, the employee needs a Personal Public Service Number (PPSN), applied for through the Department of Social Protection (MyWelfare) once in Ireland, with proof of address and the reason for the number (employment). The employment must then be registered with Revenue through Revenue myAccount so that a Revenue Payroll Notification (RPN) is available to the employer before the first pay run.

Without an RPN in place before the first payroll, PAYE is deducted at the emergency tax rate — a common and entirely avoidable first-payslip problem, and the Irish equivalent of the ''tax card before first pay'' trap seen in other corridors. Source: Revenue and the Department of Social Protection.', 'dd06e739ceafcbdadc78dbfc396c6fa1662c8450bb60d758c05a55cc3cb05039', 200, true),
  ('ES_IE', 'https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/', 1, '# Spain to Ireland Critical Skills journey — order of steps and timeline

The correct order for a Venezuelan national relocating from Spain to Dublin on the Critical Skills route is: (1) sign a qualifying two-year employment contract; (2) the employer applies for the Critical Skills Employment Permit with DETE; (3) the permit is granted; (4) apply for the long-stay ''D'' Employment visa from Spain and wait for it to be granted before travelling; (5) travel to Ireland; (6) register immigration permission (IRP / Stamp 1) at Burgh Quay within 90 days of arrival (EUR 300 fee); (7) obtain a PPSN; (8) register the employment with Revenue so an RPN issues before the first pay run; (9) open a bank account (proof of address is a chicken-and-egg barrier, which a digital account such as Revolut or N26 can bridge); (10) register with a GP and arrange private health cover, because public eligibility depends on an ''ordinarily resident'' test.

Timeline estimates — NOT yet verified against recent real cases; confirm with the relocation agent on the ground: the Critical Skills permit decision typically takes about 12 to 16 weeks, and the Burgh Quay IRP appointment about 6 to 8 weeks. Because the permit must be lodged well ahead of the start date, treat any target start date under roughly 20 weeks away as a feasibility risk that should be flagged at case open. Personalised tax-residency, social-insurance (PRSI / totalisation), shadow-payroll, and permanent-establishment questions are determinations for a regulated professional and must not be answered in ReloPass''s own voice. Source: DETE and Immigration Service Delivery (ISD).', '52e9358154ee7c810d5a824751a4c78d5ccbda6dbe5e24fd0d760d30beeb0dc8', 200, true)
on conflict (corridor, source_url, content_hash) do nothing;

commit;
