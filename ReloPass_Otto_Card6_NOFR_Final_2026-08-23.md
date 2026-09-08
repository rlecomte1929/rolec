# Otto — Card 6: NO→FR final pass (scope tagging + the last 7 quotes)

**Paste the whole block below into one Otto chat.** It replaces Cards 1 and 5.

Card 5 landed well: the three URSSAF-homepage citations are fixed and verified, the Legifrance
bot wall is gone, and the self-assessment was accurate on 11 of 12 records. What is left is one
pass over the same 17 records and the same pages, so it should be done in one chat, not two.

**Status after the repair was MERGED and re-verified (2026-08-23):**
**10 of 17 quotes verify · 7 do not · 0 of 17 records carry `nationality_scope_basis`**

The three uncitable URSSAF-homepage records are fixed and confirmed. The one regression is fixed
in-repo — do NOT ask for it again. Job B below is now **7 records, not 8**.

That last number is the one that matters. It is why Denis is served nothing.

---

```
TASK — NO→FR final pass. Two jobs over the same 17 records (batch
no-fr-general-curated-2026-08-22). Do JOB A for all 17. Do JOB B for the 8 named at the end.

=== JOB A — TAG nationality_scope_basis ON ALL 17. This is the priority. ===

Right now every record is tagged nationality "EEA" (15) or "non-EEA" (2), and NONE carries
nationality_scope_basis. Our serving layer gates on that field, and the result is that our
reference mover is served ZERO of the 17.

WHY: Denis is a FRENCH national moving Oslo -> Paris. Returning to his own country makes him an
OWN-NATIONAL, which is neither "EEA" nor "non-EEA". No record matches him, so he sees nothing.

For each of the 17, decide from the SOURCE — not from who the batch was researched for:

  nationality_scope_basis: "audience_scope"
      The rule does not turn on nationality. It applies to everyone on this corridor.
      Expect MOST of these 17 to be this. A French social security number, the CGI art. 4B
      tax-domicile tests, the A1 / posted-worker mechanics, and the single-state principle of
      Reg. 883/2004 are not nationality-gated — they apply to anyone in that situation.

  nationality_scope_basis: "nationality_determined"
      The rule genuinely turns on nationality. On this batch that is the carte de séjour
      "citoyen UE/EEE/Suisse" family (a right that exists BECAUSE the holder is EEA) and the
      non-EEA work-permit rule.

THEN, for every record you tag nationality_determined, answer this explicitly:
      Does this rule apply to a returning FRENCH national in France?
Usually the answer is no, and for a reason worth stating: a French citizen in France needs no
residence document at all, so a rule about an EEA residence card does not reach him — he is not
exempt from a burden, the burden never existed. Where that is the case, say so in
`own_national_note`. If a rule DOES have a distinct own-national form, emit it as its own record
with nationality: "own-national".

Do NOT tag a rule audience_scope just to make it reach Denis. A wrong audience_scope tells him
to do something he need not do; a wrong nationality_determined hides something he must. Both are
failures. Decide from the source and say which sentence decided it, in `scope_justification`.

=== JOB B — FINISH THE LAST 7 QUOTES ===

RULE THAT COST US ONE RECORD LAST ROUND — read it, it applies to everything below:
if the page you already cite CONTAINS the sentence, KEEP THAT URL. Only change a citation when
the page genuinely does not carry the claim. Last round
no_fr_non_eea_worker_work_permit_required was moved off a page that had the sentence onto one
that does not mention "autorisation de travail" at all, and was marked confirmed. That record is
already corrected on our side — do not touch it, and do not re-cite it.

Copy an exact contiguous run for these 7, from the URL each already cites:
  BOFiP  (bofip.impots.gouv.fr/bofip/1911-PGP.html/identifiant=BOI-IR-CHAMP-10-20160728)
    no_fr_france_tax_domicile_trigger_cgf_4b__eea
    no_fr_france_tax_domicile_trigger_cgf_4b__non_eea
      The page is fetchable now, so a verbatim run is available. If the two records assert the
      SAME statutory test (art. 4B does not vary by nationality), say so — they may be one fact.
  service-public.gouv.fr F16003
    no_fr_eea_sejour_card_three_conditions
    no_fr_eea_sejour_card_validity_employee_cdi
    no_fr_eea_sejour_card_documents_employee
    no_fr_eea_sejour_card_documents_self_employed
  service-public.gouv.fr F35600/0
    no_fr_france_eea_right_to_remain_unemployed
      You already flagged needs_lawyer_review here because the fiche states "chômage
      involontaire" as a qualifying situation without the duration or France Travail
      registration the fact asserts. Good catch — keep the flag, and quote only what the page
      states. If the extra conditions are on another official page, cite that page for them as
      a separate record rather than stretching this quote.

THE EXACT SELF-CHECK — this is our checker's rule, verbatim, so you can pre-run it:
  Fold BOTH your quote and the page text the same way, then your quote must appear as one
  unbroken substring:
    strip HTML and decode entities; collapse all whitespace to single spaces;
    curly quotes/apostrophes -> straight; every hyphen and dash -> a space;
    drop list bullets; remove the literal token "titlecontent" (service-public renders it);
    "/" -> a space; close up a space BEFORE , . ; : ! ? );
    close up a space AFTER an apostrophe  ("L' article" and "l'article" are the same words).
  Nothing reorders, drops or substitutes a WORD, so a paraphrase still fails.
  Set quote_verbatim_confirmed TRUE only after actually running this. Last round two records
  claimed true and were not; false is always better than a false true.

=== DELIVER ===
One file, data/corridor-facts/no-fr-final-2026-08-23.ndjson, one record per fact_key, all 17.
(Job A covers all 17; Job B changes the quote on 7 of them.)
Each record: fact_key, citation_url, evidence_quote, quote_verbatim_confirmed,
nationality_scope_basis, nationality, scope_justification, own_national_note (where relevant),
assertion_mode + conditional_on (where the source states a consequence without determining its
trigger), non_obvious + non_obvious_note, needs_lawyer_review.
Report: the audience_scope / nationality_determined split, how many quotes you self-verified,
and any record where the source does NOT support the fact_text we already hold.
```

---

## Still open after this, unchanged

`Card 2` (Norway exit) and `Card 3` (Spain exit) in the earlier pack — both corridors still have
no origin side at all. `Card 4` is done; I fetched those pages and all 38 ES→IE quotes verified.
