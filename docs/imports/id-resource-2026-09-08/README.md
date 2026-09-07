# id-resource-2026-09-08 — STILL HELD (not landed)

**Punch-list item:** *"Indonesia — BPJS Kesehatan: foreigner ≥6 months must enrol"* (HEALTHCARE).
The **claim is true**, but this batch is **not landed** — see below.

## Why it stays held
The claim rests on the definition of *Peserta* in **Perpres 82/2018** (Health Insurance). The
researcher's `facts.ndjson` supplies:

> "Peserta adalah setiap orang, termasuk orang asing yang bekerja paling singkat 6 (enam) bulan di
> Indonesia, **yang telah membayar Iuran Jaminan Kesehatan**."

with `quote_verbatim_confirmed:true` — but that flag reflected a **visual** read of the printed PDF,
because BPK's `peraturan.bpk.go.id` copy has a garbled ClearScan-OCR text layer (mojibake) and the
`confirm_quotes.py` referee could not match it.

On independent re-check, the researcher's quote is **inaccurate**. Perpres 82/2018 Pasal 1 actually
reads *"…dan telah membayar iuran"* — i.e. **"dan"** not "yang", and **"iuran"** not "Iuran Jaminan
Kesehatan" (two transcription errors). Landing the supplied quote would ship a wrong verbatim; the
garbled-OCR referee failure had masked the error.

## What blocked correction this session
- `peraturan.bpk.go.id` — reachable in-browser, but the only full text is the garbled-OCR PDF; the
  detail page (id 94711) is metadata-only ("Materi Pokok"/"Abstrak" empty).
- `peraturan.go.id` (national portal) — connection refused / navigation denied (down).
- A web-search *synthesis* gives the correct wording but a search snippet is **not** a
  reproducibly-fetchable official page, so it is not an acceptable verification source.

## To clear later
Re-source the exact Pasal 1 *Peserta* definition from a reproducibly-fetchable official/JDIH page
(national `peraturan.go.id` when up, or a clean ministry JDIH mirror), correct the quote to the
real wording, then run the normal pipeline. Claim is sound; only the verbatim needs a clean source.
