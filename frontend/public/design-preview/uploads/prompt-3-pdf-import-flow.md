# PROMPT 3 — HR Policy Builder: PDF Import & AI Extraction Flow

## Context

This prompt is part of the ReloPass HR Policy Builder feature. Prompts 1 & 2 cover the canvas builder for creating a policy from scratch or from a template. This prompt covers the **"Import from document"** path — when an HR Mobility lead has an existing relocation policy document (PDF or Word) and wants to import it into the ReloPass structured policy matrix.

The platform already has a backend pipeline for this. Your job is to design the **end-to-end HR-facing UI** for that pipeline, making it feel guided and trustworthy (not a black box).

---

## Tech stack & design system

- **Framework**: React 18 + TypeScript, Vite, TailwindCSS
- **Design system**: `frontend/src/components/antigravity/` — use Button, Card, Input, Badge, Alert, Modal, Drawer, Stepper components from this system.
- **Routing**: Modal overlay on top of the Policy Builder canvas at `/hr/policy-builder`. No separate route.
- **State**: Local component state within the import flow. On completion, the extracted data is merged into the canvas state (same state managed by `usePolicyConfigWorkspace` hook).

---

## Entry point

The import flow is triggered from two places:
1. The **mode switcher** in the Policy Builder header: clicking "Import from document" (Prompt 1)
2. The **empty state CTA**: "Import your existing policy" when no tiers exist

Both open a full-screen modal overlay (not a drawer — this flow needs space). The modal has an `X` close button in the top right. Closing at any step shows a confirmation: "Exit import? Your upload will be lost." with `Cancel` and `Exit` buttons.

---

## The 4-step flow

Show a horizontal stepper at the top of the modal with 4 steps. The stepper persists across all steps. Completed steps show a checkmark; the active step is highlighted; future steps are muted.

**Step 1 — Upload**
**Step 2 — Processing**
**Step 3 — Review extraction**
**Step 4 — Map to policy**

---

## Step 1 — Upload

### Layout
A clean centred upload area, ~600px wide, vertically centred in the modal.

### Upload dropzone
A dashed-border dropzone area (~300px tall). Inside:
- Icon: document with upward arrow
- Primary text: "Drop your policy document here"
- Secondary text: "Supports PDF and Word (.docx) — max 50MB"
- A `Browse files` button below the text

On drag-over, the dropzone border becomes solid and the background tints lightly (use the primary color at 5% opacity).

On file select, show a file preview card replacing the dropzone:
- Document icon (PDF or Word based on mime type)
- Filename + file size
- A `Remove` (×) button to start over

### Document type hint (below the dropzone)
A compact info box: "For best results, upload your full assignment policy document — not a summary sheet. The AI extracts benefit rules, caps, and conditions automatically."

### What happens to the file
The file is uploaded via `POST /policy-canonical/ingest` (multipart form). The response returns a `canonical_document_id`. Store this ID — it's used in all subsequent steps.

### CTA
A `Start extraction →` button (primary, full width below dropzone area). Disabled until a file is selected. Clicking uploads the file and advances to Step 2.

---

## Step 2 — Processing

### Layout
A centered status view — no form inputs. HR waits here while the backend pipeline runs.

### Status sequence (poll `GET /policy-canonical/documents/{canonical_document_id}` every 3 seconds)

Map `processing_status` values to human-readable stages with an animated progress indicator:

| `processing_status` | Display label | Progress |
|---|---|---|
| `uploaded` | "Uploading document…" | 10% |
| `text_extracted` | "Reading document text…" | 30% |
| `classified` | "Identifying policy type…" | 50% |
| `normalized` | "Extracting benefit rules…" | 75% |
| `review_required` | "Extraction complete — review needed" | 95% |
| `approved` / `failed` | handled below | 100% |

Show a linear progress bar at the top of the step area, and below it the current stage label with a spinner next to it.

Also show a **live log** (collapsible, collapsed by default): a monospace-style running list of what was detected so far. Each time the status advances, add a log line:
- "✓ Document classified as: Assignment Policy"
- "✓ Policy scope: Long-term assignment + Permanent transfer"
- "✓ Currency detected: EUR"
- "✓ 24 benefit rules extracted"

### On `failed` status
Show an error state: a red alert banner with the `extraction_error` message from the API. Below it: `Try again with a different file` (secondary button) + `Contact support` (ghost link).

### On `review_required` or `normalized`
Automatically advance to Step 3.

**Do not show a loading spinner for more than 90 seconds.** If polling exceeds 90 seconds without reaching `normalized` or `review_required`, show a timeout message: "This is taking longer than expected. We'll email you when extraction is complete." with a `Close and continue manually` button that exits the import flow.

---

## Step 3 — Review extraction

### Purpose
Show HR what the AI extracted before it's applied to the canvas. This is the trust-building step — HR sees every rule, can accept or reject individually.

### Layout
Split panel (two-column):
- **Left (~40%)**: The source document viewer — a simplified page-by-page text view of the extracted raw text, with extracted clauses highlighted in yellow. Clicking a highlighted clause scrolls the right panel to the matching extracted rule.
- **Right (~60%)**: The extracted benefit rules list, grouped by category (same 6 categories from Prompt 2).

### Right panel — extracted rules

Each extracted rule is shown as a card. Card anatomy:

```
[ Category badge ]    [ Confidence chip: 94% ]    [ ⚠ Review flag if confidence < 75% ]
Benefit: Host country housing cap
Value: Up to €2,500/month
Conditions: Long-term assignment only
Assignment types: long_term
                                         [ ✓ Accept ]  [ ✗ Reject ]  [ ✎ Edit ]
```

- **Accept**: Marks the rule as `review_status: accepted`. Card gets a green left border.
- **Reject**: Marks the rule as `review_status: rejected`. Card is greyed out / struck through.
- **Edit**: Opens a mini inline edit form on the card to correct the extracted value before accepting.

Show a sticky top bar on the right panel:
- "24 rules extracted · 18 accepted · 3 rejected · 3 pending"
- `Accept all` button (accepts all pending rules)
- `Accept high-confidence` button (accepts all rules with confidence ≥ 80%)

### Validation errors
If `GET /policy-canonical/documents/{canonical_document_id}/validation-errors` returns errors, show a collapsible warning section at the top of the right panel: "3 validation issues found" → expands to list them.

### Editing an extracted rule inline
When HR clicks Edit on a rule card, the card expands to show:
- Benefit key selector (dropdown of all 31 canonical keys + "Custom")
- Value type + amount inputs
- Frequency selector
- Conditions tags
- A `Save edit` button

The edited rule is saved via `PATCH /policy-canonical/documents/{canonical_document_id}` (if available) or stored in local state for Step 4.

### CTA
`Continue to mapping →` button (primary), enabled once at least 1 rule is accepted. Disabled if zero rules accepted. Below it: a small text link "Skip review — apply all extracted rules" for power users.

---

## Step 4 — Map to policy

### Purpose
Connect the reviewed extraction to the HR's tier structure. This is where the document becomes structured policy config rows on the canvas.

### Layout
A mapping interface — left column shows tiers (from the canvas, or a setup prompt if no tiers exist yet), right shows the accepted extracted rules being assigned to tiers.

### If no tiers exist yet
Show an inline mini-tier-creator: "You don't have any tiers yet. Add at least one tier to map rules to." → a compact version of the tier creation UI from Prompt 1 (name + 3 targeting axes). Minimum one tier required.

### Mapping panel
For each accepted extracted rule (right side), show a **tier assignment control**:

```
Host country housing cap  •  €2,500/month  •  Long-term
Assign to tier(s): [ Entry ]  [ Manager ✓ ]  [ Director ✓ ]  [ VP ✓ ]  [ C-Suite ✓ ]
                              Toggle buttons — multi-select
```

Smart defaults:
- If the rule has `assignment_type: long_term` only → auto-assign to tiers that include long_term
- If the rule has no conditions → assign to all tiers by default
- Rules flagged as dependent-only (`family_status: accompanied_family`) → auto-assign only to tiers that include accompanied_family

At the top, show: `Apply smart defaults` button that sets all assignments based on the logic above. HR can then adjust manually.

### Conflict detection
If a rule being mapped would overwrite an existing benefit value in the canvas:
- Show a warning on that rule card: "⚠ Tier 'Manager' already has a value for this benefit (€2,000/month). Importing will overwrite it."
- Offer: `Overwrite` | `Keep existing` | `Use higher value` per conflict.

### Summary before applying
At the bottom, a summary box:
- "About to apply 18 rules across 4 tiers"
- "3 conflicts will be overwritten"
- "6 rules will add new benefits not previously configured"

### CTA
`Apply to canvas →` button (primary). On click:
1. Merge all accepted+mapped rules into the draft state via `PUT /api/hr/policy-config/draft`
2. Close the modal
3. Show a success toast: "Policy imported — 18 rules applied across 4 tiers. Review and publish when ready."
4. The canvas now shows the imported rules in their respective tier cells, with a small `IMPORTED` badge on each affected cell.

---

## API connections for this prompt

| Purpose | Endpoint |
|---|---|
| Upload document | `POST /policy-canonical/ingest` (multipart) |
| Poll processing status | `GET /policy-canonical/documents/{id}` |
| Get extracted facts | `GET /policy-canonical/documents/{id}/facts` |
| Get validation errors | `GET /policy-canonical/documents/{id}/validation-errors` |
| Get audit summary | `GET /policy-canonical/documents/{id}/audit` |
| Apply extracted rules to draft | `PUT /api/hr/policy-config/draft` |

---

## UX constraints

- The flow must feel guided, not technical. Never expose internal status codes or database language.
- Confidence percentages should be shown as visual bars or chips, not raw numbers alone.
- The document viewer (Step 3, left panel) is read-only — HR cannot edit the source document.
- All step transitions must be animated (slide in from right, slide out to left).
- If HR leaves Step 3 mid-review and closes the modal, the extraction result is preserved server-side. Re-opening the import flow from the same document shows a "Resume previous import" prompt.
