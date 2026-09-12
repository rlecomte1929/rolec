# requirement_items changelog — rollback

Every catalog write that changes a tracked field (`description`, `severity`, `owner`,
`citations_json`, `non_obvious`, `timing`, `review_status`) inserts a row on
`public.requirement_item_changelog`. There is no UPDATE/DELETE on that table.

## How to revert a poisoned or mistaken requirement

1. `GET /api/admin/countries/{code}/requirements/{id}/changelog`
2. Pick the `change_id` whose `previous_value` is the last known-good snapshot.
3. Apply those fields through the **existing** admin / load path (review endpoint or a
   reviewed YAML load). That writes a **new** changelog row (`requirement_revised` or
   `severity_changed`). Do not UPDATE the history row.
4. If `review_status` was flipped, use Publish / Withhold — never a raw SQL overwrite of
   `requirement_items`.
5. Critical-severity diffs emit a process log warning (`critical-severity requirement change`).

## What this is not

WorkspaceDB `corridor_requirements_changelog` is the wrong store. ReloPass serves
`requirement_items`.
