# Design System — ReloPass

> Source of truth for ReloPass's visual system. Created by `/design-consultation`
> in **infer + audit** mode (2026-06-14) — this documents the system **already
> shipped in the codebase**, it does not introduce a new one. Values are pulled
> from `frontend/tailwind.config.js`, `frontend/src/index.css`,
> `frontend/design/system/tokens.css`, and the `antigravity/` component library.
> Read this before any visual/UI change. In QA, flag code that doesn't match it.

## Product Context
- **What this is:** ReloPass — a cross-border employee relocation / mobility platform. Builds bespoke relocation roadmaps, immigration requirement tracking, policy management, and vendor coordination.
- **Who it's for:** three personas — **Employees** (relocation wizard + roadmap), **HR** (company command center, policy, cases), **Admin** (full CMS).
- **Space/industry:** global mobility / HR tech / relocation SaaS.
- **Project type:** React + TypeScript SPA (Vite + Tailwind) on a FastAPI backend.
- **The memorable thing:** *serious, trustworthy software for serious work* — calm navy structure with a single teal accent. No purple, no coral, no toy aesthetics.

## Aesthetic Direction
- **Direction:** clean enterprise SaaS — restrained, information-dense, structure-first.
- **Decoration level:** minimal — typography, whitespace, and a single accent carry the design. No gradients, blobs, or decorative texture.
- **Mood:** competent and calm. Navy conveys structure/trust; teal marks the few things that matter (links, primary actions, active state).
- **Hard rule (from the Branding Blueprint):** there is **no purple/violet/indigo** in the brand. Teal is used **sparingly** as the accent, not as a fill.

## Typography
- **UI / Body:** **Inter** (weights 300–800), loaded from Google Fonts in `src/index.css`. Fallback stack: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, …`.
- **Code / Data:** **JetBrains Mono** (mono stack: Fira Code, Cascadia Code, Consolas).
- **Scale (px / line-height):** xs 11/1.5 · sm 12/1.5 · base 14/1.6 · md 15/1.6 · lg, xl, 2xl per `relopass-design-tokens.json` → `typography.scale`.
- **Tailwind:** `fontFamily.sans = ['Inter', 'sans-serif']`.
- > Note: Inter is a deliberate, shipped choice (documented in both the tokens file and tokens.css). It is the established brand font — do not swap it without an explicit rebrand decision.

## Color
Two brand scales (50→900) + neutrals + semantic. **Light is default; dark via `[data-theme='dark']`.**

- **Primary — Navy** (`navy.*` in Tailwind; `--rp-color-primary-*`): structure, headings, primary buttons, dark inverted strips.
  - `800 = #0b2b43` (the canonical brand navy), 900 `#061a2a`, 700 `#133456`, 500 `#2d5f8e` … 50 `#f0f5fa`.
- **Accent — Teal** (`accent.*`; `--rp-color-secondary-*`): links, active state, sparing emphasis. **Not** a background fill.
  - `500 = #1f8e8b` (the canonical accent), 600 `#167572` (link hover), 700 `#105d5b` … 50 `#ebf7f6`.
- **Neutrals:** slate/gray. Body text `#1f2937` (`--rp-text-primary` / `neutral-800`); secondary `neutral-600`; tertiary/muted `neutral-500`; surfaces `neutral-0/50/100`.
- **Semantic** (Tailwind palette, as used across the app): success **emerald**, warning **amber**, error **rose/red**, info **blue**.
- **Surfaces:** page `--rp-surface` (white), subtle (`neutral-50`, alt rows), muted (`neutral-100`, disabled/raised), inverse (`navy-800`).
- **Muted-text contrast (WCAG AA) — A11Y-2 / AIQ-1211:** secondary/muted **text on light surfaces must be `text-slate-500` (≈4.6:1) or darker** — **never `text-slate-400` / `text-gray-400` / `*-300`** (≈2.6:1, fails AA's 4.5:1). On dark/navy/colored fills the lighter slate tokens are correct (light-on-dark). New code: `text-slate-500` for muted, `text-slate-600` for secondary body. (Migration of the ~490 existing light-surface usages is in progress, by feature area.)

## Spacing
- **Base unit:** 8px grid.
- **Density:** comfortable (forms/cards), compact for data tables.
- **Scale (px):** 0.5=4 · 1=8 · 1.5=12 · 2=16 · 2.5=20 · 3=24 · 4=32 · 5=40 · 6=48 · 8=64 · 10=80 · 12=96 · 16=128.
- **Marketing:** dedicated `--marketing-space-section / -block` tokens for the public site.

## Layout
- **Approach:** hybrid — `AppShell` (left sidebar + topbar + main) for the authenticated app; marketing-container tokens for the public site.
- **Shell:** `AppShell.tsx` → `PlatformShellSidebar` (240px, collapsible to 64px) + topbar + main. **Responsive:** below `md` (768px) the sidebar collapses into a slide-in drawer toggled by a hamburger (AIQ-1017, #708); desktop unchanged.
- **Max content width:** `max-w-7xl` for standard app pages; `marketing` container tokens for the site.

## Border Radius
- sm 4px · md 8px · lg 12px · xl 16px · 2xl 24px · full 9999px (`relopass-design-tokens.json` → `radius`).

## Motion
- **Approach:** minimal-functional. `fade-in` keyframe (`opacity + translateY(4px)`, 0.2s ease-out) is the standard entrance; transitions on hover/state only.

## Components — `frontend/src/components/antigravity/`
The in-house component library is the first stop for any UI. Use these before reaching for anything else:
**Alert · Badge · Button · Card · Checkbox · Container · FileInput · Input · LoadingButton · ProgressBar · Radio · Select · StalenessBadge.**
(`Button` variants: primary / secondary / outline / ghost.)

## ⚠️ Drift Audit (2026-06-14) — fix forward, don't reset
Inferred from the codebase. The *intended* system above is coherent; adoption has drifted:

1. **Hardcoded hex literals (~1,159 occurrences).** Components write `#0b2b43` / `#1f8e8b` as raw literals instead of using the `navy-*` / `accent-*` Tailwind classes or `--rp-*` CSS vars. `tokens.css` explicitly says "do not hardcode hex values in any component." → *Fix forward:* new code uses the token classes/vars; migrate literals opportunistically.
2. **Stale primitive palette in `relopass-design-tokens.json`.** Its raw `teal` (`#1DBFA2`) and `blue` (`#2B82D8`) primitives do **not** match the shipped navy/teal and appear only ~12× — a confusing second source. The *semantic* layer in `design/system/tokens.css` correctly overrides to `#0b2b43` / `#1f8e8b`. → *Fix:* reconcile the JSON primitives to the navy/accent scales (or delete the unused primitive block).
3. **CSS-var token pipeline barely adopted.** Only ~3 files consume the `--rp-*` / `--marketing-*` custom properties despite the full pipeline existing. → *Fix forward:* prefer tokens in new components; the pipeline is ready.

None of these change the *intended* look — navy `#0b2b43` + teal `#1f8e8b` + Inter is consistent across all three sources. The drift is in *how* it's referenced, not *what* it is.

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-14 | DESIGN.md created (infer + audit mode) | Documented the shipped system (navy `#0b2b43` + teal `#1f8e8b` + Inter + 8px grid + antigravity) as the formal source of truth; flagged 3 adoption drifts to fix forward. Created by `/design-consultation`. |
