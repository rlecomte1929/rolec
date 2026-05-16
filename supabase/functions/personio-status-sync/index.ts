/**
 * AIQ-72 (AIQ-33-D) · personio-status-sync Edge Function
 *
 * Triggered by the Postgres trigger fn_notify_personio_status_sync() via pg_net
 * whenever relocation_cases.status changes.
 *
 * Flow:
 *   1. Parse incoming payload (case_id, new_status, employee_id, company_id)
 *   2. Look up the employee's email from public.profiles
 *   3. Fetch the Personio OAuth token from public.hris_connections
 *   4. Search Personio by email → get Personio employee ID
 *   5. PUT custom attributes to Personio
 *   6. Log the result (success/skip/warn/error) to public.personio_sync_log
 *
 * Env vars required:
 *   SUPABASE_URL              — set automatically by Supabase runtime
 *   SUPABASE_SERVICE_ROLE_KEY — set automatically by Supabase runtime
 *   HRIS_TOKEN_ENCRYPTION_KEY — 32-byte hex key, set in Edge Function secrets
 *
 * The function is idempotent: calling it twice with the same payload writes
 * the same data to Personio (PUT is idempotent) and appends a new log row.
 *
 * Rate limit: Personio allows 200 req/min. This function makes ≤2 Personio API
 * calls per invocation (GET employees + PUT custom-attributes). At 200 case
 * updates/min this would saturate the limit — in practice status changes are
 * far less frequent. Add a queue if volume exceeds ~80 updates/min.
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TriggerPayload {
  case_id: string;
  new_status: string;
  old_status: string | null;
  employee_id: string | null;
  company_id: string | null;
  host_country: string | null;
  updated_at: string | null;
}

interface HrisConnection {
  id: string;
  company_id: string;
  provider: string;
  access_token_enc: string | null;
  refresh_token_enc: string | null;
  token_expiry: string | null;
  base_url: string;
  field_mappings: Record<string, string>;
  status: string;
}

interface SyncLogEntry {
  case_id: string;
  company_id: string | null;
  employee_email: string | null;
  personio_employee_id: number | null;
  direction: "relopass_to_personio";
  sync_status: "success" | "skip" | "warn" | "error";
  new_case_status: string | null;
  fields_updated: Record<string, unknown> | null;
  error_message: string | null;
  personio_response: Record<string, unknown> | null;
}

// ---------------------------------------------------------------------------
// Default Personio custom field names (can be overridden per org via field_mappings)
// ---------------------------------------------------------------------------
const DEFAULT_FIELD_MAPPINGS = {
  relocation_status: "relocation_status",
  relocation_case_url: "relocation_case_url",
  estimated_completion_date: "estimated_completion_date",
};

// ---------------------------------------------------------------------------
// Token decryption
// AES-256-GCM, hex-encoded ciphertext format: <12-byte-iv-hex><ciphertext-hex>
// ---------------------------------------------------------------------------
async function decryptToken(encHex: string, keyHex: string): Promise<string> {
  const keyBytes = hexToBytes(keyHex);
  const encBytes = hexToBytes(encHex);
  const iv = encBytes.slice(0, 12);
  const ciphertext = encBytes.slice(12);

  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    keyBytes,
    { name: "AES-GCM" },
    false,
    ["decrypt"]
  );

  const decrypted = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv },
    cryptoKey,
    ciphertext
  );

  return new TextDecoder().decode(decrypted);
}

function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.slice(i, i + 2), 16);
  }
  return bytes;
}

// ---------------------------------------------------------------------------
// Personio API helpers
// ---------------------------------------------------------------------------

interface PersonioEmployee {
  id: number;
  attributes: Record<string, { value: unknown; type: string }>;
}

async function personioGetEmployeeByEmail(
  baseUrl: string,
  accessToken: string,
  email: string
): Promise<PersonioEmployee | null> {
  const url = `${baseUrl}/api/v2/company/employees?filter[email]=${encodeURIComponent(email)}&limit=1`;
  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      Accept: "application/json",
    },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Personio GET /employees failed: ${res.status} — ${body.slice(0, 300)}`);
  }

  const json = (await res.json()) as { data: PersonioEmployee[] };
  return json.data?.[0] ?? null;
}

async function personioUpdateCustomAttributes(
  baseUrl: string,
  accessToken: string,
  employeeId: number,
  attributes: Record<string, string | number | null>
): Promise<Record<string, unknown>> {
  const url = `${baseUrl}/api/v2/company/employees/${employeeId}/custom-attributes`;

  // Personio PUT body: { data: { <field_id>: { value: <v> } } }
  const body: Record<string, { value: string | number | null }> = {};
  for (const [key, val] of Object.entries(attributes)) {
    body[key] = { value: val };
  }

  const res = await fetch(url, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ data: body }),
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
      `Personio PUT /employees/${employeeId}/custom-attributes failed: ${res.status} — ${responseText.slice(0, 300)}`
    );
  }

  return responseJson;
}

// ---------------------------------------------------------------------------
// Map ReloPass status to Personio-friendly string
// ---------------------------------------------------------------------------
function mapStatus(status: string): string {
  const map: Record<string, string> = {
    draft: "Draft",
    created: "Draft",
    active: "In Progress",
    in_progress: "In Progress",
    on_hold: "On Hold",
    completed: "Completed",
    closed: "Completed",
    archived: "Completed",
  };
  return map[status.toLowerCase()] ?? status;
}

// ---------------------------------------------------------------------------
// Main handler
// ---------------------------------------------------------------------------
Deno.serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: { "Access-Control-Allow-Origin": "*" } });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const encryptionKey = Deno.env.get("HRIS_TOKEN_ENCRYPTION_KEY") ?? "";

  const supabase = createClient(supabaseUrl, serviceKey);

  // --- Parse payload ---
  let payload: TriggerPayload;
  try {
    payload = (await req.json()) as TriggerPayload;
  } catch (e) {
    console.error("[personio-sync] Failed to parse payload:", e);
    return Response.json({ ok: false, error: "invalid_payload" }, { status: 400 });
  }

  const { case_id, new_status, employee_id, company_id, updated_at } = payload;

  console.log(
    `[personio-sync] case_id=${case_id} status=${payload.old_status}→${new_status} company=${company_id}`
  );

  const logBase: Omit<SyncLogEntry, "sync_status" | "error_message" | "fields_updated" | "personio_response"> = {
    case_id,
    company_id: company_id ?? null,
    employee_email: null,
    personio_employee_id: null,
    direction: "relopass_to_personio",
    new_case_status: new_status,
  };

  const writeLog = async (entry: SyncLogEntry) => {
    const { error } = await supabase.from("personio_sync_log").insert(entry);
    if (error) {
      console.error("[personio-sync] Failed to write sync log:", error.message);
    }
  };

  // --- Guard: skip if no company ---
  if (!company_id) {
    console.warn("[personio-sync] No company_id on case — skipping.");
    await writeLog({ ...logBase, sync_status: "skip", error_message: "no company_id on case", fields_updated: null, personio_response: null });
    return Response.json({ ok: true, status: "skip", reason: "no_company_id" });
  }

  // --- Step 1: Fetch Personio connection ---
  const { data: conn, error: connErr } = await supabase
    .from("hris_connections")
    .select("*")
    .eq("company_id", company_id)
    .eq("provider", "personio")
    .eq("status", "active")
    .single();

  if (connErr || !conn) {
    console.log(`[personio-sync] No active Personio connection for company ${company_id} — skipping.`);
    await writeLog({ ...logBase, sync_status: "skip", error_message: "no_active_personio_connection", fields_updated: null, personio_response: null });
    return Response.json({ ok: true, status: "skip", reason: "no_active_personio_connection" });
  }

  const connection = conn as HrisConnection;

  // --- Step 2: Decrypt access token ---
  if (!connection.access_token_enc || !encryptionKey) {
    console.warn("[personio-sync] No token or encryption key — skipping.");
    await writeLog({ ...logBase, sync_status: "skip", error_message: "missing_token_or_encryption_key", fields_updated: null, personio_response: null });
    return Response.json({ ok: true, status: "skip", reason: "missing_token" });
  }

  let accessToken: string;
  try {
    accessToken = await decryptToken(connection.access_token_enc, encryptionKey);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("[personio-sync] Token decryption failed:", msg);
    await writeLog({ ...logBase, sync_status: "error", error_message: `token_decryption_failed: ${msg}`, fields_updated: null, personio_response: null });
    return Response.json({ ok: false, status: "error", reason: "token_decryption_failed" }, { status: 500 });
  }

  // --- Step 3: Resolve employee email from profiles ---
  let employeeEmail: string | null = null;
  if (employee_id) {
    const { data: profile } = await supabase
      .from("profiles")
      .select("email")
      .eq("id", employee_id)
      .single();
    employeeEmail = (profile as { email?: string } | null)?.email ?? null;
  }

  if (!employeeEmail) {
    console.warn(`[personio-sync] No employee email for case ${case_id} — skipping.`);
    await writeLog({ ...logBase, sync_status: "skip", error_message: "no_employee_email", fields_updated: null, personio_response: null });
    return Response.json({ ok: true, status: "skip", reason: "no_employee_email" });
  }

  logBase.employee_email = employeeEmail;

  // --- Step 4: Lookup Personio employee by email ---
  let personioEmployee: PersonioEmployee | null;
  try {
    personioEmployee = await personioGetEmployeeByEmail(
      connection.base_url,
      accessToken,
      employeeEmail
    );
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("[personio-sync] Personio GET failed:", msg);
    await writeLog({ ...logBase, sync_status: "error", error_message: msg, fields_updated: null, personio_response: null });
    return Response.json({ ok: false, status: "error", reason: "personio_get_failed" }, { status: 502 });
  }

  if (!personioEmployee) {
    console.warn(`[personio-sync] No Personio employee found for email ${employeeEmail}`);
    await writeLog({ ...logBase, sync_status: "warn", error_message: `no_personio_employee_for_email:${employeeEmail}`, fields_updated: null, personio_response: null });
    return Response.json({ ok: true, status: "warn", reason: "personio_employee_not_found" });
  }

  logBase.personio_employee_id = personioEmployee.id;

  // --- Step 5: Build the custom attribute payload ---
  const fieldMappings = { ...DEFAULT_FIELD_MAPPINGS, ...connection.field_mappings };
  const caseUrl = `${Deno.env.get("RELOPASS_APP_URL") ?? "https://app.relopass.com"}/hr/cases/${case_id}`;

  const attributesToWrite: Record<string, string | null> = {
    [fieldMappings.relocation_status]: mapStatus(new_status),
    [fieldMappings.relocation_case_url]: caseUrl,
    // estimated_completion_date: not available in trigger payload; leave as null unless
    // extended in the future to include projected_end_date from relocation_cases.
    [fieldMappings.estimated_completion_date]: updated_at?.slice(0, 10) ?? null,
  };

  // --- Step 6: PUT to Personio ---
  let personioResponse: Record<string, unknown>;
  try {
    personioResponse = await personioUpdateCustomAttributes(
      connection.base_url,
      accessToken,
      personioEmployee.id,
      attributesToWrite
    );
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("[personio-sync] Personio PUT failed:", msg);
    await writeLog({
      ...logBase,
      sync_status: "error",
      error_message: msg,
      fields_updated: attributesToWrite,
      personio_response: null,
    });
    return Response.json({ ok: false, status: "error", reason: "personio_put_failed" }, { status: 502 });
  }

  // --- Update connection last_sync_at ---
  await supabase
    .from("hris_connections")
    .update({ last_sync_at: new Date().toISOString() })
    .eq("id", connection.id);

  // --- Log success ---
  await writeLog({
    ...logBase,
    sync_status: "success",
    error_message: null,
    fields_updated: attributesToWrite,
    // Truncate personio response to avoid storing huge payloads
    personio_response: JSON.parse(JSON.stringify(personioResponse).slice(0, 2000)),
  });

  console.log(
    `[personio-sync] ✓ case ${case_id} → Personio employee ${personioEmployee.id} updated (status: ${new_status})`
  );

  return Response.json({
    ok: true,
    status: "success",
    personio_employee_id: personioEmployee.id,
    fields_updated: Object.keys(attributesToWrite),
  });
});
