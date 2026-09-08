# PT facts — third-country-national professional relocated to Portugal (Lisbon)

- **Destination:** PT (hub: Lisbon)
- **Perspective nationality:** `non-EEA` (third-country pathway only; no EU-free-movement facts)
- **Persona:** professional relocated by their employer
- **Generated:** 2026-08-31
- **Facts:** 12 (all `confidence: high`, all `quote_verbatim_confirmed: true`)
- **Grounding method:** each page fetched from its official government domain and the
  `evidence_quote` verified programmatically as a verbatim substring of the fetched page
  text (whitespace-normalised), each quote < 200 chars. Portuguese-language quotes kept
  verbatim; `fact_text` written in English. The MFA visa portal and AIMA pages were also
  opened in-browser; fetch + substring check is what produced the confirmed quotes below.

## Source domains used (all official / statutory)
- `vistos.mne.gov.pt` — Ministry of Foreign Affairs visa portal
- `aima.gov.pt` — Agency for Integration, Migration & Asylum (SEF successor)
- `info.portaldasfinancas.gov.pt` — Tax & Customs Authority (AT)
- `www2.gov.pt` / `gov.pt` — Portuguese government services portal (Finanças/Seg. Social/SNS/IMT service pages)

## Per-fact source + verification

| # | fact_key | pillar | type | verbatim? | source URL |
|---|----------|--------|------|-----------|------------|
| 1 | PT:immigration:residency-visa-two-step | IMMIGRATION | process | yes (len 175) | https://vistos.mne.gov.pt/en/national-visas/general-information/type-of-visa |
| 2 | PT:immigration:aima-appointment-gap | IMMIGRATION | process | yes (len 161) | https://vistos.mne.gov.pt/en/highlights/residence-visa-issued-without-appointment-at-aima |
| 3 | PT:immigration:eu-blue-card-threshold | IMMIGRATION | eligibility | yes (len 140) | https://aima.gov.pt/pt/viver/concessao-de-cartao-azul-ue-e-autorizacao-de-residencia-para-titulares-de-cartao-azul-ue-noutro-estado-membro-art-121-o-a-e-segu |
| 4 | PT:immigration:eu-blue-card-mobility | IMMIGRATION | eligibility | yes (len 185) | https://aima.gov.pt/pt/viver/concessao-de-cartao-azul-ue-e-autorizacao-de-residencia-para-titulares-de-cartao-azul-ue-noutro-estado-membro-art-121-o-a-e-segu |
| 5 | PT:immigration:criminal-record-apostille | IMMIGRATION | document | yes (len 174) | https://vistos.mne.gov.pt/en/national-visas/necessary-documentation/residency |
| 6 | PT:family:reunification-aima-first | FAMILY | process | yes (len 191) | https://vistos.mne.gov.pt/en/national-visas/general-information/family-reunification |
| 7 | PT:tax:nif-fiscal-representative | TAX | obligation | yes (len 124) | https://info.portaldasfinancas.gov.pt/pt/apoio_contribuinte/Folhetos_informativos/Documents/Atribuicao_de_NIF_a_cidadaos_estrangeiros_nao_residentes.pdf |
| 8 | PT:tax:ifici-former-nhr | TAX | eligibility | yes (len 128) | https://info.portaldasfinancas.gov.pt/pt/apoio_contribuinte/questoes_frequentes/pages/faqs-01018.aspx |
| 9 | PT:tax:residency-183-days | TAX | obligation | yes (len 132) | https://info.portaldasfinancas.gov.pt/pt/informacao_fiscal/codigos_tributarios/cirs_rep/Pages/irs16.aspx |
| 10 | PT:employment:niss-third-country | EMPLOYMENT | document | yes (len 127) | https://www2.gov.pt/migrantes-viver-e-trabalhar-em-portugal/migrantes-impostos-e-seguranca-social-em-portugal/como-pedir-o-nif-e-o-niss-para-cidadaos-estrangeiros-em-portugal |
| 11 | PT:healthcare:sns-user-number | HEALTHCARE | process | yes (len 107) | https://www2.gov.pt/migrantes-viver-e-trabalhar-em-portugal/migrantes-cuidados-de-saude-em-portugal |
| 12 | PT:immigration:driving-licence-exchange | IMMIGRATION | deadline | yes (len 138) | https://www2.gov.pt/servicos/trocar-carta-de-conducao-estrangeira-por-portuguesa |

## Verbatim quotes (as stored in `evidence_quote`)
1. "Residency visas allow two entries and is valid for a period of 4 months. During that time, the holder of a residency visa is required to apply for a residency permit with AIMA"
2. "there are no appointments available with AIMA, your visa sticker will be printed and affixed to your passport without the link containing the appointment details"
3. "de duração não inferior a seis meses, a que corresponda uma remuneração anual de, pelo menos, 1,5 vezes o salário anual bruto médio nacional"
4. "Pode ainda ser concedida autorização de residência aos que tenham residido pelo menos 18 meses como titulares de «cartão azul UE» noutro Estado membro que lho concedeu pela primeira vez"
5. "Criminal record certificate, issued by the competent authority of the country of the applicant’s nationality or of the country where the applicant has resided for over a year"
6. "going to a consular post to request a residency permit for family reunification purposes, a foreign national entitled to the right for family reunification should request a concession at AIMA"
7. "não é obrigatória a designação de um representante fiscal. Contudo, se o cidadão estabelecer uma relação jurídica tributária"
8. "Não tenham residido, para efeitos fiscais , em Portugal nos cinco anos anteriores e se tornem fiscalmente residentes em Portugal"
9. "Hajam nele permanecido mais de 183 dias, seguidos ou interpolados, em qualquer período de 12 meses com início ou fim no ano em causa"
10. "Pessoas de país terceiro devem apresentar todos os seguintes documentos: Passaporte Visto de trabalho Autorização de Residência"
11. "Ter número de utente de saúde por si só não garante a cobertura das despesas dos cuidados de saúde pelo SNS"
12. "Se residir em Portugal, deve trocar a carta de condução estrangeira por portuguesa no prazo de 2 anos depois de ter residência em Portugal"

## Topics covered
Two-step residency visa → AIMA residence permit; AIMA appointment gap; EU Blue Card
threshold; EU Blue Card intra-EU mobility (18 months); apostilled criminal-record
certificate; family reunification filed at AIMA first; NIF fiscal representative;
IFICI (former NHR) tax regime; 183-day tax residency + habitual-home trigger; NISS
documents; SNS user-number vs coverage; driving-licence exchange.

## Unverifiable / dropped categories (not written — no verbatim official quote obtained)
- **EU Blue Card 30-day intra-EU mobility filing deadline** — a search summary mentioned
  "within 30 days of entry", but that string was not found in the static text of the AIMA
  Blue Card page, so it was not written. Only the 18-month prior-residence clause (fact 4)
  was verbatim-confirmed.
- **Portuguese bank account / proof-of-address requirement** — no single official gov page
  gave a clean verbatim statement tying account/address to the relocation flow; NIF and SNS
  facts partially cover the "address needed" angle instead.
- **Highly-qualified subordinate-work residence *visa* (art. 61-A) salary threshold** — the
  MFA `residency` page carries it but in OCR-garbled English ("1,5 times de annual gross
  salary … three times de indexed value (IAS)"); the clean, quotable salary threshold was
  taken from the AIMA EU Blue Card page instead (fact 3), so no separate art. 61-A visa fact
  was written to avoid an unclean quote.
- **IMT driving pages (imt-ip.pt) detail** — the IMT exchange page renders its 90-day /
  eligibility content via JavaScript accordions not present in static HTML; the equivalent
  facts were sourced from the official gov.pt service page (fact 12) instead.

## Notes on scope discipline
All facts are third-country-specific and avoid EU-free-movement content:
- Immigration facts concern visas/permits an EU citizen does not need.
- NIF fiscal-representative and NISS facts are explicitly the third-country branch
  (the sources state EU/EEA nationals are treated differently).
- Tax-regime and tax-residency facts (IFICI, 183-day) were explicitly requested; they are
  framed in the third-country relocation context and tagged `nationality: non-EEA`.
