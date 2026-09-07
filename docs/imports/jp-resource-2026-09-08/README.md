# jp-resource-2026-09-08 — re-source clearing a held fact

**Clears:** punch-list hold *"Japan — Dependent visa 28-hours/week part-time cap"* (not on the
originally-cited page).

**Landed:** JAPAN · EMPLOYMENT · 1 `requirement_item`, `review_status='pending'` (append-only).

## Fact
- key: `JP:employment:dependent_28_hours`
- title: Dependent visa: work capped at 28 hours/week with permission
- pillar / nationality: EMPLOYMENT / non-EEA
- source: https://www.moj.go.jp/isa/applications/procedures/nyuukokukanri07_00004.html
  (Immigration Services Agency — 資格外活動許可)
- quote: "１週について２８時間以内の収入を伴う事業を運営する活動（注）又は報酬を受ける活動を行う場合は、
  資格外活動の包括許可が必要となります。"

## Verification
`confirm_quotes.py` → **CONFIRMED** (1.0 bigram, exact) against the ISA page.

## Append-only
approved count unchanged (325), expert_verified 0, nationality scope guard green.
