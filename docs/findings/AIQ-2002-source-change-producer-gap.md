# AIQ-2002 — the `source_change_reviews` producer gap is not a missing function

**Date:** 2026-08-19 · **Verdict:** do not build the producer yet · **Status:** needs a human decision

The task asked me to persist a `source_change_reviews` row when the classifier judges a diff
material — *or*, if that omission turns out to be deliberate, to write an evidenced finding
instead and **not invent a producer**. This is that finding.

The omission is not deliberate. But writing the glue today would produce a code path that
**still cannot fire**, because three of its four inputs do not exist. The gap is upstream.

---

## 1. What was actually built, and what wasn't

`source_change_classifier.py` (P2-02b / AIQ-690) is a pure, deterministic material-vs-cosmetic
classifier. Its own docstring names the missing piece:

> "The caller (the change-detection / pipeline glue, **a later subtask**) supplies the old and
> new extracted page text. This module deliberately does not read storage or the DB itself."

`grep` for `classify_diff` across the repo returns **its own test file and nothing else**. The
"later subtask" never landed. The classifier has never run in production.

`source_change_reviews` (P2-02d / AIQ-692) is the admin review queue that classifier was meant to
feed. Verified in prod 2026-08-19: **0 rows, ever**.

## 2. What the live pipeline does instead

The crawl pipeline *is* live — `crawl_scheduler_service.py:505` calls
`run_change_detection_for_crawl_run` (4 crawl runs, 15 documents, 9 change events). But it
classifies **without reading the text**:

```python
if prev_hash == new_hash:   change_type = "unchanged"
else:                       change_score = 0.5
                            if prev.page_title != doc.page_title: change_score = 0.8
                            change_type = "significant_change" if change_score >= 0.5 else "minor_change"
```

`change_score` is never below 0.5 on the else branch, so **every** content change is
`significant_change` and `minor_change` is unreachable. Confirmed empirically against the 9 live
events: `new`=5, `unchanged`=2, `significant_change`=2 (score exactly 0.5), **`minor_change`=0**. It writes `document_change_events`, not
`source_change_reviews`. The rule-aware classifier that would tell a fee change from a footer
timestamp is sitting unused next to it.

## 3. The three blockers that make the glue unbuildable today

### 3a. There is no text to classify

`classify_diff(old_text, new_text)` needs both documents' text.
`crawled_source_documents` has **no text column** — only `storage_path` and `content_hash`:

```
id, crawl_run_id, source_name, source_url, final_url, country_code, city_name, source_type,
trust_tier, content_type, content_hash, fetched_at, storage_path, page_title, language_code,
http_status, parse_status, extraction_status, created_at
```

And `extraction_status` is **`pending` on all 15 documents** — extraction has never run on
anything. So the text is neither in the row nor demonstrably in storage in extracted form.

### 3b. A review row cannot be constructed — `rule_version_id` is NOT NULL, and nothing joins

`source_change_reviews.rule_version_id uuid NOT NULL`. Rule versions live in `rce.rule_versions`
and carry a `source_url`, so `source_url` is the natural join. Measured:

| | |
|---|---|
| `rce.rule_versions` rows | 34 (all with a `source_url`) |
| distinct crawled URLs | 11 |
| **crawled URL matching any rule_version `source_url`** | **0** |

Zero overlap. There is no rule version any crawled document could be attributed to, so no review
row can satisfy the NOT NULL constraint.

### 3c. The crawler is storing bot-block pages as source documents

Six of the fifteen documents have `page_title = "Radware Captcha Page"` at
`validate.perfdrive.com/?ssa=…` — for sources `make_it_in_germany_health` and
`make_it_in_germany_living`. They are recorded with `http_status: 200` and
`parse_status: "parsed"`.

The crawler is being bot-blocked, receiving the interstitial, and **storing it as the source
document while reporting success**. Any diff computed against those rows compares one CAPTCHA
page to another.

The nine non-blocked documents are generic landing pages (`ruter.no/en`,
`oslo.kommune.no/english`, `make-it-in-germany.com/en/living-in-germany`), not the specific rule
pages the 34 rule versions cite.

## 4. Why this matters beyond this ticket

AIQ-2005 (attested → stale invalidation) and AIQ-1985 (per-requirement freshness + staleness
queue) both consume drift as their signal. On today's pipeline that signal is: mostly CAPTCHA
pages, never extracted, attributable to no rule version. Building either on top would ship a
monitoring feature that reports "nothing has changed" indefinitely — which is
indistinguishable, from the outside, from everything being fresh.

That is the failure mode worth naming: **a silent, confident "all clear" from a pipeline that is
not actually looking at the sources.**

## 5. What has to happen first

In dependency order:

1. **Fix the crawl targets.** Point the crawler at the URLs the 34 `rce.rule_versions` actually
   cite, so a change event can be attributed to a rule version at all.
2. **Fix the bot-blocking** — or fail loudly. A `validate.perfdrive.com` response must not be
   stored with `parse_status='parsed'`; it should be recorded as a fetch failure so the corpus
   is not quietly poisoned.
3. **Run extraction.** `extraction_status` must reach a terminal state and the extracted text
   must be reachable, or `classify_diff` has no input.
4. **Then** wire the glue: `run_change_detection_for_crawl_run` → `classify_diff(old, new)` →
   on material, insert `source_change_reviews` (rule_version_id, old_excerpt, new_excerpt,
   changed_sections). This is the small part, and it is the last part.

Step 4 is roughly a day. Steps 1–3 are the actual project.

## 6. What I did not do

I did not add an insert to `run_change_detection_for_crawl_run`. It would have passed a unit test
with hand-fed text, merged green, and produced zero rows in production forever — the same class of
defect as the feature this ticket was opened to protect.

---

### Evidence index (all verified 2026-08-19, prod `nsvefcvpvwwwhuqyuqmp`)

| claim | check |
|---|---|
| classifier never called in prod | `grep -rn classify_diff` → test file only |
| review queue empty | `SELECT count(*) FROM source_change_reviews` → 0 |
| pipeline live | `crawl_runs` 4 · `crawled_source_documents` 15 · `document_change_events` 9 |
| no text column | `information_schema.columns` on `crawled_source_documents` |
| extraction never ran | `extraction_status = 'pending'` on 15/15 |
| no rule-version linkage | join on `source_url` → 0 matches against 34 rule_versions |
| bot-blocked crawls | 6/15 rows `page_title = 'Radware Captcha Page'`, `http_status` 200, `parse_status` 'parsed' |
| `minor_change` unreachable | 9 live events: new=5, unchanged=2, significant_change=2, minor_change=**0** |
