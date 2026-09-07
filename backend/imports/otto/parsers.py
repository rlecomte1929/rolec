"""Read an Otto immigration-research JSONL file into `FactRow` objects.

Why this module exists: on 2026-08-11 the France immigration batch loaded **24 of 109 facts**
and `otto_staging.load_log` recorded the reason as *"85 facts unreachable via browser (systemic
capture ceiling on large threads)"*. Extraction was being done by scrolling Otto's chat thread,
and that method is capped. The vendor workstream had already hit the same wall and solved it:
Otto writes a *file* into the git-synced workspace, the `[audos-sync]` bot commits it, and a
repo-side reader loads it (`backend/imports/suppliers/`). This is that reader, for facts.

**Format is JSONL — one JSON object per line**, not CSV. `applies_to` is `jsonb` and
`evidence_quote` is a verbatim multi-line source quote full of commas and quote marks; pushing
those through CSV means inventing escaping rules an agent will get wrong. JSONL is also
self-delimiting, so a truncated file loses only its last record instead of corrupting from the
truncation point onward — which matters when the producer is an agent that may hit a ceiling
mid-write.

Two decisions live here rather than in the executor, because both are properties of *this file
format* and of what an immigration fact is:

**The publisher's domain decides how far a fact may be trusted — `source_name` gets no vote.**
Same reasoning as the supplier parser (`../suppliers/parsers.py:10-15`): the domain cannot lie
about who published the page. Three classes, and the middle one is the point:

    OFFICIAL       a government or statutory body      may be auto_accepted
    SEMI_OFFICIAL  a public agency without a gov TLD   forced to needs_review
    UNOFFICIAL     blog, law firm, relocation vendor   rejected outright

A blunt official-or-rejected rule was the first design and it is wrong here. The 24 rows already
in the table include 3 from `campusfrance.org` — Campus France is a French public establishment,
so the fact is worth keeping, but it is not `service-public.gouv.fr` and must not be
auto-accepted. Those 3 rows are already `needs_review`/`medium` in production, so this tiering
is not a new policy; it is the existing one, made explicit and enforced.

**A fact with no `evidence_quote` cannot be auto_accepted.** All 24 rows currently in the table
have `evidence_quote IS NULL`, which means nothing in them can be re-checked without re-reading
the source. In a compliance product one wrong fact destroys trust, so an unquotable fact is
allowed in — downgraded to `needs_review` — but never waved through.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple
from urllib.parse import urlsplit

#: Keys every record must carry. Mirrors the NOT NULL columns of
#: `otto_staging.immigration_fact_candidates`, minus the ones this module derives
#: (`confidence_score`, `accuracy_tier`, `dedupe_key`, `extraction_method`).
REQUIRED_FIELDS: Tuple[str, ...] = (
    "destination_country",
    "entity_topic_key",
    "fact_key",
    "fact_text",
    "source_url",
)

#: Accepted and understood, but not required.
OPTIONAL_FIELDS: Tuple[str, ...] = (
    "entity_title", "fact_type", "applies_to", "evidence_quote", "confidence",
)

#: `fact_type` values already in production. An unknown type is not fatal — research finds
#: shapes we did not predict — but it is normalised to `other` so the column stays queryable.
KNOWN_FACT_TYPES: Tuple[str, ...] = (
    "fee", "eligibility", "document", "deadline", "step", "where_to_apply", "other",
)

#: `confidence` -> `confidence_score`, matching the values in production (high -> 0.9).
CONFIDENCE_SCORES: Dict[str, float] = {"high": 0.9, "medium": 0.6, "low": 0.3}

TIER_AUTO = "auto_accepted"
TIER_REVIEW = "needs_review"

OFFICIAL = "official"
SEMI_OFFICIAL = "semi_official"
UNOFFICIAL = "unofficial"

#: Host patterns that make a domain governmental on their own, without an allowlist entry.
#: Suffix-matched against the hostname, so `www.service-public.gouv.fr` matches `.gouv.fr`.
_OFFICIAL_SUFFIXES: Tuple[str, ...] = (
    "gouv.fr", "gov.uk", "gov.pt", "gov.pl", "gov.ie", "gov.it", "gov.gr",
    "gob.es", "governo.it", "admin.ch", "overheid.nl", "public.lu",
    "europa.eu", "bund.de", "gc.ca", "govt.nz", "gov.au", "gov",
    # Singapore (FR->SG / Adrien): the statutory bodies all publish under `.gov.sg` —
    # mom.gov.sg (Ministry of Manpower / work passes), ica.gov.sg (Immigration & Checkpoints),
    # iras.gov.sg (tax), cpf.gov.sg (Central Provident Fund). The bare `gov` above does NOT
    # catch these — `mom.gov.sg` ends in `.sg`, not `.gov` — so the whole 30-fact FR->SG batch
    # scored UNOFFICIAL until this was added (the 4th too-narrow-allowlist instance).
    "gov.sg",
    # Ecuador (US->EC / Abraham): every statutory body publishes under `.gob.ec` —
    # cancilleria.gob.ec (visas), trabajo.gob.ec (labour), sri.gob.ec (tax), iess.gob.ec
    # (social security), registrocivil.gob.ec (cédula). `gob.es` above is Spain only; the
    # bare `gov` does not match `.ec`. 5th too-narrow-allowlist instance.
    "gob.ec",
    # Canada (destination rank 5, Toronto). Federal content lives on `canada.ca` (IRCC, CRA,
    # Service Canada all publish there now), which the legacy `gc.ca` suffix above does NOT
    # match — every canada.ca fact scored UNOFFICIAL until this was added. `ontario.ca` is the
    # Government of Ontario's own domain (OHIP, ServiceOntario, driving, the private-school
    # list on data.ontario.ca), a statutory provincial government publishing its own rules —
    # same call as `madrid.es` / `service.berlin.de`. 6th too-narrow-allowlist instance.
    "canada.ca", "ontario.ca",
    # United Arab Emirates (destination rank 8, Dubai). Federal bodies publish under `.gov.ae`
    # (tax.gov.ae = Federal Tax Authority, icp.gov.ae = ICP/residency, gdrfad.gov.ae = GDRFA Dubai,
    # mohre.gov.ae = labour) and the official one-stop portal is `u.ae` — neither matched the bare
    # `gov` suffix (`.gov.ae` ≠ `.gov`). 7th too-narrow-allowlist instance.
    "gov.ae", "u.ae",
    # Belgium (rank 15, Brussels) — federal bodies publish under `.fgov.be` (inami.fgov.be, rsz.fgov.be).
    # Austria (rank 16, Vienna) — the whole public sector sits under `.gv.at` (oesterreich.gv.at,
    # migration.gv.at, wien.gv.at, help.gv.at). Neither matched the bare `gov`.
    "fgov.be", "gv.at",
    # Japan (destination rank 18, Tokyo) — the entire central government publishes under `.go.jp`
    # (isa.go.jp = Immigration Services Agency, moj.go.jp, mofa.go.jp, mhlw.go.jp, nta.go.jp,
    # digital.go.jp), and cities/prefectures under `.lg.jp` (residence registration, My Number).
    # `.go.jp` ≠ `.gov`, so the bare `gov` matched none of them.
    "go.jp", "lg.jp",
    # Saudi Arabia (destination rank 12, Riyadh) — federal bodies publish under `.gov.sa`
    # (mol.gov.sa / hrsd.gov.sa labour, moi.gov.sa Interior/Absher, mofa.gov.sa visas,
    # zatca.gov.sa tax, sama.gov.sa central bank, premiumresidency.gov.sa). `.gov.sa` ≠ `.gov`.
    "gov.sa",
    # Hong Kong (destination rank 21) — the whole government publishes under `.gov.hk`
    # (immd.gov.hk Immigration, ird.gov.hk Inland Revenue, td.gov.hk Transport, gov.hk portal,
    # mpfa.org.hk is the MPF authority — added as a host below). `.gov.hk` ≠ `.gov`.
    "gov.hk",
    # Qatar (destination rank 23, Doha) — government bodies publish under `.gov.qa`
    # (moi.gov.qa Interior, hukoomi.gov.qa the e-gov portal, mol.gov.qa labour). `.gov.qa` ≠ `.gov`.
    "gov.qa",
    # (New Zealand rank 22 uses `govt.nz`, already listed above; Poland rank 25 uses `gov.pl`,
    # already listed above — udsc.gov.pl, podatki.gov.pl, nfz.gov.pl all match it.)
    # South Korea (destination rank 27, Seoul) — government publishes under `.go.kr`
    # (hikorea.go.kr immigration, immigration.go.kr, nts.go.kr tax, moel.go.kr labour). `.go.kr` ≠ `.gov`.
    "go.kr",
    # Israel (destination rank 28, Tel Aviv) — government bodies publish under `.gov.il`
    # (piba.gov.il Population & Immigration Authority, taxes.gov.il, gov.il). `.gov.il` ≠ `.gov`.
    "gov.il",
    # Kuwait (destination rank 29, Kuwait City) — government publishes under `.gov.kw`
    # (moi.gov.kw Interior, paci.gov.kw Civil Information / Civil ID, e.gov.kw portal). `.gov.kw` ≠ `.gov`.
    "gov.kw",
    # (Luxembourg rank 30 uses `public.lu`, already listed above — guichet.public.lu matches it;
    # the bare guichet.lu host is added below.)
    # Czech Republic (destination rank 31, Prague) — the new unified portal is `gov.cz`; the
    # statutory bodies also publish on their own `.cz` (mvcr.cz, mzv.cz — added as hosts below).
    "gov.cz",
    # Greece (destination rank 32, Athens) — the unified portal + ministries publish under `.gov.gr`
    # (migration.gov.gr, efka.gov.gr). `.gov.gr` ≠ `.gov`.
    "gov.gr",
    # Mexico (destination rank 33, Mexico City) — the whole federal government publishes under `.gob.mx`
    # (inm.gob.mx immigration, sat.gob.mx tax, imss.gob.mx social security, sre.gob.mx foreign affairs).
    "gob.mx",
    # Brazil (destination rank 34, São Paulo) — the whole federal government publishes under `.gov.br`
    # (gov.br/mj + gov.br/pf residence, gov.br/receitafederal tax, gov.br/inss social security).
    "gov.br",
    # Bahrain (destination rank 35, Manama) — government bodies publish under `.gov.bh`
    # (lmra.gov.bh Labour Market Regulatory Authority, moi.gov.bh, nbr.gov.bh VAT). `.gov.bh` ≠ `.gov`.
    "gov.bh",
    # Oman (destination rank 36, Muscat) — government bodies publish under `.gov.om`
    # (rop.gov.om Royal Oman Police / residence, manpower/labour, tax authority). `.gov.om` ≠ `.gov`.
    "gov.om",
    # South Africa (destination rank 37, Johannesburg) — the whole government publishes under `.gov.za`
    # (dha.gov.za Home Affairs / visas & permits, sars.gov.za tax, labour.gov.za). `.gov.za` ≠ `.gov`.
    "gov.za",
    # Malaysia (destination rank 38, Kuala Lumpur) — the whole government publishes under `.gov.my`
    # (imi.gov.my Immigration / Expatriate Services Division, hasil.gov.my Inland Revenue). `.gov.my` ≠ `.gov`.
    "gov.my",
    # Thailand (destination rank 39, Bangkok) — the whole government publishes under `.go.th`
    # (immigration.go.th, rd.go.th tax, mfa.go.th visa, sso.go.th social security). `.go.th` ≠ `.gov`.
    "go.th",
    # China (destination rank 40, Shanghai) — the government publishes under `.gov.cn`
    # (nia.gov.cn National Immigration Administration, chinatax.gov.cn, mfa.gov.cn visa). `.gov.cn` ≠ `.gov`.
    "gov.cn",
    # India (destination rank 41, Bengaluru) — the government publishes under `.gov.in`
    # (mha.gov.in Home Affairs, indianfrro.gov.in / boi.gov.in immigration, incometax.gov.in, mea.gov.in visa).
    "gov.in",
    # Turkey (destination rank 42, Istanbul) — the government publishes under `.gov.tr`
    # (goc.gov.tr Migration Management, gib.gov.tr tax, turkiye.gov.tr e-portal). `.gov.tr` ≠ `.gov`.
    "gov.tr",
    # Hungary (rank 43) — `.gov.hu` (oif.gov.hu / enterhungary.gov.hu residence, nav.gov.hu tax).
    "gov.hu",
    # Romania (rank 44) — `.gov.ro` (igi.mai.gov.ro immigration). ANAF tax = anaf.ro (host below).
    "gov.ro",
    # Argentina (rank 45) — `.gob.ar` (migraciones.gob.ar, argentina.gob.ar, arca.gob.ar tax).
    "gob.ar",
    # Chile (rank 46) — `.gob.cl` (chileatiende.gob.cl, extranjeria.gob.cl). serviciomigraciones.cl /
    # sii.cl are not gob.cl — hosts below.
    "gob.cl",
    # Cyprus (rank 48) — `.gov.cy` (moi.gov.cy Civil Registry & Migration, mof.gov.cy tax).
    "gov.cy",
    # Malta (rank 50) — `.gov.mt` (identita.gov.mt residence, cfr.gov.mt tax, homeaffairs.gov.mt).
    "gov.mt",
    # (Estonia rank 47 and Iceland rank 49 use no governmental suffix — their statutory bodies are
    # added as hosts below.)
    # Wave 9 — Asia-Pacific tail, ranks 53-56. Each is a registry-reserved government namespace:
    # Taiwan `.gov.tw` (immigration.gov.tw NIA, mol.gov.tw labour, nhi.gov.tw health, ntbt.gov.tw tax);
    # Vietnam `.gov.vn` (xuatnhapcanh.gov.vn immigration, molisa.gov.vn labour, gdt.gov.vn tax,
    # baohiemxahoi.gov.vn social insurance); Indonesia `.go.id` (imigrasi.go.id, kemnaker.go.id labour,
    # pajak.go.id tax, bpjsketenagakerjaan.go.id); Philippines `.gov.ph` (immigration.gov.ph BI,
    # dole.gov.ph labour, bir.gov.ph tax, philhealth.gov.ph, sss.gov.ph).
    "gov.tw", "gov.vn", "go.id", "gov.ph",
    # Wave 10 — Latin America cluster, ranks 57-61. Registry-reserved government namespaces:
    # Colombia `.gov.co` (migracioncolombia.gov.co, dian.gov.co tax); Peru `.gob.pe`
    # (migraciones.gob.pe, sunat.gob.pe tax); Uruguay `.gub.uy` (migracion.gub.uy, dgi.gub.uy tax,
    # bps.gub.uy); Costa Rica `.go.cr` (migracion.go.cr, hacienda.go.cr tax) — plus ccss.sa.cr
    # (the Caja / social-security fund, a `.sa.cr` host, added below); Panama `.gob.pa`
    # (migracion.gob.pa, css.gob.pa social security).
    "gov.co", "gob.pe", "gub.uy", "go.cr", "gob.pa",
    # Wave 11 — EU cluster, ranks 66-70. EU member states; each has a government suffix, though
    # several statutory bodies sit on bare national domains (added as hosts below): Croatia
    # `.gov.hr` (mup.gov.hr police/residence); Slovenia `.gov.si` (fu.gov.si tax, e-uprava.gov.si);
    # Slovakia `.gov.sk` (many ministries use bare `.sk` — hosts below); Latvia `.gov.lv`
    # (pmlp.gov.lv migration, vid.gov.lv tax, vsaa.gov.lv social insurance); Lithuania `.gov.lt`
    # (plus migracija.lrv.lt / vmi.lt / sodra.lt on bare `.lt` — hosts below).
    "gov.hr", "gov.si", "gov.sk", "gov.lv", "gov.lt",
)

#: Statutory bodies whose domain does not advertise itself as governmental. These publish the
#: rule; they are the primary source even though the TLD does not say so.
_OFFICIAL_HOSTS: Tuple[str, ...] = (
    # France
    "service-public.fr", "legifrance.gouv.fr", "urssaf.fr", "ameli.fr",
    "impots.gouv.fr", "france-visas.gouv.fr", "ofii.fr",
    # France — the two social-security bodies a mover actually deals with, neither of which
    # sits under `gouv.fr`. CLEISS is the French liaison body for international social
    # security: it publishes the coordination and totalisation rules for a move between
    # France and another state, which is the single most load-bearing source for an inbound
    # EEA corridor, and it scored UNOFFICIAL. The CAF is the family-benefits arm of the
    # Sécurité sociale and publishes its own entitlement conditions. Both publish the rule
    # rather than restating one. This is the fourth time this list has been too narrow, and
    # the failure mode is always the same: the rejects cluster by country.
    "cleiss.fr", "caf.fr",
    # Norway
    "udi.no", "skatteetaten.no", "politiet.no", "nav.no", "altinn.no", "lovdata.no",
    "helsenorge.no", "brreg.no", "folkeregisteret.no",
    # Germany
    "bamf.de", "auswaertiges-amt.de", "gesetze-im-internet.de", "bundesregierung.de",
    "make-it-in-germany.com", "arbeitsagentur.de",
    # FR-DE wave (2026-09): the federal portal is make-it-in-germany.DE (the .com above is the
    # legacy host); deutsche-rentenversicherung.de is the statutory pension body and
    # gkv-spitzenverband.de the statutory-health-insurance umbrella — both public-law bodies that
    # publish the rule, like bamf.de. Missing here = same too-narrow-allowlist reject as riigiteataja.
    "make-it-in-germany.de", "deutsche-rentenversicherung.de", "gkv-spitzenverband.de",
    # Portugal
    "aima.gov.pt", "seg-social.pt", "portaldasfinancas.gov.pt",
    # Ireland. Immigration Service Delivery, the Department of Justice unit that operates
    # registration and issues the IRP — it publishes the rule, it does not restate one, which
    # is what separates it from citizensinformation.ie below. The `.ie` domain does not end in
    # `gov.ie`, so the suffix rule alone rejected it and took the whole first-time
    # registration entity with it: the 90-day deadline, the €300 fee, the 10-working-day card
    # delivery. This repo's own Otto card contract already names the host as statutory
    # (docs/audos/otto-batch-2026-08-13/otto-batch.json:699, otto_verify.py:56) — the
    # importer's allowlist had simply never been told.
    "irishimmigration.ie",
    # Ireland — the statutory bodies an EU/EEA free mover actually deals with. Immigration
    # Service Delivery above covers the non-EEA track; none of it applies to a free mover, who
    # instead needs a PPSN, health entitlement, a tenancy and a driving licence. Every one of
    # those is published by a body outside `gov.ie`, so the suffix rule scored them UNOFFICIAL
    # and rejected the facts outright — the same failure the Spain block below records. The HSE
    # is the health service setting out its own ordinary-residence entitlement; the RTB is the
    # statutory board that runs tenancy registration; the NDLS and its parent RSA run licence
    # exchange; welfare.ie and mywelfare.ie are the Department of Social Protection's own
    # portals, and MyWelfare is where a PPSN application is actually made. Each publishes its
    # own rule rather than restating one, which is the line this list draws.
    "hse.ie", "rtb.ie", "ndls.ie", "rsa.ie", "welfare.ie", "mywelfare.ie",
    # Ireland — municipal and transport, for city-level settle-in content. Same call as
    # `madrid.es` and `service.berlin.de` below and above: Dublin City Council runs and
    # publishes its own services rather than restating a national rule. Transport for Ireland
    # and the Leap card scheme are operated by the National Transport Authority, which sets
    # and publishes the fare and card rules it describes — the same reasoning that admits
    # `rundfunkbeitrag.de`, the body that levies the fee it explains.
    "dublincity.ie", "transportforireland.ie", "leapcard.ie", "nationaltransport.ie",
    # Denmark. Denmark uses no governmental suffix at all, so the suffix rule scored the
    # national tax authority itself as a relocation blog and rejected it.
    "skat.dk",
    # Germany. `bund.de` covers the federal portal, but the bodies that actually publish the
    # rule mostly do not sit under it: the BZSt issues the tax ID, service.berlin.de is the
    # Land of Berlin's own service catalogue for the Anmeldung, and Rundfunkbeitrag is the
    # body that levies the broadcasting fee it describes.
    "bzst.de", "service.berlin.de", "rundfunkbeitrag.de",
    # Spain. Only the `gob.es` suffix was recognised, so every statutory body that does not
    # sit under it scored UNOFFICIAL and was rejected outright — which is every Spain-side
    # fact in an ES->IE deliverable. `boe.es` is the starkest: the Boletín Oficial del Estado
    # publishes the law itself, exactly as `legifrance.gouv.fr` and `lovdata.no` do, and both
    # of those were already listed. The AEAT was *half* admitted, because
    # `agenciatributaria.gob.es` (the sede) passes on the suffix while `agenciatributaria.es`
    # does not — so a tax fact survived or died on which of the agency's own two domains the
    # researcher happened to cite. All five publish their own rule rather than restating one.
    "boe.es", "seg-social.es", "agenciatributaria.es", "policia.es", "sepe.es",
    # Spain — municipal (padrón). Same call as `service.berlin.de` above: the town hall runs
    # and publishes its own registration procedure, so it is the publisher, not a portal
    # restating someone else's rule. Neither `.es` nor `.cat` carries a governmental suffix
    # (`.cat` is a *linguistic* TLD), so both councils were scored as relocation blogs and the
    # padrón vanished from any ES-side deliverable. Named hosts only — a third city is a
    # decision, not a silent addition.
    "madrid.es", "barcelona.cat",
    # Italy (destination rank 11, Milan). `gov.it` above catches interno.gov.it / agenziaentrate.gov.it,
    # but `normattiva.it` — the official consolidated-law database (Istituto Poligrafico e Zecca dello
    # Stato) where the D.Lgs / TUIR articles are published — has no gov TLD, like boe.es / lovdata.no.
    "normattiva.it",
    # Sweden (destination rank 14, Stockholm). Sweden uses no governmental suffix; each agency has its
    # own `.se` domain: Migrationsverket (migration), Skatteverket (tax + population register),
    # Försäkringskassan (social insurance). Each publishes its own rule. 8th too-narrow-allowlist instance.
    "migrationsverket.se", "skatteverket.se", "forsakringskassan.se",
    # Belgium — statutory bodies not under `.fgov.be`: the Immigration Office (ibz.be), the City of
    # Brussels (brussels.be) and the federal single-permit One-Stop Counter.
    "ibz.be", "brussels.be", "onestopcounter.workinginbelgium.be",
    # Saudi Arabia — statutory portals not under `.gov.sa`: Qiwa (labour/work-permit platform,
    # MHRSD), Absher (MoI e-services) and Muqeem (residency). Each is the operator of the process
    # it documents, like Absher/Muqeem being where the Iqama and exit/re-entry visa are actioned.
    "qiwa.sa", "absher.sa", "muqeem.sa",
    # Portugal — IMT (Instituto da Mobilidade e dos Transportes) runs and publishes driving-licence
    # exchange; its `imt-ip.pt` domain has no `gov.pt` suffix. (aima.gov.pt / seg-social.pt /
    # portaldasfinancas.gov.pt above cover immigration/social-security/tax; `gov.pt` covers sns.gov.pt.)
    "imt-ip.pt",
    # Finland (destination rank 26, Helsinki) — Finland uses no governmental suffix; each agency owns
    # its own `.fi`: Migri (immigration), Enter Finland (permit portal), UM (MFA), Vero (tax),
    # Kela (social insurance), DVV (population register / personal identity code), Suomi.fi (state
    # portal), Traficom (driving), Tyosuojelu (occupational safety) and Finlex (the official law
    # database, like normattiva.it / boe.es / lovdata.no). Each publishes its own rule.
    "migri.fi", "enterfinland.fi", "um.fi", "vero.fi", "kela.fi", "dvv.fi",
    "suomi.fi", "traficom.fi", "tyosuojelu.fi", "finlex.fi",
    # Hong Kong — the MPF (Mandatory Provident Fund) Schemes Authority publishes retirement-savings
    # rules under `mpfa.org.hk`, an org TLD, so `gov.hk` does not catch it.
    "mpfa.org.hk",
    # Poland — ZUS (Zakład Ubezpieczeń Społecznych, the social-insurance institution) publishes its
    # own contribution/coverage rules under `zus.pl`, which is not a `gov.pl` host.
    "zus.pl",
    # South Korea — the national health-insurance service publishes coverage rules under `nhis.or.kr`
    # (an or.kr TLD, not go.kr).
    "nhis.or.kr",
    # Luxembourg — the state's one-stop portal is `guichet.lu` (the content also mirrors under
    # guichet.public.lu, which the `public.lu` suffix catches; the bare host is added for safety).
    "guichet.lu",
    # Czech Republic — statutory bodies on their own `.cz` (not gov.cz): mvcr.cz (Ministry of Interior /
    # immigration), mzv.cz (MFA / visas), mpsv.cz (labour), financnisprava.cz (tax), cssz.cz (social
    # security), vzp.cz (public health insurer).
    "mvcr.cz", "mzv.cz", "mpsv.cz", "financnisprava.cz", "cssz.cz", "vzp.cz",
    # Greece — statutory bodies not under gov.gr: aade.gr (Independent Authority for Public Revenue /
    # tax), mfa.gr (Ministry of Foreign Affairs / visas).
    "aade.gr", "mfa.gr",
    # Bahrain — the national e-government portal is `bahrain.bh` (the eGovernment Authority's own
    # domain), which is not a `gov.bh` host.
    "bahrain.bh",
    # Romania — ANAF (Agenția Națională de Administrare Fiscală, the tax authority) publishes under
    # `anaf.ro`, not a `gov.ro` host.
    "anaf.ro",
    # Chile — the National Migration Service (`serviciomigraciones.cl`) and the tax authority SII
    # (`sii.cl`) publish on their own `.cl`, not under `gob.cl`.
    "serviciomigraciones.cl", "sii.cl",
    # Estonia (rank 47) — no governmental suffix; each body owns its own `.ee`: politsei.ee (Police
    # & Border Guard Board / residence permits), emta.ee (Tax & Customs Board), eesti.ee (state
    # portal), sotsiaalkindlustusamet.ee (Social Insurance Board). riigiteataja.ee is the Riigi
    # Teataja (State Gazette) — the official consolidated-law database that publishes the Aliens Act
    # itself, exactly like boe.es / lovdata.no / normattiva.it above. It was missing here, so the two
    # Estonian immigration-quota facts (Aliens Act §113/§115) scored UNOFFICIAL and were rejected —
    # the same too-narrow-allowlist failure whose rejects always cluster by source.
    "politsei.ee", "emta.ee", "eesti.ee", "sotsiaalkindlustusamet.ee", "riigiteataja.ee",
    # Iceland (rank 49) — no governmental suffix; utl.is (Directorate of Immigration /
    # Útlendingastofnun), skatturinn.is (tax), island.is (state portal).
    "utl.is", "skatturinn.is", "island.is",
    # Costa Rica (wave 10) — the Caja Costarricense de Seguro Social publishes on ccss.sa.cr, a
    # `.sa.cr` host the `.go.cr` suffix does not cover (migracion.go.cr / hacienda.go.cr do).
    "ccss.sa.cr",
    # EU cluster (wave 11) — statutory bodies that publish the rule on bare national domains, not
    # under the government suffix. Croatia: porezna-uprava.hr (Tax Administration), hzzo.hr (health
    # fund), mirovinsko.hr (pension). Slovenia: policija.si (police / residence registration),
    # zzzs.si (health-insurance institute), zpiz.si (pension institute). Slovakia (ministries sit
    # on bare `.sk`): minv.sk (Interior/police — residence), financnasprava.sk (Financial
    # Administration/tax), socpoist.sk (Sociálna poisťovňa), slovensko.sk (state e-portal).
    # Lithuania: migracija.lrv.lt (Migration Dept), vmi.lt (State Tax Inspectorate), sodra.lt
    # (social insurance), vlk.lt (compulsory-health-insurance fund). Latvia: latvija.lv (state
    # portal; pmlp/vid/vsaa are gov.lv, covered by the suffix above).
    "porezna-uprava.hr", "hzzo.hr", "mirovinsko.hr",
    "policija.si", "zzzs.si", "zpiz.si",
    "minv.sk", "financnasprava.sk", "socpoist.sk", "slovensko.sk",
    # slov-lex.sk is the official Slovak legislation portal (the state law gazette, like
    # riigiteataja.ee / boe.es); vszp.sk is Všeobecná zdravotná poisťovňa, the state health
    # insurer (a public-law body). Both publish the rule; neither carries the gov suffix.
    "slov-lex.sk", "vszp.sk",
    "migracija.lrv.lt", "vmi.lt", "sodra.lt", "vlk.lt",
    "latvija.lv",
    # Cross-border / EU
    "eur-lex.europa.eu", "ec.europa.eu", "efta.int",
)

#: Public agencies and para-statal bodies: authoritative enough to keep, not authoritative
#: enough to auto-accept. A fact sourced here always lands in the review queue.
_SEMI_OFFICIAL_HOSTS: Tuple[str, ...] = (
    "campusfrance.org", "welcometofrance.com", "workinnorway.no",
    "newtonorway.no", "study.eu", "youreurope.europa.eu",
    # Ireland. Both are statutory bodies whose domain does not end in `.gov.ie`, so the
    # suffix rule alone read them as a relocation blog and REJECTED them outright. That
    # cost us the facts nobody else publishes plainly: emergency tax until the Revenue
    # job registration lands, RTB tenancy registration, and the non-Schengen consequence
    # of an Irish permission. Citizens Information is run by the Citizens Information
    # Board (a statutory agency under the Department of Social Protection); Revenue is
    # the tax authority itself. Semi-official, not official: both restate rules published
    # elsewhere, so a fact from here is worth keeping and belongs in the review queue.
    "citizensinformation.ie", "revenue.ie",
    # Denmark. borger.dk is the Danish state's official citizen portal, run by the Agency
    # for Digital Government — so it belongs in, not out. Semi-official for the same reason
    # as citizensinformation.ie: it is a portal that restates what SKAT, the CPR office and
    # the regions publish elsewhere, so a fact from here belongs in the review queue.
    "borger.dk",
    # Vietnam. baochinhphu.vn (Báo Chính phủ / the Online Newspaper of the Government of Viet
    # Nam) is run by the Government Office (Văn phòng Chính phủ) — a state organ, so it belongs
    # in, not out. Semi-official for the same reason as citizensinformation.ie / borger.dk: it
    # reports and restates the decrees (219/2025, 152/2020, 143/2018 …) rather than promulgating
    # them, and the primary texts (vbpl.vn) sit behind a WAF while the decree PDFs are scanned —
    # so a fact from here is worth keeping and belongs in the review queue for a check against
    # the statute. The `.vn` government suffix is `gov.vn`; baochinhphu.vn does not carry it.
    "baochinhphu.vn",
    # Austria. wko.at is the Wirtschaftskammer Österreich, a public-law chamber (Körperschaft
    # öffentlichen Rechts) that reproduces the NAG statute (§53/§77) verbatim, incl. the exact
    # Anmeldebescheinigung fine that the strictly-statutory ris.bka.gv.at states but which is
    # CAPTCHA-walled. Semi-official for the same reason as citizensinformation.ie / borger.dk:
    # it restates the law published elsewhere, so a fact from here belongs in the review queue.
    "wko.at",
)


class FactRowError(ValueError):
    """A record whose *shape* is unusable — bad JSON, missing key, unparseable number.

    Distinct from a record that parses fine but fails the sourcing gate: that one is a
    *rejection*, collected and reported, not an exception.
    """


@dataclass
class FactRow:
    """One validated fact, ready for `otto_staging.immigration_fact_candidates`."""

    destination_country: str
    entity_topic_key: str
    fact_key: str
    fact_text: str
    source_url: str
    batch_id: str
    entity_title: str
    fact_type: str = "other"
    applies_to: Optional[Dict[str, Any]] = None
    evidence_quote: Optional[str] = None
    confidence: str = "medium"
    confidence_score: float = 0.6
    accuracy_tier: str = TIER_REVIEW
    source_class: str = SEMI_OFFICIAL
    #: Every downgrade applied to this row, so a reviewer sees what was derived, not read.
    #: The table has no `notes` column, so these surface in the CLI and in `load_log.notes`.
    downgrades: List[str] = field(default_factory=list)

    @property
    def dedupe_key(self) -> str:
        """`FR|eu_free_movement_worker|cardFee` — the convention already in production."""
        return f"{self.destination_country}|{self.entity_topic_key}|{self.fact_key}"


def _host(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    if "//" not in raw:
        raw = "//" + raw
    return (urlsplit(raw).hostname or "").lower().lstrip(".")


def _matches(host: str, suffixes: Tuple[str, ...]) -> bool:
    return any(host == s or host.endswith("." + s) for s in suffixes)


def classify_source(source_url: str) -> str:
    """OFFICIAL / SEMI_OFFICIAL / UNOFFICIAL for an evidence URL.

    Unrecognised is UNOFFICIAL, deliberately. The safe default for a compliance fact is to
    refuse it and put it on the re-sourcing worklist, not to admit it on the chance that the
    domain is fine — an unrecognised host is exactly where a relocation blog paraphrasing a
    2019 rule would land.

        >>> classify_source("https://www.service-public.gouv.fr/particuliers/F16003")
        'official'
        >>> classify_source("https://www.campusfrance.org/en/fees")
        'semi_official'
        >>> classify_source("https://some-relocation-blog.com/moving-to-france")
        'unofficial'
    """
    host = _host(source_url)
    if not host:
        return UNOFFICIAL
    if _matches(host, _OFFICIAL_HOSTS) or _matches(host, _OFFICIAL_SUFFIXES):
        return OFFICIAL
    if _matches(host, _SEMI_OFFICIAL_HOSTS):
        return SEMI_OFFICIAL
    return UNOFFICIAL


# Single-segment paths that address a SITE rather than a rule. `classify_source` cannot see
# these because it only ever looks at the host: `https://www.urssaf.fr/accueil` is served by a
# statutory publisher and identifies nothing.
_HOMEPAGE_SEGMENTS = frozenset(
    {"accueil", "home", "index", "index.html", "index.htm", "en", "fr", "de", "no", "es", "nl"}
)

# A directory record — a contact card for an office — is not a normative page. The ws 630
# fabrication was cited to one of these.
_DIRECTORY_HOSTS = ("lannuaire.service-public.gouv.fr", "lannuaire.service-public.fr")
_DIRECTORY_SEGMENTS = frozenset({"centres-contact", "annuaire"})

#: Citation forms that are not URLs and resolve anyway. NOT REJECTED: a bare UUID. It looks like a dangling reference and is not one —
# `requirement_items.citations_json` legitimately carries three formats (raw URL,
# `source_records` UUID, `immigration_rule.*` corpus ref) and all three resolve. Checked
# 2026-08-23: all four FRANCE rows citing a raw UUID resolve to a `source_records` row with a
# real url, publisher_domain, published_date and snippet — they are the best-cited rows in the
# set, not the worst. `scripts/check_requirement_provenance.py` refuses this check for the same
# reason and says so: "A checker that demanded one format would flag 24 legitimate rows and be
# switched off within a day." Zero of the 940 distinct `source_url` values in prod are a UUID,
# so a rule here would fire on nothing while encoding a false premise for whoever copies it.
_RESOLVABLE_NON_URL_REF = re.compile(
    r"^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"|immigration_rule\.[\w.]+)$",
    re.I,
)


def unspecific_citation_reason(source_url: str) -> Optional[str]:
    """Why this citation cannot evidence a specific claim, or None when it can.

    A companion to `classify_source`, which answers "is the publisher official?" and stops
    there. Both questions have to be asked, because the existing checks are each blind to this
    in a different way: the publisher test passes (a homepage on a statutory domain is on a
    statutory domain), and the verbatim-quote test passes too, since navigation-menu words
    really are on the page. Measured on the NO->FR corpus 2026-08-23: three SERVED FRANCE rows
    cite a bare domain and two cite a bare UUID.

        >>> unspecific_citation_reason(
        ...     "https://www.service-public.gouv.fr/particuliers/vosdroits/F16003") is None
        True
        >>> "homepage" in unspecific_citation_reason("https://www.urssaf.fr/accueil")
        True
    """
    raw = (source_url or "").strip()
    if not raw:
        return "no source_url"
    if _RESOLVABLE_NON_URL_REF.match(raw):
        return None

    host = _host(raw)
    if not host:
        return "not a resolvable URL"

    path = urlsplit(raw if "//" in raw else "//" + raw).path or ""
    segments = [seg for seg in path.split("/") if seg]

    if _matches(host, _DIRECTORY_HOSTS) or (segments and segments[0] in _DIRECTORY_SEGMENTS):
        return "a directory contact record, not a normative page"
    if not segments:
        return "a bare domain with no path — identifies a site, not a rule"
    if len(segments) == 1 and segments[0].lower() in _HOMEPAGE_SEGMENTS:
        return "a homepage — identifies a site, not a rule"
    return None


def _humanise(topic_key: str) -> str:
    """`eu_free_movement_worker` -> `Eu free movement worker`, a last-resort entity title."""
    return re.sub(r"[_\-]+", " ", topic_key).strip().capitalize()


def grade(row: FactRow) -> FactRow:
    """Set `accuracy_tier` and `confidence_score` from the evidence, recording every downgrade.

    `auto_accepted` requires an official publisher, a quotable line of evidence, and that the
    quote has not been explicitly marked unconfirmed. Otto's own `confidence` is an input, never
    the last word: an agent calling its own finding "high" is not evidence, and every one of the
    24 rows already staged called itself high.
    """
    row.confidence_score = CONFIDENCE_SCORES.get(row.confidence, CONFIDENCE_SCORES["medium"])

    if row.source_class != OFFICIAL:
        row.downgrades.append(
            f"publisher {_host(row.source_url)!r} is not a statutory source "
            f"({row.source_class})"
        )
    unspecific = unspecific_citation_reason(row.source_url)
    if unspecific:
        row.downgrades.append(f"source_url is {unspecific}")
    if not (row.evidence_quote or "").strip():
        row.downgrades.append("no evidence_quote — the claim cannot be re-checked from the row")
    # A batch that captured a quote but never re-read it against the page says so, via
    # `quote_verbatim_confirmed`. There is no column for that flag, so it rides in
    # `applies_to`. Without this, an unchecked quote scores exactly like a checked one and a
    # row a lawyer still has to clear is badged as though the evidence were verified — which is
    # how an unreviewed claim survives review by looking already-done.
    #
    # Tested with `is False`, never falsiness: an absent key and `None` mean "not claimed", not
    # "not confirmed". Every batch before ve-ie-entry-family-2026-08-20 omits the key, and
    # re-grading those rows would invalidate reviews that have already happened.
    if (row.applies_to or {}).get("quote_verbatim_confirmed") is False:
        row.downgrades.append(
            "evidence_quote is not verbatim-confirmed — captured but never re-checked "
            "against the source page"
        )
    if row.confidence not in CONFIDENCE_SCORES:
        row.downgrades.append(f"unrecognised confidence {row.confidence!r}, scored as medium")

    row.accuracy_tier = TIER_AUTO if not row.downgrades else TIER_REVIEW
    if row.downgrades:
        # A row the evidence will not carry must not also claim high confidence.
        row.confidence_score = min(row.confidence_score, CONFIDENCE_SCORES["medium"])
    return row


def _to_row(rec: Dict[str, Any], batch_id: str, lineno: int) -> FactRow:
    missing = [k for k in REQUIRED_FIELDS if not str(rec.get(k) or "").strip()]
    if missing:
        raise FactRowError(f"missing required field(s): {', '.join(missing)}")

    applies_to = rec.get("applies_to")
    if applies_to is not None and not isinstance(applies_to, dict):
        raise FactRowError(f"applies_to must be an object, got {type(applies_to).__name__}")

    fact_type = str(rec.get("fact_type") or "other").strip().lower()
    if fact_type not in KNOWN_FACT_TYPES:
        fact_type = "other"

    row = FactRow(
        destination_country=str(rec["destination_country"]).strip().upper(),
        entity_topic_key=str(rec["entity_topic_key"]).strip(),
        fact_key=str(rec["fact_key"]).strip(),
        fact_text=str(rec["fact_text"]).strip(),
        source_url=str(rec["source_url"]).strip(),
        batch_id=batch_id,
        entity_title=str(rec.get("entity_title") or "").strip()
        or _humanise(str(rec["entity_topic_key"])),
        fact_type=fact_type,
        applies_to=applies_to,
        evidence_quote=(str(rec.get("evidence_quote") or "").strip() or None),
        confidence=str(rec.get("confidence") or "medium").strip().lower(),
    )
    row.source_class = classify_source(row.source_url)
    return grade(row)


def read_jsonl(path: Path, *, batch_id: str) -> Tuple[List[FactRow], List[str]]:
    """Parse the file into (accepted rows, rejection messages).

    A malformed line raises `FactRowError` and stops the read: a file we cannot parse is a
    delivery failure, and importing its readable half would report a partial batch as a
    complete one. A well-formed line from an unofficial publisher is a *rejection* — collected,
    reported, and left for re-sourcing, because that is a research problem, not a file problem.
    """
    rows: List[FactRow] = []
    rejections: List[str] = []
    seen: Dict[str, int] = {}

    with Path(path).open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise FactRowError(f"line {lineno}: not valid JSON — {exc}") from exc
            if not isinstance(rec, dict):
                raise FactRowError(f"line {lineno}: expected an object, got {type(rec).__name__}")
            try:
                row = _to_row(rec, batch_id, lineno)
            except FactRowError as exc:
                raise FactRowError(f"line {lineno}: {exc}") from exc

            if row.source_class == UNOFFICIAL:
                rejections.append(
                    f"line {lineno}: {row.dedupe_key} — source {_host(row.source_url)!r} "
                    "is not an official or public-agency publisher"
                )
                continue

            # Two rows claiming the same fact key would collide on the table's UNIQUE
            # (dedupe_key). Catch it here, naming both lines, rather than as an IntegrityError
            # that names neither.
            if row.dedupe_key in seen:
                rejections.append(
                    f"line {lineno}: {row.dedupe_key} duplicates line {seen[row.dedupe_key]} "
                    "in this same file"
                )
                continue
            seen[row.dedupe_key] = lineno
            rows.append(row)

    return rows, rejections
