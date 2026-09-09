# Import — Multi-Country Datasheet Export methodology (Otto)

**Date:** 2026-09-09 · **Source:** Otto/Audos meeting *"Multi-Country Datasheet Export Methodology"*
(workspace `d0c29613-…`) · **Consumed by:** `backend/app/services/datasheet_export.py` (Phase 3 export).

Otto produced the data-driven export methodology that lets **"add a country" stay data-only**: a
canonical export schema + a per-country channel decision + per-country content. These files were
authored by Otto as ReloPass editorial assessment and are **NOT lawyer-verified**
(`lawyer_verified: false` throughout) — treat as representative until counsel sign-off.

## Files (under `data/`)

| File | Records / shape | Purpose |
|---|---|---|
| `export-channels.json` | 3 country blocks (NO, DE, FR) | `country_iso → export_channel` (`acroform` / `render_data_sheet` / `portal_only`) + portal metadata. All three are `render_data_sheet` (no fillable government AcroForm). |
| `export-schema.json` | 25 CSV columns, PDF section layout, `fact_key_conventions` | The canonical export shape — fixed across corridors; country content populates it. |
| `corridor-content/NO.ndjson` | 10 records | Per-step content: `section`, `step`, `authority`, `field_label`, `fact_key`, `deadline_*`, `responsible_party`, `is_non_obvious` + the `official_guidance/actual_reality/action_required/source` framework. |
| `corridor-content/DE.ndjson` | 8 records | same, Germany |
| `corridor-content/FR.ndjson` | 8 records | same, France |

Record counts reconcile against Otto's informal manifest (NO=10, DE=8, FR=8).

## Capture note (why a repair step was needed)

Otto delivered the files **inline in chat** (its GCS/attachment store path was unavailable). Audos's
code-block renderer **auto-linkified URLs**, corrupting the JSON (`"url": "www.udi.no"}` rendered as
`"url": "[www.udi.no"}/](https://www.udi.no"})`). Capture + repair:

1. Bundled the five `<pre>` blocks into a Blob and downloaded it (byte-exact vs the rendered DOM).
2. Reversed the linkification by rebuilding each URL from the markdown **href** (which carries the
   full URL + the real JSON delimiter), discarding the mangled/truncated display.
3. Validated: all five files parse; record counts match the manifest; zero `](` artifacts remain.

The only lossy field is the occasional URL that Otto truncated in the display with `…`; those were
recovered from the href, so the stored URL is the full `https://` form.

## Adding a country later (data-only)

Write `data/corridor-content/{ISO}.ndjson` following the same record shape and add a block to
`data/export-channels.json`. No code change: `datasheet_export.resolve_export_channel` reads the
channels file, and the renderer iterates corridor content by `country_iso`.
