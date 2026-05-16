/**
 * AIQ-72 (AIQ-33-D) · personio-status-sync Edge Function
 *
 * Triggered by the Postgres trigger fn_notify_personio_status_sync() via pg_net
 * whenever relocation_cases.status changes.
 *
 * Flow:
 *   1. Parse incoming payload (case_id, new_status, employee_id, company_id)
 *   2. Look up the employee's email from public.profiles
 *   3. Fetch the Personio connection from public.hris_connections (by org_id = company_id)
 *   4. Fetch field mappings from public.hris_field_mappings
 *   5. Search Personio by email → get Personio employee ID
 *   6. PUT custom attributes to Personio
 *   7. Log the result to public.personio_sync_log
 *
 * Env vars (set automatically by Supabase runtime):
 *   SUPABASE_URL
 *   SUPABASE_SERVICE_ROLE_KEY
 *   RELOPASS_APP_URL  (optional, defaults to https://app.relopass.com)
 *
 * Schema notes (from AIQ-33-B):
 *   hris_connections.org_id       = relocation_cases.company_id
 *   hris_connections.access_token = plain-text OAuth token (managed by AIQ-33-B)
 *   hris_connections.api_base_url = Personio API base (e.g. https://api.personio.de)
 *   hris_field_mappings           = per-connection field mapping overrides
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
  org_id: string;
  provider: string;
  access_token: string | null;
  refresh_token: string | null;
  token_expires_at: string | null;
  api_base_url: string;
  subdomain: string | null;
  status: string;
}

interface FieldMapping {
  hris_field: string;
  relopass_field: string;
}

interface SyncLogEntry {
  case_id: string;
  org_id: string | null;
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
// Default Personio custom field IDs
// Can be overridden per connection via hris_field_mappings rows where
// relopass_field matches one of these keys.
// ---------------------------------------------------------------------------
const DEFAULT_PERSONIO_FIELDS: Record<string, string> = {
  relocation_status: "relocation_status",
  relocation_case_url: "relocation_case_url",
  estimated_completion_date: "estimated_completion_date",
};

// ---------------------------------------------------------------------------
// Map ReloPass status → human-readable Personio value
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
// Main handler
// ---------------------------------------------------------------------------
Deno.serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: { "Access-Control-Allow-Origin": "*" } });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const appUrl = Deno.env.get("RELOPASS_APP_URL") ?? "https://app.relopass.com";

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

  const logBase = {
    case_id,
    org_id: company_id ?? null,
    employee_email: null as string | null,
    personio_employee_id: null as number | null,
    direction: "relopass_to_personio" as const,
    new_case_status: new_status,
  };

  const writeLog = async (entry: SyncLogEntry) => {
    const { error } = await supabase.from("personio_sync_log").insert(entry);
    if (error) console.error("[personio-sync] Failed to write sync log:", error.message);
  };

  // --- Guard: skip if no company ---
  if (!company_id) {
    await writeLog({ ...logBase, sync_status: "skip", error_message: "no_company_id", fields_updated: null, personio_response: null });
    return Response.json({ ok: true, status: "skip", reason: "no_company_id" });
  }

  // --- Step 1: Fetch Personio connection (org_id matches company_id) ---
  const { data: conn, error: connErr } = await supabase
    .from("hris_connections")
    .select("id, org_id, provider, access_token, api_base_url, subdomain, status, token_expires_at")
    .eq("org_id", company_id)
    .eq("provider", "personio")
    .eq("status", "active")
    .single();

  if (connErr || !conn) {
    console.log(`[personio-sync] No active Personio connection for org ${company_id} — skipping.`);
    await writeLog({ ...logBase, sync_status: "skip", error_message: "no_active_personio_connection", fields_updated: null, personio_response: null });
    return Response.json({ ok: true, status: "skip", reason: "no_active_personio_connection" });
  }

  const connection = conn as HrisConnection;

  if (!connection.access_token) {
    await writeLog({ ...logBase, sync_status: "skip", error_message: "no_access_token", fields_updated: null, personio_response: null });
    return Response.json({ ok: true, status: "skip", reason: "no_access_token" });
  }

  // --- Step 2: Resolve employee email from profiles ---
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

  // --- Step 3: Fetch field mappings for this connection ---
  const { data: mappingRows } = await supabase
    .from("hris_field_mappings")
    .select("hris_field, relopass_field")
    .eq("connection_id", connection.id);

  const fieldMappings: Record<string, string> = { ...DEFAULT_PERSONIO_FIELDS };
  for (const row of (mappingRows ?? []) as FieldMapping[]) {
    // relopass_field is our key (e.g. "relocation_status"),
    // hris_field is the Personio custom attribute ID to write to.
    if (row.relopass_field in fieldMappings) {
      fieldMappings[row.relopass_field] = row.hris_field;
    }
  }

  // --- Step 4: Lookup Personio employee by email ---
  let personioEmployee: PersonioEmployee | null;
  try {
    personioEmployee = await personioGetEmployeeByEmail(
      connection.api_base_url,
      connection.access_token,
      employeeEmail
    );
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("[personio-sync] Personio GET failed:", msg);
    await writeLog({ ...logBase, sync_status: "error", error_message: msg, fields_updated: null, personio_response: null });
    return Response.json({ ok: false, status: "error", reason: "personio_get_failed" }, { status: 502 });
  }

  if (!personioEmployee) {
    console.warn(`[personio-sync] No Personio employee found for ${employeeEmail}`);
    await writeLog({ ...logBase, sync_status: "warn", error_message: `no_personio_employee: ${employeeEmail}`, fields_updated: null, personio_response: null });
    return Response.json({ ok: true, status: "warn", reason: "personio_employee_not_found" });
  }

  logBase.personio_employee_id = personioEmployee.id;

  // --- Step 5: Build custom attribute payload ---
  const caseUrl = `${appUrl}/hr/cases/${case_id}`;
  const attributesToWrite: Record<string, string | null> = {
    [fieldMappings.relocation_status]: mapStatus(new_status),
    [fieldMappings.relocation_case_url]: caseUrl,
    [fieldMappings.estimated_completion_date]: updated_at?.slice(0, 10) ?? null,
  };

  // --- Step 6: PUT to Personio ---
  let personioResponse: Record<string, unknown>;
  try {
    personioResponse = await personioUpdateCustomAttributes(
      connection.api_base_url,
      connection.access_token,
      personioEmployee.id,
      attributesToWrite
    );
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("[personio-sync] Personio PUT failed:", msg);
    await writeLog({ ...logBase, sync_status: "error", error_message: msg, fields_updated: attributesToWrite, personio_response: null });
    return Response.json({ ok: false, status: "error", reason: "personio_put_failed" }, { status: 502 });
  }

  // Update connection last_sync_at
  await supabase
    .from("hris_connections")
    .update({ last_sync_at: new Date().toISOString() })
    .eq("id", connection.id);

  // Log success
  await writeLog({
    ...logBase,
    sync_status: "success",
    error_message: null,
    fields_updated: attributesToWrite,
    personio_response: JSON.parse(JSON.stringify(personioResponse).slice(0, 2000)),
  });

  console.log(
    `[personio-sync] ✓ case ${case_id} → Personio employee ${personioEmployee.id} (status: ${new_status})`
  );

  return Response.json({
    ok: true,
    status: "success",
    personio_employee_id: personioEmployee.id,
    fields_updated: Object.keys(attributesToWrite),
  });
});
