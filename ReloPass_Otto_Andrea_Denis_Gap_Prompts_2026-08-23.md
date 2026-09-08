# Otto prompts — the gaps that actually block Andrea & Denis

**Date:** 2026-08-23 · **Author:** Claude Code (Lane 1 session, PR #2016)
**Supersedes §9 of the Parallel Launch Pack** for these corridors. Every number below was
measured against the repo and production this session, not inferred.

## Read this before you paste anything

Two things will silently destroy the run if you don't fix them first. **Neither is Otto's job.**

**1. CLEISS and CAF are classified `unofficial` and rejected outright.**
`backend/imports/otto/parsers.py::classify_source` returns `unofficial` for `cleiss.fr`,
`caf.fr`, `dublincity.ie` and `leapcard.ie`. CLEISS is the French liaison body for
international social security — it is *the* source for Denis's Norway→France totalization, and
card B-1 of the launch pack names it. Every CLEISS fact Otto researches tonight would be thrown
away at import. This is the fourth time this allowlist has been too narrow. Add these hosts to
the OFFICIAL list before the batches come back.

**2. The ES→IE batch cannot be read by the importer at all.**
`read_jsonl()` dies on line 1: `missing required field(s): entity_topic_key`. The ES→IE file
uses a nested `entity{}` object; the parser requires **flat** `entity_topic_key` +
`entity_title`. The NO→FR file uses the flat shape and parses cleanly (17/17). The prompts
below pin the flat shape, but the existing ES→IE artifact needs converting, not re-issuing.

## The gaps, measured

| # | Gap | Measured |
|---|---|---|
| 1 | **Denis is served 0 of 17 NO→FR facts** | He is a French national returning to France → `OWN_NATIONAL`. All 17 rows are tagged `nationality: "EEA"` (15) or `"non-EEA"` (2), and **none** carries `nationality_scope_basis`. No row matches. |
| 2 | Norway-exit side missing entirely | 0 rows |
| 3 | Spain-exit side missing entirely | 0 rows |
| 4 | 8 of 10 ES→IE sources have no page text | `source_doc_id` is NOT NULL; promotion is blocked without it |
| 5 | All 17 NO→FR rows downgraded to `needs_review` | `quote_verbatim_confirmed: false` on every row |
| 6 | No `assertion_mode` anywhere in NO→FR | conditional facts render as flat rules |

Gap 1 is the one that matters most: it is the same mis-serve class Lane 1 exists to prevent,
and it hits your second reference case head-on.

---

# PREAMBLE — paste once at the top of every Otto chat

```
ROLE — You are Otto, researching relocation corridors for ReloPass. You do DISCOVERY-ONLY
research from OFFICIAL sources and hand verified CANDIDATE facts to Claude Code, which stages
them. You never touch the rolec repo or the ReloPass database. You NEVER self-certify a fact as
"verified" — you produce representative, pending, evidence-linked candidates. The company is
ReloPass (do not let the auto-namer drift).

OUTPUT SHAPE — this is a hard contract, verified against backend/imports/otto/parsers.py.
One JSON object per line (NDJSON). FLAT keys. A nested "entity" object FAILS AT LINE 1.

REQUIRED on every line (import refuses the file without these five):
  destination_country   ISO-2, e.g. "FR", "IE", "NO", "ES"
  entity_topic_key      bare snake_case, e.g. "carte_sejour_eea"  (NOT "NO-FR:eea:carte_sejour")
  fact_key              bare snake_case, unique within the batch
  fact_text             the requirement, in plain language
  source_url            the exact page the quote came from

ALSO EMIT on every line:
  entity_title          human title for the topic
  fact_type             one of: eligibility | document | step | deadline | fee |
                        where_to_apply | account | other
  evidence_quote        VERBATIM text copied from source_url. Not paraphrased.
  confidence            "high" | "medium" | "low"
  applies_to            object, see below

applies_to — EVERY key below matters, and two of them decide WHO IS SHOWN THE FACT:

  nationality_scope_basis   ** MANDATORY. Omitting it hides the fact from people it applies to. **
      "audience_scope"          the rule applies to EVERYONE on this corridor regardless of
                                nationality (PPSN, emergency tax, registering an address,
                                opening a bank account). Use this whenever the law does not
                                turn on nationality — even if you researched it for one persona.
      "nationality_determined"  the rule genuinely turns on nationality (work permits, entry
                                visas, third-country registration).
      If you are unsure, choose "audience_scope". Hiding a rule from someone it applies to is
      the more expensive error: it costs them money they cannot get back.

  nationality               ONLY meaningful when nationality_determined. One of:
                            "EEA" | "non-EEA" | "own-national"
                            "own-national" = a citizen of the destination country returning
                            home. THIS IS A DISTINCT CASE — an EEA-tagged rule does not reach
                            a returning national.

  assertion_mode            "assertion" (the source states it flatly) or "conditional" (the
                            source states a consequence but does NOT determine the trigger).
  conditional_on            REQUIRED when assertion_mode is "conditional". One sentence naming
                            what the fact depends on and where that is determined.

  non_obvious               true when this is an easy-to-miss trap: high cost of not knowing,
                            and nothing in the normal process prompts you.
  non_obvious_note          REQUIRED when non_obvious is true. Say what people wrongly believe,
                            what is actually true, and the action to take. Two or three
                            sentences.

  timing                    when in the move this applies, if the source says.
  needs_lawyer_review       true on any legal-status or eligibility conclusion.
  quote_verbatim_confirmed  true ONLY if you re-opened source_url and confirmed evidence_quote
                            appears on the page character-for-character. Every fact in the last
                            NO→FR batch had this false, and all 17 were downgraded to
                            needs_review on import. If you cannot confirm it, say false —
                            do not guess true.
  review_status             always "pending"
  verification_status       always "representative"

SOURCE RULE — a fact whose source is not on this list is thrown away at import. Prefer:
  France   service-public.fr, impots.gouv.fr, urssaf.fr, ameli.fr, legifrance.gouv.fr,
           france-visas.gouv.fr, ofii.fr, interieur.gouv.fr (any *.gouv.fr)
  Norway   skatteetaten.no, nav.no, udi.no, politiet.no, altinn.no, helsenorge.no,
           folkeregisteret.no, lovdata.no, workinnorway.no
  Ireland  irishimmigration.ie, revenue.ie, citizensinformation.ie, hse.ie, welfare.ie,
           mywelfare.ie, ndls.ie, rtb.ie, rsa.ie (any *.gov.ie)
  Spain    *.gob.es, agenciatributaria.es, seg-social.es, sepe.es, boe.es, policia.es,
           madrid.es
  EU       europa.eu, ec.europa.eu, eur-lex.europa.eu, youreurope.europa.eu

  If the ONLY official source for a fact is a body NOT on this list (cleiss.fr and caf.fr are
  the known cases), still emit the fact, and add "source_allowlist_gap": true to applies_to so
  it can be reviewed rather than silently dropped.

NEVER: invent a source, a number, a fee, a deadline or a confidence score. A field the source
does not give you is omitted, not filled. If a page contradicts a fact you already emitted,
say so rather than quietly reconciling it.

DELIVER: write data/corridor-facts/<name>.ndjson, log a coverage summary to otto.md, and stop.
Do not request promotion — that is a human gate after the serving layer lands.
```

---

# CARD 1 — Denis is invisible. Re-tag the 17 NO→FR facts. (do this first)

```
TASK — RE-TAG, not new research. The 17 facts in the NO→FR batch
(no-fr-general-curated-2026-08-22) are currently served to NOBODY, because every one is tagged
nationality "EEA" or "non-EEA" with no nationality_scope_basis, and our reference mover Denis
is a FRENCH national returning to France — an own-national, which matches neither label.

Re-emit all 17 with, for each:
  - nationality_scope_basis: decide honestly per fact. Most of these are corridor-wide:
    getting a French social security number, the tax-domicile tests, the A1/posted-worker
    rules, the single-state principle of Reg. 883/2004 — none of those turn on nationality.
    Tag those "audience_scope". Reserve "nationality_determined" for the rules that genuinely
    do (the non-EEA work permit fact, the carte de séjour rules that exist only for EEA
    nationals).
  - where nationality_determined and the rule is about EEA nationals, state explicitly in
    fact_text whether it also applies to a returning FRENCH national, and tag
    nationality "own-national" on a separate row if the answer differs.
  - assertion_mode + conditional_on where the source states a consequence without determining
    the trigger.
  - quote_verbatim_confirmed: re-open each source_url and confirm the quote character-for-
    character. All 17 are currently false, which downgrades every one of them.

Sources: service-public.fr, urssaf.fr, ameli.fr, impots.gouv.fr, legifrance.gouv.fr.
Output data/corridor-facts/no-fr-dest-retag-2026-08-23.ndjson.
Report: how many you moved to audience_scope, and any fact where the own-national answer
differs from the EEA answer — that difference is the whole point of this card.
```

# CARD 2 — Norway exit (Denis leaving). Nothing exists.

```
TASK — NEW. Corridor NO→FR, ORIGIN side. Nothing has been researched for the Norway exit.
PERSONA: Denis, French national, leaving Oslo/Stavanger for Paris, family, energy sector.
destination_country stays "FR" (this is the FR corridor); entity_topic_key should name the
Norway-exit topic, e.g. "norway_exit_folkeregister".

OFFICIAL SOURCES ONLY: skatteetaten.no, nav.no, udi.no, politiet.no, altinn.no.
COVER: the folkeregister "flytte til utlandet" move-abroad notice and its deadline; skattekort
and exit taxation / kildeskatt; what happens to the D-number or fødselsnummer after leaving;
NAV membership exit and S1/A1 portability into France; keeping or closing a Norwegian bank
account and BankID, and what breaks if you close it too early.

Almost all of this is audience_scope — leaving Norway works the same regardless of passport.
Flag non_obvious heavily on the ordering traps: things that must be done BEFORE departure and
cannot be done after. Those are the facts that make this corridor worth having.
```

# CARD 3 — Spain exit (Andrea leaving). Nothing exists.

```
TASK — NEW. Corridor ES→IE, ORIGIN side. The destination side is done (38 facts); the Spain
exit is empty. destination_country stays "IE"; entity_topic_key names the Spain-exit topic.
PERSONA: Andrea, VENEZUELAN national (third country) legally resident in Spain, family of 4,
leaving Madrid for Dublin.

OFFICIAL SOURCES ONLY: *.gob.es (sede.administracionespublicas.gob.es for extranjería,
inclusion.gob.es, exteriores.gob.es), agenciatributaria.es, seg-social.es, madrid.es.
COVER: padrón de-registration; ending Spanish tax residency (modelo 030, non-resident status);
what happens to her TIE on departure and whether leaving forfeits her Spanish residence;
TGSS social-security de-registration and what totalization is and is not available to a
THIRD-COUNTRY national moving Spain→Ireland; Spanish healthcare on exit; driving licence;
obtaining school records for the children.

Her nationality matters here — the TIE and totalization answers differ for a third-country
national. Tag those nationality_determined + nationality "non-EEA", and set
needs_lawyer_review true. The padrón, tax and school-records facts are audience_scope.
```

# CARD 4 — Page text for the 8 uncited ES→IE sources (unblocks promotion)

```
TASK — SOURCE CAPTURE, not new facts. The ES→IE batch is blocked from promotion: its facts
require a stored source document, and 8 of its 10 source URLs have none. Do NOT write a
placeholder — 705 existing facts already cite a document whose entire text is
"Otto bridge capture, unverified", and they can never be evidence-checked.

For each URL below, fetch and return the page's READABLE MAIN TEXT (not navigation, not the
cookie banner), as: {"source_url": ..., "fetched_at": ..., "text_content": "..."}
  https://services.mywelfare.ie/en/topics/identity-services/personal-public-service-pps-number/
  https://www.irishimmigration.ie/registering-your-immigration-permission/frequently-asked-questions-for-registration/
  https://www.irishimmigration.ie/registering-your-immigration-permission/how-to-register-your-immigration-permission-for-the-first-time/required-documents/
  https://www.revenue.ie/en/jobs-and-pensions/emergency-tax/emergency-tax-rules.aspx
  https://www.revenue.ie/en/jobs-and-pensions/emergency-tax/index.aspx
  https://www.revenue.ie/en/jobs-and-pensions/starting-your-first-job/index.aspx
  https://www.revenue.ie/en/jobs-and-pensions/tax-residence/index.aspx
  https://www2.healthservice.hse.ie/files/690/

Also RE-FETCH this one — the stored copy captured a cookie banner instead of the page:
  https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/

If a page will not render its text (JavaScript shell), say so explicitly and name the static
equivalent if one exists. Do not return the shell. If HSE returns an empty "Website update"
placeholder, that is a TRANSIENT OUTAGE — retry before reporting it dead.

Output data/corridor-facts/es-ie-source-texts-2026-08-23.jsonl.
```
