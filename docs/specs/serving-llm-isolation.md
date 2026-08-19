# Serving/LLM isolation — the generation/serving split as an enforced invariant

**Status:** enforced in CI (P0, Architecture — Notion AI Work Queue task "generation/serving split").

## The invariant

ReloPass's trust story ("why not just use ChatGPT?") depends on one architectural fact:

> A **served requirement** is produced only by the **deterministic engine over verified
> data** — rule engines reading curated, source-attributed catalog rows. The serving
> path must **never** call an LLM at request time. Transformers belong in the
> authoring/drafting/dependency-scoring layer, where their output is reviewed by a
> human **before** it becomes served data.

Until this change that split was a convention held up by code review. It is now a
build-failing invariant.

## Where the guardrail lives

| Piece | Path |
|---|---|
| Static check (import-graph analysis) | `scripts/check_serving_llm_isolation.py` |
| CI job (PR-blocking) | `serving-llm-isolation` in `.github/workflows/ci.yml` (runs when the `backend` path filter matches, same gating as `backend-tests`) |
| Test-suite enforcement (second wire) | `scripts/tests/test_check_serving_llm_isolation.py` — unit tests for the checker **plus** integration tests that assert the real repo graph is clean; discovered by the `backend-tests` pytest run |

Two independent CI paths (the dedicated job and pytest discovery) both fail the build
on a violation, so disabling one lane by accident does not silently drop the gate.

## What is protected

The **serving roots** — the deterministic requirement-serving engines — are registered
in `SERVING_ROOTS` inside the script:

- `backend.app.services.requirements_builder` — in-country relocation dossier
  (`requirement_items`, keyed destination × purpose)
- `backend.app.services.rules_engine` — deterministic applicability rules (STA
  waivers, nationality gating, anti-silence confirmations)
- `backend.app.services.requirement_evaluation_service` — the "deterministic MVP
  evaluator (no AI)" over the mobility-case graph
- `backend.app.services.immigration_requirement_service` — entry-visa checklist +
  risk flags, keyed corridor × visa_type
- `backend.app.services.hr_policy_resolver` — deterministic HR policy benefit
  resolution

When a new serving engine is added (anything whose output reaches a customer as a
requirement without human review in between), it must be added to `SERVING_ROOTS`.

## How it detects a violation

The script parses **every** `backend/**/*.py` file with `ast` and builds a
module-level import graph. Crucially it collects **all** import statements —
including lazy, function-local imports (`def f(): from .llm_client import …`), which
are this codebase's convention in `backend/db/*` and in `llm_client.py` itself — so a
lazy import cannot hide a path. It then BFS-walks from each serving root.

A module is an **LLM boundary** when either:

1. it is listed in `LLM_GATEWAY_MODULES` (`llm_client`, `policy_assistant_llm_client`,
   `llm_policy_extractor`, `policy_extractor`, `roadmap_generator`,
   `rce_entity_resolution_ai`, `embeddings`, `policy_assistant_embedder`,
   `mistral_ocr_client`), or
2. it imports an LLM vendor SDK anywhere in the file (`openai`, `anthropic`,
   `mistralai`, `google.generativeai`, `litellm`, … — see `LLM_SDK_MODULES`).

Rule 2 means a brand-new module that calls OpenAI directly is caught without anyone
remembering to list it; rule 1 means a gateway that switches to raw HTTP still trips
the guard.

## Exactly how it fails

- **exit 0** — invariant holds. Output: `[serving-llm-isolation] OK — 5 serving
  roots, N reachable modules, no path to an LLM gateway or SDK.`
- **exit 1** — violation. The job output names every offending path, e.g.:

  ```
  [serving-llm-isolation] FAIL — 1 serving path(s) can reach an LLM call:

    serving root backend.app.services.immigration_requirement_service
         backend.app.services.immigration_requirement_service
      -> backend.database
      -> backend.db.policies
      -> backend.app.services.llm_policy_extractor   [LLM gateway module]
  ```

  The fix is always to **break the import**: move the LLM use into the authoring
  layer and have it write reviewed rows the serving engine reads. Deleting the root
  or the boundary from the script's lists to make CI green is a review-rejectable
  change — there is deliberately **no allowlist**, because the invariant is "never",
  not "usually".
- **exit 2** — configuration error (also fails the job): a `SERVING_ROOTS` module no
  longer exists on disk (renamed/deleted), or a serving root failed to parse. This
  guarantees the guard can never silently pass while protecting nothing.

## Verified baseline

At the time this gate landed, the full transitive import closure of all five serving
roots (≈50 modules: the requirement/rules engines, `backend.app` crud/db/models/
schemas, `backend.database` and every `backend/db/*` mixin, and the deterministic
policy-template/intake helpers) was audited module-by-module and contains **no** LLM
gateway import and **no** LLM SDK import — the served answer is provably produced by
the deterministic engine over verified data. The guard exists to keep it that way.
