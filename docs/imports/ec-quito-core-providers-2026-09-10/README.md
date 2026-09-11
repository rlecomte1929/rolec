# ec-quito-core-providers-2026-09-10

- **Corridor:** US-EC (Abraham — Seattle, US -> Quito, EC)
- **Phase:** CORE
- **Package type:** core_providers
- **Providers file:** `1789135793079_7p0n4z6j.csv`
- **Accepted providers:** 10
- **Rejected/blocked sources:** 5
- **Generated at:** 2026-09-11T00:00:00Z
- **Vetting status:** all vendor rows `platform_vetting_status: 'pending'`

## Accepted providers
- **10 accepts:** 5 banks + 5 legal/immigration firms.
  - **Banks (5)** — verified via the **Superintendencia de Bancos** Consulta de Catastro Público (Bancos Privados Nacionales), captured when the catastro was up in the earlier run: Banco Pichincha, Produbanco, Banco Internacional, Banco General Rumiñahui, Banco Bolivariano.
  - **Legal/immigration (5)** — sourced from the **Foro de Abogados** directory (Consejo de la Judicatura, funcionjudicial.gob.ec), Estudios Jurídicos Colectivos – Pichincha: Juriscorp, Litigium Abogados Asociados, A&B Asesoría Legal Empresarial, A&T Abogados, Advok Abogados.

## Register-egress blockers
5 sources blocked/unreachable on this run: Superbancos **appweb** reportes backend returned RES_NOT_FOUND (404); datosabiertos.gob.ec returned 403 (WAF); the Foro de Abogados JSF app was intermittent ('Acceso Restringido'/hangs); CCPE/Colegio de Contadores member directory is login-gated.

## Retry recommendation
Re-run from an Ecuador-based or allowed-egress IP/proxy able to reach the Superbancos appweb backend and pass the Función Judicial JSF app to refresh/expand the bank and immigration-lawyer lists.
