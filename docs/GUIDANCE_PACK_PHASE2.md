## Guidance Pack Phase 2 (Option A)

Feature-flagged generation of a plan + checklist + markdown guide from curated knowledge packs.

### Enable backend

```
GUIDANCE_PACK_ENABLED=true
```

### Enable frontend

```
NEXT_PUBLIC_FEATURE_GUIDANCE_PACK=true
```

### Seed data

Run the migration:

- `supabase/migrations/20260228020000_guidance_pack_phase2.sql`

The seed includes minimal SG/US knowledge packs with official sources only.

### Notes

- Guidance uses curated knowledge packs only (no live web search in generation).
- Missing coverage is explicitly listed under “Not covered / needs confirmation”.
- No numeric tax thresholds are included.
