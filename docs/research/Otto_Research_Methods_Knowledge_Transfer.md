# Otto Research Methods — Knowledge Transfer Document

**Authored:** 2026-08-12 by Otto (Claude Sonnet 4.5, Audos platform, workspace 776786)
**For:** Romain Lecomte — use as a rebuild manual
**Companion doc:** `Otto_Methods_Reverse_Engineered_and_Blueprint.md`

**Legend:** `[AUDOS]` = platform-specific, cannot be replicated outside Audos · `[PORTABLE]` = standard pattern, reproducible in any stack.

---

## 1. High-level architecture

End-to-end pipeline for a research task (e.g. "produce verified provider rows for City X"):

```
TASK ARRIVES (chat message or job draft)
        │
        ▼
[PLANNING] — I decompose into subtasks: which cities/categories,
  which source tier to target, how many parallel agents, budget estimate.
  I record the plan structure in otto.md before executing.
        │
        ▼
[AGENT DISPATCH] — For each independent city-pair batch, I spawn a
  background general-purpose agent via the Agent tool (concurrent).
  Each agent runs its own loop independently.
        │
        ▼
  [PER-AGENT LOOP]
  ┌─────────────────────────────────────────────────────────────┐
  │  1. web_search  — find authoritative source URLs            │
  │  2. web_fetch   — retrieve page content                     │
  │  3. LLM extract — me reading content → structured JSON       │
  │  4. Source-tier gate — T1 only; T2 acceptable; T3 rejected   │
  │  5. store_attachment — persist JSON to GCS                  │
  │  6. QA sweep — web_fetch each source_url, check 200/alive    │
  │  7. Patch & re-upload if dead URLs found                    │
  └─────────────────────────────────────────────────────────────┘
        │
        ▼
[CONSOLIDATION] — Main agent collects GCS URLs from each sub-agent.
  Updates otto.md with delivered batch URLs + row counts.
  Reports to founder with links, row totals, and any open blockers.
        │
        ▼
[SUPABASE LOAD] — Separate step (requires DB creds): upsert JSON rows
  into `service_catalog_items` via the Supabase MCP or founder's
  local environment. This step CANNOT run from the Audos chat runner.
```

**What triggers each stage**

| Stage | Trigger |
|---|---|
| Planning | Founder's chat message, or a job-draft `run_job_drafts` call |
| Agent dispatch | My explicit `Agent(...)` tool call with the batch brief |
| GCS persist | `store_attachment` inside each sub-agent |
| Supabase load | Manual step by founder (or a Cursor task with `DATABASE_URL`) |

---

## 2. Tools & APIs

| Tool | What it does | Key parameters | Portable? |
|---|---|---|---|
| `web_search` | Full-text web search; returns snippet + URL list | query string | **[AUDOS]** — wrapper; underlying engine unknown to me (likely Bing or Brave). Not inspectable. |
| `web_fetch` | Fetches a URL, returns rendered text content | `url` | **[AUDOS]** — wrapper. Limited JS rendering; static HTML works well, heavy SPAs may return skeleton only. PDFs: returns extracted text if the server sends `application/pdf`. |
| `store_attachment` | Persists a file/blob to GCS, returns a permanent public URL | `filename`, `content`, `mimeType` | **[AUDOS]** — Audos-managed GCS bucket `audos-images`, path `workspace-media/{workspaceId}/{timestamp}_{random}.{ext}`. Auth is Audos-internal; not replicable externally. |
| `Agent(...)` | Spawns a parallel sub-agent (Claude instance) | `prompt`, `subagent_type`, `run_in_background` | **[PORTABLE]** — this is the Claude Agent SDK pattern. Equivalent to spawning a new Claude API call with tools + system prompt. |
| `db_query` | Queries the Audos workspace database (PostgreSQL, workspace-scoped) | `sql` | **[AUDOS]** — workspace DB only; cannot reach Supabase/external DB from here. |
| `mcp__claude_ai_Supabase__*` | Reads/writes the external Supabase/Postgres project (service catalog, cases, etc.) | table name, filters | **[AUDOS]** wiring, but standard Supabase client underneath — **[PORTABLE]** if you have your own `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`. |
| `read_otto_notes` / `update_otto_notes` | Reads/writes `otto.md` (my persistent memory) | `offset`, `maxChars` / content string | **[AUDOS]** — stored in the Audos platform. Portable equivalent: a markdown file in a git repo, read/written by the agent each run. |
| `write_plan_section` / `read_plan` | Reads/writes the founder's Notes document | section key, content | **[AUDOS]** — platform-specific. |
| `create_job_drafts` / `run_job_drafts` | Creates/runs background "job" tasks with specific agent types | task description, `agentType` | **[AUDOS]** — platform job queue. Portable equivalent: a task queue (Celery, BullMQ) with a worker pool. |
| `Read`, `Write`, `Edit`, `Glob`, `Grep` | Standard filesystem tools | file paths | **[PORTABLE]** — Claude Code standard toolset. |
| `Bash` | Shell execution | command string | **[PORTABLE]** — Claude Code standard. |

**Search API specifically.** `web_search` is an opaque Audos wrapper; I cannot inspect which engine it calls. Query strategy: prefer specific operator-style queries like `"FIDI member" site:fidi.org Oslo` or `"international school" Oslo accredited IBO` over broad natural-language queries. I rank results by whether the domain is a `.gov`, an official association site, or the provider's own homepage — **not** by snippet confidence.

**Page fetch/render.** `web_fetch` returns text. It handles most static government pages and corporate sites well. It fails *silently* (returns empty or skeleton) on heavy React/Next.js apps requiring JS execution. For those, I use `web_search` to find a more accessible alternative URL (e.g. the provider's "About" or "Contact" page rather than a SPA dashboard).

---

## 3. Task decomposition & orchestration

**Job drafts [AUDOS].** A draft is a record in the Audos platform queue holding: a task description string, an `agentType` (e.g. `cursor_delegation`, `sub_otto`), and an optional `appId`. Drafts sit in a "Drafts" column visible to the founder in the Tasks panel. Running a draft dispatches it to a worker. State: `draft → running → completed/failed`. The internal datastore is Audos-managed and not inspectable by me.

**How I split large requests**

1. Identify the natural unit of independent work (e.g. one city-pair batch of ~70–85 rows).
2. Independent batches → parallel agents (all dispatched in one message as multiple `Agent(...)` calls).
3. Sequential only when batch B needs output from batch A (rare in research; common in build tasks).
4. Budget control: estimate ~$5–15 per batch agent, tracked against session budget. With no explicit budget given, I target ≤20 parallel tasks before checking in with the founder.

**Task state.** Recorded in `otto.md` — delivered batches get a ✅ with their GCS URL and row count; pending batches listed under "next candidate hubs." That is the checkpoint. There is no separate task-state database for research tasks.

---

## 4. Source discovery & tiering

**How I find authoritative sources for a corridor/topic**

1. **Government/statutory sources** — search for the exact agency by name (e.g. `Skatteetaten D-number registration`, `UDI EEA residence permit Norway`), then confirm the domain matches the known official domain (`.gov.no`, `udi.no`, `skatteetaten.no`, …).
2. **Industry association directories** — movers → FIDI (`fidi.org/find-a-mover`), FAIM certification list. Schools → IBO (`ibo.org/find-an-ib-school`). Advisors → EuRA (`eura.org`). These are my T1 lists for professional services.
3. **Provider own-site verification** — for any provider found in a directory, search for their official homepage and use *that* URL (not the directory listing) as `source_url`.

**Source tier rubric** (exact, as applied)

| Tier | Definition | Example |
|---|---|---|
| **T1** | Official primary source: a government/statutory site, OR the entity's own official website | `skatteetaten.no`, `udi.no`, `pickfords.co.uk` (their own site) |
| **T2** | Major industry association directory or well-known aggregator | `fidi.org/find-a-mover`, `ibo.org/schools`, `eura.org/directory` |
| **T3** | Reddit threads, roundup blog posts, TripAdvisor, Numbeo, generic "expat guide" articles | `reddit.com/r/Norway/...`, `expatarrivals.com` |

**Rule:** T3 sources are **rejected** — never used as `source_url`, even if they led me to a provider. I then find the provider's official site separately. T2 is acceptable as `source_url` *only* if the provider's own site cannot be located. T1 is the target for every row.

**Gap:** I do not maintain a persistent source registry. Sources are re-discovered per session via `web_search`. The closest thing to a registry is the GCS JSON files (each contains `source_url` per row) plus the city × category coverage map in `otto.md`. **If rebuilding this, a reusable source registry table (`city`, `category`, `source_name`, `source_url`, `tier`, `last_verified`) would dramatically accelerate subsequent runs.**

---

## 5. Fetching & change detection

```
1. web_fetch(url)  →  returns plain text (stripped HTML, paragraphs intact)
2. If result is empty or skeleton: retry with a different URL for same entity
3. For PDFs: web_fetch returns extracted text if Content-Type is application/pdf
4. For JS-heavy SPAs: web_fetch returns skeleton only — I fall back to
   (a) a static subpage of the same domain, or
   (b) the search snippet text only (no full fetch)
```

**Rate limits.** `web_fetch` has an implicit rate limit I have not quantified. In practice, a batch of 40 URLs fetched sequentially within a sub-agent has not hit explicit rate errors. Parallel agents each have their own fetch budget.

**Change detection — NOT IMPLEMENTED.** I do not currently store raw document content or detect changes over time. This is a gap. The `crawled_source_documents` table in the ReloPass Supabase schema exists precisely to fill it — I have not yet populated it. The current approach is: re-run a batch from scratch when you want freshness.

A proper change-detection loop would be:

1. Store raw page content + hash at crawl time.
2. On re-crawl, compare new hash to stored hash.
3. If changed → re-extract and re-QA.

This would need to run from the Cursor environment (has DB access), not from the Audos chat runner.

---

## 6. Extraction method

**Method:** schema-guided in-context LLM extraction. I read the fetched page text and output structured JSON matching a target schema. There is no separate parser or regex layer — it's the LLM reading and extracting in one step.

**Schema for `service_catalog_items` rows**

```json
{
  "provider_name": "string — exact official name",
  "category": "one of: living_areas | movers | schools | banks | insurance | electricity | pets",
  "city": "string — destination city name",
  "country": "string — ISO country name",
  "source_url": "string — T1/T2 verified URL (official site or major directory)",
  "source_tier": "T1 | T2",
  "confidence_score": 0.0,
  "notes": "string — optional; accreditation, caveats, service scope"
}
```

**Extraction prompt template** (verbatim, as used)

```
You are a research agent producing verified provider data for
service_catalog_items. For the city [CITY], category [CATEGORY]:

1. Search for providers using: web_search("[CATEGORY] [CITY] [country]
   [accreditation qualifier if applicable]")
2. For each candidate provider:
   a. Find their official website URL (not a directory listing, not Reddit)
   b. web_fetch the official URL to confirm it is real and live
   c. Confirm the provider actually operates in [CITY]
3. Output a JSON array. Each element:
   {
     "provider_name": "exact official name",
     "category": "[CATEGORY_KEY]",
     "city": "[CITY]",
     "country": "[COUNTRY]",
     "source_url": "the official site URL you verified live",
     "source_tier": "T1",
     "confidence_score": 0.85-1.0,
     "notes": "one line: key qualifier (FIDI member, IB World School, etc.)"
   }

Rules:
- Do NOT fabricate any provider. If you cannot find 5 real providers
  for a category, output fewer rows rather than inventing.
- source_url must be the provider's own official domain (not a directory
  listing, not a blog roundup, not Reddit).
- confidence_score = 1.0 if you fetched the official URL and confirmed
  the provider is real + city-specific. 0.85 if confirmed via directory
  listing only.
- Drop any row where you cannot confirm the provider is real via
  web_fetch or a major association directory.
```

**Source quote capture.** For compliance/regulatory facts (Case Command corridor data), I extract `source_quote` as a verbatim excerpt from the fetched page. For provider data I don't capture a source quote — I capture the `source_url` instead. The difference: regulatory facts need a specific claim quotation; provider-existence facts need a live URL.

---

## 7. Verification / QA

Pre-delivery QA process, run after extraction and before marking a batch delivered. For each row in the extracted JSON:

1. `web_fetch(source_url)`
   - Returns content → ✅ live
   - Returns empty/error → retry once
   - Still dead → replace with the provider's official page found via `web_search("provider_name official site")`, or drop the row
2. **Anti-bot 403/000 rule:** a curl-level `000` or `403` is **NOT** proof of death. Large banks, government portals and Cloudflare-fronted sites commonly block curl. `web_fetch` (browser-like agent) is the authoritative check. If `web_fetch` returns content → the row is live.
3. **Miscategorisation check:** does the fetched page confirm the provider actually operates in the stated city? If ambiguous → note it in `notes`.
4. **Official domain check:** is `source_url` the provider's own domain, or a directory listing? If directory → search for the own domain and update.

**Confidence rubric**

| Score | Meaning |
|---|---|
| **1.0** | `web_fetch` of official site returned a page confirming real provider + city match |
| **0.9** | Confirmed via major industry association directory (FIDI/IBO/FAIM) + official site found |
| **0.85** | Confirmed via directory only; own site not successfully fetched (anti-bot) |
| **< 0.80** | Not used — row dropped or flagged for manual review |

**What gets rejected.** Any row where I cannot confirm the provider is real via at least one of (a) a successful `web_fetch` of their own site, or (b) presence in a T1/T2 directory. Providers found only on Reddit, Quora or blog roundups, or whose official site is dead → dropped.

---

## 8. Deduplication

| Data type | Dedup key | Where enforced |
|---|---|---|
| `service_catalog_items` | `(category, external_id)` — UNIQUE constraint in Supabase | DB layer; upsert-on-conflict updates rather than inserts |
| Per-batch JSON (GCS) | `(provider_name, city, category)` | In-context during extraction |
| Cities already researched | City name in the `otto.md` "Delivered" list | I read `otto.md` before starting any batch |

**In-context dedup logic.** Before dispatching a new batch I check `otto.md` for the list of already-delivered cities and never dispatch a batch for a city already marked ✅. Within a batch, if two search results point to the same provider under slightly different names (e.g. "Crown Relocations" vs "Crown Worldwide"), I normalise to the official legal name from their own site.

**Cross-batch dedup gap.** I do not cross-check new batches against prior batches' JSON content. The DB UNIQUE constraint handles this at load time — if a provider appears in both a city batch and a Phase 1A backfill batch, the upsert updates rather than duplicates.

---

## 9. Memory (`otto.md`)

**What it is.** A flat Markdown file stored in the Audos platform (not in git). It is my persistent working memory across sessions. The founder can read it; it's formatted for human readability but primarily organised for me.

**Sections it contains**

- Company overview + key file paths + active branch
- Session-by-session findings (Stripe status, domain DNS, etc.)
- Research delivery log (each batch → GCS URL + row count)
- Open blockers + next actions
- Founder personalisation notes (how Romain wants me to behave)
- Standing process rules (e.g. "all future commit Tasks must target branch X")

**Read/write mechanism [AUDOS]**

- **Read:** `read_otto_notes(offset, maxChars)` — paginated; currently 85,941 chars → ~7 reads to cover fully.
- **Write:** `update_otto_notes(content)` — *full replace*. I must read current content, merge additions, then write back the whole document.

**Conflict detection.** Manual and in-context. I read `otto.md` before starting any new task and look for instructions that contradict the incoming request — e.g. "all Tasks must target branch X" vs. a new task saying "push to main" → I flag the conflict to the founder before acting. There is no automated conflict-detection system.

**Portable equivalent.** An `otto.md` file in a git repo (not committed to history — `.gitignore`'d, or a separate memory repo). The agent reads it at session start, updates in-context, writes back at session end. Key additions needed vs. Audos:

- A **read-at-startup hook** (Audos injects an excerpt automatically; outside Audos the agent must explicitly read it).
- A **write-at-checkpoint hook** (write after each significant decision, not only at end).
- A **conflict-check step**: before executing any task, grep `otto.md` for contradictory standing rules.

---

## 10. Persistence & delivery (`store_attachment`)

**Mechanism [AUDOS].** `store_attachment` is an Audos-managed GCS upload tool. I pass `filename` + `content` + `mimeType`; Audos handles auth internally (service account with write access to `gs://audos-images/`). I receive back a permanent public URL.

**URL structure**

```
https://storage.googleapis.com/audos-images/workspace-media/{workspaceId}/{timestamp_ms}_{random_8chars}.{ext}
```

Example:

```
https://storage.googleapis.com/audos-images/workspace-media/d0c29613-9cb5-4652-9c6a-494eeed352e5/1786521125498_lcj4pnfl.json
```

**Auth.** Not standard GCS client auth — Audos-internal. Cannot be reproduced from outside Audos. The resulting URL is public-read (no auth needed to fetch it).

**Known failure mode.** During this session `store_attachment` failed with `cannot execute INSERT in a read-only transaction` — a platform DB state issue, not a GCS issue. It cleared after ~30 minutes with no action. Audos-platform transient; nothing fixable from outside.

**Portable equivalent** — standard GCS client with a service account key:

```python
from google.cloud import storage

client = storage.Client()
bucket = client.bucket("your-deliverables-bucket")
blob = bucket.blob(f"research/{batch_id}/{filename}")
blob.upload_from_string(json_content, content_type="application/json")
url = blob.public_url  # or generate_signed_url() for private
```

AWS S3, Cloudflare R2 or any object store works identically. The only Audos-specific parts are the auth and the specific bucket.

---

## 11. Model & cost

**Which model I am.** Claude Sonnet 4.5 (as of 2026-08-12, per the system prompt header). Background agents spawned via `Agent(...)` are also Claude instances; the specific sub-agent model is not explicitly confirmed to me — likely the same, or Haiku for cheaper steps.

**Cost per step** (estimates, not metered)

| Step | Tokens (approx) | Notes |
|---|---|---|
| Planning + `otto.md` read | ~8k–15k input, ~1k output | `otto.md` is 85k chars; I read paginated excerpts |
| Per batch agent (70–85 rows) | ~30k–60k input, ~5k–10k output | Includes search snippets + fetched content + extraction |
| QA sweep (20 URLs) | ~10k–20k input | Fetch results + decision reasoning |
| `otto.md` write-back | ~15k–20k input (full doc), ~85k output (full doc write) | Expensive — should be incremental, not full-replace |

**Typical batch cost:** $0.50–2.00 per city-pair batch at Sonnet pricing (~$3/M input, $15/M output). 10 batches × ~$1 avg ≈ **$10 for 774 rows**. Estimate only; I have no metered billing data.

**Budget bounding.** I estimate before dispatching. For large runs (20+ batches) I check in with the founder at natural breakpoints rather than dispatching all at once.

---

## 12. Failure handling & resumability

**Checkpointing.** The GCS URL in `otto.md` *is* the checkpoint. Batch has a delivered URL → skip it. No URL → re-run it. This is manual: I check `otto.md` at session start, not automatically.

**Idempotency**

- **DB layer:** UNIQUE constraint on `(category, external_id)` → upsert on conflict → safe to re-run.
- **GCS layer:** no dedup; re-uploading a batch creates a new file at a new URL (old one orphaned but not deleted). Minor waste, not a correctness problem.
- **Extraction layer:** re-extract from scratch on failure — no partial-extraction checkpoint.

**Retry logic.** If `web_fetch` returns empty, retry once with the same URL, then fall back to an alternate URL for the same provider. No exponential backoff.

**Server restarts / session interrupts.** If an Audos session dies mid-run, sub-agents that completed will have persisted their GCS files; main-agent context is lost. Recovery: start a new session, read `otto.md` to see what was delivered, re-dispatch only the missing batches. **This is why writing `otto.md` after each batch is critical — I sometimes fail to write it promptly.**

**What I would change.** Write a checkpoint to `otto.md` after *every* batch completes (not at session end), using a `{batch_id: gcs_url}` map so recovery is an O(1) lookup.

---

## 13. Prompts & configuration

### (a) Research planning prompt — what I tell sub-agents

```
You are a research agent for ReloPass's service_catalog_items database.
Your job: produce verified provider rows for the cities [CITY_A] and [CITY_B].

TARGET CATEGORIES (geo-bound only — these require per-city providers):
- schools (international schools, IB/British curriculum preferred)
- movers (international relocation companies with local office/agent)
- living_areas (premium serviced/furnished apartments for expats)

TARGET CATEGORIES (geo-agnostic — do NOT create duplicate global entries):
- banks, insurance, electricity (research once, not per-city)

SOURCE TIER RULES:
- T1 only: the provider's own official website, OR a major industry
  association directory (FIDI for movers, IBO for schools, EuRA for
  relocation agents)
- T2 acceptable only if T1 not available: major aggregator directories
- T3 rejected: Reddit, Numbeo, generic expat blogs, TripAdvisor

FOR EACH CITY, FOR EACH GEO-BOUND CATEGORY:
1. web_search("[category] [city] [country]") and note candidate providers
2. For each candidate: web_search("provider_name official site [city]")
   to find their own domain
3. web_fetch their official URL to confirm it's real and city-specific
4. If 403/empty on web_fetch: try an alternate URL (/about, /contact)
   before marking as unconfirmed

OUTPUT: one JSON array per city following this schema:
[
  {
    "provider_name": "Official Name",
    "category": "movers",
    "city": "Oslo",
    "country": "Norway",
    "source_url": "https://example.com/",
    "source_tier": "T1",
    "confidence_score": 1.0,
    "notes": "FIDI member, FAIM certified"
  }
]

After generating, do a QA sweep: web_fetch each source_url. Any that
return dead/empty: find the real URL via web_search and replace, or drop
the row. Return: the final QA'd JSON array. Minimum 5 rows per category
per city; drop below 5 if you cannot find 5 real verified providers.

Do NOT fabricate any provider. Do NOT use a roundup blog as source_url.
If you can't find a provider's own site: use the IBO/FIDI directory page
for that provider as source_url (mark tier: T2).
```

### (b) Extraction prompt — regulatory/corridor content (used inline)

```
Extract from the following page text all facts relevant to
[REQUIREMENT_TYPE] for [EMPLOYEE_PROFILE] moving [CORRIDOR].

For each fact output:
{
  "requirement": "plain English description",
  "timeline_weeks_before_move": number or null,
  "responsible_party": "HR | employee | employer | both",
  "source_quote": "verbatim text from the page that states this fact",
  "source_url": "[url fetched]",
  "confidence": 0.0-1.0
}

Only include facts that appear verbatim in the source text.
Do NOT infer, extrapolate, or add facts from your training data.
If a fact is not stated explicitly on this page, omit it.
```

### (c) QA / verification prompt — standing instruction to sub-agents

```
After producing your JSON output, perform a URL QA sweep:

For each row in your output:
  1. web_fetch(source_url)
  2. If the page returns content confirming the provider/requirement → keep
  3. If web_fetch returns empty or error:
     a. Try web_fetch on the root domain or /about page
     b. If still empty: web_search("provider_name official website")
        and replace source_url
     c. If no confirmed URL found: drop the row entirely
  4. Anti-bot rule: if web_fetch returns a bot-challenge page or 403,
     that is NOT dead — mark confidence 0.85 (directory-confirmed)
     rather than 1.0, but keep the row

Report: (a) rows kept unchanged, (b) rows patched with new URL,
(c) rows dropped. Then output the final QA'd JSON only.
```

**Model settings.** I have no direct control over temperature or `max_tokens` — these are set by the Audos platform for my invocations. Based on output behaviour I estimate temperature ≈ 0.3–0.5 for extraction tasks (low-variance outputs). Exact values unknown to me.

---

## 14. Rebuild recommendation

### Recommended stack for ~80% capability parity

| Layer | Tool | Notes |
|---|---|---|
| Agent runtime | Claude API (`claude-sonnet-4-5` or newer) with `tool_use` | Direct Anthropic API; use streaming for long runs |
| Orchestration | Python `asyncio` + simple task queue (Redis + rq, or just `asyncio.gather`) | Replaces Audos job drafts. For durability: Celery or Temporal. |
| Search API | Brave Search API (`api.search.brave.com`) | ~$3/1k queries; clean JSON with URLs + snippets. Bing Search API is the alternative. |
| Page fetch/render | `httpx` (static) + Playwright (JS-heavy) | Playwright handles SPAs, `httpx` handles government pages. Rotating user-agent + 2–3s delay between fetches. |
| PDF parse | `pypdf` or `pdfplumber` | Feed extracted text to the LLM |
| Extraction | Claude `tool_use` with a Pydantic schema | Define the target schema as a Pydantic model, pass as JSON Schema in the tool definition; the LLM fills it |
| Storage | GCS or S3 (`google-cloud-storage` / `boto3`) | Standard client; public-read bucket for deliverable JSONs |
| Database | Supabase — existing schema: `service_catalog_items`, `crawled_source_documents`, `agent_runs` | Tables already exist. Use `supabase-py` or `psycopg2` directly. |
| Memory | An `otto.md` file in a private git repo, loaded at agent startup | Read at init, write at natural checkpoints and at shutdown |
| Scheduler | GitHub Actions (cron) or Cloud Scheduler | Trigger nightly re-crawl of `crawl_schedules` entries |
| Eval | Manual QA sweep (§7) + spot-check against live source URLs | No automated eval framework needed at this scale |

### Minimal working loop

```python
import asyncio
import json

from anthropic import AsyncAnthropic
from brave import BraveSearch       # pip install brave-search
import httpx

client = AsyncAnthropic()
search = BraveSearch(api_key="...")


async def research_batch(city: str, category: str) -> list[dict]:
    # 1. Search
    results = await search.search(f"{category} {city} official site")
    snippets = [r["url"] + ": " + r["snippet"] for r in results[:10]]

    # 2. Fetch top candidates
    fetched = []
    async with httpx.AsyncClient(timeout=15) as http:
        for url in [r["url"] for r in results[:5]]:
            try:
                resp = await http.get(url, headers={"User-Agent": "Mozilla/5.0"})
                fetched.append(f"URL: {url}\n{resp.text[:3000]}")
            except Exception:
                pass

    # 3. LLM extract
    msg = await client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": EXTRACTION_PROMPT.format(
                city=city, category=category,
                search_snippets="\n".join(snippets),
                page_content="\n\n---\n\n".join(fetched),
            ),
        }],
    )
    return json.loads(msg.content[0].text)


# Run batches in parallel
results = await asyncio.gather(*[
    research_batch(city, cat)
    for city, cat in [("Oslo", "schools"), ("Paris", "movers")]
])
```

### The 3 hardest parts to replicate

**1. Compound memory across sessions — HARDEST.** The Audos platform injects an excerpt of `otto.md` automatically at session start. Outside Audos you must build a read-at-startup hook, manage truncation/pagination yourself, and handle write-back races if multiple agents run concurrently. The current full-replace-on-every-write approach **breaks under concurrency** — you need a proper merge or a lock.

**2. JS-rendered page fetching.** `web_fetch` in Audos handles JS rendering transparently. Outside Audos you need Playwright (headless Chromium) configured with stealth mode (to avoid bot detection), a realistic user-agent pool, and careful rate limiting. Many government pages and corporate sites (e.g. French prefectures) are static HTML — but the harder ones (e.g. some Norwegian government portals) require JS. **Budget ~30% more development time for Playwright integration than you expect.**

**3. Regulatory content freshness / change detection.** The `crawled_source_documents` + `crawl_schedules` tables in the Supabase schema are the right design — they just need populating. The hard part isn't the crawl; it's (a) knowing which hash-change represents a material rule change vs. a website redesign, and (b) routing material changes to a lawyer-review step before updating the Case Command output. **This is a human-in-the-loop workflow problem, not a purely technical one.**

### What I would NOT bother replicating

- **The Audos job-drafts UI** — a simple CLI task runner (`python run_batch.py --cities "Oslo,Paris"`) achieves 90% of the same thing with 10% of the complexity. The visual draft board is founder UX, not capability.
- **Audos CRM / booster integration for research tasks** — irrelevant to the research loop; research output lands in Supabase and serves the FastAPI backend directly.
- **The full `otto.md` auto-injection** — an `agent_memory.py` loader that reads the memory file at startup and passes it as part of the system prompt achieves the same thing in ~20 lines of Python.

---

*End of document — 14 sections. The extraction prompts in §13 are the single most valuable element: they encode the source-tier discipline and the no-fabrication rule that distinguish this research from naive LLM generation.*
