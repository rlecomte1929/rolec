# ReloPass — Figma Wireframe Specification

**Version:** April 2026  
**Stage:** Low-fidelity structural spec (Phase 1 of 2)  
**Use:** Give this document to a designer or Claude Design alongside the audit brief. Every section description specifies content blocks, copy direction, and layout logic. Visual polish comes in Phase 2.

---

## Global design system rules

These apply to every page and every component. Resolve these before building any page template.

### Typographic hierarchy
- **Display / Hero headline:** Large, weight-heavy, single declarative line. No taglines stacked directly beneath without a subheading separator.
- **Section headline:** Mid-weight, used to anchor each content block. Never decorative — always functional.
- **Body:** Regular weight. Short paragraphs. Max 2–3 sentences before a break.
- **Microcopy / labels:** Small, muted, high-information-density. Used for CTA context, form field guidance, trust cues.

### Spacing system
- Use an 8px base unit. All spacing values are multiples of 8.
- Sections separated by generous vertical breathing room (80–120px desktop). This signals structure and calm, not crowding.
- Content should never feel compressed. White space is part of the brand signal.

### Grid
- 12-column desktop grid, 4-column mobile grid.
- Content max-width: 1200px. Hero content narrower: 800px centred.
- Product screenshot panels may bleed wider (1440px) to suggest system scale.

### Colour intent
- **Background:** Off-white or very light neutral. Not pure white — too clinical; not grey — too generic.
- **Primary accent:** One controlled accent colour for CTAs and active states. Use sparingly.
- **Text:** Near-black for headlines, medium-dark grey for body, lighter grey for secondary/microcopy.
- **Product UI surfaces:** Slightly elevated from background (subtle card shadow or border). Must read as software, not marketing illustration.

### CTA system (global)
Every page must contain:
- **Primary CTA:** "Book a demo" — high-contrast, solid fill.
- **Secondary CTA:** "See the platform" — outline or ghost variant, lower visual weight.
- Sticky nav CTA: "Book a demo" visible at all scroll depths on desktop.
- Both CTAs must be visible without scrolling on every hero section.

### Visual language rules
**Use:**
- Annotated product UI screenshots (timeline view, case overview, workflow state, document list)
- Structural diagrams showing the system's coordination logic
- Minimal iconography (functional, not decorative)
- Data-density UI surfaces that imply operational depth

**Do not use:**
- Stock photography of planes, passports, city skylines, or moving boxes
- People dragging suitcases
- Generic relocation lifestyle imagery
- Abstract gradient blobs or geometric decorative elements
- Illustration styles that read as friendly/consumer (Notion-style illustration is borderline; Stripe-style is correct)

---

## Page 1: Homepage

**Page role:** Establish category, primary buyer, the coordination problem, and the system that solves it. Move the visitor from awareness to enough understanding to book a demo or explore the platform.

**URL:** `/` or `/home`

---

### Section 1.1 — Hero

**Layout:** Full-width. Headline left-aligned (or centred on narrow viewport). Two CTAs side-by-side beneath subheadline. Product UI preview partially visible below the fold to imply depth.

**Content blocks:**

| Block | Copy direction | Notes |
|---|---|---|
| Pre-headline label | Optional: "Global mobility infrastructure" in small caps or a subtle tag | Frames category before the headline lands |
| Headline | Category statement that leads with operational control, not inspiration. Example: "The operating layer for global mobility." | One line. No punctuation at end. High weight. |
| Subheadline | What it replaces + what it enables. Example: "Replace email threads, spreadsheets, and fragmented vendors with one policy-driven system of record." | 1–2 sentences max. |
| Primary CTA | "Book a demo" | Solid fill. Left of pair. |
| Secondary CTA | "See the platform" | Outline/ghost. Right of pair. |
| Hero visual | Partial product screenshot — case timeline or workflow overview — partially visible below fold | Crop implies there is more below; invites scroll |

**Copy rules for this section:**
- Do not use "journey", "seamless", "powerful", or "all-in-one".
- Buyer (HR manager) is the implied subject. Employee not mentioned in hero.
- The system of record framing should appear here or be immediately implied.

---

### Section 1.2 — Problem stakes

**Layout:** Two to three columns or a bold typographic block. This section should feel weighty, not explanatory. It names the pain.

**Content blocks:**

| Block | Copy direction | Notes |
|---|---|---|
| Section headline | "Relocation still runs on email and spreadsheets." | Or variant: "Relocation fails in the handoffs." Use the approved gold-standard copy. |
| Problem statements | 3–4 short, sharp pain points in parallel structure | Each is one sentence. No bullet-point overflow. |
| Pain point 1 | HR is accountable for outcomes they cannot see. | |
| Pain point 2 | Vendors operate outside the case, not inside it. | |
| Pain point 3 | Every delay is a compliance, cost, or employee risk. | |
| Pain point 4 | Status lives in inboxes, not in systems. | |
| Visual | Optional: a deliberately "broken" process diagram — disconnected boxes, no central system — then a visual transition into Section 1.3 | Contrast device. Must not feel decorative. |

**Copy rules for this section:**
- Make the problem operational, not emotional. No "stressful for employees" language here — that comes later and only as a consequence of bad operations.
- Short sentences. No hedging. These are facts, not claims.

---

### Section 1.3 — System overview (ReloPass as the operating layer)

**Layout:** Centred headline, followed by a module grid or visual system map. This is where the product's architecture becomes legible.

**Content blocks:**

| Block | Copy direction | Notes |
|---|---|---|
| Section headline | "One system for cases, timelines, documents, providers, and status." | Avoid "all-in-one". This sentence is already approved directionally. |
| Subtext | 1–2 sentences framing this as a system of record, not a tool collection. Example: "ReloPass connects every part of the relocation workflow into a single, policy-driven operating system." | |
| Module grid | 5–6 cards: Cases / Timelines / Documents / Providers / Policy controls / Visibility | Each card: icon + label + 1-line function description. Not feature lists. |
| Module card: Cases | "Every relocation case in one place, from open to close." | |
| Module card: Timelines | "Structured task sequences, policy-applied at creation." | |
| Module card: Documents | "Required documents tracked to the case, not to inboxes." | |
| Module card: Providers | "Vendor tasks assigned and monitored inside the case." | |
| Module card: Policy controls | "Your relocation policy becomes the system's operating rules." | |
| Module card: Visibility | "Real-time status across every open case and provider." | Do not use "real-time" if it implies over-engineered tech claims. "Live case status" is safer. |

**Copy rules for this section:**
- Each module description should name a stakeholder, a document type, or a workflow step — never just describe the feature abstractly.
- The visual should imply a connected system, not a list of tabs.

---

### Section 1.4 — How it works

**Layout:** Horizontal step sequence (desktop), vertical (mobile). Maximum 4 steps. Each step: number + short headline + 1-line description + optional supporting UI element.

**Content blocks:**

| Step | Headline | Description |
|---|---|---|
| 1 | Set up your policy and operating rules | Define the relocation types, required steps, document requirements, and provider assignments for your corridors. |
| 2 | Open a case and apply the right policy | Create the case, select the corridor, and let the system generate the structured workflow. |
| 3 | Coordinate documents, providers, and timelines | Tasks route to the right parties. Progress is tracked inside the case, not across email chains. |
| 4 | Monitor execution until completion | Track open items, exceptions, and evidence. Every case is audit-ready on close. |

**Visual direction:** Each step should have a supporting product UI thumbnail — small, annotated with a single callout pointing to the relevant feature (policy selector, case creation modal, task assignment panel, case timeline).

**Copy rules:**
- No abstract verbs ("enable", "empower", "leverage").
- Each step describes what the system does, not what HR "gets to" do.
- Step 4 should land on the audit/compliance angle — this is a key differentiator.

---

### Section 1.5 — Product proof

**Layout:** Wide product screenshot, optionally full-bleed with a slight drop shadow or border to frame it as software. Add 2–3 annotated callouts pointing to specific features.

**Content blocks:**

| Block | Copy direction | Notes |
|---|---|---|
| Section headline | "See the case in full." | Or "Every case. Every status. Every stakeholder." |
| Primary screenshot | Case overview or timeline view — the most dense, information-rich view available | Must read as a serious operational tool. Avoid showing a near-empty demo state. |
| Callout 1 | Point to case status / progress indicator | Label: "Policy-applied workflow — tasks generated at case creation." |
| Callout 2 | Point to provider task section | Label: "Vendor tasks inside the case, not outside it." |
| Callout 3 | Point to document tracker or evidence log | Label: "Audit-ready at every stage." |
| Secondary CTA | "See the platform" | Lower friction option. No commitment required. |

---

### Section 1.6 — Differentiation

**Layout:** Contrast block. Two columns or a before/after structure. This section makes the category argument explicit.

**Content blocks:**

| Block | Copy direction | Notes |
|---|---|---|
| Section headline | "Not an agency. Not a marketplace. The operating layer." | Or: "Built for mobility operators, not relocation shoppers." |
| Contrast block — left | "Without ReloPass" — bullet list of the fragmented state: threads, spreadsheets, vendor emails, no visibility, no audit trail | Sparse, factual, no drama |
| Contrast block — right | "With ReloPass" — bullet list of the structured state: policy-driven case, visible workflow, documents tracked, providers coordinated, compliant close | Match the structure of the left column precisely |
| Optional positioning line | "ReloPass is not a vendor you use. It is the system you run everything through." | Use only if it does not feel too abstract in context |

---

### Section 1.7 — Trust

**Layout:** Understated. This section should feel earned, not shouted. 3–4 trust signals in a horizontal row or grid.

**Content blocks:**

| Block | Copy direction |
|---|---|
| Signal 1 | "Policy-driven execution. Your rules, applied consistently to every case." |
| Signal 2 | "Audit-ready close. Every document, step, and provider decision logged to the case." |
| Signal 3 | "Corridor intelligence. Structured for the routes your team runs most." |
| Signal 4 | "Visibility without chasing. Status is in the system, not in someone's inbox." |
| Optional: logos | Client logos or partner logos when available. If not available, omit. Do not use placeholder logos. |

---

### Section 1.8 — Final CTA

**Layout:** Full-width band, background slightly differentiated from main page. Centred content.

**Content blocks:**

| Block | Copy direction |
|---|---|
| Headline | "Ready to run relocation as a system?" |
| Subtext | "Tell us how your relocations run today. We'll show you what changes." |
| Primary CTA | "Book a demo" |
| Secondary CTA | "See the platform walkthrough" |

---

## Page 2: Platform

**Page role:** Make the product's architecture legible. Translate the positioning claim into a concrete mental model. Answer "what is in the platform?" and "how does it work together?"

**URL:** `/platform`

---

### Section 2.1 — Platform hero

| Block | Copy direction |
|---|---|
| Pre-headline | "The platform" (page label) |
| Headline | "Every part of the relocation workflow. One connected system." |
| Subtext | "Cases, timelines, documents, providers, and policy controls — structured into a single operating layer." |
| CTA | "Book a demo" + "Sign in" |

---

### Section 2.2 — Platform architecture overview

**Layout:** Visual system map showing the modules and their relationships. Not a flowchart. A structural diagram — think of how Stripe's product pages show the API architecture.

| Block | Copy direction |
|---|---|
| Section headline | "Built around the case." |
| Architecture diagram | Central node = Case. Spokes = Policy / Timeline / Documents / Providers / Status / Reporting. Arrows show information flow direction. |
| Explanatory line | "The case is the unit of work. Everything else — policy, tasks, documents, providers — connects to it." |

---

### Section 2.3 — Module-by-module breakdown

**Layout:** For each module, a two-column layout: copy left, annotated product screenshot right (or reverse, alternating for visual rhythm).

#### Module A: Cases

| Block | Copy direction |
|---|---|
| Module label | "Cases" |
| Headline | "One case per relocation. Complete from open to close." |
| Body | "Every relocation starts as a structured case. The case holds the policy, the timeline, the documents, the providers, and the evidence — in one place, from day one." |
| Key capabilities | Case creation / Corridor assignment / Policy application / Status tracking / Audit log |
| Screenshot | Case detail view — show fields populated, timeline present, status indicator active |

#### Module B: Timelines and workflows

| Block | Copy direction |
|---|---|
| Module label | "Timelines" |
| Headline | "Structured task sequences. Policy-applied at creation." |
| Body | "When a case opens, the system generates the correct task sequence for that corridor and policy. Nothing is manually assembled. Nothing is forgotten." |
| Key capabilities | Policy-driven task generation / Deadline assignment / Dependency sequencing / Exception flagging |
| Screenshot | Timeline view — show task states (complete / in progress / blocked / upcoming) |

#### Module C: Documents

| Block | Copy direction |
|---|---|
| Module label | "Documents" |
| Headline | "Required documents tracked to the case." |
| Body | "Document requirements are set at the policy level. Uploads are matched to the case. Nothing lives in email. Nothing is chased manually." |
| Key capabilities | Document checklist by policy / Upload tracking / Evidence log / Compliance status per document type |
| Screenshot | Document tracker panel within a case |

#### Module D: Providers

| Block | Copy direction |
|---|---|
| Module label | "Providers" |
| Headline | "Vendor tasks inside the case, not outside it." |
| Body | "Service providers receive structured task assignments tied to the case. Their actions are logged. Their status is visible. No separate inboxes. No manual status updates." |
| Key capabilities | Provider task assignment / Progress visibility / Escalation flags / Communication log |
| Screenshot | Provider task view within the case — show multiple providers, status per task |

#### Module E: Policy controls

| Block | Copy direction |
|---|---|
| Module label | "Policy controls" |
| Headline | "Your relocation policy becomes the system's operating rules." |
| Body | "Define what is required for each relocation type and corridor. The system applies those rules consistently at case creation. No exceptions by accident." |
| Key capabilities | Policy builder / Corridor-specific rule sets / Tier configuration / Mandatory vs optional steps |
| Screenshot | Policy configuration view — show corridor, tier, and required steps |

#### Module F: Visibility and reporting

| Block | Copy direction |
|---|---|
| Module label | "Visibility" |
| Headline | "Status across every open case. Without asking." |
| Body | "HR managers see the full case portfolio in one view. Open items, upcoming milestones, exceptions, and overdue tasks — surfaced automatically." |
| Key capabilities | Portfolio dashboard / Exception alerts / SLA tracking / Reporting export |
| Screenshot | Dashboard or portfolio view — show multiple cases in different states |

---

### Section 2.4 — Dual perspective (HR vs employee)

**Layout:** Split two-column. Left: HR manager's view. Right: Employee's view.

| Side | Headline | Content |
|---|---|---|
| Left (HR) | "What HR sees" | Case portfolio, policy adherence, exception flags, compliance status, provider progress |
| Right (Employee) | "What the employee sees" | Their own case timeline, document requirements, next steps, provider contacts |
| Bridging line | "Same case. Two structured views." | |

---

### Section 2.5 — CTA

| Block | Copy direction |
|---|---|
| Headline | "See the platform in a 30-minute walkthrough." |
| Subtext | "We'll walk through your specific relocation types and show you how ReloPass structures them." |
| Primary CTA | "Book a demo" |
| Secondary CTA | "Sign in" |

---

## Page 3: Why ReloPass

**Page role:** Win the category argument. This page must answer: why not keep using spreadsheets and vendors? Why is this a new category? Why now?

**URL:** `/why-relopass`

---

### Section 3.1 — Hero

| Block | Copy direction |
|---|---|
| Headline | "Relocation fails in the handoffs." |
| Subtext | "Not because teams aren't capable. Because the tools aren't built for coordination." |
| CTA | "Book a demo" |

---

### Section 3.2 — The coordination problem

**Layout:** Text-heavy, typographic. This is the argument section. No decorative elements.

| Block | Copy direction |
|---|---|
| Section headline | "Relocation is a coordination problem first." |
| Body paragraph 1 | "Most relocation failures are not policy failures. They are coordination failures. Tasks dropped between HR, employees, and vendors. Documents requested twice and never tracked. Timelines managed in threads. Status buried in inboxes." |
| Body paragraph 2 | "The tools that exist either own the service (agencies) or help with one part of the problem (document tools, vendor directories, HR modules). None of them are built to coordinate the whole workflow." |
| Body paragraph 3 | "ReloPass is the coordination layer. Not a service. Not a marketplace. The system through which HR, employees, and providers operate in one structured workflow." |

---

### Section 3.3 — Why current tools fail

**Layout:** Three-column grid. Each column is a category of existing approach.

| Column | Label | Body |
|---|---|---|
| 1 | "Relocation agencies" | "Agencies own the service. They don't give HR visibility into what's happening or why. You get outcomes without control." |
| 2 | "Spreadsheets and email" | "Manual tracking breaks at scale. Status is wherever the last email is. Nothing is auditable. Nothing is proactive." |
| 3 | "HR platform add-ons" | "Generic workflow tools aren't built for relocation complexity: corridors, compliance, multi-vendor coordination, document chains." |
| Bridging line (below grid) | "ReloPass is not any of these. It is the operating layer that connects them." | |

---

### Section 3.4 — The contrast blocks

**Layout:** Clean two-column contrast. Left column: the fragmented state. Right column: the ReloPass state.

| | Without ReloPass | With ReloPass |
|---|---|---|
| Status | In inboxes, spreadsheets, and chased by phone | Visible in the case, updated by the system |
| Documents | Requested manually, tracked in email | Tied to the case with completion status |
| Providers | Operating outside HR's view | Assigned tasks inside the case, progress visible |
| Policy | Applied inconsistently | Encoded as operating rules at case creation |
| Compliance | Reconstructed after the fact | Logged automatically throughout the case |
| Handoffs | The main source of failure | Structured, sequenced, and tracked |

---

### Section 3.5 — Category framing

| Block | Copy direction |
|---|---|
| Section headline | "A new category: mobility operations." |
| Body | "ReloPass is not a better version of what exists. It is a different kind of tool — one built specifically to structure the execution of relocation, not just support it from the edges." |
| Optional positioned line | "For HR teams running relocation at scale, the question is no longer which vendor to use. It is whether relocation has an operating system." |

---

### Section 3.6 — CTA

| Block | Copy direction |
|---|---|
| Headline | "See how it changes the way relocation runs." |
| CTA | "Book a demo" |

---

## Page 4: How it works

**Page role:** Remove cognitive friction. Give the buyer a clear, concrete adoption path. If buyers cannot see how they get from today to using ReloPass, they defer.

**URL:** `/how-it-works`

---

### Section 4.1 — Hero

| Block | Copy direction |
|---|---|
| Headline | "Four steps from fragmented to structured." |
| Subtext | "ReloPass is configured to your policy and corridors, then runs every case through the same structured workflow." |

---

### Section 4.2 — Step sequence

**Layout:** Horizontal step flow (desktop), vertical stack (mobile). Each step: large step number, bold headline, 2-sentence description, small supporting UI element.

| Step | Headline | Description | UI element |
|---|---|---|---|
| 1 | Configure your policy and corridors | Define the relocation types you run, the steps required for each, the documents needed, and the providers assigned. This becomes the operating rulebook. | Policy configuration screen — show corridor selector and required steps list |
| 2 | Open a case and apply the policy | When a relocation begins, create the case, assign the corridor, and let the system generate the structured workflow automatically. No manual assembly. | Case creation modal — show corridor applied, timeline preview generated |
| 3 | Coordinate tasks across HR, employees, and providers | Tasks route to the right party at the right time. Documents are requested and tracked. Vendors receive structured assignments inside the case. | Task assignment view — show multi-party task routing, status per task |
| 4 | Track progress to compliant close | Monitor open items, exceptions, and milestones. Every case closes with a complete evidence log. Audit-ready on day one. | Case timeline at completion — show completed states, evidence log, close status |

---

### Section 4.3 — Setup timeline (optional)

**Layout:** Simple horizontal timeline or 3-step onboarding arc. Keep brief.

| Phase | Label | Description |
|---|---|---|
| Week 1 | Policy configuration | Your relocation types, corridors, and operating rules are configured with your team. |
| Week 2 | First cases | Run live cases through the system. Validate workflows against your existing process. |
| Ongoing | Full operation | Every new case opens in ReloPass. HR has visibility. Providers are coordinated. Cases close with evidence. |

---

### Section 4.4 — CTA

| Block | Copy direction |
|---|---|
| Headline | "Start with one corridor. Run it in ReloPass." |
| Subtext | "Most teams are fully operational within two weeks." |
| Primary CTA | "Book a demo" |
| Secondary CTA | "See the platform" |

---

## Page 5: Get started

**Page role:** Convert interest into a meeting. Remove every friction point between intent and booking.

**URL:** `/get-started`

---

### Section 5.1 — Hero

| Block | Copy direction |
|---|---|
| Pre-headline | "Get started" (page label) |
| Headline | "Three ways in. Book a demo, sign in, or create an account." |
| Subtext | "Tell us how your relocations run today. We'll show you what changes." |

*(Both are approved gold-standard lines — use verbatim.)*

---

### Section 5.2 — Primary path: Book a demo

**Layout:** Left column — form. Right column — what to expect.

**Form fields (left):**
- First name
- Last name
- Work email
- Company
- Number of relocations per year (dropdown: 1–10 / 10–50 / 50–200 / 200+)
- Optional: What's the main challenge you're trying to solve? (short text)

**Trust microcopy (left, below CTA):**
- "30-minute walkthrough, tailored to your process."
- "No commitment required."
- "We typically respond within one business day."

**What to expect panel (right):**
| Element | Content |
|---|---|
| Panel headline | "What the demo covers" |
| Item 1 | How ReloPass structures your specific relocation types |
| Item 2 | The case, timeline, and document workflow in practice |
| Item 3 | How providers are coordinated inside the system |
| Item 4 | How your policy becomes the system's operating rules |
| Item 5 | What implementation looks like for your team |

---

### Section 5.3 — Secondary paths

**Layout:** Two smaller cards below the main demo form.

| Card | Headline | Body | CTA |
|---|---|---|---|
| Sign in | "Already have an account?" | Access your cases and workflows. | "Sign in" |
| See the platform | "Not ready to talk yet?" | Walk through the platform at your own pace. | "See the platform" |

---

### Section 5.4 — Optional trust reinforcement

**Layout:** Horizontal row of 3–4 operational proof statements. Understated. No icons needed.

| Statement |
|---|
| "Built for HR and mobility teams running 10 to 500+ relocations per year." |
| "Configured to your corridors and policy — not a generic template." |
| "Your data stays in your system. No vendor lock-in on provider relationships." |

---

## Navigation specification

**Global nav items (desktop):**

| Label | Destination | Notes |
|---|---|---|
| Platform | `/platform` | Describes the product |
| Why ReloPass | `/why-relopass` | Makes the category argument |
| How it works | `/how-it-works` | Removes adoption friction |
| Get started | `/get-started` | Conversion |
| Sign in | App sign-in URL | Visually separated from marketing nav items (right-aligned, subdued) |
| Book a demo | `/get-started` | Sticky CTA button — primary accent colour — always visible |

**Nav copy rules:**
- Labels are functional, not brand-y. No "Our story", "About us", "Resources" as primary nav items at this stage.
- "Sign in" must be visually differentiated from the acquisition nav so the marketing site feels buyer-focused, not customer-portal-focused.

---

## Footer specification

**Column 1 — Product**
- Platform
- How it works
- Why ReloPass
- Get started

**Column 2 — Company**
- About (if page exists)
- Contact

**Column 3 — Legal**
- Privacy policy
- Terms

**Footer brand line:**
"ReloPass — Global mobility infrastructure."

**Footer contact line (approved gold-standard):**
"Tell us how your relocations run today. We'll show you what changes."

**Footer copy rules:**
- No "journey", "adventure", or lifestyle language in footer.
- The brand descriptor in the footer should always be "Global mobility infrastructure" — not a tagline variant.

---

## Phase 2 handoff notes (high-fidelity)

Once low-fidelity wireframes are validated against this spec, the Phase 2 Figma pass should address:

1. **Type scale** — define 5–6 levels (display, H1, H2, H3, body, small) with exact sizes and weights.
2. **Component library** — CTA button variants, module cards, contrast blocks, step sequences, callout annotations.
3. **Product screenshot presentation rules** — how screenshots are cropped, scaled, bordered, and annotated.
4. **Motion brief** — minimal. Scroll-triggered section entrance only. No parallax. No auto-playing animations.
5. **Responsive breakpoints** — desktop (1440), laptop (1280), tablet (768), mobile (390).
6. **Dark mode consideration** — optional. If pursued, must maintain the same operational/infrastructure aesthetic.

---

*End of wireframe specification. Use with `relopass-audit-brief.md` for a complete audit and redesign brief package.*
