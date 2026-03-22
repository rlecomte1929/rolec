# ReloPass UI copy style guide

Operational product copy for HR, employees, and admins. Prefer clarity over warmth.

## Tone

- **Direct:** say what the screen does or what the user should do next.
- **Active voice:** “Upload the policy” not “The policy can be uploaded.”
- **Plain language:** avoid consulting-speak and startup slogans.
- **Credible:** no fake enthusiasm, no assistant persona.

## Banned or avoid

- Em dashes (`—`) in any user-visible string.
- Filler transitions: “At this stage…”, “This will help you…”, “Once X is available…” unless legally or operationally required.
- Synthetic empathy (“We know this can be stressful”) unless a specific crisis UX warrants it.
- Empty reassurance (“You’re all set!”) without a concrete outcome.
- Parallel triples everywhere (“fast, simple, secure”) as decoration.
- Over-explaining what a button already says.
- **Readiness** and other abstract labels without a short concrete gloss nearby.

## Punctuation

- Use **periods** to end instructions where it helps scanning.
- Use **colons** after labels when introducing a value or list (`Destination: Berlin`).
- Prefer **hyphen** (`-`) for compound adjectives, not em dash.
- Avoid ornamental semicolons in marketing-style sentences.
- **Ellipsis** only in loading states (`Saving…`) where the pattern already exists.

## Empty, loading, and error states

- **Empty:** one sentence + optional action (“No assignments yet. Create one from the dashboard.”).
- **Loading:** short and specific (“Loading case”, “Checking assignments”).
- **Error:** what failed + what to try (“Could not save. Retry.”). No melodrama, no over-apology.

## Domain terms (keep precise)

Use consistently: **assignment**, **case**, **published policy**, **employee contact**, **compliance check**, **pending assignment**, **linked assignment**, **claim** (linking an assignment to an account). Do not mix “relocation” as a synonym for assignment in admin tools unless the UI already does so consistently.

## Buttons and nav

- Verb-first: **Save**, **Link assignment**, **Open case**, **Upload policy**.
- Match the real action (no “Continue” to a dead end).
- Same action, same label across HR / employee / admin where the action is the same.

## Before / after (style)

| Before | After |
|--------|--------|
| We’ll help you get started on your journey. | Choose an assignment to open your case. |
| Hang on — we’re loading your details… | Loading case details. |
| Here’s everything you need to know about… | [Delete; show the form.] |
| You can now proceed to the next step. | Continue. |

## Implementation

- Primary copy lives next to components unless the repo already has a shared constants module for that surface.
- When touching strings, fix nearby copy only if it is clearly user-visible and in the same block (avoid unrelated refactors).
