# São Paulo providers — Brazil destination (2026-08-31)

Corridor `XX-BR` (destination-coverage). Every row is evidenced by an **official statutory
register or recognized accreditation body**, cited in `source_url` — never the firm's own
marketing site. Firms that could not be confirmed on a real register were excluded; two
categories are SKIPPED (see below) rather than filled from self-declared sources.

## What landed (15 rows, all `platform_vetting_status` should default to `pending` on load)

| category | n | register cited | per-entity URL? | number captured |
|---|---|---|---|---|
| movers | 4 | FIDI Global Alliance — per-affiliate detail page | yes (`/find-fidi-affiliate/<slug>`) | FAIM expiry where shown (2 of 4 = 2028) |
| banks | 5 | Banco Central do Brasil — Portal de Dados Abertos, per-institution SFN page | yes (`dadosabertos.bcb.gov.br/dataset/ir-<CNPJ>`) | CNPJ (BCB institution key) |
| schools | 4 | IBO — Find an IB World School | yes (`ibo.org/en/school/<id>`) | IB school id |
| legal_admin | 2 | OAB-SP — Consulta ao Cadastro das Sociedades de Advocacia | yes (`consultaSociedades03.asp?param=<n>`) | OAB-SP sociedade registration Nº |
| housing_agencies | 0 | **SKIPPED** | — | — |
| tax_finance | 0 | **SKIPPED** | — | — |

## Registers used, per category

### movers — FIDI Global Alliance (FAIM)
Register: `fidi.org/find-fidi-affiliate`. Each row cites the **per-affiliate detail page**
(not the search URL). Confirmed each firm's São Paulo address on its detail page:
- Transportes Fink (Fink Mobility) — Vila Leopoldina, São Paulo — FAIM Plus valid through **2028**.
- Gerson & Grey Mobility Ltda — Av. Brig. Faria Lima, Jd. Paulistano, São Paulo.
- Netmove Assessoria Internacional Ltda — Jardim Piratininga, São Paulo — FAIM valid through **2028**.
- One Moving & Logistics Ltda — Caieiras (**Grande São Paulo** / SP metro), serves São Paulo.

### banks — Banco Central do Brasil (BCB)
Authoritative register: BCB "Relação de Instituições em Funcionamento no País" /
"Encontre uma instituição regulada/supervisionada pelo BC". Each row cites the BCB
**Portal de Dados Abertos per-institution page** (`dataset/ir-<CNPJ>`), which BCB publishes
"por determinação do Banco Central do Brasil" for each SFN institution — a per-bank, BCB-hosted,
name-bearing page. `accreditation_number` = the CNPJ (the key the BCB register uses),
verified on each page:
- Itaú Unibanco S.A. — 60701190000104
- Banco Bradesco S.A. — 60746948000112
- Banco do Brasil S.A. — 00000000000191
- Banco Santander (Brasil) S.A. — 90400888000142
- Caixa Econômica Federal — 00360305000104

### schools — IBO (International Baccalaureate Organization)
Register: `ibo.org/en/school/<id>` ("Find an IB World School"). Each row cites the per-school
IBO page and captures the IB id. All four are São Paulo IB World Schools, addresses confirmed
from the IBO directory entries:
- Associação Escola Graduada de São Paulo (Graded) — id 000353 — Av. Giovanni Gronchi, SP.
- St. Paul's School — id 000377 — Jardim Paulistano, SP.
- Beacon School — id 019016 — São Paulo.
- The British College of Brazil — id 060188 — Morumbi, SP.

Note: `ibo.org` returns HTTP 403 to automated direct-fetch (Cloudflare), so grounding was via
the IBO directory search results (which return the live per-school page content: name, city,
address, IB id, authorization dates). URLs follow the canonical `ibo.org/en/school/<id>` form.

### legal_admin — OAB-SP (Ordem dos Advogados do Brasil, Seção São Paulo)
Register: OAB-SP "Consulta ao Cadastro das Sociedades de Advocacia"
(`www2.oabsp.org.br/asp/consultaSociedades/`). **No CAPTCHA.** Searched by razão social,
opened each firm's per-firm detail page, captured the sociedade registration Nº and confirmed
São Paulo/SP:
- Pinheiro Neto Advogados — Nº de Registro **11** — Rua Hungria, Jardim Europa, São Paulo/SP.
- Mattos Filho, Veiga Filho, Marrey Jr. e Quiroga Advogados — Nº de Registro **1979** —
  Al. Joaquim Eugênio de Lima, Jardim Paulista, São Paulo/SP.

Only 2 firms captured (target was 3-4). The register works and is CAPTCHA-free, but its result
page submits via a JS-bound anchor that needs a composited browser pane; the shared browser
pane in this environment was repeatedly stolen/hijacked by concurrent agents mid-submit, which
capped the run at the two firms confirmed during brief windows of control. More are readily
obtainable (e.g. Machado Meyer, Demarest, TozziniFreire) when the register can be driven
without contention.

## SKIPPED categories (register exists but could not be used honestly)

- **housing_agencies (CRECI-SP)** — the official register search
  `crecisp.gov.br/cidadao/buscarporimobiliaria` (search by name / CNPJ / CRECI number) is
  **gated by Google reCAPTCHA** (`g-recaptcha-response` + `ReCAPTCHAToken` submitted with the
  query). Completing CAPTCHAs is prohibited, so no imobiliária could be verified on the register.
  Skipped rather than cite firm sites or invent CRECI-J numbers.

- **tax_finance (CRC-SP / CFC)** — the public CRC register is the CFC national
  "Consulta Cadastral" (`www3.cfc.org.br/SPw/ConsultaNacional/ConsultaCadastralCFC.aspx`).
  It is **unreachable from this environment**: direct-fetch returns `ECONNREFUSED` and browser
  navigation is denied/fails on every attempt. `crcsp.org.br` exposes only login-gated
  professional/org self-service, not a public cadastral lookup. With no reachable official
  register, skipped rather than cite firm sites or invent CRC numbers.

## Verification method
- movers: WebFetch of each FIDI per-affiliate detail page (São Paulo address confirmed).
- banks: WebFetch of each BCB `dataset/ir-<CNPJ>` page (institution name + CNPJ confirmed).
- schools: IBO directory results (live per-school page content; ibo.org blocks direct fetch).
- legal_admin: browser-driven OAB-SP sociedades search → per-firm detail page (Nº + SP confirmed).

## Gate remaining (human)
Nothing here is served to an employee. On load these are candidates only
(`platform_vetting_status='pending'`); each must be vetted before it is served, per the
standard provider-vetting gate.
