# US→EC providers — Abraham (Seattle → Quito), 2026-08-30

Greenfield EC provider batch. Otto's sourcing returned **0 rows** — all 6 Ecuadorian registers are
JavaScript-rendered / iframe / login-gated and its scraper could not read them. Its `blocked.json`
(preserved here) is a precise browser-grounding worklist. This batch lands the **one** firm Otto
confirmed by name, browser-grounded to its per-entity register page.

## Landed (1, pending vet)
| category | firm | register | evidence |
|---|---|---|---|
| movers | **INSA International Shipping & Storage** | FIDI FAIM directory | per-entity page `fidi.org/find-fidi-affiliate/insa-international-shipping-storage`, FAIM→2029, info@insa.com.ec, Quito |

INSA is the sole Ecuador FIDI-FAIM mover. Landed via scoped promote (0 rejected).

## Browser-grounding worklist (`blocked.json` — Otto blocked all 6)
- **housing_agencies** — CAINEC Great Place (`cainec.com/greatplace.php`): 7 firms confirmed by name
  (FORXA, EDENCORP, Aquaterra, Ksa, Huasi360, G.P. Tacuri, IMMOBILLIS) — need per-entity "Ver ficha"
  URLs + emails (JS-driven).
- **banks** — Superintendencia de Bancos, Catastro Público (`superbancos.gob.ec`) — JS table, 0 sourced.
- **schools** — MinEduc AMIE (`web.educacion.gob.ec/CNIE`) — login/JS, 0 sourced (filter Quito private
  international).
- **legal_admin** — Colegio de Abogados de Pichincha (`abogadospichincha.com/directorio-profesional/`)
  — iframe, 0 sourced (immigration specialists).
- **tax_finance** — Colegio de Contadores Públicos (`ccpp.org.ec`) — login-gated, 0 sourced.

These are the next browser-grounding round: render each register, extract firms + per-entity URLs +
emails, then land — the same pattern that grounded the SG/EC fact cores.
