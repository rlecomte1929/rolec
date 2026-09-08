/// <reference types="vite/client" />
/**
 * Personio integration settings API client  (AIQ-33-B)
 *
 * Covers the 5 settings routes added to the FastAPI backend:
 *   status / connect / disconnect / sync / sync-log / field-mappings
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
      const body = await res.json() as Record<string, unknown>
      if (body.detail != null) {
        message =
          typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail as Record<string, unknown>)
      }
    } catch {
      // ignore
    }
    throw new Error(message)
  }
  if (res.status === 204) return undefined as unknown as T
  return res.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PersonioStatus {
  connected: boolean
  status: "connected" | "disconnected" | "not_configured" | "error"
  api_base_url: string
  last_sync_at: string | null
  last_error: string | null
}

export interface PersonioConnectResult {
  ok: boolean
  connection_id: string
  status: string
}

export interface PersonioSyncResult {
  ok: boolean
  job_id: string
  message: string
}

export interface PersonioSyncLogEntry {
  id: string
  sync_type: "poll" | "manual" | "webhook"
  status: "running" | "completed" | "partial" | "failed"
  started_at: string
  completed_at: string | null
  new_hires_found: number
  cases_created: number
  error_count: number
  errors_json: Array<{ personio_id?: string; error: string }> | null
}

export interface PersonioSyncLog {
  entries: PersonioSyncLogEntry[]
}

export interface PersonioFieldMappings {
  mappings: Record<string, string>
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export async function getPersonioStatus(): Promise<PersonioStatus> {
  const res = await fetch(`${BASE}/api/integrations/personio/status`, {
    headers: getAuthHeaders(),
  })
  return handleResponse<PersonioStatus>(res)
}

export async function connectPersonio(
  client_id: string,
  client_secret: string,
): Promise<PersonioConnectResult> {
  const res = await fetch(`${BASE}/api/integrations/personio/connect`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ client_id, client_secret }),
  })
  return handleResponse<PersonioConnectResult>(res)
}

export async function disconnectPersonio(): Promise<{ ok: boolean; status: string }> {
  const res = await fetch(`${BASE}/api/integrations/personio/disconnect`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  })
  return handleResponse<{ ok: boolean; status: string }>(res)
}

export async function syncPersonio(): Promise<PersonioSyncResult> {
  const res = await fetch(`${BASE}/api/integrations/personio/sync`, {
    method: "POST",
    headers: getAuthHeaders(),
  })
  return handleResponse<PersonioSyncResult>(res)
}

export async function getPersonioSyncLog(limit = 20): Promise<PersonioSyncLog> {
  const res = await fetch(
    `${BASE}/api/integrations/personio/sync-log?limit=${limit}`,
    { headers: getAuthHeaders() },
  )
  return handleResponse<PersonioSyncLog>(res)
}

export async function getPersonioFieldMappings(): Promise<PersonioFieldMappings> {
  const res = await fetch(
    `${BASE}/api/integrations/personio/field-mappings`,
    { headers: getAuthHeaders() },
  )
  return handleResponse<PersonioFieldMappings>(res)
}

export async function updatePersonioFieldMappings(
  mappings: Record<string, string>,
): Promise<PersonioFieldMappings> {
  const res = await fetch(
    `${BASE}/api/integrations/personio/field-mappings`,
    {
      method: "PUT",
      headers: getAuthHeaders(),
      body: JSON.stringify({ mappings }),
    },
  )
  return handleResponse<PersonioFieldMappings>(res)
}
