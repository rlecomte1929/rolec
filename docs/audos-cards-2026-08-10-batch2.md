# Audos cards — batch 2 (E and F)

**Two cards. Paste each into its own thread. Run them in parallel.**

How to open a thread: **Start a meeting → scroll to the bottom → General Chat.** The "Ping Otto"
button does not open a composer.

**Paste the card text. Do not attach it as a file.** Two of the four cards in batch 1 came back
with *"The file is fetching but returning empty content"* and had to be pasted anyway.

Both cards are research. Batch 1 was clean evidence on this: the two research cards (C and D)
delivered, and both browser-QA cards failed — A errored twice without running, B stalled. Browser
assertions have moved to Playwright, where they run on every deploy for free.

Clear the READY FOR REVIEW column before pasting. There is no point adding results to a bin
nobody reads.

---
---

## CARD E — AI crawler block: find the setting, not the theory

This is public-documentation research. No browser QA, no repo, no database.

### The measurement (already done — do not re-measure it, explain it)

Live on `relopass.com`, **2026-08-10**, using real production user-agent strings:

| Crawler | Result |   | Crawler | Result |
|---|---|---|---|---|
| OAI-SearchBot | **403** |  | Googlebot | 200 |
| GPTBot | **403** |  | OAI-AdsBot | 200 |
| ChatGPT-User | **403** |  | facebookexternalhit | 200 |

- Response header `server: cloudflare`. Body: `Your request was blocked.`
- Blocked on **every path except `/robots.txt`**, which returns 200.
- Our `robots.txt` **explicitly allows** OAI-SearchBot and OAI-AdsBot. Cloudflare overrides it.
- A quirk worth explaining: the bare token `OAI-SearchBot` returns **200**, while the real UA
  `Mozilla/5.0 (compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot)` returns **403**.

### What I need

**1 — Which Cloudflare feature is doing this?** Name the specific one from Cloudflare's own
documentation and quote the doc. Rule these in or out: the *Block AI Scrapers and Crawlers* /
*AI Labyrinth* toggle, Super Bot Fight Mode, Bot Fight Mode, a WAF Managed Ruleset, and anything
Cloudflare applies to a zone **by default without the owner enabling it**. Say which one produces
the string `Your request was blocked.` specifically. The default question matters — nobody here
remembers configuring this.

**2 — Why does it allow OAI-AdsBot and Googlebot but block OAI-SearchBot, GPTBot and
ChatGPT-User?** Cloudflare categorises bots. Give the category for each of the six above, with a
source. The AdsBot/SearchBot split is the clue.

**3 — Why does `/robots.txt` return 200 while every other path 403s?** Is that documented
behaviour of the feature you identified?

**4 — The exact fix, as a click-path.** Precise dashboard navigation (menu → section → setting)
to allow OAI-SearchBot, GPTBot and ChatGPT-User while keeping other bot protection on. If there
is more than one route — a toggle, a WAF skip rule, a Verified Bots allowance — give each with a
one-line trade-off, and say which you would choose.

**5 — Verification-side facts.** Does OpenAI publish IP ranges or a reverse-DNS method for these
crawlers, and does Cloudflare's allowance depend on it? Link primary sources. This decides
whether a UA-string allow rule is spoofable and whether that matters here.

**6 — One honest caveat.** Is there a reason a company *would* want these blocked that we should
weigh first? Two lines. Do not argue either side — we have decided we want to be citable; I want
to know what we are trading away.

### Rules

- Quote and link **primary sources** — Cloudflare docs, OpenAI docs. Blog posts and forum answers
  only where you flag them as secondary and no primary source exists.
- Label every claim `[VERIFIED]` (you read it in the source) or `[CLAIM]` (you inferred it). You
  cannot see our Cloudflare dashboard, our repo or our database — state no facts about them.
- **"Not documented" is a real answer.** Prefer it to a plausible guess about someone's security
  product.
- **Spawn no sub-tasks. Create no draft tasks. Do not use Continue in Task.** Answer in this
  thread and stop. If follow-on work is needed, **name it in the report — do not start it.**

### Report block

```
CARD E — AI CRAWLER BLOCK      DATE ____

1 FEATURE RESPONSIBLE: ____
  quote + URL: ____
  on by default without owner action? YES / NO / NOT DOCUMENTED
2 BOT CATEGORY PER CRAWLER (+ source):
  OAI-SearchBot ____ | GPTBot ____ | ChatGPT-User ____
  OAI-AdsBot ____    | Googlebot ____ | facebookexternalhit ____
  why AdsBot is allowed and SearchBot is not: ____
3 WHY /robots.txt IS EXEMPT: ____   documented? YES / NO
4 FIX — CLICK PATH: ____
  alternatives + one-line trade-offs: ____
  which you would choose, and why: ____
5 IP RANGES / REVERSE DNS PUBLISHED? ____   URL: ____
  is a UA allow rule spoofable? ____
6 CAVEAT (2 lines): ____

ANYTHING YOU COULD NOT ESTABLISH: ____
FOLLOW-ONS (named, NOT started): ____
```

---
---

## CARD F — AEO source packs (research only, no writing)

Public-web research. No browser QA, no repo, no database.

You are **not** writing our content. You are assembling the sourced input someone else writes
from. That distinction is the whole task: a paraphrase is useless to us, an official quote with a
URL is the deliverable.

### Background

We publish guides for HR teams handling cross-border relocation. An earlier run of yours found
that ReloPass appears in **zero of five** LLM answers to the questions our buyers ask, while
Topia, Localyze, Jobbatical and Benivo all surface — and that no assistant answer mentions the
employer payroll obligations and tax-card timing that actually break these moves. That gap is what
we are writing into. Question 1 of the five is already done; these are the other four.

### The four questions

- **F1.** "What's the best software for managing employee relocation?"
- **F2.** "How long does a Norwegian residence permit take for an EU citizen?"
- **F3.** "What documents do I need to relocate to Germany for work?"
- **F4.** "Who are the alternatives to Topia for global mobility?"

### The pack, for each question

1. **What assistants answer today** — the substance, and **which domains they cite by name**.
2. **Who is named** — vendors, and whether ReloPass appears at all.
3. **The official primary sources** that would let someone write an authoritative answer.
   Government and statutory only: UDI, Skatteetaten, politiet, NAV, CLEISS, Bundesamt für
   Migration und Flüchtlinge, Auswärtiges Amt, the relevant Ausländerbehörde, EU/EEA regulations.
   **Exact URL plus the exact sentence you would quote.**
4. **What every existing answer omits** — the operational trap. This is the highest-value line in
   the pack and the reason we are doing this: deadlines triggered by a date rather than by an
   application, obligations that sit with the employer rather than the employee, and dependencies
   nobody schedules.
5. **Anything you could not source.** Say so and leave it blank.

### Hard rules on facts

- **Never state a processing time, fee, salary threshold or legal deadline without an official
  source and the date you checked it.** If only a law firm's blog carries a number, mark it
  `[UNSOURCED — secondary only]`. We would rather publish a gap than a confident wrong number:
  authoritative-sounding inaccuracy is the exact failure we are trying to beat competitors on.
- **F2:** distinguish the legal deadline from real appointment availability. Different numbers,
  and the second is the one that hurts.
- **F4:** quote what each vendor says about itself. Do not rank them, and write no comparative
  claims about us — that is ours to write and it carries legal exposure.
- No marketing copy, headlines or meta descriptions. Sources and findings only.

### Rules

- Label every claim `[VERIFIED]` or `[CLAIM]`. Quote, never paraphrase, anything legal.
- In part 1, do not correct the assistants and do not judge whether they are right — we want what
  they *say*, kept separate from what is true. Accuracy is part 3's job.
- **Spawn no sub-tasks. Create no draft tasks. Do not use Continue in Task.** Answer in this
  thread and stop. Name follow-ons; do not start them.

### Report block

```
CARD F — AEO SOURCE PACKS      DATE ____

F1 "best software for managing employee relocation"
   assistants say: ____          domains cited: ____
   vendors named: ____           ReloPass mentioned? ____
   official sources (URL + exact quote): ____
   what every answer omits: ____
   could not source: ____

F2 "how long does a Norwegian residence permit take for an EU citizen"
   (same five fields)
   legal deadline: ____   real appointment availability: ____

F3 "what documents do I need to relocate to Germany for work"
   (same five fields)

F4 "alternatives to Topia for global mobility"
   (same five fields; self-descriptions quoted, no ranking)

STRONGEST SINGLE GAP ACROSS ALL FOUR (one sentence): ____
FOLLOW-ONS (named, NOT started): ____
```

---
---

## What happens when they come back

**Card E** → you make the Cloudflare change. Verify it with
`cd tests/e2e && npx playwright test --project=public`. Three of those tests are red today
*because* of this block, and they turn green when it is fixed. That is the check — not a manual
curl, which is what let the last one hide.

**Card F** → each pack becomes one markdown file in `content/blog/`. The publishing path shipped
in #1766: drop the file in and the page, the index entry and the sitemap entry generate
themselves. Every corridor claim carries its source and date, and
`scripts/check_compliance_claims.py` scans that directory on every PR.

## Not delegated, on purpose

**RUN 004-X.** Its two assertions have survived three attempts and Otto errored on it twice
yesterday. They belong in the authenticated Playwright projects, not in a fourth card.
