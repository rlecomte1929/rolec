# AIQ-2018a — 20 replacement citations, proposed for confirmation

**Nothing here has been written to the database.** The card's binding constraint is that a
`source_url` is never machine-written, because a model picking a plausible URL for
*"Utlendingsloven §109"* is exactly how the current 20 were produced. This is a proposal list.
Confirm or reject each line; the write is a separate step.

Date: 2026-08-23 · every candidate probed · 19/20 returned HTTP 200 directly, the 20th verified
by content (see the Legifrance note).

---

## How the current 20 were produced

Not by a model. `corridor_persistence.derive_source_url` (line 86) ends with:

```python
return f"https://www.gesetze-im-internet.de/Teilliste_{quote_plus(ref)}.html"
```

Every unrecognised legal reference is pasted into the German federal law portal's URL template.
That is why Norwegian, Spanish, Dutch and Swiss statutes all "cite" a German site — and why even
the genuinely German entries 404, since `Teilliste_` is not how that site addresses a section.

The gate shipped in PR #2039 stops new ones. This repairs the existing rows.

## Sourcing principle

Each replacement points at **the publishing authority for that jurisdiction**, not at an
aggregator or a summary:

| jurisdiction | authority |
|---|---|
| Netherlands | `wetten.overheid.nl` |
| Switzerland | `fedlex.admin.ch` (official ELI permalinks) |
| Germany | `gesetze-im-internet.de` — correct section-level form, `/<act>/__<§>.html` |
| Spain | `boe.es` — consolidated text |
| Norway (statute) | `lovdata.no` |
| Norway (tax/registry practice) | `skatteetaten.no` |
| France | `legifrance.gouv.fr` |
| EEA Agreement | EUR-Lex |

---

## The 20

### Netherlands — corridor `ES_NL_2026`

| rule_id | reference | proposed URL | probe |
|---|---|---|---|
| `NL_WET_BRP` | Wet BRP | `https://wetten.overheid.nl/BWBR0033715` | 200 |
| `NL_ZVW` | Zorgverzekeringswet | `https://wetten.overheid.nl/BWBR0018450` | 200 |

### Switzerland — corridor `FR_CH_2026`

| rule_id | reference | proposed URL | probe |
|---|---|---|---|
| `CH_AIG` | AIG/LEI | `https://www.fedlex.admin.ch/eli/cc/2007/758/de` | 200 |
| `CH_AFMP` | EU–CH Free Movement Agreement | `https://www.fedlex.admin.ch/eli/cc/2002/243/de` | 200 |
| `CH_KVG` | KVG/LAMal | `https://www.fedlex.admin.ch/eli/cc/1995/1328_1328_1328/de` | 200 |
| `CH_VEP` | VEP/OLCP | `https://www.fedlex.admin.ch/eli/cc/2002/295/de` | 200 |

### Germany — corridor `FR_DE_EU_2026`

These four were *already* on the right domain and still 404'd, because `Teilliste_` is not the
section addressing scheme. The fix is the form, not the host.

| rule_id | reference | proposed URL | probe |
|---|---|---|---|
| `DE_BMG_17` | BMG §17 | `https://www.gesetze-im-internet.de/bmg/__17.html` | 200 |
| `DE_FREIZUEGG_2` | FreizügG/EU §2 | `https://www.gesetze-im-internet.de/freiz_gg_eu_2004/__2.html` | 200 |
| `DE_FREIZUEGG_5` | FreizügG/EU §5 | `https://www.gesetze-im-internet.de/freiz_gg_eu_2004/__5.html` | 200 |
| `DE_SGBV_193` | SGB V §193 | `https://www.gesetze-im-internet.de/sgb_5/__193.html` | 200 |

### Spain — corridor `FR_ES_2026`

| rule_id | reference | proposed URL | probe |
|---|---|---|---|
| `ES_PADRON` | Ley 7/1985 (empadronamiento) | `https://www.boe.es/buscar/act.php?id=BOE-A-1985-5392` | 200 |
| `ES_RD_240_2007` | Real Decreto 240/2007 | `https://www.boe.es/buscar/act.php?id=BOE-A-2007-4184` | 200 |

### Norway / EEA — corridor `FR_NO_EEA_2026`

| rule_id | reference | proposed URL | probe |
|---|---|---|---|
| `EEA_ART_28` | EEA Agreement Art. 28 | `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A21994A0103%2801%29` | 200 |
| `NO_FOLKEREG_4_1` | Folkeregisterloven §4-1 | `https://lovdata.no/lov/2016-12-09-88/%C2%A74-1` | 200 |
| `NO_UTL_109` | Utlendingsloven §109 | `https://lovdata.no/lov/2008-05-15-35/%C2%A7109` | 200 |
| `NO_UTL_110` | Utlendingsloven §110 | `https://lovdata.no/lov/2008-05-15-35/%C2%A7110` | 200 |
| `NO_UTL_117` | Utlendingsloven §117 | `https://lovdata.no/lov/2008-05-15-35/%C2%A7117` | 200 |

### Returning mover — corridor `NO_FR_RETURNING_EEA_2026`

| rule_id | reference | proposed URL | probe |
|---|---|---|---|
| `FR_CGI_4B` | CGI art. 4 B | `https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006302201` | **403** — see below |
| `NO_FOLKEREG_MOVE` | Folkeregisterloven — reporting a move abroad | `https://www.skatteetaten.no/en/person/national-registry/moving/moving-from-norway/` | 200 |
| `NO_TAX_EMIGRATION` | Skatteetaten — emigration / tax residence | `https://www.skatteetaten.no/en/person/taxes/get-the-taxes-right/abroad/` | 200 |

---

## Three notes you should read before confirming

**1. The Legifrance 403 is a bot block, not an absence.** `curl` gets 403 from
`legifrance.gouv.fr` on every URL form tried. Fetching the page's *content* confirms it is the
right article — it opens *"Sont considérées comme ayant leur domicile fiscal en France au sens de
l'article 4 A :"*, which is CGI art. 4 B. This is precisely why the PR #2039 checker treats only
404/410 as DEAD and never 403: a bot block would otherwise reject the official source. **Open it
in a browser once before confirming.**

**2. `NO_TAX_EMIGRATION` — I rejected my own first candidate.** The obvious-looking page,
`.../registered-as-emigrated-in-the-national-registry-because-you-no-longer-have-lawful-residence-in-norway/`,
returns 200 and *sounds* right. It is about losing lawful residence, not about the tax-residence
emigration test the rule describes ("tax residence ends only on a strict emigration test, NOT on
the physical move"). Substituting it would have been the exact failure this card exists to
prevent: replacing a 404 with a plausible-but-wrong link, which is worse because it looks
checked. The proposed `/taxes/get-the-taxes-right/abroad/` is the tax-side page.

Supporting evidence for the pairing: the `moving-from-norway` page states *"Reporting a move
abroad does not mean that your liability to pay tax in Norway ends"* — which is the rule's claim,
stated by the registry page itself and pointing at the tax page for the detail.

**3. The four German ones were never a host problem.** `BMG §17`, `FreizügG/EU §2` and `§5`, and
`SGB V §193` are genuinely German law on the correct domain. They 404'd only because
`Teilliste_<ref>.html` is not how `gesetze-im-internet.de` addresses a section. If anything makes
the case that this was a mechanical URL-construction bug rather than a research failure, it is
these four.

---

## If you confirm

The write is 20 targeted `UPDATE`s keyed on `rule_version_id`, correcting `source_url` in place.
Row count stays 34 — **corrected, not deleted**, per the card, so the audit trail of what was
originally cited survives in git and in this document.

Verification afterwards:

```sql
SELECT count(*) FROM rce.rule_versions WHERE source_url LIKE '%/Teilliste_%';  -- expect 0
```

Confirm all 20, or name the ones to hold back and I will write only the rest.
