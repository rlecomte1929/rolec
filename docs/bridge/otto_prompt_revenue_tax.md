# Otto prompt — ES→IE revenue/tax bundle (bus id 7)

Paste the block below into the Audos/Otto chat. If Otto's bus tools are unavailable in that
chat, attach `docs/bridge/context_bundle_revenue_tax.md` instead and delete Step 1.

---

Otto — a context bundle is waiting for you on the Claude bridge. Please delegate it to Cursor
and relay the result back. Do not attempt the generation yourself, and do not research
anything: everything Cursor needs is inside the bundle, and going outside it is a failure mode,
not a bonus.

**Step 1 — pull the bundle.**

POST `https://audos.com/api/hooks/execute/workspace-776786/otto-claude-bridge`
header `x-hook-secret: <workspace bridge secret>`
body `{"action":"pull","direction":"claude_to_otto"}`

Take row **id 7**. Its `payload.content_md` is the full bundle (45,542 bytes, markdown).
`payload.subtype` is `context_bundle`. **Do not `ack` it yet** — ack only after Cursor's
output is safely pushed back in Step 3.

**Step 2 — delegate to Cursor, verbatim.**

Hand Cursor the entire `content_md` as a file, not as pasted chat text. Then give it this
instruction:

> You are the generator in a Generator-Relay-Applier loop. The attached context bundle is a
> read-only snapshot of a production database you cannot reach and must not assume you can
> reach. A separate wired agent will dry-run your SQL inside a transaction, diff the result
> against your own prediction, and only then apply it.
>
> Do exactly what section 6 (TASK + OUTPUT CONTRACT) asks. Obey every rule in section 5. Return
> **only** the three delimited sections — `===ARTIFACT_SQL===`, `===PREDICTION_JSON===`,
> `===VERIFICATION_SQL===` — and nothing before, between or after them. No commentary, no
> explanation of your approach, no markdown fences around the sections.
>
> The five things most likely to make your output rejected, in the order they have bitten this
> loop before:
>
> 1. **Titles are the dedup key.** `(country_code, purpose, title)` upserts, and on collision
>    the incoming payload silently overwrites an existing row's description and citations. Your
>    7 titles must collide with none of the 52 live IRELAND titles in section 4, and with none
>    of each other. A one-character dash difference is a different row — check the exact
>    character.
> 2. **`pillar='EMPLOYMENT'` on all 7 rows.** Never write the literal `TAX`, even though two
>    facts carry it in `applies_to.pillar`. The column has no CHECK constraint, so a wrong
>    value is accepted and invents a pillar nothing renders.
> 3. **`review_status='pending'` explicitly on every row.** The column defaults to `'approved'`,
>    which would publish unreviewed immigration and tax content to real users on write.
> 4. **`description` is the fact's `fact_text` verbatim**, newlines and all. Several facts carry
>    a `Commonly believed: / Actually: / Action required:` block — that prose is the entire
>    value of this batch. Do not summarise, reflow, trim or "improve" it. Keep the year stamp in
>    "8% in 2026".
> 5. **Append-only.** `INSERT` only. No `UPDATE`, no `DELETE`, no `ON CONFLICT`, no
>    `BEGIN`/`COMMIT`/`ROLLBACK` — the applier supplies the transaction.
>
> Where your judgement is actually wanted: **the titles.** Five of the seven rows are facets of
> one mechanism — no RPN, so the emergency basis applies; 40% with no PPSN; a single person's
> rate band for four weeks; the week-5 cliff; 8% USC on top. Titled badly they read as five
> near-duplicates a reader skims past. Titled well they read as a sequence a person arriving in
> Dublin can act on, and the week-5 cliff — the expensive one — is legible as the real deadline
> rather than the first payslip. The live sibling rows use bare declarative sentences that state
> the rule (*"Irish tax residence turns on 183 days in a year, or 280 across two"*), not the
> `Ireland — …` prefix that marks immigration rows in this corpus.
>
> If any rule in section 5 makes the task impossible, say so in `assumptions` and emit no SQL
> for that row. Refusing is a correct outcome; a plausible row that overwrites reviewed work is
> not.

**Step 3 — relay the result back.**

Push Cursor's output to the bridge **unmodified** — do not reformat it, do not strip the
delimiters, do not summarise it:

POST same URL, same secret, body:

```json
{"action":"push","direction":"otto_to_claude","kind":"message","source":"otto",
 "payload":{"subtype":"cursor_artifact",
            "bundle_id":"context_bundle:ES-IE:thirdcountry:revenue_tax",
            "in_reply_to":7,
            "content":"<Cursor's three sections, verbatim>"}}
```

Then `{"action":"ack","ids":[7]}`.

**What happens next, so you know what you are handing off to:** Cowork verifies Cursor's chosen
titles against production for exact and fuzzy collisions; Claude Code dry-runs the SQL in a
`BEGIN … ROLLBACK`, checks the before/after count and an md5 fingerprint over the untouched
rows, and only then applies. The 7 rows land `review_status='pending'`, which means
`requirements_builder` does not serve them — no relocating employee sees any of this until a
human approves it at `/admin/countries`. Nothing you or Cursor does here can reach a mover.

**Expected result: exactly 7 rows**, all `IRELAND` / `employment` / `EMPLOYMENT` / `pending`.
If Cursor returns any other count without explaining it in `assumptions`, send it back rather
than relaying it.
