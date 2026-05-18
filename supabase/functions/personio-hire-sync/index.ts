// personio-hire-sync — Supabase Edge Function  (AIQ-33-C)
//
// Invoked every 15 minutes by Supabase Cron (pg_cron) or manually.
// Polls Personio for employees updated since last_sync_at across all active
// hris_connections, and creates draft relocation_cases for any employee with
// relocation_required = true.  Idempotent — duplicate runs are safe.
//
// To schedule after deploying (cron expression: every 15 min):
//   SELECT cron.schedule('personio-hire-sync', '*/15 * * * *', $$
//     SELECT net.http_post(
//       url := current_setting('app.supabase_functions_url') || '/personio-hire-sync',
//       headers := jsonb_build_object('Authorization', 'Bearer ' ||
//                  current_setting('app.service_role_key')),
//       body := '{}'::jsonb)$$);
//
// Required env vars:
//   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, HRIS_TOKEN_ENCRYPTION_KEY (64 hex chars)

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// ---------------------------------------------------------------------------
// AES-256-GCM token decryption
// Wire format: base64( 12-byte IV || ciphertext || 16-byte GCM tag )
// Must match hris_token_crypto.py and token-crypto.ts.
// ---------------------------------------------------------------------------

function hexToBytes(hex: string): Uint8Array {
  const arr = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    arr[i / 2] = parseInt(hex.slice(i, i + 2), 16);
  }
  return arr;
}

function base64ToBytes(b64: string): Uint8Array {
  const binary = atob(b64);
  const arr = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) arr[i] = binary.charCodeAt(i);
  return arr;
}

async function decryptToken(ciphertextB64: string, keyHex: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    hexToBytes(keyHex),
    { name: "AES-GCM" },
    false,
    ["decrypt"],
  );
  const raw = base64ToBytes(ciphertextB64);
  const iv = raw.slice(0, 12);
  const ciphertextWithTag = raw.slice(12);
  const plaintext = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, ciphertextWithTag);
  return new TextDecoder().decode(plaintext);
}

// ---------------------------------------------------------------------------
// Personio API types + helpers
// ---------------------------------------------------------------------------

interface PersonioEmployee {
  id: number;
  attributes: Record<string, { value: unknown } | unknown>;
}

/** Extract a scalar from Personio's { value: ... } attribute wrapper. */
function getAttr(emp: PersonioEmployee, key: string): string | null {
  const raw = emp.attributes?.[key];
  if (raw === null || raw === undefined) return null;
  if (typeof raw === "object" && "value" in (raw as Record<string, unknown>)) {
    const v = (raw as { value: unknown }).value;
    return v !== null && v !== undefined ? String(v) : null;
  }
  return String(raw);
}

function isRelocationRequired(emp: PersonioEmployee): boolean {
  const val = getAttr(emp, "relocation_required");
  if (val !== null) return ["true", "yes", "1"].includes(val.toLowerCase());
  // Fallback: any non-empty relocation_status
  const status = getAttr(emp, "relocation_status");
  return Boolean(status?.trim());
}

/**
 * Fetch all employees from Personio, paging through 200 at a time.
 * Respects the 200 req/min limit with a 400 ms inter-page delay.
 */
async function fetchPersonioEmployees(
  accessToken: string,
  apiBase: string,
  updatedSince?: string | null,
): Promise<PersonioEmployee[]> {
  const employees: PersonioEmployee[] = [];
  let offset = 0;

  while (true) {
    const url = new URL(`${apiBase}/company/employees`);
    url.searchParams.set("limit", "200");
    url.searchParams.set("offset", String(offset));
    if (updatedSince) url.searchParams.set("updated_since", updatedSince);

    const resp = await fetch(url.toString(), {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        Accept: "application/json",
        "X-Personio-Partner-ID": "ReloPass",
      },
    });

    if (resp.status === 429) {
      console.warn("[personio-hire-sync] Rate limit — waiting 60 s");
      await new Promise((r) => setTimeout(r, 60_000));
      continue; // retry same page
    }

    if (!resp.ok) {
      const text = await resp.text();
      console.error(`[personio-hire-sync] API error ${resp.status}: ${text.slice(0, 200)}`);
      break;
    }

    const batch = ((await resp.json()).data ?? []) as PersonioEmployee[];
    employees.push(...batch);
    if (batch.length < 200) break; // last page
    offset += 200;
    await new Promise((r) => setTimeout(r, 400)); // rate-limit courtesy delay
  }

  return employees;
}

// ---------------------------------------------------------------------------
// Case creation helper
// ---------------------------------------------------------------------------

function buildCasePayload(
  emp: PersonioEmployee,
  orgId: string,
  hrUserId: string,
): Record<string, unknown> {
  const pid = String(emp.id);
  const a = (k: string) => getAttr(emp, k);
  const now = new Date().toISOString();

  return {
    id: crypto.randomUUID(),
    hr_user_id: hrUserId,
    company_id: orgId,
    employee_id: `personio:${pid}`,
    status: "draft",
    profile_json: JSON.stringify({
      full_name: `${a("first_name") ?? ""} ${a("last_name") ?? ""}`.trim(),
      email: a("email") ?? "",
      start_date: a("hire_date") ?? a("start_date") ?? null,
      nationality: a("nationality") ?? null,
      destination_office: a("office") ?? null,
      source: "personio_sync",
      personio_id: pid,
    }),
    host_country: a("office_country") ?? a("work_country") ?? "",
    home_country: a("home_address_country") ?? a("nationality") ?? "",
    expected_start_date: a("hire_date") ?? a("start_date") ?? null,
    compliance_flag: false,
    created_at: now,
    updated_at: now,
  };
}

// ---------------------------------------------------------------------------
// Main handler
// ---------------------------------------------------------------------------

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: { "Access-Control-Allow-Origin": "*" } });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const encKey = Deno.env.get("HRIS_TOKEN_ENCRYPTION_KEY") ?? "";
  const supabase = createClient(supabaseUrl, serviceKey);

  if (!encKey || encKey.length !== 64) {
    console.error("[personio-hire-sync] HRIS_TOKEN_ENCRYPTION_KEY not set or wrong length");
    return Response.json(
      { ok: false, error: "HRIS_TOKEN_ENCRYPTION_KEY missing or invalid" },
      { status: 500, headers: { "Access-Control-Allow-Origin": "*" } },
    );
  }

  // Fetch all active Personio connections
  const { data: connections, error: connErr } = await supabase
    .from("hris_connections")
    .select("id, org_id, access_token, api_base_url, last_sync_at")
    .eq("provider", "personio")
    .eq("status", "connected");

  if (connErr) {
    console.error("[personio-hire-sync] Could not load connections:", connErr);
    return Response.json(
      { ok: false, error: connErr.message },
      { status: 500, headers: { "Access-Control-Allow-Origin": "*" } },
    );
  }

  const results: Record<string, unknown>[] = [];

  for (const conn of connections ?? []) {
    const logId = crypto.randomUUID();
    const runStart = new Date().toISOString();

    // Open sync log entry
    await supabase.from("hris_sync_log").insert({
      id: logId,
      connection_id: conn.id,
      org_id: conn.org_id,
      sync_type: "cron_poll",
      status: "running",
      started_at: runStart,
    });

    // Decrypt access token
    let accessToken: string;
    try {
      accessToken = await decryptToken(conn.access_token, encKey);
    } catch (e) {
      console.error(`[personio-hire-sync] Token decryption failed (conn ${conn.id}):`, e);
      await supabase.from("hris_sync_log").update({
        status: "failed",
        error_count: 1,
        errors_json: [{ error: "token_decryption_failed", detail: String(e) }],
        completed_at: new Date().toISOString(),
      }).eq("id", logId);
      results.push({ org_id: conn.org_id, error: "token_decryption_failed" });
      continue;
    }

    const apiBase = conn.api_base_url ?? "https://api.personio.de/v1";
    const employees = await fetchPersonioEmployees(accessToken, apiBase, conn.last_sync_at);
    const relocating = employees.filter(isRelocationRequired);

    console.log(
      `[personio-hire-sync] org=${conn.org_id}: ${employees.length} employees, ${relocating.length} relocating`,
    );

    // Resolve default HR user for this org
    const { data: hrUsers } = await supabase
      .from("users")
      .select("id")
      .eq("company", conn.org_id)
      .eq("role", "hr")
      .limit(1);
    const hrUserId: string = hrUsers?.[0]?.id ?? "system";

    let casesCreated = 0;
    const errors: Array<Record<string, string>> = [];

    for (const emp of relocating) {
      const employeeKey = `personio:${emp.id}`;

      // Idempotency: skip if case already exists
      const { data: existing } = await supabase
        .from("relocation_cases")
        .select("id")
        .eq("employee_id", employeeKey)
        .eq("company_id", conn.org_id)
        .limit(1);

      if (existing && existing.length > 0) {
        console.log(`[personio-hire-sync] Case already exists for ${employeeKey} — skipping`);
        continue;
      }

      const casePayload = buildCasePayload(emp, conn.org_id, hrUserId);
      const { error: insertErr } = await supabase.from("relocation_cases").insert(casePayload);

      if (insertErr) {
        console.error(`[personio-hire-sync] INSERT failed for ${employeeKey}:`, insertErr);
        errors.push({ personio_id: String(emp.id), error: insertErr.message });
      } else {
        console.log(`[personio-hire-sync] Created draft case for ${employeeKey}`);
        casesCreated++;
      }
    }

    const completedAt = new Date().toISOString();
    const syncStatus =
      errors.length === 0
        ? "completed"
        : casesCreated > 0
        ? "partial"
        : "failed";

    // Close sync log
    await supabase.from("hris_sync_log").update({
      status: syncStatus,
      new_hires_found: relocating.length,
      cases_created: casesCreated,
      error_count: errors.length,
      errors_json: errors.length > 0 ? errors : null,
      completed_at: completedAt,
    }).eq("id", logId);

    // Update last_sync_at on the connection
    await supabase.from("hris_connections").update({
      last_sync_at: completedAt,
      last_error: errors.length > 0 ? errors[0].error : null,
    }).eq("id", conn.id);

    results.push({
      org_id: conn.org_id,
      new_hires_found: relocating.length,
      cases_created: casesCreated,
      error_count: errors.length,
    });
  }

  return Response.json(
    {
      ok: true,
      connections_processed: results.length,
      results,
    },
    { headers: { "Access-Control-Allow-Origin": "*" } },
  );
});
