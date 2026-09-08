Research what a citizen of an EU/EEA member state must do on arrival in Ireland to take up employment. Worked example: a Spanish national moving Madrid to Dublin. The audience is exclusively EU/EEA free movers. Ireland's non-EEA visa, employment-permit and IRP tracks are already covered and must not appear.

ALREADY COVERED — do not research these, we already hold them, anything you produce on them is a duplicate: registering the job with Revenue / myAccount, the Revenue Payroll Notification (RPN), emergency tax, PRSI compulsion, combining social insurance contributions paid abroad, the 183/280-day tax residence test, and split-year treatment.

WHAT IS MISSING is everything upstream of payroll — above all the PPSN, which every one of those covered facts silently depends on.

Write the deliverable to audos-workspace-776786/data/IE-eu-immig-2026-08-21.jsonl, one JSON object per line. Follow the shape of ve-ie-entry-family-2026-08-20.jsonl exactly. Set destination_country to "IE". The applies_to object must contain: "corridor": "ES->IE", "nationality": "EU", "status": "professional", "fact_uid": "ES_IE:EU_EEA:<entity_topic_key>", "pillar", "non_obvious", "needs_lawyer_review", "quote_verbatim_confirmed", "source_name", and "batch_id": "IE-eu-immig-2026-08-21".

RULES, all mandatory:

1. "nationality": "EU" and "status": "professional" on every single line. Never "any" — a rule that applies to everyone still applies to EU nationals, so scope it EU. A missing nationality makes the entity unusable; a missing status makes the row invisible to the employment track. Both fail silently, so omit neither.

2. evidence_quote must be a verbatim sentence copied from the page at source_url, not a paraphrase. A fact you cannot quote is a fact you must drop.

3. Set "quote_verbatim_confirmed": true only if you re-read the quote against the live page. Otherwise false. Do not omit the key — false is honest and costs only a review flag, whereas a wrong true badges an unchecked claim as verified.

4. source_url must be on one of: gov.ie, irishimmigration.ie, hse.ie, rtb.ie, ndls.ie, rsa.ie, welfare.ie, mywelfare.ie (preferred — these are the publishing authority), or citizensinformation.ie, revenue.ie (acceptable only where nothing else publishes the rule plainly). Any other domain is rejected on import. Mixing a weaker source into a topic downgrades that whole requirement, so keep each topic on its best available source.

5. fact_type is one of: eligibility, step, document, deadline, fee, where_to_apply, other. confidence is one of: high, medium, low.

6. One entity_topic_key per requirement. entity_title is what the relocating employee reads — a real imperative phrase such as "Get a Personal Public Service Number (PPSN)", never a humanised topic key like "Ireland — ppsn registration".

7. Keep the fact_text house style: "Commonly believed: ... / Actually: ... / Action required: ..."

DO NOT INVENT A REQUIREMENT THAT DOES NOT EXIST. Ireland has no address registration, no padron, no residence-permit card and no immigration registration for EEA nationals. Do not produce facts for those merely because France, Germany or Spain have them. Where the honest answer is "no such obligation exists for an EU national", put that in your chat reply, not in the file.

TOPICS to confirm or drop, each with evidence — and add any I have missed: ppsn_registration (highest priority, the precondition for everything else); eu_right_of_residence (the right to reside beyond three months as a worker, and the fact that no registration or card is required); travel_id_document (national ID card or passport — Ireland is outside Schengen and the Common Travel Area does not cover Spain); public_health_entitlement (ordinary-residence basis, EHIC in the interim, GP visit card, medical card); rtb_tenancy_registration (what a tenant should expect and verify); driving_licence_exchange (validity of a Spanish licence in Ireland, and whether exchange is required or optional).

When the file is written, reply with the total line count and each entity_topic_key with its fact count and source host.
