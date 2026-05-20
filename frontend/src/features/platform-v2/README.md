# platform-v2

Home for the staged port of the Claude Design "ReloPass Platform" handoff.

The static prototype lives at [`frontend/public/design-preview/`](../../../public/design-preview/) and renders at `/design-preview`. This directory is where each prototype screen is reimplemented as a real React component against real ReloPass APIs.

## Current operating mode

**Solo, pre-customer.** One developer is the only user of this codebase. The relaxed rules below are tuned for that reality. **When the product takes on real users, flip back to the "Production mode" column** (see [`DECISIONS.md`](./DECISIONS.md) for the trigger condition).

## Operating rules

| # | Rule | Solo mode (now) | Production mode (later) |
|---|---|---|---|
| 1 | **Side-by-side, never replace** | Optional — keep both implementations only when *you* want to compare in DevTools | Mandatory until V2 has soaked |
| 2 | **Flag-gated by default** | Keep — still useful for one-click V2/legacy toggle in your browser | Keep — required for cohort rollout |
| 3 | **Atomic, revertable commits** | Keep — future-you reading git log is the user being protected | Keep |
| 4 | **Type-check + build green before each commit** | Keep — the solo dev's only safety net against rot | Keep |
| 5 | **Adapter pattern as translation layer** | Keep — pure code quality concern, independent of users | Keep |
| 6 | **No silent schema changes** | Keep — but you can apply migrations directly (no branch dance) | Migrations land on a Supabase branch first |
| 7 | **Write down every "we decided X because Y"** | Keep — sole memory across sessions | Keep |
| 8 | **Dogfood / soak before flipping flag** | ~10 minutes of clicking around | 3–5 working days, then cohort, then everyone |
| 9 | **Tier C "teammate clicks through it"** | Drop — no teammate yet | Restore |
| 10 | **Commit speculative WIP often** | Yes — committed WIP is safer than untracked. `git revert` is free | Limit to feature branches |

## Per-screen recipe

Every ported screen follows this 10-step ritual. Each step is its own commit.

1. **Read** the prototype JSX + the existing legacy page. Write a comparison in `DECISIONS.md`.
2. **Identify the real endpoints** and stub the adapter file.
3. **Write the adapter** (`adapter.ts`) with type definitions for both sides + pure `toV2Shape(real)` function.
4. **Test the adapter** with one Vitest unit test using a frozen sample of real API output.
5. **Build the V2 component** — visual only, fed by hardcoded sample data.
6. **Wire the real query** — hook calls real endpoint, passes through adapter, feeds the component.
7. **Add the flag gate** — mount V2 at a sibling route (e.g. `/admin/companies-v2`) gated by `useV2Flag('companies')`.
8. **Solo-mode QA** — open legacy and V2 in two tabs. Click through. Capture discrepancies in `DECISIONS.md`. Fix or explicitly accept. *(Production mode: add a written checklist + 3–5 day soak.)*
9. **Promote** — once accepted, the V2 route replaces the legacy *behind the flag*. Flag on = V2, flag off = legacy.
10. **Cleanup** — delete legacy code once V2 has been the default for a session or two and nothing surprised you. *(Production mode: delete only after weeks of default-on with no rollbacks.)*

## Per-screen recipe

Every ported screen follows this 10-step ritual. Each step is its own commit.

1. **Read** the prototype JSX + the existing legacy page. Write a comparison in `DECISIONS.md`.
2. **Identify the real endpoints** and stub the adapter file.
3. **Write the adapter** (`adapter.ts`) with type definitions for both sides + pure `toV2Shape(real)` function.
4. **Test the adapter** with one Vitest unit test using a frozen sample of real API output.
5. **Build the V2 component** — visual only, fed by hardcoded sample data.
6. **Wire the real query** — hook calls real endpoint, passes through adapter, feeds the component.
7. **Add the flag gate** — mount V2 at a sibling route (e.g. `/admin/companies-v2`) gated by `useV2Flag('companies')`.
8. **Side-by-side QA** — open legacy and V2 in two tabs. Walk a written checklist. Capture discrepancies in `DECISIONS.md`. Fix or explicitly accept.
9. **Promote** — once accepted, the V2 route replaces the legacy *behind the flag*. Flag on = V2, flag off = legacy.
10. **Soak** — flag on for one account only for 3–5 working days. Then small cohort. Then default-on. Then (much later) delete legacy.

## Directory layout (per screen, once we start porting)

```
features/platform-v2/<screen>/
├── adapter.ts            # real API shape ↔ V2 shape, pure function
├── adapter.test.ts       # frozen fixture + adapter unit test
├── adapter.fixture.json  # captured real API response
├── useScreenData.ts      # the React Query (or current axios) hook
├── ScreenV2.tsx          # the component, uses antigravity primitives
└── index.ts              # barrel
```

## Validation gates

See the matching section in `DECISIONS.md` for the canonical checklist.

- **Tier A (every commit)**: `tsc --noEmit` + `npm run build` — kept in both modes.
- **Tier B (before flipping flag in your own browser)**: + `vitest run` if tests exist for the screen + click the golden path + console clean — kept in both modes.
- **Tier C (before declaring a screen "done")**: solo mode = ~10 minutes of clicking around on real data. Production mode = 3–5 days of dogfood + teammate sign-off + side-by-side diff captured here.

## Stop conditions

Pause and reassess if:

- Two consecutive screens reveal the same schema gap → schema migration before continuing.
- An adapter grows >50 lines of branching → real API and prototype have diverged; reconcile one or the other.
- Type-check breaks on main → halt new work, root-cause, restore green.
- A flag flip causes a real incident → post-mortem in `DECISIONS.md`; recipe gets a new gate.
