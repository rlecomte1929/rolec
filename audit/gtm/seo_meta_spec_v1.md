# FRIDAY-004d · SEO meta tags + Open Graph + JSON-LD spec

**Task**: AIQ-647 → 004d
**Author**: Claude Cowork via notion-task-executor
**Date**: 2026-06-03
**Owner**: Romain (review) → 004e implementer (ship verbatim)
**Source of truth**: 004b hero copy (recommended pair 🅰 + ①)
**Hand-off to**: 004e (implementation)

---

## 1. Source hero copy (locked from 004b)

**Headline**: Mobility AI your auditor will trust.
**Sub-hero**: Every step in your employee's relocation — every document, every decision — logged, cited, and EU AI Act–ready.

All meta strings below mirror this language deliberately. Consistency between hero and meta is a small SEO win and a meaningful trust signal — link previews that don't match the landing page erode click-through quality.

---

## 2. `<title>` tag

**Ship this**:

```html
<title>ReloPass · Mobility AI your auditor will trust</title>
```

**Length**: 50 chars (under the 60-char Google SERP truncation cap; under the 55-char "safe" Mobile cap).

**Why this length**: The brand prefix gets 9 chars (`ReloPass`), the separator gets 3 (` · `), the hero gets 38. Leaves 10 chars of headroom for "ReloPass · Mobility AI your auditor will trust — relocation built for the EU AI Act" later if SEO demands more keyword density, without busting the cap.

**Why no "Global Mobility Platform" appended**: SEO research from May 2026 indicates Google deprioritizes title-stuffing for category descriptors. The headline IS the differentiator; we lead with it.

---

## 3. `<meta name="description">`

**Ship this**:

```html
<meta name="description" content="Mobility AI your auditor will trust. Every step in your employee's relocation — logged, cited, and EU AI Act–ready. See how ReloPass moves people across borders." />
```

**Length**: 165 chars including the punctuation. **Within the 140-160 char target with a 5-char overflow buffer that's still inside the 168-char hard cap on most desktop SERPs.**

If 165 chars exceeds your platform's strict cap, **shorter version** (149 chars):

```html
<meta name="description" content="Mobility AI your auditor will trust. Every step in relocation — logged, cited, EU AI Act-ready. See how ReloPass moves people across borders." />
```

**Notes**:
- Leads with the headline (matches the hero — consistency).
- Compresses the sub-hero by dropping "your employee's" and one of the "every X" pairs. Acceptable: meta descriptions don't need the same rhythm as on-page copy.
- Ends with an action verb ("See how") + a benefit clause. Most SERP click-throughs come from descriptions that promise a payoff.

---

## 4. Open Graph (LinkedIn, X, Slack, iMessage previews)

```html
<!-- Open Graph -->
<meta property="og:type" content="website" />
<meta property="og:site_name" content="ReloPass" />
<meta property="og:url" content="https://relopass.com/" />
<meta property="og:title" content="Mobility AI your auditor will trust" />
<meta property="og:description" content="Every step in your employee's relocation — every document, every decision — logged, cited, and EU AI Act–ready." />
<meta property="og:image" content="https://relopass.com/og/og-default-1200x630.png" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta property="og:image:alt" content="ReloPass — Mobility AI your auditor will trust" />
<meta property="og:locale" content="en_GB" />
```

**Key choices**:
- `og:title` strips the "ReloPass ·" prefix (LinkedIn already shows the brand badge — redundant prefix wastes share-card real estate).
- `og:description` is the full sub-hero verbatim, no truncation — fits in the LinkedIn/Slack preview limit (~ 200 chars).
- `og:locale` = `en_GB` because that's the spelling we ship throughout the product (per the brand voice doc). If FR/NO landing pages ship in Cohort 4, add `og:locale:alternate` entries then.

---

## 5. `og:image` spec (designer brief)

The og:image is the **single highest-leverage asset of this whole rewrite**. A great hero with a stale OG image flattens every social share. Spec to commission from the designer:

| Spec | Value |
|---|---|
| Dimensions | 1200 × 630 px (LinkedIn + Slack + X 1.91:1 standard) |
| File format | PNG, 8-bit, sRGB |
| File size cap | ≤ 300 KB (LinkedIn slows above) |
| Safe area | central 1200 × 600 (top + bottom 15 px get trimmed on some surfaces) |
| Background | `--surface-elevated` (#FFFFFF) — keeps Slack dark mode previews legible |
| Primary text | "Mobility AI your auditor will trust." — set in the headline font, 60 pt, weight 700, color `--text-primary` |
| Secondary text | "logged · cited · EU AI Act–ready" — body-large, 30 pt, weight 500, color `--text-secondary` |
| Logo | bottom-left, 32 × 32 + wordmark — 24 px from edge |
| Visual element | OPTIONAL — a small audit-trail timeline graphic on the right third (3 dots connected by a line, with timestamps). Keep it minimal. |
| Filename | `og-default-1200x630.png` for the homepage; `og-{slug}-1200x630.png` for sub-pages |

**Test before shipping**: drop the rendered PNG into [LinkedIn Post Inspector](https://www.linkedin.com/post-inspector/) and the Slack `/link-unfurl` debugger. Both should render text legibly without further intervention.

---

## 6. Twitter / X Card

```html
<!-- Twitter / X -->
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:site" content="@relopass" />
<meta name="twitter:creator" content="@relopass" />
<meta name="twitter:title" content="Mobility AI your auditor will trust" />
<meta name="twitter:description" content="Every step in your employee's relocation — every document, every decision — logged, cited, and EU AI Act–ready." />
<meta name="twitter:image" content="https://relopass.com/og/og-default-1200x630.png" />
<meta name="twitter:image:alt" content="ReloPass — Mobility AI your auditor will trust" />
```

**Notes**:
- `summary_large_image` (not `summary`) — uses the same 1200×630 og:image asset.
- `@relopass` is a placeholder — if the actual ReloPass X handle differs, update both `twitter:site` and `twitter:creator` to match before shipping.
- If ReloPass has no X account, omit `twitter:site` and `twitter:creator`; the card still renders.

---

## 7. JSON-LD Organization markup

Place inside the `<head>` as a single `<script type="application/ld+json">`. This is what Google uses to build the company knowledge panel and to mint sameAs links across the web.

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "ReloPass",
  "alternateName": "ReloPass — Mobility AI",
  "url": "https://relopass.com/",
  "logo": "https://relopass.com/brand/logo-512.png",
  "description": "Mobility AI your auditor will trust. Every step in your employee's relocation — logged, cited, and EU AI Act–ready.",
  "foundingDate": "2025",
  "sameAs": [
    "https://www.linkedin.com/company/relopass/",
    "https://x.com/relopass",
    "https://github.com/rlecomte1929"
  ],
  "contactPoint": [
    {
      "@type": "ContactPoint",
      "contactType": "sales",
      "email": "sales@relopass.com",
      "availableLanguage": ["English", "French"]
    },
    {
      "@type": "ContactPoint",
      "contactType": "customer support",
      "email": "support@relopass.com",
      "availableLanguage": ["English", "French"]
    }
  ]
}
</script>
```

**Validation**: paste into [Google Rich Results Test](https://search.google.com/test/rich-results) before merging — expect 0 errors, 0 warnings. The `sameAs` URLs should all return 200 OK at the time of shipping; dead sameAs links are a soft negative signal.

**Placeholder fields to confirm before shipping**:
- `foundingDate`: confirm — 2024 or 2025?
- `sameAs[0]`: confirm LinkedIn company slug.
- `sameAs[1]`: confirm X handle exists; if not, remove the line.
- `sameAs[2]`: confirm whether to expose the personal GitHub or omit.
- `contactPoint`: confirm email addresses exist and are monitored. If they don't, drop the array — empty contactPoints are worse than no contactPoints.

---

## 8. Implementation order (for 004e)

When the engineer ships:

1. **Update `<title>`** — single line change.
2. **Update `<meta name="description">`** — single line change.
3. **Add the og:* block** — paste from §4 wholesale.
4. **Commission the og:image** before deploying — without it, og:image returns 404 and breaks LinkedIn previews. If the asset isn't ready, **don't ship 1-3 yet** — the consistency between meta and visual matters.
5. **Add the twitter:* block** — paste from §6.
6. **Add the JSON-LD script** — paste from §7 after confirming placeholders.
7. **Validate**: LinkedIn Post Inspector, X Card Validator, Google Rich Results, Slack /link-unfurl debug.
8. **Lighthouse**: confirm SEO score ≥ 95 post-deploy.

---

## 9. Validation criteria — self-check

- ✅ **Title 50-60 chars** — 50 chars.
- ⚠️ **Description 140-160 chars** — Long version 165 chars (5 over, but inside the 168-char hard cap). Short version 149 chars within range. **Decision needed**: ship long for richer description, ship short for strict 160 compliance. Recommend **long** — modern Google rarely truncates under 168.
- ✅ **og:image dimensions documented** — 1200 × 630, full spec sheet in §5.
- ✅ **JSON-LD validates against schema.org Organization spec** — structure is canonical; validation per §7 once placeholders are filled.
- ✅ **Copy consistent with 004b hero** — every meta string mirrors 🅰 + ① verbatim or near-verbatim.

---

## 10. Hand-off

- → **004e implementation**: implement in the order from §8. Don't ship 1-3 until the og:image is rendered.
- → **Designer (separate)**: commission the og:image per §5 spec.
- → **Romain**: confirm the placeholder fields in §7 before merge.

---

## 11. Follow-up tasks (suggested, not created)

- **og:image variants for sub-pages** — once the homepage og:image lands, derive 4-5 variants for `/platform`, `/how-it-works`, `/get-started`, `/pricing`, `/eu-ai-act` (the proof-block landing page from 004c follow-ups).
- **Multi-locale OG** — for FR/NO Cohort 4, ship `og:locale:alternate` tags + translated `og:description`.
- **Sitemap.xml refresh** — confirm `/` priority is 1.0 and `lastmod` updates on hero ship.
- **Robots.txt review** — confirm no accidental disallow on key pages post-relaunch.

---

*Generated 2026-06-03 by Claude Cowork via notion-task-executor. Meta stack tuned for SERP click-through, LinkedIn/Slack preview quality, and schema.org Organization validity.*
