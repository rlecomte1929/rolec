/// <reference types="vite/client" />
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
        message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail)
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

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

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
