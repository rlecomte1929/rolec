# Test-Drive videos — production plan + scripts (TD-11)

**Owner:** Romain · **Status:** Scripts ready for production · 2026-07-04
**Reads with:** `test-drive-copy.md` (page + survey), `test-drive-build-plan.md §4` (pipeline), `test-drive-execution-plan.md` TD-11.
**Decisions locked:** 3 clips (Start / HR / Employee) · show workflow, protect outputs · captions **+ AI voiceover** · pure operator how-to tone.

---

## 1. Goals (what these clips must and must not do)

- **Primary — orientation, not promotion.** Get a tester through the HR and Employee tasks with minimal friction so completion rate (the headline number) stays high. These are guides.
- **Secondary — quiet competence.** Prospects watch too; the clips should read calm and professional. The moment they feel like an ad, the tester disengages.
- **Mirror the task.** Built on **blank profiles** filled live, so the video shows exactly what the tester is about to do.
- **Protect the moat.** Reveal *how to operate*, not *how it decides* (see §3).

---

## 2. Global format spec

| Attribute | Value |
|-----------|-------|
| Clips | 3 — `start.mp4`, `hr.mp4`, `employee.mp4` |
| Length | Clip 0 ~45s · Clip 1 ~75s · Clip 2 ~90s |
| Orientation | Landscape 1280×720 (desktop web app; embeds on `/test-drive`) |
| Narration | On-screen captions **+ AI voiceover** (brand voice, §6) |
| Tone | Pure operator how-to — calm, "do this, then this" |
| On-screen corridor | A **Tier-A** corridor as the visual example (default **Paris → Oslo**); voiceover stays corridor-agnostic ("your assigned corridor") since testers are assigned different ones |
| Data | Blank/synthetic seeded accounts; no real names, suppliers, or prices |
| Watermark | Subtle "ReloPass · Confidential beta" lower-corner |
| Hosting | `frontend/public/test-drive/` — embedded only on the gated `/test-drive`; **noindex**, never posted publicly |
| Delivery | Also copy the final mp4s to **`~/Downloads/relopass-test-drive/`** so Romain has local copies to review/share |

---

## 3. Anti-copy rules (the on-screen checklist)

The workflow is table-stakes; the moat is the *logic of the outputs*. Show the first fully, protect the second. Apply to every clip:

- **Show freely:** navigation, buttons, the shape of the flow, empty→filled forms, where to click, the two-login switch.
- **Protect (≤2s on screen, no zoom/slow-pan, generic/blank data):** immigration guidance text, the requirement/rules engine, recommendation **rationale or scoring**, roadmap **step content**, policy-resolution output.
- **Never show:** real supplier names/prices (use synthetic catalog or mask), the actual depth of a corridor's knowledge base, any Tier-B corridor.
- **Framing:** feature Paris→Oslo (Tier-A) so nothing looks thin; keep voiceover generic so no clip is tied to one corridor's content.
- **Distribution control:** clips live behind the gated page only; add `noindex`; don't upload to public YouTube/social.

> Rule of thumb: if a frame would help a competitor understand *how ReloPass reaches an answer*, cut it or genericize it. If it only shows *which button a tester clicks*, keep it.

---

## 4. The three clips — beat-by-beat scripts

Each beat = one on-screen action, its caption, and its voiceover line (~2–4s, one idea). "Playwright" column = the automation step for TD-11. 🛡 = apply an anti-copy rule.

### Clip 0 — Getting started (~45s)
*Purpose: the two logins and how to switch. Defuses the biggest UX risk.*

| # | On-screen (Playwright) | Caption | Voiceover |
|---|------------------------|---------|-----------|
| 1 | Load `/test-drive`, hero in view | Start here | Everything you need is on one page. |
| 2 | Type first name → click **Start** | Enter your first name | Enter your first name. We create two accounts for you. |
| 3 | Two credential cards render (HR + Employee) | Two logins: HR and Employee | You get two logins — one for HR, one for the employee. You'll use both. |
| 4 | Copy HR login → open sign-in → submit | Sign in as HR first | Start as HR. Copy the HR login and sign in. |
| 5 | Highlight the profile-switch / sign-out control | Switch here to become the Employee | When HR's done, come back and switch to the employee login. |
| 6 | End card | Next: the HR side | Let's start with the HR side. |

### Clip 1 — The HR side (~75s)
*Purpose: create company, assign a case on the corridor, hand off.*

| # | On-screen (Playwright) | Caption | Voiceover |
|---|------------------------|---------|-----------|
| 1 | HR command center, empty state | Your HR command center | As HR, this is your command center. It starts empty. |
| 2 | Create company (name + size) | Create your company | First, create your company — just a name and size. |
| 3 | Start a case → add employee (EMP account name) | Add the relocating employee | Add the employee who's relocating — use your Employee login's name. |
| 4 | Set origin → destination | Set the route: origin → destination | Set where they're moving from and to. That's the corridor. |
| 5 | 🛡 Configure package/policy — **brief, generic view, ≤2s** | Set the relocation package | Choose what the package covers. |
| 6 | Assign / hand off → confirmation | Hand the case to the employee | Then hand the case to the employee. |
| 7 | End card | Your turn: create a company, assign a case | Now do the same — create a company and hand off a case. |

### Clip 2 — The Employee side (~90s)
*Purpose: accept, intake, roadmap, vendor + cost, mark complete.*

| # | On-screen (Playwright) | Caption | Voiceover |
|---|------------------------|---------|-----------|
| 1 | Sign in as Employee → pending case visible | Sign in as the Employee | Now switch to the employee. You'll see the case HR assigned. |
| 2 | Accept the case | Accept your case | Accept it to begin. |
| 3 | 🛡 Intake — answer **2–3 generic** questions (don't reveal full set) | Complete a short intake | Answer a few questions about your move. |
| 4 | 🛡 Roadmap renders — **glance only, no zoom** | Your roadmap appears | Your roadmap builds from your answers. |
| 5 | 🛡 Open services → vendor list — **no scoring/rationale on screen** | Pick a service and a vendor | Open your services and choose a vendor. |
| 6 | Select a vendor → estimated cost shows (synthetic) | Review the estimated cost | You'll see an estimated cost. |
| 7 | Click **I've completed my test** | Then mark your test complete | When your roadmap's set and a vendor's chosen, mark the test complete. |
| 8 | Point to the feedback button | Use the feedback button anytime | Use the feedback button along the way — that's what we're here for. |

---

## 5. Production pipeline (TD-11)

This upgrades TD-11 from captions-only to **captions + voiceover** in v1. Steps:

1. **Record** — one Playwright script per clip drives the seeded accounts at 1280×720 with deterministic pauses (explicit waits, not `sleep`), `recordVideo` → webm. Blank profiles; synthetic data only.
2. **Voiceover** — feed the §6 script lines to a TTS API (OpenAI TTS, a calm neutral voice) → one mp3 per clip (or per line for precise sync).
3. **Captions + watermark** — ffmpeg burns caption overlays timed to each beat + the confidential watermark.
4. **Mux** — ffmpeg combines video + voiceover; pad/pace so caption, action, and voice line land together.
5. **Export** → `frontend/public/test-drive/{start,hr,employee}.mp4`; embed in `/test-drive` (TD-3), page set to `noindex`. **Also copy each final mp4 to `~/Downloads/relopass-test-drive/`** (create the folder if absent) so Romain has local copies — this is a required output, not optional.
6. **v2 (post-launch):** swap AI voiceover for a human take on the intro if desired; regenerate any clip whose UI changed by re-running its Playwright script.

**Validation (updated TD-11):** three mp4s exist **in both `frontend/public/test-drive/` and `~/Downloads/relopass-test-drive/`**, each shows its flow with legible captions **and audible voiceover**, watermark present, no protected panel on screen >2s. `Test Command`: `ls frontend/public/test-drive/*.mp4 && ls ~/Downloads/relopass-test-drive/*.mp4`.

---

## 6. Voiceover script (clean, ready for TTS)

Brand voice: calm, precise, second person, present tense, one idea per line, no "journey", no hype.

**start.mp4**
1. Everything you need is on one page.
2. Enter your first name. We create two accounts for you.
3. You get two logins — one for HR, one for the employee. You'll use both.
4. Start as HR. Copy the HR login and sign in.
5. When HR's done, come back and switch to the employee login.
6. Let's start with the HR side.

**hr.mp4**
1. As HR, this is your command center. It starts empty.
2. First, create your company — just a name and size.
3. Add the employee who's relocating — use your Employee login's name.
4. Set where they're moving from and to. That's the corridor.
5. Choose what the package covers.
6. Then hand the case to the employee.
7. Now do the same — create a company and hand off a case.

**employee.mp4**
1. Now switch to the employee. You'll see the case HR assigned.
2. Accept it to begin.
3. Answer a few questions about your move.
4. Your roadmap builds from your answers.
5. Open your services and choose a vendor.
6. You'll see an estimated cost.
7. When your roadmap's set and a vendor's chosen, mark the test complete.
8. Use the feedback button along the way — that's what we're here for.

---

## 7. Open items to finalize before recording
1. **Demo corridor:** confirm Paris → Oslo (default) or India → Munich for the on-screen example.
2. **Sample identity:** the first name shown in the demo (e.g. "Sam" → `HR-Sam-###` / `EMP-Sam-###`).
3. **TTS voice:** confirm provider/voice (default OpenAI TTS, calm neutral).
4. **Watermark text:** "ReloPass · Confidential beta" — confirm wording.
5. **TD-11 update:** update the Notion task's Expected Output + Validation to reflect captions **+ voiceover** in v1 (currently says captions-only). Want me to?
