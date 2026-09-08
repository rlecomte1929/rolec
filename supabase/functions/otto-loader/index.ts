// otto-loader v6 — tolerant loader across Otto's heterogeneous file schemas.
// v6 changes vs v5:
//   1. fact text also read from `fact_value` (wave 3a/3c schema) — was silently dropping 202 facts.
//   2. manifest rows also read from the `manifest` key (master manifest v2) — was a silent no-op.
//   3. readiness_templates routed (opt-in via ?tables=, NOT included in "all" — it is a live
//      product table, not a pending-candidate staging table).
// Fact text: fact_text|body|requirement|text|fact_value. Topic: topic_key|entity.topic_key|domain(synth).
// Vendor name: name|vendor_name|provider_name|company. dry_run=false inserts (status='pending').
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// ─── auth ────────────────────────────────────────────────────────────────────
// This function is deployed with `verify_jwt: false`, so Supabase's own gate is OFF and this
// check is the ONLY thing between the open internet and a handler holding
// SUPABASE_SERVICE_ROLE_KEY (which bypasses every RLS policy).
//
// The token used to be a string literal in this file, passed as `?token=…`. Two problems:
// a query parameter lands in Supabase's request logs and every proxy in between, and `!==`
// on a secret leaks length and prefix through timing. It now comes from the environment and
// arrives in a header.
//
// ⚠ BREAKING FOR CALLERS, deliberately: the old literal is burned and must be rotated, so
// every caller has to change anyway. Send `x-otto-token: <secret>` instead of `?token=…`.
// Compat (2026-08-19): the secret is also accepted from `Authorization: Bearer <secret>` for
// callers whose proxy can only inject the Authorization header. Same secret, same constant-time
// compare; `?token=…` stays unsupported.
const TOKEN = Deno.env.get("OTTO_LOADER_TOKEN") ?? "";

/** Constant-time string compare. Returns false on any length difference. */
function safeEqual(a: string, b: string): boolean {
  const ea = new TextEncoder().encode(a);
  const eb = new TextEncoder().encode(b);
  if (ea.length !== eb.length) return false;
  let diff = 0;
  for (let i = 0; i < ea.length; i++) diff |= ea[i] ^ eb[i];
  return diff === 0;
}

// ─── SSRF containment ────────────────────────────────────────────────────────
// `manifest` is caller-supplied and every row inside it names another URL that this function
// then fetches — so an attacker past the token controls the whole fan-out, not just one
// request. Hostname allowlisting is the strongest available control here because the real
// data lives in exactly one place; combined with `redirect: "manual"` it also closes the
// DNS-rebind and redirect-to-internal routes without needing IP-range checks.
const ALLOWED_FETCH_HOSTS = new Set(["storage.googleapis.com"]);
const MAX_FETCH_BYTES = 32 * 1024 * 1024;

function assertFetchableUrl(raw: string): URL {
  let u: URL;
  try {
    u = new URL(raw);
  } catch {
    throw new Error("url rejected: unparseable");
  }
  if (u.protocol !== "https:") throw new Error("url rejected: https required");
  // Exact hostname match, never startsWith — `storage.googleapis.com.evil.tld` would pass a
  // prefix test.
  const host = u.hostname.toLowerCase();
  const ok = ALLOWED_FETCH_HOSTS.has(host) ||
    [...ALLOWED_FETCH_HOSTS].some((h) => host.endsWith(`.${h}`));
  if (!ok) throw new Error("url rejected: host not allowlisted");
  if (u.username || u.password) throw new Error("url rejected: credentials in url");
  return u;
}

const SCAFFOLD_PACK_ID = "2515da7d-02ab-40d0-af7b-a552d52fc6b9";
const SCAFFOLD_DOC_SENTINEL = "otto://research-intake/pending";

const ALLOWED_DOMAINS = new Set(["immigration","registration","tax","social_security","healthcare","housing","other","vehicle","vehicle_import","domestic_move","financial","employer_compliance","pet"]);
const FACT_TYPES = new Set(["eligibility","document","step","deadline","fee","where_to_apply","account","other"]);

const SB_URL = Deno.env.get("SUPABASE_URL")!;
const SB_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const sb = createClient(SB_URL, SB_KEY, { auth: { persistSession: false } });

const CN: Record<string,string> = {
  "united states":"US","usa":"US","united kingdom":"GB","uk":"GB","great britain":"GB","germany":"DE","france":"FR",
  "spain":"ES","italy":"IT","norway":"NO","sweden":"SE","netherlands":"NL","ireland":"IE","switzerland":"CH","austria":"AT",
  "belgium":"BE","denmark":"DK","portugal":"PT","canada":"CA","australia":"AU","new zealand":"NZ","japan":"JP","singapore":"SG",
  "united arab emirates":"AE","uae":"AE","poland":"PL","south korea":"KR","korea":"KR","india":"IN","china":"CN","brazil":"BR",
  "mexico":"MX","hong kong":"HK","ukraine":"UA","russia":"RU","israel":"IL","south africa":"ZA","czechia":"CZ","czech republic":"CZ",
};
function cleanCode(s: string): string { let o = ""; for (const ch of s) { if ((ch >= "A" && ch <= "Z") || (ch >= "a" && ch <= "z")) o += ch; } return o; }
function iso2(v: any): string | null {
  if (v == null) return null;
  const s = String(v).trim(); if (!s) return null;
  if (s.length === 2) return s.toUpperCase();
  const m = CN[s.toLowerCase()]; if (m) return m;
  const c = cleanCode(s); if (c.length === 2) return c.toUpperCase(); if (c.length === 3) return c.toUpperCase();
  return null;
}
function numConf(v: any): number | null {
  if (typeof v === "number") return Math.max(0, Math.min(1, v));
  if (typeof v === "string") { if (/^[0-9.]+$/.test(v)) return Math.max(0, Math.min(1, parseFloat(v))); const m: Record<string,number> = {high:0.9,medium:0.7,low:0.5}; return m[v.toLowerCase()] ?? null; }
  return null;
}
function confBucket(v: any): string { const n = numConf(v); if (n == null) return "medium"; if (n >= 0.85) return "high"; if (n >= 0.6) return "medium"; return "low"; }
function tierInt(v: any): number | null { if (v == null) return null; if (typeof v === "number") return Math.max(1, Math.min(3, Math.round(v))); const m = String(v).match(/([1-3])/); return m ? parseInt(m[1]) : null; }
function factType(v: any): string { const s = String(v||"").toLowerCase(); if (FACT_TYPES.has(s)) return s; if (s === "timeline") return "deadline"; return "other"; }
function mapDomain(v: any): string { const s = String(v||"immigration").toLowerCase(); return ALLOWED_DOMAINS.has(s) ? s : "other"; }
const entObj = (r: any) => (r.entity && typeof r.entity === "object") ? r.entity : {};
// v6 fix 1: accept fact_value
const factText = (r: any) => r.fact_text || r.body || r.requirement || r.text || r.fact_value || null;
const factDomain = (r: any) => mapDomain(entObj(r).domain_area || r.domain_area || r.domain || "immigration");
const factTopic = (r: any) => r.topic_key || entObj(r).topic_key || factDomain(r);
const factKey = (r: any) => r.fact_key || (r.dedupe_key ? String(r.dedupe_key).split("|").pop() : null) || (r.fact_type ? String(r.fact_type) : "fact");
const vendorName = (r: any) => r.name || r.vendor_name || r.provider_name || r.company || null;
function factDest(r: any): string | null {
  const e = entObj(r);
  let c = iso2(e.destination_country) || iso2(r.destination_country) || iso2(r.destination_country_code); if (c) return c;
  const dk = r.dedupe_key ? String(r.dedupe_key).split("|")[0] : ""; if (dk) { const seg = dk.includes("-") ? dk.split("-").pop() : dk; c = iso2(seg); if (c) return c; }
  const corr = r.corridor ? String(r.corridor) : ""; if (corr) { const seg = corr.includes("-") ? corr.split("-").pop() : corr; c = iso2(seg); if (c) return c; }
  return null;
}
async function fetchJson(u: string): Promise<any> {
  const url = assertFetchableUrl(u);
  // `manual` so a 3xx to an internal address is refused rather than followed. Without this
  // the allowlist only guards the first hop.
  const r = await fetch(url, { redirect: "manual" });
  if (r.status >= 300 && r.status < 400) throw new Error("redirect refused");
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const len = Number(r.headers.get("content-length") ?? "0");
  if (len > MAX_FETCH_BYTES) throw new Error("response too large");
  const body = await r.text();
  if (body.length > MAX_FETCH_BYTES) throw new Error("response too large");
  return JSON.parse(body);
}
function chunk<T>(a: T[], n: number): T[][] { const o: T[][] = []; for (let i = 0; i < a.length; i += n) o.push(a.slice(i, i + n)); return o; }
async function pagedSet(table: string, cols: string, keyFn: (r: any) => string, filter?: (q: any) => any): Promise<Set<string>> {
  const set = new Set<string>(); let from = 0; const page = 1000;
  for (;;) { let q = sb.from(table).select(cols).range(from, from + page - 1); if (filter) q = filter(q); const { data, error } = await q; if (error) throw new Error(`${table}: ${error.message}`); if (!data || !data.length) break; for (const r of data) set.add(keyFn(r)); if (data.length < page) break; from += page; }
  return set;
}
async function existingFactKeys(): Promise<Set<string>> {
  const set = new Set<string>(); let from = 0; const page = 1000;
  for (;;) { const { data, error } = await sb.from("requirement_facts").select("fact_key, entity:requirement_entities!inner(destination_country,topic_key)").range(from, from + page - 1); if (error) throw new Error(`facts join: ${error.message}`); if (!data || !data.length) break; for (const r of data as any[]) { const e = Array.isArray(r.entity) ? r.entity[0] : r.entity; set.add(`${e?.destination_country}|${e?.topic_key}|${r.fact_key}`); } if (data.length < page) break; from += page; }
  return set;
}

Deno.serve(async (req) => {
  const p = new URL(req.url).searchParams;
  // Fail CLOSED when the secret is unset. An empty TOKEN with a `!==` check would have made
  // every request with no header succeed.
  if (!TOKEN) {
    console.error("otto-loader: OTTO_LOADER_TOKEN is not set — refusing all requests");
    return json({ ok: false, error: "unauthorized" }, 401);
  }
  // Accept the secret from x-otto-token (canonical) OR Authorization: Bearer <secret>, so a
  // caller whose proxy can only set the Authorization header still authenticates. Same
  // constant-time compare; a query-param token stays unsupported.
  const xOttoToken = req.headers.get("x-otto-token") ?? "";
  const bearerToken = (req.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "");
  const presentedToken = xOttoToken !== "" ? xOttoToken : bearerToken;
  if (!safeEqual(presentedToken, TOKEN)) {
    return json({ ok: false, error: "unauthorized" }, 401);
  }
  // Params come from the query string, with a JSON POST body as fallback — some callers (e.g.
  // the Audos Bridge proxy) can only send a body, not a query string. Body is read only AFTER
  // auth passes, and a malformed body is ignored rather than trusted.
  let body: any = {};
  if (req.method !== "GET" && req.method !== "HEAD") {
    try { const t = await req.text(); if (t) { const parsed = JSON.parse(t); if (parsed && typeof parsed === "object") body = parsed; } } catch { /* ignore malformed body */ }
  }
  const param = (k: string) => { const v = p.get(k); return v !== null ? v : body[k]; };

  // Accept the manifest URL from ?manifest=, then common body keys, then any allowlisted URL
  // found anywhere in the body — so a caller that puts the GCS link in the body under any name
  // still works. The host allowlist below is still enforced, so this widens input, not trust.
  let manifest = String(param("manifest") ?? body.manifest_url ?? body.url ?? body.gcs_url ?? "");
  if (!manifest) {
    for (const v of Object.values(body)) {
      if (typeof v === "string" && /^https:\/\/([a-z0-9-]+\.)?storage\.googleapis\.com\//i.test(v)) { manifest = v; break; }
    }
  }
  if (!manifest) return json({ ok: false, error: "manifest required" }, 400);
  // Reject a bad manifest URL before any network call, and say only that it was rejected —
  // echoing the parser's reason back turns this into an SSRF oracle.
  try { assertFetchableUrl(manifest); } catch {
    return json({ ok: false, error: "manifest url rejected" }, 400);
  }
  const dryRun = String(param("dry_run") ?? "true") !== "false";
  const tf = String(param("tables") ?? "all").toLowerCase();
  const want = (t: string) => tf === "all" || tf.split(",").includes(t);
  // readiness_templates is a LIVE product table, not a pending-candidate staging table.
  // It is never included in "all" — it must be named explicitly via ?tables=readiness_templates
  const wantRT = tf.split(",").includes("readiness_templates");
  const limitFiles = parseInt(String(param("limit_files") ?? "0")) || 0;

  const R: any = { ok: true, loader_version: 6, dry_run: dryRun, manifest, files_total: 0, files_fetched: 0, files_failed: [] as any[],
    by_table: {
      requirement_entities: { seen: 0, mapped_new: 0, dup_existing: 0, inserted: 0, errors: [] as any[] },
      requirement_facts: { seen: 0, mapped_new: 0, dup_existing: 0, dup_in_batch: 0, skip_no_source: 0, skip_no_dest: 0, skip_no_text: 0, skip_no_entity: 0, inserted: 0, errors: [] as any[] },
      pet_import_rules: { seen: 0, groups: 0, new_rows: 0, merge_existing: 0, inserted: 0, updated: 0, errors: [] as any[] },
      vendor_candidates: { seen: 0, mapped_new: 0, dup_existing: 0, dup_in_batch: 0, skip_no_name: 0, inserted: 0, errors: [] as any[] },
      staged_resource_candidates: { seen: 0, mapped_new: 0, dup_existing: 0, dup_in_batch: 0, inserted: 0, errors: [] as any[] },
      readiness_templates: { seen: 0, mapped_new: 0, dup_existing: 0, dup_in_batch: 0, skip_incomplete: 0, inserted: 0, opt_in: wantRT, errors: [] as any[] },
      unrouted: { seen: 0, tables: {} as Record<string, number> },
    } };

  let man: any;
  try {
    man = await fetchJson(manifest);
  } catch (e) {
    // Detail to the server log, a fixed string to the caller. The old version returned the
    // raw error, which reports connection-refused vs timeout vs 404 and so answers "what is
    // listening on this address" for anything the allowlist ever let through.
    console.error("otto-loader: manifest fetch failed", String(e));
    return json({ ok: false, error: "manifest fetch failed" }, 502);
  }
  // v6 fix 2: also accept the `manifest` key (master manifest v2 shape)
  const rawRows = man.manifest_rows || man.files || man.manifest || [];
  let rows: any[] = (Array.isArray(rawRows) ? rawRows : []).filter((r: any) => r && (r.gcs_url || r.url || r.file_url || typeof r === "string"));
  if (limitFiles) rows = rows.slice(0, limitFiles);
  R.files_total = rows.length;

  const ex: any = {};
  try {
    if (want("requirement_entities") || want("requirement_facts")) ex.entKeys = await pagedSet("requirement_entities", "destination_country,topic_key", (r) => `${r.destination_country}|${r.topic_key}`);
    if (want("requirement_facts")) ex.factKeys = await existingFactKeys();
    if (want("vendor_candidates")) ex.vendor = await pagedSet("vendor_candidates", "dedupe_key", (r) => r.dedupe_key, (q) => q.not("dedupe_key", "is", null));
    if (want("pet_import_rules")) ex.pet = await pagedSet("pet_import_rules", "destination_country_code,species", (r) => `${(r.destination_country_code||"").trim()}|${r.species}`);
    if (want("staged_resource_candidates")) ex.res = await pagedSet("staged_resource_candidates", "country_code,city_name,category_key,title", (r) => `${r.country_code}|${r.city_name}|${r.category_key}|${r.title}`);
    if (wantRT) ex.rt = await pagedSet("readiness_templates", "destination_key,route_key", (r) => `${r.destination_key}|${r.route_key}`);
  } catch (e) {
    // Not an SSRF oracle like the fetch paths, but a Postgres error string names tables and
    // constraints. Log it, return a fixed string.
    console.error("otto-loader: preload failed", String(e));
    return json({ ok: false, error: "preload failed" }, 500);
  }

  const entityMap = new Map<string, any>();
  const facts: any[] = [];
  const petMap = new Map<string, any[]>();
  const vendors: any[] = [];
  const resources: any[] = [];
  const templates: any[] = [];
  const seenFact = new Set<string>(), seenVendor = new Set<string>(), seenRes = new Set<string>(), seenRT = new Set<string>();

  const CONC = 8;
  for (let i = 0; i < rows.length; i += CONC) {
    const results = await Promise.allSettled(rows.slice(i, i + CONC).map((row: any) => { const fu = typeof row === "string" ? row : (row.gcs_url || row.url || row.file_url); return fetchJson(fu).then((data) => ({ row, data })); }));
    for (const res of results) {
      if (res.status === "rejected") {
        // Same reasoning as the manifest fetch: the reason goes to the log, a coarse label to
        // the caller. A rejected row is usually a rejected URL, and the rejection reason
        // ("host not allowlisted" vs "HTTP 500") is exactly the probe signal to withhold.
        console.error("otto-loader: file fetch failed", String(res.reason));
        R.files_failed.push(
          String(res.reason).startsWith("Error: url rejected") ? "url rejected" : "fetch failed",
        );
        continue;
      }
      R.files_fetched++;
      const recs = Array.isArray(res.value.data) ? res.value.data : [res.value.data];
      for (const rec of recs) {
        const tt = String(rec?.target_table || (typeof res.value.row === "object" ? res.value.row.target_table : "") || "").toLowerCase();
        if (tt.includes("readiness_template")) {
          const T = R.by_table.readiness_templates; T.seen++;
          if (!wantRT) continue;
          const dest = iso2(rec.destination_key || rec.destination_country || rec.country || rec.country_code);
          const route = rec.route_key || rec.route || null;
          if (!dest || !route) { T.skip_incomplete++; continue; }
          const k = `${dest}|${route}`;
          if (ex.rt?.has(k)) { T.dup_existing++; continue; }
          if (seenRT.has(k)) { T.dup_in_batch++; continue; } seenRT.add(k);
          templates.push({ destination_key: dest, route_key: route, route_title: rec.route_title || rec.title || null, employee_summary: rec.employee_summary || null, hr_summary: rec.hr_summary || null, internal_notes_hr: rec.internal_notes_hr || null, watchouts_json: rec.watchouts_json || rec.watchouts || {} });
          T.mapped_new++; continue;
        }
        if (tt.includes("requirement_entit") && want("requirement_entities")) {
          const T = R.by_table.requirement_entities; T.seen++;
          const cc = iso2(rec.destination_country || rec.destination_country_code), topic = rec.topic_key; if (!cc || !topic) continue;
          const k = `${cc}|${topic}`; if (!entityMap.has(k)) { entityMap.set(k, { destination_country: cc, domain_area: mapDomain(rec.domain_area || rec.domain), topic_key: topic, title: rec.title || `${cc} ${topic}`, status: "pending" }); if (!ex.entKeys?.has(k)) T.mapped_new++; else T.dup_existing++; }
          continue;
        }
        if (tt.includes("requirement_fact") && want("requirement_facts")) {
          const T = R.by_table.requirement_facts; T.seen++;
          const cc = factDest(rec); const txt = factText(rec);
          if (!rec.source_url) { T.skip_no_source++; continue; }
          if (!cc) { T.skip_no_dest++; continue; }
          if (!txt) { T.skip_no_text++; continue; }
          const topic = factTopic(rec), fk = factKey(rec), dom = factDomain(rec);
          const bkey = `${cc}|${topic}|${fk}|${JSON.stringify(rec.applies_to||{})}`;
          if (seenFact.has(bkey)) { T.dup_in_batch++; continue; } seenFact.add(bkey);
          if (ex.factKeys?.has(`${cc}|${topic}|${fk}`)) { T.dup_existing++; continue; }
          const ek = `${cc}|${topic}`; if (!entityMap.has(ek)) entityMap.set(ek, { destination_country: cc, domain_area: dom, topic_key: topic, title: entObj(rec).title || rec.title || `${cc} ${topic}`, status: "pending" });
          facts.push({ cc, topic, row: { fact_type: factType(rec.fact_type), fact_key: fk, fact_text: txt, applies_to: rec.applies_to || (rec.route ? { route: rec.route } : {}), required_fields: rec.required_fields || [], source_url: rec.source_url, evidence_quote: rec.source_quote || rec.evidence_quote || null, confidence: confBucket(rec.confidence_score), status: "pending" } });
          T.mapped_new++; continue;
        }
        if (tt.includes("pet_import") && want("pet_import_rules")) {
          const cc = iso2(rec.CC || rec.destination_country_code || rec.destination_country); let sp = String(rec.species||"").toLowerCase(); if (sp !== "dog" && sp !== "cat") sp = "other"; if (!cc) continue;
          const k = `${cc}|${sp}`; if (!petMap.has(k)) petMap.set(k, []);
          petMap.get(k)!.push({ origin_group: rec.origin_group || "ALL", microchip: !!rec.microchip_required, rabies: !!(rec.rabies_required || rec.rabies_cert_required), title: rec.title || null, body: rec.body || rec.notes || null, source_url: rec.source_url || null, trust_tier: rec.trust_tier || null, confidence_score: numConf(rec.confidence_score), source_quote: rec.source_quote || null });
          continue;
        }
        if (tt.includes("vendor_candidate") && want("vendor_candidates")) {
          const T = R.by_table.vendor_candidates; T.seen++;
          const nm = vendorName(rec); if (!nm) { T.skip_no_name++; continue; }
          const cc = iso2(rec.country || rec.country_code || rec.destination_country_code);
          const cat = rec.category || rec.service_category || "other";
          const dk = rec.dedupe_key || `${String(cat).toLowerCase()}|${cc}|${(rec.city||"").toLowerCase()}|${String(nm).toLowerCase().trim()}`;
          if (ex.vendor?.has(dk)) { T.dup_existing++; continue; } if (seenVendor.has(dk)) { T.dup_in_batch++; continue; } seenVendor.add(dk);
          const svcArr = Array.isArray(rec.services) ? `services: ${rec.services.join(", ")}` : null;
          const langs = Array.isArray(rec.languages_supported) ? `langs: ${rec.languages_supported.join(",")}` : null;
          const notes = [rec.description, rec.notes, svcArr, langs, rec.meeting_id ? `mtg:${rec.meeting_id}` : null].filter(Boolean).join(" | ") || null;
          vendors.push({ name: nm, website_url: rec.website || rec.website_url || null, email: rec.contact_email || rec.email || null, phone: rec.contact_phone || rec.phone || null, city: rec.city || null, country_code: cc, service_category: cat, source_url: rec.source_url || null, source_name: rec.source_name || null, source_tier: tierInt(rec.source_tier), confidence_score: numConf(rec.confidence ?? rec.confidence_score), status: "pending", dedupe_key: dk, notes });
          T.mapped_new++; continue;
        }
        if (tt.includes("staged_resource") && want("staged_resource_candidates")) {
          const T = R.by_table.staged_resource_candidates; T.seen++;
          const cc = iso2(rec.country_code || rec.CC || rec.country); const title = rec.title || null; if (!cc || !title) continue;
          const city = rec.city_name || rec.city || null, cat = rec.category_key || rec.category || null;
          const dk = `${cc}|${city}|${cat}|${title}`; if (ex.res?.has(dk)) { T.dup_existing++; continue; } if (seenRes.has(dk)) { T.dup_in_batch++; continue; } seenRes.add(dk);
          resources.push({ country_code: cc, city_name: city, category_key: cat, title, summary: rec.summary || null, body: rec.body || rec.description || null, content_json: rec.content_json || {}, resource_type: rec.resource_type || "guide", audience_type: rec.audience_type || "all", source_url: rec.source_url || null, source_name: rec.source_name || null, trust_tier: rec.trust_tier || null, confidence_score: numConf(rec.confidence_score), provenance_json: rec.provenance_json || {}, status: "new" });
          T.mapped_new++; continue;
        }
        R.by_table.unrouted.seen++; R.by_table.unrouted.tables[tt || "(none)"] = (R.by_table.unrouted.tables[tt || "(none)"] || 0) + 1;
      }
    }
  }
  R.by_table.pet_import_rules.groups = petMap.size;
  for (const [k] of petMap) { if (ex.pet?.has(k)) R.by_table.pet_import_rules.merge_existing++; else R.by_table.pet_import_rules.new_rows++; }

  if (!dryRun) {
    try {
      let scaffoldId: string | null = null;
      if (want("requirement_facts")) {
        const found = await sb.from("knowledge_docs").select("id").eq("source_url", SCAFFOLD_DOC_SENTINEL).limit(1);
        if (found.data && found.data.length) scaffoldId = found.data[0].id;
        else { const ins = await sb.from("knowledge_docs").insert({ pack_id: SCAFFOLD_PACK_ID, title: "Otto Research — pending intake (scaffold)", source_url: SCAFFOLD_DOC_SENTINEL, text_content: "Scaffold document for Otto-researched requirement_facts pending review. Real source is on each fact's source_url + provenance.", fetch_status: "not_fetched" }).select("id").single(); if (ins.error) throw new Error(`scaffold doc: ${ins.error.message}`); scaffoldId = ins.data.id; }
      }
      if ((want("requirement_entities") || want("requirement_facts")) && entityMap.size) {
        for (const c of chunk([...entityMap.values()], 200)) { const { error } = await sb.from("requirement_entities").upsert(c, { onConflict: "destination_country,topic_key", ignoreDuplicates: true }); if (error) R.by_table.requirement_entities.errors.push(error.message); else R.by_table.requirement_entities.inserted += c.length; }
      }
      if (want("requirement_facts") && facts.length) {
        const dests = [...new Set(facts.map((f) => f.cc))]; const idMap = new Map<string, string>();
        for (const dc of chunk(dests, 50)) { const { data, error } = await sb.from("requirement_entities").select("id,destination_country,topic_key").in("destination_country", dc); if (error) throw new Error(`entity id fetch: ${error.message}`); for (const r of data || []) idMap.set(`${r.destination_country}|${r.topic_key}`, r.id); }
        const factRows: any[] = [];
        for (const f of facts) { const eid = idMap.get(`${f.cc}|${f.topic}`); if (!eid) { R.by_table.requirement_facts.skip_no_entity++; continue; } factRows.push({ ...f.row, entity_id: eid, source_doc_id: scaffoldId }); }
        for (const c of chunk(factRows, 200)) { const { error } = await sb.from("requirement_facts").insert(c); if (error) R.by_table.requirement_facts.errors.push(error.message); else R.by_table.requirement_facts.inserted += c.length; }
      }
      if (want("pet_import_rules")) {
        for (const [k, arr] of petMap) {
          const [cc, sp] = k.split("|");
          const reqs = arr.map((a) => ({ origin_group: a.origin_group, microchip_required: a.microchip, rabies_cert_required: a.rabies, title: a.title, body: a.body, source_url: a.source_url, trust_tier: a.trust_tier, confidence_score: a.confidence_score, source_quote: a.source_quote }));
          const micro = arr.some((a) => a.microchip), rab = arr.some((a) => a.rabies), src = arr.find((a) => a.source_url)?.source_url || null;
          const existing = await sb.from("pet_import_rules").select("id,requirements").eq("destination_country_code", cc).eq("species", sp).limit(1);
          if (existing.data && existing.data.length) {
            const cur = Array.isArray(existing.data[0].requirements) ? existing.data[0].requirements : [];
            const byOrigin = new Map<string, any>(); for (const r of cur) byOrigin.set(r.origin_group || "ALL", r); for (const r of reqs) byOrigin.set(r.origin_group || "ALL", r);
            const { error } = await sb.from("pet_import_rules").update({ requirements: [...byOrigin.values()], microchip_required: micro, rabies_cert_required: rab, source_url: src, updated_at: new Date().toISOString() }).eq("id", existing.data[0].id);
            if (error) R.by_table.pet_import_rules.errors.push(error.message); else R.by_table.pet_import_rules.updated++;
          } else {
            const { error } = await sb.from("pet_import_rules").insert({ destination_country_code: cc, species: sp, requirements: reqs, microchip_required: micro, rabies_cert_required: rab, health_cert_required: false, source_url: src });
            if (error) R.by_table.pet_import_rules.errors.push(error.message); else R.by_table.pet_import_rules.inserted++;
          }
        }
      }
      if (want("vendor_candidates") && vendors.length) { for (const c of chunk(vendors, 200)) { const { error } = await sb.from("vendor_candidates").insert(c); if (error) R.by_table.vendor_candidates.errors.push(error.message); else R.by_table.vendor_candidates.inserted += c.length; } }
      if (want("staged_resource_candidates") && resources.length) { for (const c of chunk(resources, 200)) { const { error } = await sb.from("staged_resource_candidates").insert(c); if (error) R.by_table.staged_resource_candidates.errors.push(error.message); else R.by_table.staged_resource_candidates.inserted += c.length; } }
      if (wantRT && templates.length) { for (const c of chunk(templates, 100)) { const { error } = await sb.from("readiness_templates").insert(c); if (error) R.by_table.readiness_templates.errors.push(error.message); else R.by_table.readiness_templates.inserted += c.length; } }
    } catch (e) { R.ok = false; R.fatal = String(e); }
  }
  return json(R, 200);
});

function json(o: any, status = 200) { return new Response(JSON.stringify(o), { status, headers: { "content-type": "application/json" } }); }
