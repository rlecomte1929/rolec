# Phase 1 — Claude Code Instructions
April 2026 | Source: Brand Audit + Branding Blueprint V02

Three content files have already been updated in this folder:
- `landingContent.ts` (homepage)
- `platformContent.ts` (/platform)
- `accessContent.ts` (/get-started)

Copy them to the correct locations in the frontend repo, then apply the
additional changes below for /why, /how-it-works, and site-wide templates.

---

## STEP 1 — Copy updated content files to the repo

```bash
cp landingContent.ts  frontend/src/pages/landing/landingContent.ts
cp platformContent.ts frontend/src/pages/public/platformContent.ts
cp accessContent.ts   frontend/src/pages/public/accessContent.ts
```

---

## STEP 2 — Wire new fields into components (landingContent.ts)

Three new fields were added. The components need to render them.

### 2a. hero.brandPromise
Find the hero component for the landing page.
Add this line below the subheadline and above the CTA buttons:

```tsx
{landingContent.hero.brandPromise && (
  <p className="brand-promise">{landingContent.hero.brandPromise}</p>
)}
```

Style: same font size as subheadline, left border in teal (matching the
eyebrow colour), slight padding-left. NOT larger than the subheadline.
Example CSS:
```css
.brand-promise {
  border-left: 3px solid var(--color-teal, #1a9e8f);
  padding-left: 10px;
  font-weight: 500;
  margin-top: 8px;
  margin-bottom: 8px;
}
```

### 2b. hero.trustMicrocopy (landing, platform, access)
Add below the primary CTA button on each hero:

```tsx
{hero.trustMicrocopy && (
  <p className="trust-microcopy">{hero.trustMicrocopy}</p>
)}
```

Style: muted grey, 11-12px, centered under the button.

### 2c. solution.sectionHeader
Add above the solution section title:

```tsx
{landingContent.solution.sectionHeader && (
  <p className="section-eyebrow">{landingContent.solution.sectionHeader}</p>
)}
```

Style: same as page eyebrow (teal, tracked caps, small).

### 2d. trust.categoryBoundary
Add at the TOP of the trust/differentiation section, before trust.title:

```tsx
{landingContent.trust.categoryBoundary && (
  <div className="category-boundary">
    <p className="category-positive">
      {landingContent.trust.categoryBoundary.positive}
    </p>
    {landingContent.trust.categoryBoundary.negatives.map((line) => (
      <p key={line} className="category-negative">{line}</p>
    ))}
  </div>
)}
```

Style: positive line in full weight (font-weight: 700), negatives in
medium weight or muted colour. No bullet points.

### 2e. accessContent.closingCta
Add below the three option cards on the /get-started page:

```tsx
{accessContent.closingCta && (
  <p className="closing-cta">{accessContent.closingCta}</p>
)}
```

---

## STEP 3 — Site-wide eyebrow template

The eyebrow "For HR and mobility teams" is now in the content for
/platform and /get-started (it was already on /). Add it to the hero
template so it renders on every page that has it in its content file.

Find the hero/page-header component. Add:

```tsx
{hero.eyebrow && (
  <p className="hero-eyebrow">{hero.eyebrow}</p>
)}
```

Style (match existing homepage eyebrow exactly):
- Teal colour
- 12px
- Tracked caps (letter-spacing: 0.08-0.1em)
- font-weight: 700
- Positioned above the H1

---

## STEP 4 — /why page changes

Find the why page content file (likely `whyContent.ts` or inline in the
component). Apply these changes:

### 4a. Add eyebrow to hero
Add `eyebrow: 'For HR and mobility teams'` to the hero object (same
pattern as other pages above).

### 4b. Add trust microcopy under "Book a demo" CTA
Add `trustMicrocopy: '30-minute walkthrough. No commitment.'` to the
hero object and wire it into the component.

### 4c. "What is different" section — add category boundary block
At the TOP of this section, before the existing "Case at the center" and
"Less chasing" columns, add:

```
One system of record for every cross-border relocation.
Not a relocation agency.
Not a vendor marketplace.
Not an HR add-on.
```

The positive line first (full weight), then the three negatives (medium
weight or muted). Keep the existing two columns below unchanged.

### 4d. Dark closing section — replace anchor copy
Current: "Try this on one case."
Replace with: "Every relocation case is visible, compliant, on-time."

Keep the "Book a demo" button below it unchanged.

Style: white text on dark background. This is the brand promise — render
it at a larger size than body copy but smaller than the page H1.

### 4e. Final CTA section — replace headline
Current: "See why teams switch"
Replace with: "Tell us how your relocations run today."

Keep the "Book a demo", "How it works", and "Sign in" options unchanged.

---

## STEP 5 — /how-it-works page changes

Find the how-it-works page content file (likely `howItWorksContent.ts`
or inline in the component). Apply these changes:

### 5a. Add eyebrow to hero
Add `eyebrow: 'For HR and mobility teams'` (same pattern).

### 5b. Add trust microcopy under "Book a demo" CTA
Add `trustMicrocopy: '30-minute walkthrough. No commitment.'`

### 5c. Subhead only — replace
Current: "See done work, gaps, and the next action in one place."
Replace with: "See completed steps, open blockers, and the next action on every case."

DO NOT change the H1 ("Clear case view end to end"). That change is
blocked pending a structural decision on page role (Phase 3).

---

## STEP 6 — Verify the copy guardrails are not violated

Before committing, grep for these strings across all changed files.
None should appear in any copy-facing string:

```bash
grep -r "glue work\|end-to-end\|end to end\|seamless\|leverage\|robust\|comprehensive\|transformative\|innovative" \
  frontend/src/pages/landing/ \
  frontend/src/pages/public/ \
  --include="*.ts" --include="*.tsx"
```

Also check for em dashes in copy strings:
```bash
grep -r " — " \
  frontend/src/pages/landing/ \
  frontend/src/pages/public/ \
  --include="*.ts" --include="*.tsx"
```

Both should return empty. If either finds a match, fix before committing.

---

## STEP 7 — Local QA checklist

```bash
cd frontend && npm run dev
```

- [ ] `/` — H1 reads "The operating layer for cross-border relocation."
- [ ] `/` — Brand promise visible above CTAs with teal left border
- [ ] `/` — "30-minute walkthrough. No commitment." below "Book a demo"
- [ ] `/` — Problem section reads "Relocation still runs on emails and spreadsheets."
- [ ] `/` — Solution section has "Global mobility. Structured." header
- [ ] `/` — Category boundary block visible in trust section
- [ ] `/platform` — H1 reads "Every relocation on one system of record."
- [ ] `/platform` — Eyebrow present above H1
- [ ] `/platform` — "30-minute walkthrough. No commitment." below "Book a demo"
- [ ] `/platform` — Section 2 reads "Case-based relocation system" (not "workspace")
- [ ] `/why` — H1 unchanged ("Relocation fails in the handoffs")
- [ ] `/why` — Eyebrow present
- [ ] `/why` — Category boundary block at top of "What is different" section
- [ ] `/why` — Dark section reads "Every relocation case is visible, compliant, on-time."
- [ ] `/why` — Final CTA reads "Tell us how your relocations run today."
- [ ] `/how-it-works` — Eyebrow present
- [ ] `/how-it-works` — Subhead reads "See completed steps, open blockers, and the next action on every case."
- [ ] `/get-started` — H1 reads "Three ways in."
- [ ] `/get-started` — Eyebrow present
- [ ] `/get-started` — Card 1 description updated
- [ ] `/get-started` — Closing CTA "Structure how you run relocation. Start with one case." visible below cards
- [ ] No console errors on any page

---

## Rollback

```bash
git checkout HEAD -- \
  frontend/src/pages/landing/landingContent.ts \
  frontend/src/pages/public/platformContent.ts \
  frontend/src/pages/public/accessContent.ts
```

For /why and /how-it-works, revert the component or content file edits
in git as normal.
