# Otto — Card 5: evidence repair (NO→FR)

**Append this to the prompt pack.** Run it in the same chat as Card 1, or its own.
It replaces the vague "re-confirm your quotes" instruction with the exact 12 records that fail,
and why. Measured 2026-08-23 by fetching every cited page and checking each quote against it.

**Result so far:** ES→IE verifies **38/38**. NO→FR verifies **5/14, with 3 unchecked.**
None of the failures are invented facts — the wording is real. The citations are the problem.

---

```
TASK — EVIDENCE REPAIR for the NO→FR batch (no-fr-general-curated-2026-08-22). Not new
research. Twelve records cannot be evidence-checked as delivered. Fix the CITATIONS; only
change fact_text if a source turns out to contradict it, and flag needs_lawyer_review if so.

GROUP 1 — THREE FACTS CITE THE URSSAF HOMEPAGE. This is the most serious of the three.
  no_fr_urssaf_posted_worker_a1_certificate
  no_fr_france_numero_secu_ss_number_assignment
  no_fr_eu_eea_single_state_principle_reg_883_2004
All three cite https://www.urssaf.fr/accueil — a site root. A homepage can never contain a
verbatim quote about A1 certificates or Regulation 883/2004, so these are uncitable by
construction, not merely unreachable. Find the actual URSSAF (or CLEISS) page that states each
rule, and return the deep link plus a verbatim quote from it. CLEISS is now an accepted source
on our side, so cleiss.fr is available to you for the totalisation and single-state rules.

GROUP 2 — TWO FACTS CITE A PAGE BEHIND A BOT WALL.
  no_fr_france_tax_domicile_trigger_cgf_4b__eea
  no_fr_france_tax_domicile_trigger_cgf_4b__non_eea
Both cite https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006302521 (CGI art. 4 B),
which answers an automated fetch with a Cloudflare interstitial, so we cannot store its text or
confirm the quote. Either return the article's text so we can archive it, or re-cite the same
rule from impots.gouv.fr, which states the domicile tests in its own words and is fetchable.
Do NOT drop the Legifrance link — keep it as the statutory reference and add the fetchable one.

GROUP 3 — SEVEN QUOTES ARE FLATTENED LISTS. The words are on the page; the quote is not
contiguous with it, because a bulleted list was joined with "/" or the separators between items
were dropped. Re-copy each as ONE CONTIGUOUS RUN of text exactly as the page renders it. If the
fact needs several bullets, either quote the whole list including its lead-in sentence, or split
into one fact per bullet.
  no_fr_eea_sejour_card_three_conditions          (27/44 words matched)
  no_fr_eea_sejour_card_validity_employee_cdi     ( 6/32)
  no_fr_eea_sejour_card_documents_employee        (18/26)
  no_fr_eea_sejour_card_documents_self_employed   (27/39)
  no_fr_eea_sejour_card_permanent_residence_5yr   ( 6/27)
  no_fr_non_eea_worker_work_permit_required       (14/23)
  no_fr_france_eea_right_to_remain_unemployed     (31/46)
Example — no_fr_non_eea_worker_work_permit_required:
  you sent : "...un salarié étranger non européen (UE + EEE + Suisse) en France doit
              préalablement obtenir une autorisation de travail."
  page says: "...un salarié étranger non européen (UE + EEE + Suisse) : en France doit
              préalablement obtenir une autorisation de travail."
  The colon is the whole difference. Copy the run as it appears.

SELF-CHECK BEFORE YOU DELIVER — this is the rule our checker applies, so you can apply it too.
Take your evidence_quote and the page text. Fold both the same way: strip HTML, collapse all
whitespace to single spaces, replace curly quotes/apostrophes with straight ones, treat every
hyphen and dash as a space, drop list bullets, and close up a space before , . ; : ! ? ).
Your quote must then appear as an unbroken substring of the page. Nothing reorders, drops or
substitutes a WORD — so a paraphrase fails, and it should.
Set quote_verbatim_confirmed TRUE only when you have actually done this. In the last batch all
17 records said false, and that was honest — it is better than a false true. But a false quote
is the one defect that cannot be caught downstream, because the source is the only appeal.

DELIVER: data/corridor-facts/no-fr-evidence-repair-2026-08-23.ndjson, same flat record shape as
the preamble, one record per repaired fact_key, and a summary saying which group each fell in
and any fact whose text the source turned out NOT to support.
```

---

## Why this is worth Otto's time and not mine

I can fetch a page and check a quote — that part is now automated
(`scripts/verify_batch_quotes.py`, in PR #2018). What I cannot do is decide *which* URSSAF page
states the A1 rule, or whether a source contradicts a fact. That is research, and it is the only
part of this loop that needs Otto.

Two of the three groups exist because a citation was recorded at the wrong granularity — a
homepage instead of a page, a statutory reference instead of a readable one. Worth folding into
the standing preamble: **cite the page that contains the sentence, never the site that contains
the page.**
