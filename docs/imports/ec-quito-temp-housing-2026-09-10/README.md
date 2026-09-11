# ec-quito-temp-housing-2026-09-10

- **Corridor:** US-EC (Abraham — Seattle, US -> Quito, EC)
- **Phase:** P3
- **Package type:** temp_housing
- **Providers file:** `1789135834948_0024bbby.csv`
- **Accepted providers:** 0
- **Rejected/blocked sources:** 5
- **Generated at:** 2026-09-11T00:00:00Z
- **Vetting status:** all vendor rows `platform_vetting_status: 'pending'`

## Status: HONEST ZERO

Ecuadorian official housing registers were WAF/JS-blocked or returned 403/timeout; no browser-grounded providers could be verified.

### Blocked sources
- MIDUVI (Ministerio de Desarrollo Urbano y Vivienda) — register did not render.
- datosabiertos.gob.ec — HTTP 403 (WAF) from datacenter egress.
- SRI RUC lookup — Angular SPA behind F5/BIG-IP WAF; per-RUC lookup only.
- ACESS register — navigation timeout.
- ICF/EMCC Quito listings — captcha-gated.

### Retry recommendation
Retry from an Ecuador-based or otherwise allowed-egress IP (or proxy) able to pass the datosabiertos WAF and render the MIDUVI/ACESS registers. No providers should be accepted without a browser-grounded official-register verification.
