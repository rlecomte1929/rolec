# Why ReloPass is not ChatGPT

HR generalists ask this on every call. The honest answer:

**General-purpose models generate statistically plausible text.** They do not check the current Skatteetaten or UDI page, and they do not fail closed when a fact is missing. ReloPass **looks up** requirements from `requirement_items` that only serve when `review_status='approved'`. Each row can carry a citation, a verification stamp, and counsel attestation. That is a catalog, not a chat completion.

## The named miss: the D-number gap

A French national moving to Norway for a short assignment often needs a **D-number** (temporary ID). ReloPass’s FR→NO facts include: the person **cannot apply themselves** — an employer, the Tax Administration, a bank, or Nav requests it. Chat checklists routinely say “apply for a D-number on skatteetaten.no,” which is the wrong actor and the wrong week.

A second trap: **a D-number does not entitle you to a fastlege.** GP rights attach to residence registration (personnummer). A fluent “register with a GP after you arrive” paragraph is the week-seven ambush.

## What you are paying for

Lookup of a published, gated catalog — not a generated essay, and not a claim that ReloPass is certified under any AI Act status.

See also `docs/sales/hallucination_audit_FR_NO.md`.
