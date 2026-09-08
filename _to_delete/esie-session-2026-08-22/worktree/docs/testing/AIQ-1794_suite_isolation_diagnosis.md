# AIQ-1794 — why the suite is order-dependent, and why the prescribed fix cannot work

**Status: diagnosis, no code change.** Three attempts have now been made at this. All three
produced the same outcome. This records the measurements so the fourth starts from evidence
rather than from the ticket's premise, which is wrong.

Measured 2026-08-10 against `c96587bf`, with `DATABASE_URL=sqlite:///./ci_test.db` — the
same invocation CI uses.

## The baseline you must reproduce before believing anything

```
backend/tests + scripts/tests, -m "not integration and not policy_assistant_audit",
with ci.yml's four --ignore files

origin/main:  6043 passed, 84 skipped, 32 deselected, 9 xfailed, 0 failed
```

**`main` is green.** Any change that produces failures here is a regression, not a fix. That
sounds obvious; it is the step the previous two attempts appear to have skipped, because each
was evaluated against the module it was trying to unbreak rather than against the whole suite.

## What the ticket asks for, and why it cannot work

> "The `backend.database` mock/real swap owned by a single fixture with guaranteed restore;
> no module-import-time swaps remain."

Five modules pop the conftest MagicMock at module import and install the real
`backend.database`, with no restore:

| module | how it pops | binds as |
|---|---|---|
| `test_case_documents_flow.py` | module level | `import ... as dbmod` |
| `test_policy_config_matrix_propagation.py` | module level | `import ... as bdb` |
| `test_policy_cap_requests_schema_drift.py` | module level | `from ... import Database` |
| `test_e1b_extraction_persist.py` | module level, inside a guard | `from ... import Database` |
| `test_answer_provenance.py` | `setUpClass` (saves the mock — the well-behaved one) | — |

Note there is no shared convention in how they bind, so nothing can key off the alias.

### Attempt A — restore the mock per module import (`pytest_collectstart`)

**Does nothing.** Instrumented: the hook fires for every module and reports
`restored=False` in each case, because pytest imports **all** modules during collection and only
then runs any test. Whichever popper is imported last owns `sys.modules` for the entire run
phase. There is no hook between "last import" and "first test" that per-module restoration
could use.

### Attempt B — restore the mock before every test (`pytest_runtest_setup`)

**Breaks the poppers.** 5 failures in `test_case_documents_flow` alone
(`no such table: relocation_cases`). The reason matters: the poppers' app-code paths resolve
`backend.database` out of `sys.modules` at **call** time, not through the reference they bound
at import. So the module-level alias is not what keeps them working, and restoring the mock
under them removes the real engine mid-test.

This is the specific fact that kills the ticket's prescribed fix. "Own the swap in a fixture
with guaranteed restore" presumes restoring is safe. It is not.

### Attempt C — pin per test from an explicit `USES_REAL_DATABASE = True` on each popper

The most promising version, and it did fix the target: all five poppers pass standalone, and
the previously-failing popper→probe ordering passed 9/9.

**Then the full suite went from 0 failures to 10**, in three modules that the change never
touched:

```
3 FAILED backend/tests/test_ai_decision_logger.py
4 FAILED backend/tests/test_hr_assign_side_effects_nonblocking.py
3 FAILED backend/tests/test_providers_company_resolution.py
```

`test_providers_company_resolution` is **precisely** the module `ci.yml` records the previous
attempt as having broken:

> "each fixed the module it was breaking and shifted the collision to another
> (catalog_promotion → providers_company_resolution), which is the signature of the shared
> `db` singleton rather than of anything this file does wrong."

That comment was a hypothesis when it was written. Reproducing it from a different direction
makes it a finding.

## The actual root cause

**It is not the `sys.modules` entry. It is the shared `db` singleton.**

`backend/database.py` exposes a module-level `db` object whose engine the poppers mutate
(`dbmod._engine = eng`, `dbmod._is_sqlite = True`). Restoring the *name* in `sys.modules` does
not restore the *object's* engine, and every app module that did `from ...database import db`
at its own import time already holds that same mutated singleton — whichever engine it had at
that moment.

So the state that leaks is not "which module is at `sys.modules['backend.database']`". It is
"what `db._engine` currently points at, and which app modules captured `db` before or after it
was swapped". No amount of `sys.modules` bookkeeping reaches that, which is why all three
attempts relocate the failure instead of removing it.

## What would actually work

Roughly in order of cost:

1. **Make the engine per-test rather than per-process** — give `Database` an engine accessor
   that reads from a context variable, so a test can bind one without mutating a shared
   attribute. Removes the class of bug rather than a member of it.
2. **Run the poppers in a separate pytest process.** CI already does this for four other files
   (Call 2 in `ci.yml`). Cheap, honest, and it makes the isolation boundary explicit rather
   than implicit. It does not fix anything; it stops the leak crossing.
3. **Give each popper a real fixture that constructs its own `Database` instance** rather than
   mutating the global. Correct, but it is a rewrite of five test modules and their helpers.

Option 2 is the pragmatic next step and is a small change to `ci.yml`. Option 1 is the one that
lets the four quarantined files and the two `collect_ignore` entries come back.

## What NOT to do

- Do not "fix" this by evaluating against the module you are unbreaking. Run the full Call 1
  invocation and compare to 6043/0. Three attempts have now failed this way.
- Do not add a tripwire test asserting the mock is installed at test time. It fails on `main`
  today, because the invariant genuinely does not hold — shipping it green would require
  weakening it until it stopped checking.

## Scope note on the ticket

AIQ-1794's requirement 1 — the non-local `DATABASE_URL` guard — **already shipped** in
`a46faf91` (AIQ-1777, #1753) as `backend/conftest.py`, and it is the half that mattered for
safety: a unit run can no longer reach production. What remains is determinism, which is this
document. Requirements 2 and 3 as written should be replaced by one of the options above.
