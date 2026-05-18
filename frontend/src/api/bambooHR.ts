/// <reference types="vite/client" />
/**
 * BambooHR integration API client  (AIQ-38-A)
 *
 * Mirrors the Personio API client pattern:
 *   - All calls proxy through the FastAPI backend (/api/integrations/bamboohr/*)
 *   - Auth via `hr_token` from localStorage
 */

const BASE = import.meta.env.VITE_API_URL

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem("hr_token")
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `Request failed with status ${res.status}`
    try {
      const body = await res.json()
      if (body?.detail) {
        message =
          typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail)
      }
    } catch {
      // ignore JSON parse errors
    }
    throw new Error(message)
  }
  if (res.status === 204) return undefined as unknown as T
  return res.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface BambooHRStatus {
  connected: boolean
  status: "connected" | "disconnected" | "not_configured" | "error"
  subdomain: string
  last_sync_at: string | null
  last_error: string | null
}

export interface BambooHRConnectResult {
  ok: boolean
  connection_id: string
  status: string
}

export interface BambooHRTestResult {
  ok: boolean
  status: "connected" | "error"
}

export interface BambooHRSyncResult {
  ok: boolean
  job_id: string
  message: string
}

export interface BambooHRSyncLogEntry {
  id: string
  sync_type: "poll" | "manual" | "webhook"
  status: "running" | "completed" | "partial" | "failed"
  started_at: string
  completed_at: string | null
  new_hires_found: number
  cases_created: number
  error_count: number
  errors_json: Array<{ bamboohr_id?: string; error: string }> | null
}

export interface BambooHRSyncLog {
  entries: BambooHRSyncLogEntry[]
}

export interface BambooHRFieldMappings {
  mappings: Record<string, string>
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

/** Fetch current BambooHR connection status for the user's org. */
export async function getBambooHRStatus(): Promise<BambooHRStatus> {
  const res = await fetch(`${BASE}/api/integrations/bamboohr/status`, {
    headers: getAuthHeaders(),
  })
  return handleResponse<BambooHRStatus>(res)
}

/** Save (or update) BambooHR API key + subdomain. Validates credentials live. */
export async function connectBambooHR(
  api_key: string,
  subdomain: string,
): Promise<BambooHRConnectResult> {
  const res = await fetch(`${BASE}/api/integrations/bamboohr/connect`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ api_key, subdomain }),
  })
  return handleResponse<BambooHRConnectResult>(res)
}

/** Re-test an existing BambooHR connection without re-saving credentials. */
export async function testBambooHRConnection(): Promise<BambooHRTestResult> {
  const res = await fetch(`${BASE}/api/integrations/bamboohr/test`, {
    method: "POST",
    headers: getAuthHeaders(),
  })
  return handleResponse<BambooHRTestResult>(res)
}

/** Trigger an immediate BambooHR employee sync (runs in background). */
export async function syncBambooHR(): Promise<BambooHRSyncResult> {
  const res = await fetch(`${BASE}/api/integrations/bamboohr/sync`, {
    method: "POST",
    headers: getAuthHeaders(),
  })
  return handleResponse<BambooHRSyncResult>(res)
}

/** Disconnect the BambooHR integration and clear stored credentials. */
export async function disconnectBambooHR(): Promise<{ ok: boolean; status: string }> {
  const res = await fetch(`${BASE}/api/integrations/bamboohr/disconnect`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  })
  return handleResponse<{ ok: boolean; status: string }>(res)
}

/** Fetch the last N sync log entries (default: 20). */
export async function getBambooHRSyncLog(
  limit = 20,
): Promise<BambooHRSyncLog> {
  const res = await fetch(
    `${BASE}/api/integrations/bamboohr/sync-log?limit=${limit}`,
    { headers: getAuthHeaders() },
  )
  return handleResponse<BambooHRSyncLog>(res)
}

/** Fetch current field mappings for this org. */
export async function getBambooHRFieldMappings(): Promise<BambooHRFieldMappings> {
  const res = await fetch(
    `${BASE}/api/integrations/bamboohr/field-mappings`,
    { headers: getAuthHeaders() },
  )
  return handleResponse<BambooHRFieldMappings>(res)
}

/** Persist updated field mappings. */
export async function updateBambooHRFieldMappings(
  mappings: Record<string, string>,
): Promise<BambooHRFieldMappings> {
  const res = await fetch(
    `${BASE}/api/integrations/bamboohr/field-mappings`,
    {
      method: "PUT",
      headers: getAuthHeaders(),
      body: JSON.stringify({ mappings }),
    },
  )
  return handleResponse<BambooHRFieldMappings>(res)
}
