# Destination playbook — adding a corridor that alerts

How to add a destination so that its deadlines reach the person who has to meet
them. The goal of the model is that this is a **data and copy exercise, never a
code change**: author a corridor's step graph, tag the steps that carry a hard
legal window, run the evals.

> **Scope.** This covers deadline **alerting**. It does not cover corridor
> authoring itself (eligibility branches, documents, rules), which is the
> corridor YAML's existing job.

---

## 1. The model, in one pass

Four pieces, all of which already existed except the alert layer:

| Piece | Where | What it does |
|---|---|---|
| Corridor identity | `corridors/<ORIGIN_DEST>/corridor.yaml` | ISO codes, display name, pathways |
| Step graph | `corridors/<ORIGIN_DEST>/pathways/<ID>/v1.yaml` | the obligations, their prerequisites and statutory windows |
| Resolver | `backend/relopass/corridors/scheduler.py` | pure, `today` injected: `schedule_steps` → `compute_deadlines` → `classify_step_flags` |
| **Alert layer** | `backend/relopass/corridors/deadline_alerts.py` | which alerts are open today, the tag invariant, the copy |
| **Ledger** | `public.corridor_deadline_events` | exactly-once, keyed `case \| step \| due_date` |
| **Sweep** | `backend/app/services/corridor_deadline_sweep.py` | daily job; resolves cases through the resolver, never re-implements it |

A step opts into alerting by declaring a `deadline_trigger`. Absent, everything
behaves exactly as before — alerting is additive, and a corridor that declares
none is not broken, it is silent on purpose.

```yaml
- step_id: EEA_POLICE_REGISTRATION
  name: "EEA registration with the police (registreringsbevis)"
  responsible_party: EMPLOYEE
  expected_duration_days: 14
  prerequisite_step_ids: [TRAVEL_TO_NO]
  time_window_relative_to: TRAVEL_TO_NO
  time_window_min_days: 0
  time_window_max_days: 90
  cite: NO_UTL_110
  deadline_trigger:
    tag: "relopass-deadline-eea-police-registration-no"
    label: "EEA police registration in Norway"
    channel: "email"          # email | in_app
    lead_days: 30             # window opens this many days before the due date
    # jurisdiction: "NOR"     # only for EXIT obligations — see §3
```

---

## 2. The steps

### 1. Find the reuse before authoring anything

```bash
python -m backend.scripts.corridor_alert_metrics
```

The `gap` column lists every step that states a statutory window but declares no
trigger — a deadline the product already knows about and stays silent on. That
list is your work. If a corridor shows `windowed 0`, the authoring gap is
upstream: the step graph states no legal window, so there is nothing to alert on
yet and no amount of alert work will change that.

### 2. Tag the steps that carry a hard gate

Only steps whose authored text states a legal window. A trigger on a step with no
`time_window_relative_to` is **refused at load time** — `compute_deadlines` only
dates windowed steps, so such an alert could never fire, and shipping it would be
shipping silence.

**Naming.** `relopass-deadline-<step-slug>` while the step exists on exactly one
jurisdiction; `relopass-deadline-<step-slug>-<iso2-lower>` the moment the same
slug exists for a second jurisdiction whose rules differ.

### 3. Pick `lead_days` from the real-world lead time

Not from the window length. `lead_days` is "how much notice does this person need
to actually do it" — appointment availability, document turnaround, a vet visit.
A 90-day window with 30 days' lead says: you have three months, and we will speak
up when a third of it is left.

The one case to weight differently is an obligation whose miss is **unrecoverable
and invisible**. NO_FR's Folkeregister move-abroad report has an 8-day window and
5 days' lead — most of the window — because the failure surfaces months later as a
Norwegian tax assessment.

### 4. Write nothing; the copy writes itself

`render_alert` assembles the message from the step's own `name`, its window
derivation, and its `cite`. That is deliberate, and it is the guardrail: **copy
cannot state a legal fact the corridor did not already state.** If the message
reads thin, the fix is a better-authored step, not better-authored copy.

What the renderer guarantees:

- **Window phrasing, never "due today".** An alert fires across a window. "Due
  today" on day one of thirty is false, and teaches the reader to ignore the next.
- **Owner-aware.** An employee-owned step speaks to the reader; an HR-owned step
  says HR needs to act; an authority-owned step is a wait, not a task.

### 5. Run the evals

```bash
DATABASE_URL=sqlite:///./probe.db pytest \
  backend/tests/test_corridor_deadline_alerts.py \
  backend/tests/test_corridor_deadline_sweep.py -q
```

Add your destination's marker terms to `_MARKERS` in
`test_corridor_deadline_alerts.py` in the same commit. A destination absent from
that map is **unlinted**, and the leak test then passes by having nothing to
check — which is why `test_e7_marker_list_covers_every_jurisdiction_that_can_alert`
fails on an unlisted jurisdiction.

### 6. Dry-run the sweep before it can send anything

```bash
curl -X POST -H "Authorization: Bearer $CRON_SECRET" \
  -H 'Content-Type: application/json' -d '{"dry_run": true}' \
  https://api.relopass.com/api/crons/corridor-deadline-sweep
```

Read three things in the report: `would_fire` (right cases, right dates),
`skips` (every skipped case names its reason), and `alerts_in_window` against
`cases_scanned`. The GitHub Actions workflow defaults `workflow_dispatch` to
`dry_run: true` for this reason.

---

## 3. The invariant: one tag = one rule set

**A deadline tag maps to exactly one jurisdiction's rules.** Enforced in
`check_tag_destination_invariant`, tested repo-wide, not a convention.

This is not hypothetical. One dog-import tag was once bound to both the
France→Norway and Norway→France steps. Norway requires an anti-echinococcus
treatment 24–120 hours before arrival and bans six breeds; France requires no
tapeworm treatment and instead mandates I-CAD registration within 7 days of
arrival. No single message could state either rule set without being wrong for
half its readers, so the copy stayed uselessly vague until the tag was split.

**What the invariant permits — and this is the point of the model:** the same tag
across two corridors when it is genuinely the same rule. `ANMELDUNG` shares one
tag between `FR_DE` and `IN_DE` because it is one German obligation. One rule,
stated once, one message. Rising reuse ratio is the evidence the model is working.

**Exit obligations.** A step's jurisdiction defaults to its corridor's
destination, which is correct for every entry obligation. It is wrong for an exit
obligation owed to the origin: NO_FR's "report the move abroad to Folkeregisteret"
is a **Norwegian** rule inside a France-bound corridor. Declare
`jurisdiction: "NOR"` on such a trigger. Without it the rule is filed under
France, and a second Norway-exit corridor would read as a tag conflict between
two copies of the same rule.

### Splitting a tag that is already live

Change **only** `deadline_trigger.tag`. Never `step_id`.

`step_id` is part of the ledger key (`case | step | due_date`), so renaming it
re-fires history to everyone. `tag` selects copy only, so a split re-points
messages and fires nothing. Create the new tags, point each binding at the right
one, and delete the old tag's copy — with no binding referencing it, it can never
fire again.

---

## 4. Metrics

```bash
python -m backend.scripts.corridor_alert_metrics                  # repo only
DATABASE_URL=... python -m backend.scripts.corridor_alert_metrics --with-ledger
```

| Metric | Target |
|---|---|
| Corridors alerting / corridors authored | grows every cycle |
| `windowed_without_trigger` (the gap column) | 0 at corridor launch |
| Reuse ratio (tags bound to >1 corridor) | rising — proves "state once" works |
| Tag invariant violations | 0, enforced by the test suite |
| Duplicate event keys | 0, enforced by the ledger PK |
| Failures needing attention (`no_contact` / `error`) | reviewed, never silent |

Alert precision (fired outside the window) is enforced structurally rather than
measured: `due_alerts` is the only thing that decides, it is pure, and its four
boundary cases are pinned.

---

## 5. Known gaps

State these when reporting on the system; do not let them be discovered.

**No completion state.** Nothing records "has THIS case completed THIS corridor
step". `rce.steps` is corridor-scoped and shared across cases;
`case_requirement_checklist_state` is keyed on `requirement_items.id`, a different
taxonomy. **So the sweep alerts on schedule, not on progress**, and may remind
someone about something they have already done. `completed_step_ids` is threaded
through both sweep layers, so this becomes a one-line change when a completion
source exists.

**Coverage is narrow.** 9 of 90 authored steps across 10 corridors state a
statutory window. The alert layer is complete; the content it can alert on is
not. Widening it is corridor authoring, per the gap column.

**No oracle parity test.** The reference implementation resolves
`anchor + offset_weeks`; this engine resolves a prerequisite DAG with per-step
statutory windows. The models are not equivalent, so a byte-identical parity
suite is not achievable and would only pin one of them to the other's limits.

**Publishing is not legal assurance.** Nothing here may be presented as legal or
tax advice in ReloPass's own voice. Lawyer sign-off is a separate, tracked state
(`requirement_items.attestation_status`), unrelated to whether a corridor alerts.
