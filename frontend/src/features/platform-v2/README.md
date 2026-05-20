# platform-v2

Home for the staged port of the Claude Design "ReloPass Platform" handoff.

The static prototype lives at [`frontend/public/design-preview/`](../../../public/design-preview/) and renders at `/design-preview`. This directory is where each prototype screen is reimplemented as a real React component against real ReloPass APIs.

## Operating rules

These are the rules I will not break without an explicit conversation:

1. **Side-by-side, never replace.** Every new screen lives next to its legacy version until proven. No deletions until the V2 has soaked.
2. **Flag-gated by default.** New code paths are off in prod until they're flipped for one account, then a cohort, then everyone.
3. **Atomic, revertable commits.** One conceptual change per commit. Every commit independently builds and type-checks.
4. **Three-gate validation.** Every commit: TS clean + build clean. Every PR: + tests + manual smoke. Every flag-flip: + dogfood on real data.
5. **No silent schema changes.** Migrations live in their own PRs, applied to a Supabase branch first, never bundled with UI work.
6. **Adapters are the only translation layer.** Real API ↔ prototype shape happens in one place per screen. Components never see raw API responses.
7. **Boring beats clever.** Copy a working pattern from an earlier screen rather than invent.
8. **Write down every "we decided X because Y"** in [`DECISIONS.md`](./DECISIONS.md).

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

- **Tier A (every commit)**: `tsc --noEmit` + `npm run build`
- **Tier B (before flipping flag for your account)**: + `vitest run` + manual smoke checklist + console clean + slow-3G pass + rate-limit check
- **Tier C (before flipping flag for anyone else)**: + 3–5 days of dogfood + side-by-side diff accepted + one teammate clicks through it on real data

## Stop conditions

Pause and reassess if:

- Two consecutive screens reveal the same schema gap → schema migration before continuing.
- An adapter grows >50 lines of branching → real API and prototype have diverged; reconcile one or the other.
- Type-check breaks on main → halt new work, root-cause, restore green.
- A flag flip causes a real incident → post-mortem in `DECISIONS.md`; recipe gets a new gate.
