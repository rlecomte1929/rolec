# Epic B — CONTENT TASKS (area sweeps; parallel-safe across disjoint files)

> Read `docs/epic-b/SHARED.md` first. Each task = one Conductor agent's SCOPE. Counts are a 2026-06-27
> snapshot (873 total / 131 files); RE-MEASURE live at the start of your task.

**MEASURE COMMAND (run for your area; "AREA" = your glob, e.g. `src/pages/admin`):**
```
RULES='{"@typescript-eslint/no-unsafe-member-access":"error","@typescript-eslint/no-unsafe-assignment":"error","@typescript-eslint/no-unsafe-call":"error","@typescript-eslint/no-unsafe-return":"error","@typescript-eslint/no-unsafe-argument":"error","@typescript-eslint/no-explicit-any":"error","@typescript-eslint/no-base-to-string":"error","@typescript-eslint/restrict-template-expressions":"error"}'
npx eslint AREA --rule "$RULES" --format json > /tmp/b.json 2>/dev/null
node -e "const r=require('/tmp/b.json');const c={};let t=0;for(const f of r)for(const m of f.messages){c[f.filePath.split('/frontend/src/')[1]]=(c[f.filePath.split('/frontend/src/')[1]]||0)+1;t++;}console.log('TOTAL',t);Object.entries(c).sort((a,b)=>b[1]-a[1]).forEach(([k,n])=>console.log(' ',n,k));"
```
Your task SUCCESS = this prints `TOTAL 0` for your area + SHARED Definition of Done (tsc 0, build, tests, PR merged).

---

## TASK CLIENT — `api/client.ts` + `api/rpc.ts` (~241). DEDICATED track (shared file — do NOT run another client-touching agent in parallel)
- Biggest single concentration. Many methods already DECLARE return types and just need the generic on the
  `api.get/post/...` call (see merged `adminFormTemplatesAPI`). Others need `<unknown>` + wrapper types.
- If the PR gets large, split into method-group sub-PRs (e.g. one per `xAPI = {…}` block) and land them
  sequentially. SUCCESS: `api/client.ts` + `api/rpc.ts` target-rule count = 0 + SHARED DoD. May auto-merge on green.

## TASK ADMIN — `src/pages/admin/**` (~105 post test-relax)
- Hotspots: AdminMessages (~20), AdminUsers (~13), AdminFormTemplateEditor, AdminSupplierDetail, AdminResearch.
- Per SHARED patterns: type `useState<any>`/`: any` callbacks, narrow `catch (err: any)`, cast loose API
  results to local types. SUCCESS: `src/pages/admin` target count = 0 + DoD. May auto-merge.

## TASK POLICY — `src/features/policy/**` (non-test) (~78)
- Hotspots: hrPolicyReviewFormatters (~16), PolicyBenefitsTable (~14), policy formatters/panels. Reuse
  `features/policy/types.ts`. SUCCESS: `src/features/policy` (excluding `__tests__`) target count = 0 + DoD.

## TASK EMPLOYEE — `src/pages/employee/**` (~52)
- Hotspot: CaseWizardPage (~17). Reuse the wizard/case types. SUCCESS: `src/pages/employee` count = 0 + DoD.

## TASK PLATFORM — `src/features/platform-v2/**` (~44)
- Hotspot: hr-dossier/HrCaseFormRow (~12). SUCCESS: `src/features/platform-v2` count = 0 + DoD.

## TASK POLICY-BUILDER — `src/features/policy-builder/**` (non-test) (~22)
- Reuse `features/policy/types.ts` + the Supabase-client typing pattern. SUCCESS: that area (excluding
  `__tests__`) count = 0 + DoD.

## TASK COMPONENTS — `src/components/**` (~50)
- Hotspots: RichCommuteMap (~18), guidance/GuidancePackPanel (~19). NOTE `components/**` shared primitives —
  if you change a widely-used component's prop types, verify a couple consumers still tsc-compile. SUCCESS:
  `src/components` count = 0 + DoD.

## TASK MISC — the long tail (everything not in the areas above)
- e.g. `features/messages/utils`, `pages/HrCaseSummary`, `pages/HrPolicyManagement`, `features/recommendations`,
  `features/timeline`, `pages/Hr*`. Re-measure `src` minus the other areas. SUCCESS: those files' count = 0 + DoD.

> Coordination: TASK CLIENT is the only one that may conflict with others (consumers cast the client's result,
> so they're compatible, but if two agents edit `client.ts` they collide). Everything else touches disjoint
> files → safe in parallel.
