# Golden Fixture — NO→FR (multi-national still on NO payroll)

> ⚠️ **Not legal advice — a scaffold to brief counsel.** This is the *expected-resolution content* for one relocation fixture, used to assert engine behaviour. Verified rows are hard expectations; unverified points are encoded as `pending_verification` and must NOT be asserted as fact.
>
> **Ownership split:** I own the **content** (what the engine must resolve). **Claude Code (Task 2) owns the schema** — the exact JSON serialization of this fixture and the engine output contract. Map the fields below into whatever shape Task 2 defines; do not treat the field names here as the contract.

---

## §0 — Counsel question set (the corridor's lawyer-gate; all `pending_verification`)

These five must appear in engine output as `pending_verification` / route-to-lawyer, **never as asserted content**. Each converts to a new HARD ASSERT only after counsel closes it.

1. **FR–NO tax treaty Art. 15** — exact employment-income allocation (183-day rule, employer-borne test) during the transition window. *(treaty text not retrieved)*
2. **Norway source-taxation** of employment income for work physically performed in France while on the Norwegian payroll (and any one-year/transition rule).
3. **D-number / Norwegian coverage closure** — whether any active closure step is required.
4. **FR employer registration mechanics** — exact URSSAF *Service Firmes étrangères* process for a Norwegian employer, and whether an Art. 21 employee-delegation agreement is accepted here.
5. **PUMa 3-month wait vs immediate worker-affiliation** — which governs on day one when he both resides *and* works remotely from France.

---

## §1 — Fixture input (the dimensions that drive resolution)

| Dimension | Value |
| --- | --- |
| `nationality_set` | `[FR, SE, NO]` |
| `origin` | `NO` (resident in Norway) |
| `destination` | `FR` |
| `employer` | Norwegian entity |
| `posting_status` | `not_posted` (independent relocation, no employer relo support) |
| `employment_continuity` | remains on Norwegian payroll through the move |
| `work_location_after_move` | `FR` — remote for the NO employer (transitional) → later a FR employer |
| `intent` | seek French employment after arrival |

---

## §2 — Expected resolution, keyed by dimension

**Assertion types:** `HARD` = engine must output this value · `PENDING` = must surface as `pending_verification`/route-to-lawyer, not as fact · `HONESTY` = structural assertion on presence/confidence, not silence.

### Dimension → `nationality_set = [FR, SE, NO]`

| Expected output | Assertion | Info/Advice | Basis |
| --- | --- | --- | --- |
| **Immigration/residence (FR): `nothing_to_do`**, reason = "French national returning home; EU free movement independently via FR or SE; NO/EEA nationality redundant" | **HONESTY** (must be an explicit, confident `none` **with reason** — fails if immigration is merely absent/silent) | INFO | Dir. 2004/38; FR nationality |
| `selected_nationality = FR` (rule: destination's own > other EU/EEA > third-country) | **HARD** | INFO | Multi-nationality rule |
| `NO_nationality_effect = irrelevant` (never disadvantages; social-security analysis is nationality-agnostic) | **HARD** | INFO | Reg 883/2004 scope |

### Dimension → `posting_status = not_posted` + `employer = NO`

| Expected output | Assertion | Info/Advice | Basis |
| --- | --- | --- | --- |
| **Applicable social-security legislation = FRANCE** (lex loci laboris) | **HARD** | INFO | Reg 883/2004 Art. 11(3)(a) |
| **Exits `folketrygden`** despite Norwegian employer | **HARD** | INFO | Reg 883/2004 single-state |
| **A1 issued by FRANCE** (URSSAF) — *not* Norway | **HARD** | INFO | Art. 11(3)(a); EC Practical Guide |
| Norwegian employer owes **French employer contributions** (URSSAF SFE) **or** delegates to employee | **HARD** (duty exists) | route for application | Reg 987/2009 Art. 21 |
| Exact FR registration mechanics / delegation acceptance | **PENDING** (#4) | ROUTE | — |

### Dimension → `work_location_after_move = FR`

| Expected output | Assertion | Info/Advice | Basis |
| --- | --- | --- | --- |
| Reinforces **applicable legislation = FRANCE**; if he later works ≥25% in NO too, **Art. 13** re-test (residence-state vs employer-seat) | **HARD** | INFO | Reg 883/2004 Art. 13; 987/2009 Art. 16 |
| **Health: CPAM affiliation required**, carte vitale (re)issued; two routes exist — worker-affiliation (immediate) vs PUMa residence (~3-mo wait) | **HARD** (affiliation required; both routes exist) | INFO | service-public/ameli/URSSAF |
| Which route governs on day one (resides + works remotely simultaneously) | **PENDING** (#5) | ROUTE | — |

### Dimension → `tax_residency`

| Expected output | Assertion | Info/Advice | Basis |
| --- | --- | --- | --- |
| **FR:** becomes French tax resident (CGI art. 4 B) → worldwide income taxable | **HARD** | INFO | CGI art. 4 B; impots.gouv.fr |
| Report move abroad → deregister **folkeregisteret** (stay ≥6 months) | **HARD** | INFO | Skatteetaten |
| **NO tax residency does NOT end on physical move** — strict emigration test; up to **3 income years** if resident ≥10 yrs | **HARD** | INFO (rule); ADVICE (his status) | Skatteetaten — tax emigration |
| `D-number closure = N/A` (holds fødselsnummer, not a D-number) | **HARD** (N/A stated) | INFO | — |
| Active D-number/coverage closure step required? | **PENDING** (#3) | ROUTE | — |
| FR–NO treaty allocation of NO employment income during transition | **PENDING** (#1) | ROUTE | — |
| NO source-taxation of FR-performed employment income | **PENDING** (#2) | ROUTE | — |

---

## §3 — Honesty assertions (the anti-silence / anti-overclaim gates)

1. **Immigration confident-none:** engine output MUST contain an explicit immigration resolution of `nothing_to_do` with a populated `reason`. **Test FAILS if immigration is absent, null, or silent** — a correct answer of "none" must be *stated*, not implied by omission.
2. **Pending, not asserted:** each of the five §0 items MUST appear as `pending_verification` / route-to-lawyer AND MUST NOT appear anywhere as asserted substantive content. Two-sided assertion: *present-as-pending* **and** *absent-as-fact*.
3. **Advice-line routing:** every row tagged ADVICE/ROUTE (personalised determinations — his tax-residency status, his A1 determination, employer's specific duty, PUMa route) MUST route to a named regulated professional, not be answered in the product's own voice.
4. **Verified-as-hard:** every §2 `HARD` row MUST be asserted at its stated value (this is the "engine got the hard dimension right" proof — especially FR applicable legislation, A1-issued-by-France, folketrygden exit, foreign-employer duty, NO 3-year residency test).

---

## §4 — Conversion note

When a §0 item is closed by counsel, move it from `PENDING` to a new `HARD` row with its primary citation, and add the corresponding positive assertion. Until then, a passing fixture is one where: all `HARD` rows match, immigration is a stated `nothing_to_do`, and all five `PENDING` items resolve to route/pending — **not** to content.

_Content source: "Corridor Case Test — NO→FR" (Notion, under ReloPass HQ). Schema/serialization: Claude Code Task 2._
