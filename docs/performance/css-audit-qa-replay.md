# CSS download audit — cold `/` vs recorder phantoms

**Date:** 2026-09-09  
**Branch:** `perf/css-font-audit`  
**Targets:** production `https://relopass.com/` and a local `vite build` + `vite preview` of the same tree.

## Question

Is production CSS fetched **twice** on a cold load of the marketing homepage?

## Methodology

A real DevTools Network panel with “Disable cache” was not available in this pass.
Verification used three independent views of the same assets:

1. **`curl` of production HTML** (no cookies, no JS). Parse `<link>` tags only.
2. **HTTP GET of the linked CSS** with `Accept-Encoding: identity | gzip | br`.
3. **Playwright** against live `https://relopass.com/` (Chromium, default cache).
4. **Local `vite build`** of `origin/main` then of this branch; compare `dist/assets/index-*.css` and `dist/index.html`.
5. **`vite preview` + `curl`** of the rebuilt `index.html` (stylesheet link count).

PostHog session recording was **not** started for a normal homepage visitor:
`analytics.ts` inits with `disable_session_recording: true`. Recording starts only
inside a test-drive session (`ensureTestDriveReplay`) or when the feedback widget
opens (`startBugReportRecording`). This audit did not enable either.

## Production cold `/` — one stylesheet

`GET https://relopass.com/` HTML (21 678 bytes) contains **exactly one** CSS link:

```html
<link rel="stylesheet" crossorigin href="/assets/index-BL_ZVnra.css">
```

No second `index-*.css`, no `<link rel="preload" as="style">` for CSS, no extra
`@import` of a second app bundle.

| Encoding | Bytes | Notes |
|---|---|---|
| identity (decoded) | 615 379 | Matches local `vite build` of `origin/main` (`index-BL_ZVnra.css`, 615.38 kB) |
| gzip | 129 399 | `Content-Encoding: gzip` |
| br | 130 145 | brotli slightly larger than gzip on this file (Render/CDN setting) |

**Initiator (clean document):** the HTML parser. Playwright request #5 for
`index-BL_ZVnra.css` has `referer: https://relopass.com/`.

Fonts actually downloaded on that first homepage paint were Inter **latin
400 / 500 / 600 / 700** only. Weights 300 and 800 were already in the CSS
`@font-face` list but were not fetched — nothing on `/` uses them.

## The second CSS request is a later document, not a duplicate

The same Playwright session later issued a second `GET` of `index-BL_ZVnra.css`
(request #36). Headers:

| Request | Referer | What happened |
|---|---|---|
| #5 | `https://relopass.com/` | First document (`/`) |
| #36 | `https://relopass.com/admin/` | Full navigation to `/admin/` (new HTML document), then client-side `/auth` |

That is a **second page load** of the SPA shell, not a double-fetch on a single
cold `/`. The homepage document itself requested the CSS once.

## When a recorder *does* re-fetch CSS (do not “fix”)

PostHog session replay (rrweb) snapshots stylesheets by **fetching them again**
so the replay player can reconstruct computed CSS. That second request’s
initiator is the recorder (`fetch` / `posthog-js`), not the document’s
`<link rel="stylesheet">`.

On ReloPass that path is off for ordinary visitors. It is on for:

- Test-drive sessions (`ensureTestDriveReplay` → `posthog.startSessionRecording()`)
- Bug-report recording (`startBugReportRecording`, consent-gated)

A QA Network waterfall captured **while a replay is running** (or while watching
a replay in the PostHog UI) will show `index-*.css` twice. That is the recorder,
not a product bug. There is no separate in-repo “QA recorder” that re-downloads
app CSS on a clean homepage.

**Conclusion:** double-fetch of `index-*.css` on a clean cold `/` is **not real**.
It is either a later navigation (observed) or a PostHog/rrweb snapshot (expected
when recording is on). Do not add cache-busting or split the entry CSS to “fix”
a phantom.

## Local preview (this branch)

`vite preview` of the rebuilt `dist/index.html` still has **one** stylesheet link:

```html
<link rel="stylesheet" crossorigin href="/assets/index-zdEo_Z4S.css">
```

Playwright against `http://127.0.0.1:4173/` recorded **one** CSS request
(`index-zdEo_Z4S.css`). No `countryFlagCode-*.css` on the homepage.

The marketing Landing chunk does not import `countryFlagCode` / flag-icons CSS.
Flag CSS is a separate async asset (`countryFlagCode-*.css`) loaded with
`CountryFlag`, not with `/`.

## Font trim (unused Inter 300 / 800)

`DESIGN.md` documents Inter 300–800. Grep of `frontend/src` (product + marketing)
found **no** `font-light`, `font-extralight`, `font-[300]`, `font-extrabold`, or
`font-[800]`. Inline `fontWeight` values in src are 400 / 500 / 600 / 700.

`font-weight: 800` appears only in standalone `frontend/public/design-preview/*.css`
(not the Vite CSS graph). Those pages do not use `@fontsource`.

**Change:** drop `@fontsource/inter/300.css` and `800.css` from `main.tsx`.
Kept 400 / 500 / 600 / 700. No custom unicode subset pipeline.
`font-display: swap` is unchanged (stock `@fontsource`).

| Build | `index-*.css` decoded | gzip (Vite) | `@font-face` count |
|---|---|---|---|
| `origin/main` baseline | 615 380 B (615.38 kB) | 130.01 kB | 60 (Inter 300–800 + JetBrains Mono) |
| Fonts only (300/800 dropped, flags still global) | 611 741 B | 129.59 kB | 46 |
| This branch (fonts + flag split) | **190 715 B (190.72 kB)** | **44.72 kB** | 46 (Inter 400–700 + JetBrains Mono) |

Font-only delta: **−3 639 bytes** decoded (−0.42 kB gzip). Small, as expected:
each unused weight was ~2.6 kB of `@font-face` CSS; the browser was already
skipping those woff2 files on `/`.

## Flag-icons: off the homepage CSS, still on `CountryFlag`

`flag-icons/css/flag-icons.min.css` is 28 KB source but Vite emits ~421 kB of
decoded CSS (542 `.fi-*` rules + hashed SVG `url()`s). On `main` that sat in the
**global** `index-*.css`, so every marketing visitor parsed ~601 kB of CSS.

A static `import 'flag-icons/...'` in `CountryFlag.tsx` is not enough by itself:
the antigravity barrel (`export { CountryFlag } from './CountryFlag'`) has no
`sideEffects: false`, so any `import { Button } from '.../antigravity'` evaluates
`CountryFlag.tsx` and pulls the sprite sheet into that graph.

Entry / marketing modules that imported the barrel (and therefore the flags)
were retargeted to leaf files:

- `ConsentBanner` (eager in `App.tsx`)
- `PublicHeader` / `PublicFooter` (Landing)
- `DebugAuth` (static import from `App.tsx` even though the route is DEV-only)
- `SetupAssistantPanel` (pulled in via `App.tsx` → `DebugAuth` → `AppShell`)

After that, Vite emits:

| Asset | Decoded | gzip | Loaded on cold `/`? |
|---|---|---|---|
| `index-*.css` | 190.72 kB | 44.72 kB | **Yes** (the only `<link rel="stylesheet">`) |
| `countryFlagCode-*.css` (flag-icons) | 421.03 kB | 84.68 kB | **No** — async, with `CountryFlag` |

Homepage CSS decoded: **615.38 kB → 190.72 kB (−424.66 kB, −69%)**.
Gzip: **130.01 kB → 44.72 kB (−85.29 kB)**.

`CountryFlag` still renders `fi fi-${code}` (ISO-2). The stylesheet is a
**static** import in that module, so HR/employee chunks that mount `CountryFlag`
load the CSS with the JS chunk (Vite `__vite__mapDeps` pairs
`countryFlagCode-*.js` + `countryFlagCode-*.css`). No post-paint `import()`;
no extra flash vs today’s global sheet.

Landing-*.js does not reference `countryFlagCode` or `.fi-`.

## Conclusion

| Claim | Verdict |
|---|---|
| Production `/` fetches `index-*.css` twice on a clean cold load | **False** (one `<link>`, one request; extras are navigation or replay) |
| Inter 300 / 800 unused in product + marketing | **True** — dropped from `main.tsx` |
| Flag-icons 601 kB global CSS is the cheap win | **True** — moved to `CountryFlag`; homepage no longer parses it |
