# BR facts — third-country-national professional relocated to Brazil (hub: São Paulo)

- **Corridor / destination:** `BR` (São Paulo hub)
- **Perspective:** non-EEA professional, employer-sponsored relocation
- **Produced:** 2026-08-31
- **Artifact:** `facts.ndjson` — 10 facts, all `confidence: high`, all `needs_lawyer_review: false`
- **Sourcing rule:** official Brazilian government (`*.gov.br`) only. No blogs / relocation firms / news.
- **Grounding method:** each fact direct-fetched from its official page and the `evidence_quote` confirmed as a verbatim substring of the fetched text. The in-repo browser could not reach `gov.br` (navigation denied by browser policy), so grounding was done via direct page fetch. All 10 quotes verbatim-confirmed.

## Facts by pillar

| # | Pillar | fact_type | Topic |
|---|--------|-----------|-------|
| 1 | RESIDENCE | process | Employer (interested legal person) files the residence authorization via MigranteWeb |
| 2 | RESIDENCE | process | Residence authorization decided in up to 30 days (60 if "em exigência") |
| 3 | TIMELINE | deadline | Register with Polícia Federal within 90 days of entry |
| 4 | TIMELINE | deadline | 30 days from Diário Oficial publication if authorization granted in-country |
| 5 | IDENTITY | document | CRNM is the foreigner ID card issued after PF registration (RNM + CRNM) |
| 6 | IDENTITY | cost | CRNM issuance fee R$ 204,77 (GRU, revenue code STN 140120) |
| 7 | HOUSING | process | PF registration only at the unit of the applicant's domicile circunscrição |
| 8 | EMPLOYMENT | obligation | CPF required to hold a bank account / property / vehicle |
| 9 | SOCIAL_SECURITY | obligation | INSS filiação is automatic on starting remunerated activity |
| 10 | HOUSING | deadline | Foreign driving licence valid max 180 days, then convert to CNH at DETRAN |

## Source URLs + verbatim-confirmed?

| Fact(s) | Source URL | Verbatim confirmed |
|---------|-----------|--------------------|
| 1, 2 | https://www.gov.br/pt-br/servicos/obter-autorizacao-de-residencia-para-fins-laborais-a-imigrantes (Portal Gov.br service, MJSP) | Yes |
| 3, 4, 5, 6, 7 | https://www.gov.br/pt-br/servicos/registrar-se-como-estrangeiro-no-brasil (Portal Gov.br service, Polícia Federal) | Yes |
| 8 | https://servicos.receita.fazenda.gov.br/servicos/cpf/cpfestrangeiro/ (Receita Federal — `fazenda.gov.br`) | Yes |
| 9 | https://www.gov.br/inss/pt-br/direitos-e-deveres/inscricao-e-contribuicao/tipos-de-filiacao (INSS) | Yes |
| 10 | https://www.gov.br/participamaisbrasil/habilitacao-condutor-estrangeiro-direcao-de-veiculos-em-territorio-nacional (SENATRAN/CONTRAN via Participa + Brasil) | Yes |

## Unverifiable / dropped sources (not used)

- **MRE (Ministério das Relações Exteriores) consular visa pages** — every `gov.br/mre/...` consular page for VITEM V and CPF returned a **CAPTCHA challenge** to the fetcher, so no verbatim quote could be confirmed from them. As a result the "VITEM V visa depends on prior residence authorization" point is **not shipped as its own fact**; it is instead captured (with a confirmed MJSP quote) inside fact #1's `non_obvious_note`. The ordering itself is corroborated by official MRE text ("Prior Residence Authorization ... should be requested from the Ministry of Justice and Public Security (MJSP) before visa issuance") but that page could not be verbatim-fetched, so no quote from it was used.
- **PF `pf.gov.br/servicos-pf/...` carta-de-servicos page** — 301-redirects to the generic `gov.br/pf` landing (no substantive text). The equivalent Polícia Federal service content was taken instead from the Portal Gov.br service page (rows 3–7 above), which fetched cleanly.

## Notes

- Fact #8 source is the Receita Federal services subdomain `servicos.receita.fazenda.gov.br` (under `*.gov.br`, official government). The asset list applies to "brasileiras ou estrangeiras, não residentes no Brasil ou residentes no Brasil que possuam bens e direitos sujeitos a registro público no Brasil", i.e. it covers a resident professional.
- No numbers, fees, or citations were invented. Any point without a verbatim official quote was dropped or folded into a `non_obvious_note` (see fact #1).
