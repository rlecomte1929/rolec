/// <reference types="vite/client" />
import { getAuthItem } from '../utils/demo'

const BASE = import.meta.env.VITE_API_URL

function getAuthHeaders(): HeadersInit {
  // AIQ-862: read the ReloPass session token under the SAME key the shared
  // axios client uses (`relopass_token`, set at login in useAuth.ts). The
  // old `hr_token` key is never written anywhere, so this previously sent
  // `Authorization: Bearer null` → 401 on every hr-coordination call
  // (providers list + task assign/update/cancel).
  const token = getAuthItem('relopass_token')
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token ?? ''}`,
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `Request failed with status ${res.status}`
    try {
      const body = await res.json() as Record<string, unknown>
      if (body.detail != null) {
        message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail as Record<string, unknown>)
      }
    } catch {
      // ignore JSON parse errors — use the default message
    }
    throw new Error(message)
  }
  // 204 No Content — nothing to parse
  if (res.status === 204) return undefined as unknown as T
  return res.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ProviderTask {
  id: string
  title: string
  description: string | null
  status: "pending" | "in_progress" | "completed" | "cancelled"
  due_date: string | null
  updated_at: string
}

export interface CaseProvider {
  id: string
  name: string
  type: "housing" | "immigration" | "shipping" | "other"
  status: "active" | "inactive" | "suspended"
  tasks: ProviderTask[]
  task_counts: {
    pending: number
    in_progress: number
    completed: number
    cancelled: number
  }
}

/** [AIQ-1671] One recipient (supplier) on a canonical employee-submitted RFQ. */
export interface CaseRfqRecipient {
  supplier_id: string | null
  supplier_name: string | null
  status: string | null
  last_activity_at: string | null
}

/** [AIQ-1671] A canonical RFQ the EMPLOYEE submitted (from `rfqs`), read by HR. */
export interface CaseRfq {
  id: string
  rfq_ref: string | null
  case_id: string | null
  status: string | null
  created_at: string | null
  service_keys: string[]
  recipients: CaseRfqRecipient[]
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/**
 * [AIQ-1671] The canonical RFQs an employee submitted for this case, read from the
 * `rfqs` table via GET /api/hr/cases/{caseId}/rfqs (AIQ-1669). This is what makes the
 * employee's "your HR team can see the providers you picked" true — HR now sees them.
 */
export async function getCaseRfqs(caseId: string): Promise<CaseRfq[]> {
  const res = await fetch(`${BASE}/api/hr/cases/${encodeURIComponent(caseId)}/rfqs`, {
    method: "GET",
    headers: getAuthHeaders(),
  })
  const data = await handleResponse<{ rfqs: CaseRfq[] }>(res)
  return data.rfqs
}

/** [AIQ-1677] Per-recipient outcome of a dispatch (from supplier_link_dispatch). `sent` is
 * true only when an email actually went out; `error` explains a skip (no verified address,
 * placeholder domain, RESEND not configured, …). */
export interface DispatchRfqTargetResult {
  recipient_id: string | null
  supplier_name: string | null
  ok: boolean
  sent: boolean
  error?: string | null
}

/** [AIQ-1670] Result of an HR-gated RFQ dispatch. */
export interface DispatchRfqResult {
  ok: boolean
  rfq_id: string
  dispatched: number
  /** [AIQ-1677] Per-recipient results — count `sent === true` for the honest emailed-count. */
  results?: DispatchRfqTargetResult[]
}

/**
 * [AIQ-1670] HR-gated dispatch: mint a supplier token for every recipient of this RFQ
 * (reusing the audited supplier magic-link path). `sendEmail` defaults OFF — minting a link
 * is harmless, but emailing a real supplier is opt-in and only fires with RESEND configured.
 */
export async function dispatchCaseRfq(
  caseId: string,
  rfqId: string,
  sendEmail = false
): Promise<DispatchRfqResult> {
  const res = await fetch(
    `${BASE}/api/hr/cases/${encodeURIComponent(caseId)}/rfqs/${encodeURIComponent(rfqId)}/dispatch`,
    {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ send_email: sendEmail }),
    }
  )
  return handleResponse<DispatchRfqResult>(res)
}

export async function getCaseProviders(caseId: string): Promise<CaseProvider[]> {
  const res = await fetch(`${BASE}/api/hr/cases/${encodeURIComponent(caseId)}/providers`, {
    method: "GET",
    headers: getAuthHeaders(),
  })
  const data = await handleResponse<{ providers: CaseProvider[] }>(res)
  return data.providers
}

export async function assignTask(
  caseId: string,
  providerId: string,
  title: string,
  description?: string,
  dueDate?: string
): Promise<ProviderTask> {
  const res = await fetch(`${BASE}/api/hr/cases/${encodeURIComponent(caseId)}/tasks`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({
      provider_id: providerId,
      title,
      description: description ?? null,
      due_date: dueDate ?? null,
    }),
  })
  const data = await handleResponse<{ task: ProviderTask }>(res)
  return data.task
}

export async function updateTask(
  taskId: string,
  updates: Partial<Pick<ProviderTask, "title" | "description" | "due_date" | "status">>
): Promise<ProviderTask> {
  const res = await fetch(`${BASE}/api/hr/tasks/${encodeURIComponent(taskId)}`, {
    method: "PATCH",
    headers: getAuthHeaders(),
    body: JSON.stringify(updates),
  })
  const data = await handleResponse<{ task: ProviderTask }>(res)
  return data.task
}

export async function cancelTask(taskId: string): Promise<void> {
  const res = await fetch(`${BASE}/api/hr/tasks/${encodeURIComponent(taskId)}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  })
  await handleResponse<void>(res)
}
