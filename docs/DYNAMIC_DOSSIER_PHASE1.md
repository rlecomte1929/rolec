## Dynamic Dossier Phase 1

Feature-flagged Step 5 enhancement that asks destination-specific dossier questions and stores answers.

### Enable the feature

Set the feature flag in the frontend environment:

```
VITE_FEATURE_DYNAMIC_DOSSIER=true
```

Optional compatibility:
```
NEXT_PUBLIC_FEATURE_DYNAMIC_DOSSIER=true
```

### Optional search suggestions (Phase 1)

Search is used only to **suggest** extra questions and always shows source URLs.

Provide a SerpAPI key if you want external search:

```
SERPAPI_API_KEY=your_key
```

If no key is configured, the `/api/dossier/search-suggestions` endpoint returns an empty list without error.

### Notes

- Questions are seeded for SG/US only in `supabase/migrations/20260228010000_dynamic_dossier_phase1.sql`.
- Additional case-specific questions are stored per case when the user clicks “Add this question”.
