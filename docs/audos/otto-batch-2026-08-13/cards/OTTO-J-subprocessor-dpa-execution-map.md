# OTTO-J — Sub-processor DPA execution map (how to actually sign each one)

**Unblocks:** AIQ-472 / PRIV-004 (P1, Blocked since 2026-06-09)
**Wave:** 1 · **Kind:** research (public documentation) · **Otto mode:** chat
**Paste from the rule down.**

## Why this card exists (operator context)

`docs/security/PRIV-004_sub-processor_register.md` is at v1.9 and is genuinely complete —
10 sub-processors, roles, regions, code evidence. Every single DPA status cell reads ⬜.
The task has been Blocked for two months with the note "the ONLY remaining work is human
legal DPA signing".

That framing is why it has not moved. The work is not *signing*; it is **finding out, ten
times over, whether signing is a checkbox in a dashboard, a click-through that is already
incorporated by reference, or a countersignature that takes a week and a legal contact.**
Nobody has a spare afternoon for ten vendors' legal pages. That afternoon is what this card
buys, and it converts a two-month block into a checklist Romain can work through.

Note the register is the source of truth, and it lists **ten**, not the six the Notion task
mentions. Card includes all ten.

---

## The card — paste from here

OTTO-J — sub-processor DPA execution map (public-documentation research; no browser QA)

WHY THIS CARD EXISTS
We are a small EU-facing company preparing for a pilot with an EU customer. Under GDPR
Art. 28 we need a Data Processing Agreement with every sub-processor, and under Art. 44-49
an adequate transfer mechanism for anything leaving the EEA. We know WHO our
sub-processors are. What we do not know is the MECHANICS: for each one, is the DPA already
incorporated into the terms we accepted, is it a self-serve form in the dashboard, or does
it need a countersigned document — and where exactly is the button.

You are producing an execution checklist, not legal advice. Do not interpret the law, do
not tell us whether we are compliant, and do not recommend a legal position. Quote what the
vendor publishes and give the click-path. We have counsel for the rest.

THE TEN SUB-PROCESSORS

1. Supabase — database, auth, storage (our project is in AWS eu-west-1, Ireland)
2. Render — frontend static site + backend web service
3. Cloudflare — DNS / CDN
4. OpenAI — LLM API (embeddings, extraction, Q&A)
5. Anthropic — LLM API (assistant, roadmap, entity resolution)
6. Mistral AI — Document AI OCR
7. Resend — transactional email
8. PostHog — product analytics (we are on the EU host, eu.i.posthog.com)
9. Geoapify — address autocomplete + geocoding
10. Stripe — payments (currently TEST mode only, no live keys)

FOR EACH, ANSWER EXACTLY THESE NINE

  a  dpa_mechanism — one of: incorporated_by_reference (the DPA is already part of the
     terms we accepted, no separate action), self_serve_click (a form or toggle in the
     dashboard we complete ourselves), request_countersignature (we must email/request and
     a human signs), enterprise_plan_only (not available on our plan), not_published.
  b  dpa_url — the canonical URL of the DPA document itself.
  c  click_path — if self_serve_click: the literal dashboard navigation, menu by menu.
     e.g. "Dashboard -> Organisation -> Settings -> Legal -> Data Processing Addendum ->
     Accept". If it is not self-serve, write the exact request route instead (the email
     address, the form URL, or the support path). Say NOT_APPLICABLE only when the
     mechanism is incorporated_by_reference.
  d  plan_gated — is the DPA or the EU-residency option restricted to a paid or enterprise
     tier? YES/NO/UNKNOWN, and which tier.
  e  transfer_mechanism — what the vendor says it relies on for EU->US transfers: SCCs
     (name the module/version if stated), EU-US Data Privacy Framework certification, UK
     addendum, or "no transfer — data stays in the EEA". Quote the sentence.
  f  dpf_certified — is the entity listed on the official Data Privacy Framework list at
     dataprivacyframework.gov? YES/NO/NOT_FOUND. Check the official list, not the vendor's
     own claim, and give the URL of the listing.
  g  subprocessor_list_url — the vendor's own published list of ITS sub-processors, and
     whether they offer a change-notification subscription (Art. 28(2) matters to us).
  h  eu_residency_option — can this vendor be configured to keep data in the EEA? State
     the concrete option (region, host, endpoint) and whether switching requires a new
     project/migration rather than a setting. For Render specifically: which regions exist,
     is Frankfurt available on which plan, and can an existing service be moved or must it
     be recreated.
  i  effort — one of: none, minutes, hours, days_external. Your honest read of what it
     takes us to get from ⬜ to signed.

Plus one line per vendor: gotcha — anything that will surprise a small team doing this for
the first time. Leave it EMPTY if there is none. Do not invent one.

HARD RULES ON FACTS
- Primary sources only: the vendor's own legal/trust/docs pages, and for f the official
  dataprivacyframework.gov list. Blog posts and forum answers only where you flag them
  [SECONDARY] and no primary source exists.
- Give the date you checked each vendor. Legal pages change.
- "Not documented" and "could not find" are real answers and we want them. A plausible
  guess about someone's legal terms is worse than a gap, because we will act on it.
- Do NOT state whether we are compliant, do NOT advise which mechanism to choose, and do
  NOT draft contract language. Mechanics and quotes only.
- Label every claim [VERIFIED] (you read it in the source) or [CLAIM] (you inferred it).

OUTPUT
Write ONE file: audos-workspace-776786/data/otto-j-dpa-map.json

A JSON array of ten objects, one per vendor, with exactly these keys:
vendor, checked_date, dpa_mechanism, dpa_url, click_path, plan_gated, plan_gated_tier,
transfer_mechanism, transfer_quote, dpf_certified, dpf_listing_url, subprocessor_list_url,
subprocessor_notification (true/false), eu_residency_option, eu_residency_requires_migration
(true/false), effort, gotcha, label.

Leave a string EMPTY rather than guessing. A missing value is fine; an invented URL is not,
because someone will click it.

BECAUSE YOU MAY NOT BE ABLE TO WRITE FILES FROM THIS THREAD
If you cannot, post the JSON array in this thread between the exact markers
OTTO-J-BEGIN and OTTO-J-END — valid JSON, no prose inside the markers — and NAME the single
narrow write task that would convert it to the path above. Do not start it. When I
authorise it, that task converts what is in the thread and NOTHING else: no re-checking, no
added vendor, no changed value. I will diff it.

REPORT BLOCK (in the thread, short)
OTTO-J — DPA EXECUTION MAP      DATE ____
Vendors mapped: __/10
By mechanism: incorporated __ | self_serve __ | countersignature __ | enterprise_only __ | not_published __
DPF-certified (official list): __/10
Already EU-resident, no action: ____
The 3 that will take longest, and why: ____
Anything you could not establish: ____

OUTPUT
- Write your findings to audos-workspace-776786/data/otto-j-dpa-map.json and sync. Post a
  short summary here, but the FILE is the deliverable. Structured data = CSV or JSON with a
  header row, not a markdown table and not prose. Leave a field EMPTY rather than guessing;
  a blank is fine, an invented value fails the batch.
- Then PROVE the file exists. Run `ls -la audos-workspace-776786/data/` and
  `wc -l audos-workspace-776786/data/otto-j-dpa-map.json` and paste the raw output verbatim
  as the last line of your reply. Do not describe the file, show it. If the write failed,
  say so plainly — a reported failure is worth far more to us than an unreported one.

RULES (non-negotiable)
- Spawn no sub-tasks. Create no draft tasks. Do not use Continue in Task. Answer in this
  thread and stop. If follow-on work is needed, NAME it in the report — do not start it.
  ONE exception, and only if the card asks for a file: if you cannot write files from this
  thread, say so and NAME the write task you would run. Do not start it — wait for me to
  authorise it explicitly. Never report a file as written when it was not.
- Record the deploy commit and PROCEED. Never stop on an unfamiliar commit. Stop only if
  /health itself fails (non-200, timeout, no commit field).
- Label every claim [VERIFIED] (you saw it) or [CLAIM] (you inferred it). You cannot see
  our repo, our database, our vendor dashboards or our CDN config — state no facts about
  them. In particular you cannot see which plan we are on; say what each tier offers and
  let us match it.
- A blocked path is a FINDING, not something to route around. "NONE" is a valid answer.
- Never touch campaign `insead-2026`. Never set OUTBOX_DISPATCH_CRON_ENABLED. Approve no
  supplier records. Apply no migrations. Delete nothing. Stripe test mode only.
- Stop before the budget cap. Never die mid-action.

## When it comes back (operator)

```bash
bash scripts/otto_recover.sh OTTO-J
python3 scripts/otto_verify.py --batch otto-batch.json --card OTTO-J
```

Reintegration is a documentation edit, not code: fold each vendor's `dpa_mechanism`,
`click_path` and `effort` into `docs/security/PRIV-004_sub-processor_register.md` as a new
column pair, bump to v2.0, and re-sort the register by `effort` so the `none` and `minutes`
rows can be cleared in one sitting. Then AIQ-472 stops being a two-month block and becomes
a checklist with a visible bottom.

Treat every URL as untrusted until clicked. Do not copy a `dpa_url` into the register
without opening it first — a dead legal link in a compliance register is worse than a blank.
