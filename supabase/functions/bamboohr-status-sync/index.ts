/**
 * AIQ-38-C · bamboohr-status-sync Edge Function
 *
 * Triggered by the Postgres trigger fn_notify_bamboohr_status_sync() via pg_net
 * whenever relocation_cases.status changes for a BambooHR-sourced case.
 *
 * Flow:
 *   1. Parse incoming payload (case_id, new_status, employee_id, company_id)
 *   2. Guard: employee_id must start with "bamboohr:" — skip all other cases
 *   3. Fetch the BambooHR connection from public.hris_connections (provider = bamboohr)
 *   4. Decrypt the API key (AES-256-GCM, matches Python hris_token_crypto wire format)
 *   5. Fetch field mappings from public.hris_field_mappings
 *   6. PUT custom fields to BambooHR: relocation_status, relocation_case_url,
 *      estimated_completion_date
 *   7. Log the result to public.bamboohr_sync_log
 *
 * Key difference from personio-status-sync:
 *   - BambooHR uses HTTP Basic Auth (api_key:x), not OAuth Bearer
 *   - Employee ID is embedded in employee_id ("bamboohr:<id>") — no email lookup
 *   - API key is AES-256-GCM encrypted; decrypted with HRIS_TOKEN_ENCRYPTION_KEY
 *
 * Env vars:
 *   SUPABASE_URL                  (set by Supabase runtime)
 *   SUPABASE_SERVICE_ROLE_KEY     (set by Supabase runtime)
 *   HRIS_TOKEN_ENCRYPTION_KEY     64 hex chars (32 bytes) — shared with Python backend
 *   RELOPASS_APP_URL              optional, defaults to https://app.relopass.com
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TriggerPayload {
  case_id: string;
  new_status: string;
  old_status: string | null;
  employee_id: string | null;   // "bamboohr:<id>" for BambooHR-sourced cases
  company_id: string | null;
  host_country: string | null;
  updated_at: string | null;
}

interface HrisConnection {
  id: string;
  org_id: string;
  provider: string;
  access_token: string | null;  // AES-256-GCM encrypted BambooHR API key
  api_base_url: string | null;  // BambooHR subdomain (e.g. "mycompany")
  status: string;
}

interface FieldMapping {
  hris_field: string;
  relopass_field: string;
}

interface SyncLogEntry {
  case_id: string;
  org_id: string | null;
  bamboohr_employee_id: string | null;
  direction: "relopass_to_bamboohr";
  sync_status: "success" | "skip" | "warn" | "error";
  new_case_status: string | null;
  fields_updated: Record<string, unknown> | null;
  error_message: string | null;
  bamboohr_response: Record<string, unknown> | null;
}

// ---------------------------------------------------------------------------
// Default BambooHR custom field names
// Can be overridden per connection via hris_field_mappings rows.
// ---------------------------------------------------------------------------
const DEFAULT_BAMBOOHR_FIELDS: Record<string, string> = {
  relocation_status:            "customRelocationStatus",
  relocation_case_url:          "customRelocationCaseUrl",
  estimated_completion_date:    "customEstimatedCompletionDate",
};

// ---------------------------------------------------------------------------
// Map ReloPass status → human-readable BambooHR value
// ---------------------------------------------------------------------------
function mapStatus(status: string): string {
  const map: Record<string, string> = {
    draft:       "Draft",
    created:     "Draft",
    active:      "In Progress",
    in_progress: "In Progress",
    on_hold:     "On Hold",
    completed:   "Completed",
    closed:      "Completed",
    archived:    "Completed",
  };
  return map[status.toLowerCase()] ?? status;
}

// ---------------------------------------------------------------------------
// AES-256-GCM decryption
// Wire format: base64( 12-byte IV || ciphertext || 16-byte GCM tag )
// Matches Python hris_token_crypto.py exactly.
// ---------------------------------------------------------------------------
function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.slice(i, i + 2), 16);
  }
  return bytes;
}

async function decryptToken(ciphertextB64: string, keyHex: string): Promise<string> {
  const keyBytes = hexToBytes(keyHex);
  const raw = Uint8Array.from(atob(ciphertextB64), (c) => c.charCodeAt(0));

  const iv = raw.slice(0, 12);
  const ciphertextWithTag = raw.slice(12);

  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    keyBytes,
    { name: "AES-GCM" },
    false,
    ["decrypt"],
  );

  const plaintext = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv },
    cryptoKey,
    ciphertextWithTag,
  );

  return new TextDecoder().decode(plaintext);
}

// ---------------------------------------------------------------------------
// BambooHR Basic Auth header
// BambooHR uses base64("{api_key}:x") — password field is ignored.
// ---------------------------------------------------------------------------
function basicAuthHeader(apiKey: string): string {
  return "Basic " + btoa(`${apiKey}:x`);
}

// ---------------------------------------------------------------------------
// BambooHR API: update employee custom fields
// PUT https://api.bamboohr.com/api/gateway.php/{subdomain}/v1/employees/{id}
// Body: flat JSON object of field_name → value
// ---------------------------------------------------------------------------
async function bamboohrUpdateEmployee(
  subdomain: string,
  apiKey: string,
  employeeId: string,
  fields: Record<string, string | null>,
): Promise<Record<string, unknown>> {
  const url = `https://api.bamboohr.com/api/gateway.php/${encodeURIComponent(subdomain)}/v1/employees/${encodeURIComponent(employeeId)}`;

  // Remove null values — only send fields with actual content
  const body: Record<string, string> = {};
  for (const [k, v] of Object.entries(fields)) {
    if (v !== null && v !== undefined) body[k] = v;
  }

  const res = await fetch(url, {
    method: "POST",   // BambooHR uses POST with X-HTTP-Method-Override for updates
    headers: {
      Authorization:           basicAuthHeader(apiKey),
      "Content-Type":          "application/json",
      Accept:                  "application/json",
      "User-Agent":            "ReloPass/1.0",
      "X-HTTP-Method-Override": "PUT",
    },
    body: JSON.stringify(body),
  });

  const responseText = await res.text();
  let responseJson: Record<string, unknown> = {};
  try {
    responseJson = JSON.parse(responseText);
  } catch {
    responseJson = { raw: responseText.slice(0, 500) };
  }

  if (!res.ok) {
    throw new Error(
      `BambooHR PUT /employees/${employeeId} failed: ${res.status} — ${responseText.slice(0, 300)}`,
    );
  }

  return responseJson;
}

// ---------------------------------------------------------------------------
// Main handler
// ---------------------------------------------------------------------------
Deno.serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: { "Access-Control-Allow-Origin": "*" } });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceKey  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const encKeyHex   = Deno.env.get("HRIS_TOKEN_ENCRYPTION_KEY") ?? "";
  const appUrl      = Deno.env.get("RELOPASS_APP_URL") ?? "https://app.relopass.com";

  const supabase = createClient(supabaseUrl, serviceKey);

  // --- Parse payload ---
  let payload: TriggerPayload;
  try {
    payload = (await req.json()) as TriggerPayload;
  } catch (e) {
    console.error("[bamboohr-sync] Failed to parse payload:", e);
    return Response.json({ ok: false, error: "invalid_payload" }, { status: 400 });
  }

  const { case_id, new_status, employee_id, company_id, updated_at } = payload;

  console.log(
    `[bamboohr-sync] case_id=${case_id} status=${payload.old_status}→${new_status} company=${company_id} employee=${employee_id}`,
  );

  const logBase = {
    case_id,
    org_id:               company_id ?? null,
    bamboohr_employee_id: null as string | null,
    direction:            "relopass_to_bamboohr" as const,
    new_case_status:      new_status,
  };

  const writeLog = async (entry: SyncLogEntry) => {
    const { error } = await supabase.from("bamboohr_sync_log").insert(entry);
    if (error) console.error("[bamboohr-sync] Failed to write sync log:", error.message);
  };

  // --- Guard: only process BambooHR-sourced cases ---
  if (!employee_id?.startsWith("bamboohr:")) {
    // Not a BambooHR employee — nothing to sync
    console.log(`[bamboohr-sync] employee_id "${employee_id}" is not BambooHR-sourced — skipping`);
    return Response.json({ ok: true, status: "skip", reason: "not_bamboohr_employee" });
  }

  const bamboohrEmployeeId = employee_id.slice("bamboohr:".length);
  logBase.bamboohr_employee_id = bamboohrEmployeeId;

  // --- Guard: skip if no company ---
  if (!company_id) {
    await writeLog({ ...logBase, sync_status: "skip", error_message: "no_company_id", fields_updated: null, bamboohr_response: null });
    return Response.json({ ok: true, status: "skip", reason: "no_company_id" });
  }

  // --- Fetch BambooHR connection ---
  const { data: conn, error: connErr } = await supabase
    .from("hris_connections")
    .select("id, org_id, provider, access_token, api_base_url, status")
    .eq("org_id", company_id)
    .eq("provider", "bamboohr")
    .eq("status", "connected")
    .single();

  if (connErr || !conn) {
    console.log(`[bamboohr-sync] No active BambooHR connection for org ${company_id} — skipping.`);
    await writeLog({ ...logBase, sync_status: "skip", error_message: "no_active_bamboohr_connection", fields_updated: null, bamboohr_response: null });
    return Response.json({ ok: true, status: "skip", reason: "no_active_bamboohr_connection" });
  }

  const connection = conn as HrisConnection;
  const subdomain  = connection.api_base_url ?? "";

  if (!connection.access_token) {
    await writeLog({ ...logBase, sync_status: "skip", error_message: "no_access_token", fields_updated: null, bamboohr_response: null });
    return Response.json({ ok: true, status: "skip", reason: "no_access_token" });
  }

  if (!subdomain) {
    await writeLog({ ...logBase, sync_status: "skip", error_message: "no_subdomain", fields_updated: null, bamboohr_response: null });
    return Response.json({ ok: true, status: "skip", reason: "no_subdomain" });
  }

  // --- Decrypt API key ---
  let apiKey: string;
  try {
    if (!encKeyHex || encKeyHex.length !== 64) {
      throw new Error("HRIS_TOKEN_ENCRYPTION_KEY not configured (must be 64 hex chars)");
    }
    apiKey = await decryptToken(connection.access_token, encKeyHex);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("[bamboohr-sync] Token decryption failed:", msg);
    await writeLog({ ...logBase, sync_status: "error", error_message: `token_decryption_failed: ${msg}`, fields_updated: null, bamboohr_response: null });
    return Response.json({ ok: false, status: "error", reason: "token_decryption_failed" }, { status: 500 });
  }

  // --- Fetch field mappings ---
  const { data: mappingRows } = await supabase
    .from("hris_field_mappings")
    .select("hris_field, relopass_field")
    .eq("connection_id", connection.id);

  const fieldMappings: Record<string, string> = { ...DEFAULT_BAMBOOHR_FIELDS };
  for (const row of (mappingRows ?? []) as FieldMapping[]) {
    if (row.relopass_field in fieldMappings) {
      fieldMappings[row.relopass_field] = row.hris_field;
    }
  }

  // --- Build field payload ---
  const caseUrl = `${appUrl}/hr/cases/${case_id}`;
  const fieldsToWrite: Record<string, string | null> = {
    [fieldMappings.relocation_status]:         mapStatus(new_status),
    [fieldMappings.relocation_case_url]:       caseUrl,
    [fieldMappings.estimated_completion_date]: updated_at?.slice(0, 10) ?? null,
  };

  // --- PUT to BambooHR ---
  let bamboohrResponse: Record<string, unknown>;
  try {
    bamboohrResponse = await bamboohrUpdateEmployee(subdomain, apiKey, bamboohrEmployeeId, fieldsToWrite);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("[bamboohr-sync] BambooHR PUT failed:", msg);
    await writeLog({ ...logBase, sync_status: "error", error_message: msg, fields_updated: fieldsToWrite, bamboohr_response: null });
    return Response.json({ ok: false, status: "error", reason: "bamboohr_put_failed" }, { status: 502 });
  }

  // --- Update connection last_sync_at ---
  await supabase
    .from("hris_connections")
    .update({ last_sync_at: new Date().toISOString() })
    .eq("id", connection.id);

  // --- Log success ---
  await writeLog({
    ...logBase,
    sync_status:    "success",
    error_message:  null,
    fields_updated: fieldsToWrite,
    bamboohr_response: JSON.parse(JSON.stringify(bamboohrResponse).slice(0, 2000)),
  });

  console.log(
    `[bamboohr-sync] ✓ case ${case_id} → BambooHR employee ${bamboohrEmployeeId} (status: ${new_status})`,
  );

  return Response.json({
    ok:                   true,
    status:               "success",
    bamboohr_employee_id: bamboohrEmployeeId,
    fields_updated:       Object.keys(fieldsToWrite),
  });
});
