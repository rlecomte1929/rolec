# ADS-4 — the 8 tagged destination URLs

**AIQ-1784.** Hand these to Otto verbatim. One URL per creative angle — angle-level
attribution is what tells us which angles to concentrate spend on at Gate 2. Without it,
week 2 is guesswork.

## Segment A → `/mobility-teams` (60% of budget)

| Angle | Card title | Destination URL |
|---|---|---|
| A1 | Relocation fails in the handoffs. | `https://relopass.com/mobility-teams?utm_source=chatgpt&utm_medium=cpc&utm_campaign=segment-a&utm_content=A1` |
| A2 | Relocation still runs on spreadsheets | `https://relopass.com/mobility-teams?utm_source=chatgpt&utm_medium=cpc&utm_campaign=segment-a&utm_content=A2` |
| A3 | Know which relocation is late, today | `https://relopass.com/mobility-teams?utm_source=chatgpt&utm_medium=cpc&utm_campaign=segment-a&utm_content=A3` |
| A4 | Vendor tasks tied to the case | `https://relopass.com/mobility-teams?utm_source=chatgpt&utm_medium=cpc&utm_campaign=segment-a&utm_content=A4` |
| A5 | Every relocation case, one status view | `https://relopass.com/mobility-teams?utm_source=chatgpt&utm_medium=cpc&utm_campaign=segment-a&utm_content=A5` |
| A6 | Start with one relocation case | `https://relopass.com/mobility-teams?utm_source=chatgpt&utm_medium=cpc&utm_campaign=segment-a&utm_content=A6` |

## Segment B → `/relocation-checklist` (40% of budget)

| Angle | Card title | Destination URL |
|---|---|---|
| B1 | Moving for work? Know what's required | `https://relopass.com/relocation-checklist?utm_source=chatgpt&utm_medium=cpc&utm_campaign=segment-b&utm_content=B1` |
| B2 | Your relocation, one clear checklist | `https://relopass.com/relocation-checklist?utm_source=chatgpt&utm_medium=cpc&utm_campaign=segment-b&utm_content=B2` |

---

## How to read the data back

Two sinks, and they store the angle **differently**. Know which you are querying.

**1. `analytics_events`** — the angle is its own field. `emit_event` stores `extra` as
JSON, so `utm_content` and `utm_medium` pass through untouched. Events carrying it:
`landing_page_view`, `landing_cta_click`, `landing_scroll_depth`, `landing_time_on_page`.
This is the right sink for *engagement per angle*, which is the only readable signal
early on, before conversions are dense enough to compare.

**2. `leads`** — the angle is **encoded into `utm_campaign` as `campaign|angle`**, e.g.
`segment-a|A3`. Split on `|`.

```sql
-- leads per angle
SELECT split_part(utm_campaign, '|', 1) AS campaign,
       split_part(utm_campaign, '|', 2) AS angle,
       count(*)
FROM leads
WHERE utm_source = 'chatgpt'
GROUP BY 1, 2 ORDER BY 3 DESC;
```

### Why encoded rather than its own column

`LeadCaptureIn` and the `leads` table carry `utm_source` and `utm_campaign` only. Adding
`utm_content` means a migration, and migrations here are applied **out-of-band with no
automated apply**. A merged-but-unapplied column would not *delay* angle attribution — it
would silently **lose** it, during exactly the two weeks the data decides where spend
goes. The encoding is lossless and live the day it merges.

Worth normalising into a real column later, once the campaign is not the thing depending
on it. Encoding lives in `campaignWithAngle()` —
`frontend/src/components/marketing/AdLeadForm.tsx` — pinned by
`__tests__/AdLeadForm.attribution.test.ts`.

## Before sending these to Otto

- [ ] **G1** — both URLs return prerendered HTML on the live domain. Until that is
      confirmed, these point at pages a crawler may see as blank. See the ADS-3 PR.
- [ ] **ADS-1 answer 5** — if ads must point at an Audos-hosted page instead, this whole
      table is moot and first-party attribution is lost. Settle that first.
- [ ] Confirm Otto preserves query strings on redirect — UTMs stripped in transit means no
      attribution at all, and it fails silently.
