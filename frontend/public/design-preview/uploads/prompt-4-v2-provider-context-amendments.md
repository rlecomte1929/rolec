# PROMPT 4 (v2 amendments) — Provider Context: Mode-Aware Changes Only

## Context

This document amends Prompt 4 (Live Provider Context Sidebar) to align with the two-mode architecture. The original Prompt 4 remains valid — read it first. This document lists only the changes.

---

## Change 1 — No sidebar in Configure mode

**Original**: A full collapsible sidebar panel (~360px) accessible via a "Context" toggle in the page header.

**Updated**: The sidebar **does not appear in Configure mode**. In Configure mode, market context is delivered **inline inside the benefit card** (Prompt 2a, Section 4 — "Inline market context"). This keeps Configure mode clean and focused on one decision at a time.

The sidebar toggle in the header is only visible and functional when HR is in **Adjust mode**.

---

## Change 2 — Sidebar in Adjust mode is tier-aware

**Original**: Sidebar responds to whichever benefit the HR user is hovering or editing (generic awareness).

**Updated**: In Adjust mode, the sidebar is also **tier-aware**. When HR switches tier tabs (Manager / Director / VP), the sidebar's "Your current cap" reference line updates to show the value for the newly active tier — not a global average across tiers.

The destination country selector remains at the sidebar level (not per-tier), since destination country is a policy-level concern, not a tier concern.

---

## Change 3 — "Apply to canvas" → "Apply to this tier"

**Original**: The sidebar footer button reads "Apply median to canvas".

**Updated**: The button reads **"Apply median to [Tier name]"** — e.g. "Apply median to Manager". This applies the market median for the focused benefit to the active tier only. The dropdown variant still offers "Apply to all tiers".

---

## Change 4 — Inline context in Configure mode (summary)

For clarity, here is the full spec of the inline market context block that appears inside the Configure mode benefit card (Prompt 2a). This replaces the sidebar for that mode:

**Collapsed (one line, always visible below the value input):**
```
⬡ Market context · [Country]    Median: [€X]    [Show more ↓]
```

**Expanded:**
```
⬡ Market context · [Country selector]

  Platform median:  €1,800 one-time
  Market range:     €800 – €3,000 one-time
  Your value:       €1,500  (updates live as HR types)
  
  Coverage estimate:
  Your value covers ~60% of historical cases on ReloPass for 
  this benefit in [Country].

  [ Set to median (€1,800) ]
```

API calls for this inline block:
- `GET /api/hr/assignments/benefit-spend-summary?benefit_key={key}&destination_country={code}` for coverage estimate and spend range
- Supplier pricing range from `GET /api/suppliers/search?service_category={mapped_category}&destination_country={code}` for market range

Both calls are made lazily — only when the inline section is expanded, not on card load. Show a skeleton loader while fetching.

---

## No other changes to Prompt 4.

All three tabs (Market benchmarks, Active providers, Historical selections), the sidebar footer, and the API connection table remain as specified in the original Prompt 4. They apply exclusively to Adjust mode.
