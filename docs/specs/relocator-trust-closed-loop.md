# Relocator-trust closed loop

**Status:** operator process. Not a Notion queue lane. Complements `docs/specs/feedback-closed-loop.md` (bug/spec → code). This loop asks: would a relocating adult, seeking the same advice they would get from a destination immigration officer, tax office, or school admissions desk, **trust what ReloPass just told them?**

**Personas (fixed):** Andrea (ES→IE, VE, CSEP) · Denis (NO→FR, FR, returning EEA) · Adrien (FR→SG, EP) · Abraham (US→EC, residence visa). Denise = Denis; Adrian = Adrien.

**Do not start a Work Queue card from this loop until a named relocator question has a verdict other than TRUSTED, and the fix is the smallest thing that would change that verdict.**

## Why this exists

The AI Work Queue measures tickets. A relocator measures:

- Did you tell me **what applies to me**?
- Did you tell me **what I must finish before I leave**?
- Did you put it in **order**, with **time**?
- Did you name the **trap I would miss** without an expert?
- Can I **forward a source** (URL, form, citation) to HR, a lawyer, or a school?
- If I tap every button, do I **act**, or only read?

Serving is deterministic and must never call an LLM at request time. That is necessary for trust and **not sufficient**. Trust also fails when we serve the **wrong audience**, an **unsourced** deadline, a **truncated** sentence, a **generic** 30-day lead time on a permit corridor, or a **firehose** of 200 true rows with no digest.

## The seven questions (ask as the person)

Walk **one persona at a time**. Stay in their nationality, family, origin/destination cities, and start date. Ask only what they would ask. Do not ask as an engineer.

| # | Relocator question | Specialist they are substituting |
|---|--------------------|----------------------------------|
| Q1 | What in this list is **mine**, given my passport and family? | Immigration caseworker |
| Q2 | What must I close **in the origin country** before I fly? | Origin tax / municipality / social security |
| Q3 | In **what order**, and **how many days** before start date? | Permit unit + employer mobility |
| Q4 | What would a non-expert **get wrong** (emergency tax, tourist ≠ work, EEA-not-EU customs, dual permit)? | Counsel / tax |
| Q5 | Where is the **official page or form** I send onward? | The authority itself |
| Q6 | What can I **do this week** (housing, school, bank, movers)? | Destination settlement / HR vendor |
| Q7 | If I complete intake and tap the plan, do I see **this** or a hollow generic scaffold? | Themselves, using the product |

## Verdicts (one per question per persona)

| Verdict | Meaning | Close the item? |
|---------|---------|-----------------|
| **TRUSTED** | Cited official host, correct nationality class, approved/served, not truncated, the person can act or honestly cannot-yet with a named next step | Yes, until the next content change |
| **INCOMPLETE** | True as far as it goes; origin, form, sequence, or vendor action missing | No — name the missing slice |
| **MISSING** | A relocator in this situation needs it; ReloPass is silent | No |
| **MISINFORM** | We assert the wrong person's rule, a false deadline, or a generic SLA that contradicts the pathway | No — treat as P0 for that persona |
| **UNTRUSTED** | Unsourced, `legalReviewPending` shown as settled law, empty intake producing “nothing to do”, or LLM-flavoured copy on the serving path | No |

Audience mixing (e.g. IRP-for-non-EEA rows on an **EEA** checklist without “does not apply to you”) is **MISINFORM** if the UI presents it as their task, otherwise **INCOMPLETE** (failed digest). Truncated labels (`…` mid-sentence) are **UNTRUSTED** until the full claim is shown.

## Surfaces to walk (buttons, in order)

Do not skip to requirements JSON and call the person served.

1. Login / assignment claim  
2. Intake (nationality, family, cities, dates) — if empty, **stop** and verdict Q7 UNTRUSTED  
3. Plan / roadmap (sequence, blocking, lead time)  
4. Requirements / checklist (nationality-scoped, traps, citations)  
5. Immigration Q&A / standing authority link  
6. Documents / dossier / forms  
7. Services → RFQ → quote  
8. Housing / neighbourhoods / settle-in  
9. What HR sees for the same case  

Public `GET /api/public/corridor-requirements` is the **content** check (what the platform is willing to say without a case). It is not Q7. Case APIs and the employee UI are Q7.

## Loop (closed)

```
persona + question
  → walk the surface (UI if credentials exist; else public API + say UI was not walked)
  → write verdict + evidence (HTTP, count, citation host, screenshot or quote)
  → if not TRUSTED: smallest fix (hydrate case | approve/reject fact | author pathway | fix serving leak | copy)
  → re-ask THE SAME question on THE SAME persona
  → only then TRUSTED
```

A merged GitHub PR or a Notion **Done** does **not** close the loop. The re-ask does.

## First live run — 2026-09-08 (API only, no employee login)

API `GET /health` → commit `96acf981` (evidence-quote ingest). Public corridor-requirements **HTTP 200** for all four corridors (the August 500 is gone).

| Persona | Public serve | Q1 audience | Q2 origin | Q3 sequence | Q4 traps | Q5 sources | Q6 action | Q7 case UI |
|---------|--------------|-------------|-----------|-------------|----------|------------|-----------|------------|
| Andrea VE | 206 rows, class `THIRD_COUNTRY` | INCOMPLETE (firehose; CSEP present) | MISSING (`origin_facts` empty) | not walked in UI | TRUSTED-leaning (emergency tax, IRP 90d in payload) | INCOMPLETE (6 empty `source`; labels truncated with `…`) | not walked | not walked (hydrate still required as of 23 Aug unless re-probed) |
| EEA control ES | 163 rows, class `EU_EEA` | INCOMPLETE / risk MISINFORM | MISSING | not walked | emergency tax present (good) | 6 Non-EEA/IRP rows still in the list | not walked | n/a |
| Denis FR | 21 rows, class `OWN_NATIONAL` | INCOMPLETE | INCOMPLETE (NO exit not in this public list) | no live case | INCOMPLETE | 5 unsourced incl. DPAE + tax domicile | not walked | no live case |
| Adrien FR | 16 rows, class `THIRD_COUNTRY` | INCOMPLETE | MISSING | **MISINFORM** if UI shows “30 days” | COMPASS/EP present | 4 unsourced; lead-time row has empty source | not walked | no EP pathway graph |
| Abraham US | 6 rows, class `THIRD_COUNTRY` | INCOMPLETE (thin) | MISSING | no pathway | tourist≠work **is served** (better than 30 Aug import note) | sourced `.gob.ec` | not walked | no pathway |

**Do not treat this table as a logged-in walk.** Next operator action: hydrate Andrea (confirm `VE`) and re-ask Q3 and Q7 on her plan screen.

## Non-goals

- Auto-merge.  
- Replacing counsel review. ReloPass remains indicative; the disclaimer on the public payload is correct and must stay.  
- Closing Work Queue P1s that do not change a verdict in this table.
