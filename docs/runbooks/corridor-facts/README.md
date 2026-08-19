# Corridor knowledge-pack promotion — operator runbook

Source-controlled decision record for the corridor-facts promotion work. Committed here
because until now it existed **only as files in a local Downloads folder**, and a decision
record that lives in Downloads is one `rm` away from being unreproducible.

## Why this directory exists rather than `tools/corridor-facts/`

The toolchain these documents operate on — `tools/corridor-facts/` with `gate.ts`,
`cli.ts`, `rows.ts`, `schema.ts`, `store.ts`, `official-sources.ts` and
`knowledge-pack-import.mjs` — **is not in this repository**. Verified on 2026-08-19 across
the working tree, every local and remote branch, the `audos-workspace-776786/` mirror, and
the rest of the machine. It lives in the Audos workspace, where Otto runs and where
WorkspaceDB is reachable.

So these are filed under `docs/runbooks/` deliberately: a neutral location that will not
collide with `tools/corridor-facts/` when the toolchain does land here.

`audos-workspace-776786/lib/dataSheetBuilder.ts` is the one named artifact that IS mirrored
in this repo.

## What is here

| File | What it is |
|---|---|
| `promotion-runbook-2026-08-19.md` | The full handoff: the 22 reviewed fact promotions with sources, publication dates and verbatim evidence quotes; the 4 preparation-item reclassifications; the dependency graph; expected per-corridor counts; and the acceptance criteria. Verbatim. |
| `source-verification-2026-08-15.md` | The provenance pass behind it — what was actually opened, what each official page publishes about its own revision, and the structural problem gate check (b) creates. Verbatim. |

Both are copied byte-identically from the authored originals. They are the **decision
record**, not the implementation.

## What has NOT been done

Nothing in the runbook's "Required implementation" section. Specifically absent:

- the machine-readable promotion manifest (`promotion-2026-08-19.json`)
- the deterministic promotion runner (`knowledge-pack-promote.mjs`)
- its tests
- the four dated gate reports and four guidance-lint reports
- any write to `requirement_facts` / `requirement_entities`

All of it depends either on the missing toolchain or on WorkspaceDB, which is not
reachable from this checkout. Writing a manifest and runner against an imagined schema
would have meant inventing the row shape, the column names and the `curated-import`
contract — the exact improvisation the runbook forbids, and worse than nothing for work
whose entire purpose is auditability.

## Source-of-truth order

Per the runbook, and worth restating because getting it backwards is how a stale copy wins:

1. the promotion manifest (once it exists), plus
2. the official source pages, reconciled against
3. the live verified row comparison in WorkspaceDB.

A downloaded Markdown copy — including these two files — is **an input for reconciliation,
not the runtime source of truth**. If a Downloads copy and the repository copy disagree,
compare both against live WorkspaceDB rather than silently preferring either.

## Status vocabulary

- `pending` — staged. Excluded by `gate.ts`, not rendered by `dataSheetBuilder.ts`, not
  gate-bearing. 100 pack facts sit here.
- `representative` — visible, but **awaiting counsel attestation**. Passing the
  deterministic gate is necessary and not sufficient.
- `active` — visible and provenance-complete.

No corridor is sellable on the strength of this work, and nothing here should be read as
saying otherwise.
