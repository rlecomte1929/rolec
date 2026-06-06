# antigravity — in-house design-system primitives

Use these before reaching for raw HTML or another library. Colours come from the
ReloPass brand scales (see **Brand colours** below) — never hardcode off-brand
hues.

## Button

```tsx
import { Button } from '../components/antigravity/Button';

<Button variant="primary" onClick={handleSave}>Save</Button>
```

### Props

| Prop | Type | Default | Notes |
|---|---|---|---|
| `variant` | `'primary' \| 'secondary' \| 'outline' \| 'ghost'` | `'primary'` | `primary` = navy action, `secondary` = teal |
| `size` | `'sm' \| 'md' \| 'lg'` | `'md'` | |
| `disabled` | `boolean` | `false` | |
| `fullWidth` | `boolean` | `false` | |
| `type` | `'button' \| 'submit'` | `'button'` | |
| `onClick` | `(e: React.MouseEvent<HTMLButtonElement>) => void` | — | receives the event (e.g. `e.stopPropagation()`) |
| `title` | `string` | — | native tooltip |
| `aria-label` | `string` | — | accessible name for icon-only buttons |
| `unstyled` | `boolean` | `false` | see below |

### `unstyled`

Renders the semantic `<button>` with **no design-system styling** — only the
`className` you pass, plus `type` / `onClick` / `disabled` / `title` /
`aria-label`. Use it for bespoke or container-style buttons (selectable cards,
accordion rows, brand-coloured inline actions) whose layout the styled variants
would fight. It lets every clickable element route through this one primitive —
a single a11y/behaviour chokepoint, **no raw `<button>`** — without imposing a
visual opinion.

```tsx
<Button unstyled className="w-full flex items-center gap-3 px-4 py-3 text-left">
  …custom row content…
</Button>
```

Prefer a real `variant` whenever one fits. `unstyled` is for the cases where it
genuinely doesn't.

## Brand colours

Source of truth: `design/system/tokens.css`. Exposed as Tailwind scales in
`frontend/tailwind.config.js`:

- **`navy-*`** — primary (actions, structure). `navy-800` (`#0b2b43`) is the
  default primary action.
- **`accent-*`** — teal (links, accents, highlights). Used **sparingly** per the
  Branding Blueprint.

There is **no purple in the brand.** Do not use Tailwind's `violet` / `indigo` /
`purple` / `fuchsia` — they were swept out platform-wide. Use `navy-*` for
primary actions and `accent-*` for accents/links/highlights.
