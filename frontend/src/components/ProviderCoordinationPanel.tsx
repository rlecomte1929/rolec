/// <reference types="vite/client" />
import React, { useCallback, useEffect, useRef, useState } from "react"
import { supabase } from "../api/supabase"
import {
  assignTask,
  cancelTask,
  getCaseProviders,
  updateTask,
  type CaseProvider,
  type ProviderTask,
} from "../api/hrCoordination"
import { Input } from './antigravity/Input';
import { Button } from './antigravity/Button';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isOverdue(task: ProviderTask): boolean {
  if (!task.due_date) return false
  if (task.status === "completed" || task.status === "cancelled") return false
  return new Date(task.due_date) < new Date(new Date().toDateString())
}

function typeIcon(type: CaseProvider["type"]): string {
  switch (type) {
    case "housing":
      return "🏠"
    case "immigration":
      return "⚖️"
    case "shipping":
      return "📦"
    default:
      return "🔧"
  }
}

function statusLabel(s: ProviderTask["status"]): string {
  switch (s) {
    case "pending":
      return "Pending"
    case "in_progress":
      return "In Progress"
    case "completed":
      return "Completed"
    case "cancelled":
      return "Cancelled"
    default:
      return s
  }
}

const TASK_STATUS_OPTIONS: ProviderTask["status"][] = [
  "pending",
  "in_progress",
  "completed",
  "cancelled",
]

// ---------------------------------------------------------------------------
// TaskStatusChip — inline dropdown to change status
// ---------------------------------------------------------------------------

interface TaskStatusChipProps {
  taskId: string
  status: ProviderTask["status"]
  onUpdated: () => void
}

function TaskStatusChip({ taskId, status, onUpdated }: TaskStatusChipProps) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const chipColor: Record<ProviderTask["status"], string> = {
    pending: "bg-gray-100 text-gray-700 border-gray-300",
    in_progress: "bg-blue-100 text-blue-700 border-blue-300",
    completed: "bg-green-100 text-green-700 border-green-300",
    cancelled: "bg-red-100 text-red-600 border-red-300",
  }

  async function handleChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const next = e.target.value as ProviderTask["status"]
    if (next === status) return
    setSaving(true)
    setError(null)
    try {
      if (next === "cancelled") {
        await cancelTask(taskId)
      } else {
        await updateTask(taskId, { status: next })
      }
      onUpdated()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update status")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <select
        value={status}
        onChange={handleChange}
        disabled={saving}
        className={`text-xs font-medium border rounded px-2 py-0.5 cursor-pointer focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-blue-400 disabled:opacity-60 ${chipColor[status]}`}
        aria-label="Change task status"
      >
        {TASK_STATUS_OPTIONS.map((s) => (
          <option key={s} value={s}>
            {statusLabel(s)}
          </option>
        ))}
      </select>
      {error && <p className="text-red-500 text-xs mt-0.5">{error}</p>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// TaskCard
// ---------------------------------------------------------------------------

interface TaskCardProps {
  task: ProviderTask
  onUpdated: () => void
}

function TaskCard({ task, onUpdated }: TaskCardProps) {
  const overdue = isOverdue(task)

  return (
    <div
      className={`bg-white border rounded-lg p-3 flex flex-col gap-2 shadow-sm ${
        overdue ? "border-l-4 border-l-amber-400" : "border-gray-200"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-gray-800 leading-snug">{task.title}</p>
        <TaskStatusChip taskId={task.id} status={task.status} onUpdated={onUpdated} />
      </div>
      {task.description && (
        <p className="text-xs text-gray-500 leading-relaxed">{task.description}</p>
      )}
      <div className="flex items-center gap-2 flex-wrap">
        {task.due_date && (
          <span
            className={`text-xs ${
              overdue ? "text-amber-600 font-semibold" : "text-gray-400"
            }`}
          >
            Due {task.due_date}
            {overdue && " — overdue"}
          </span>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ProviderRow
// ---------------------------------------------------------------------------

interface ProviderRowProps {
  provider: CaseProvider
  onUpdated: () => void
}

function ProviderRow({ provider, onUpdated }: ProviderRowProps) {
  const [expanded, setExpanded] = useState(true)

  const providerStatusColor: Record<CaseProvider["status"], string> = {
    active: "bg-green-100 text-green-700",
    inactive: "bg-gray-100 text-gray-500",
    suspended: "bg-red-100 text-red-600",
  }

  const { pending, in_progress, completed, cancelled } = provider.task_counts
  const total = pending + in_progress + completed + cancelled

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden bg-gray-50 shadow-sm">
      {/* Header */}
      <Button unstyled
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-100 transition-colors focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-400"
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-lg" aria-hidden>
            {typeIcon(provider.type)}
          </span>
          <span className="font-semibold text-gray-800 truncate">{provider.name}</span>
          <span
            className={`text-xs font-medium px-2 py-0.5 rounded-full ${
              providerStatusColor[provider.status]
            }`}
          >
            {provider.status}
          </span>
        </div>
        <div className="flex items-center gap-3 shrink-0 ml-2">
          {/* Task count summary bar */}
          {total > 0 && (
            <div className="hidden sm:flex items-center gap-1 text-xs text-gray-500">
              {pending > 0 && (
                <span className="bg-gray-200 text-gray-600 rounded px-1.5 py-0.5">
                  {pending} pending
                </span>
              )}
              {in_progress > 0 && (
                <span className="bg-blue-100 text-blue-600 rounded px-1.5 py-0.5">
                  {in_progress} active
                </span>
              )}
              {completed > 0 && (
                <span className="bg-green-100 text-green-600 rounded px-1.5 py-0.5">
                  {completed} done
                </span>
              )}
              {cancelled > 0 && (
                <span className="bg-red-100 text-red-500 rounded px-1.5 py-0.5">
                  {cancelled} cancelled
                </span>
              )}
            </div>
          )}
          <span className="text-gray-400 text-sm">{expanded ? "▲" : "▼"}</span>
        </div>
      </Button>

      {/* Mobile task count bar */}
      {total > 0 && (
        <div className="sm:hidden flex flex-wrap items-center gap-1 px-4 pb-2 text-xs text-gray-500">
          {pending > 0 && (
            <span className="bg-gray-200 text-gray-600 rounded px-1.5 py-0.5">
              {pending} pending
            </span>
          )}
          {in_progress > 0 && (
            <span className="bg-blue-100 text-blue-600 rounded px-1.5 py-0.5">
              {in_progress} active
            </span>
          )}
          {completed > 0 && (
            <span className="bg-green-100 text-green-600 rounded px-1.5 py-0.5">
              {completed} done
            </span>
          )}
          {cancelled > 0 && (
            <span className="bg-red-100 text-red-500 rounded px-1.5 py-0.5">
              {cancelled} cancelled
            </span>
          )}
        </div>
      )}

      {/* Collapsible task list */}
      {expanded && (
        <div className="px-4 pb-4">
          {provider.tasks.length === 0 ? (
            <p className="text-sm text-gray-400 italic py-2">No tasks assigned to this provider.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-1">
              {provider.tasks.map((task: ProviderTask) => (
                <TaskCard key={task.id} task={task} onUpdated={onUpdated} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// AssignTaskModal
// ---------------------------------------------------------------------------

interface AssignTaskModalProps {
  caseId: string
  providers: CaseProvider[]
  onClose: () => void
  onAssigned: () => void
}

function AssignTaskModal({ caseId, providers, onClose, onAssigned }: AssignTaskModalProps) {
  const [providerId, setProviderId] = useState(providers[0]?.id ?? "")
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [dueDate, setDueDate] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const overlayRef = useRef<HTMLDivElement>(null)

  // Close on Escape
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose()
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [onClose])

  // Close on outside click
  function handleOverlayClick(e: React.MouseEvent<HTMLDivElement>) {
    if (e.target === overlayRef.current) onClose()
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!title.trim()) {
      setError("Task title is required.")
      return
    }
    if (!providerId) {
      setError("Please select a provider.")
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await assignTask(
        caseId,
        providerId,
        title.trim(),
        description.trim() || undefined,
        dueDate || undefined
      )
      onAssigned()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to assign task.")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="assign-task-title"
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 flex flex-col gap-5">
        <div className="flex items-center justify-between">
          <h2 id="assign-task-title" className="text-lg font-semibold text-gray-800">
            Assign Task
          </h2>
          <Button unstyled
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none focus:outline-none"
            aria-label="Close modal"
          >
            ×
          </Button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
          {/* Provider select */}
          <div className="flex flex-col gap-1">
            <label htmlFor="at-provider" className="text-sm font-medium text-gray-700">
              Provider <span className="text-red-500">*</span>
            </label>
            <select
              id="at-provider"
              value={providerId}
              onChange={(e) => setProviderId(e.target.value)}
              required
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-400"
            >
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {typeIcon(p.type)} {p.name}
                </option>
              ))}
            </select>
          </div>

          {/* Title */}
          <div className="flex flex-col gap-1">
            <label htmlFor="at-title" className="text-sm font-medium text-gray-700">
              Task title <span className="text-red-500">*</span>
            </label>
            <Input unstyled
              id="at-title"
              type="text"
              value={title}
              onChange={(v) => setTitle(v)}
              placeholder="e.g. Confirm lease agreement"
              required
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </div>

          {/* Description */}
          <div className="flex flex-col gap-1">
            <label htmlFor="at-description" className="text-sm font-medium text-gray-700">
              Description <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <textarea
              id="at-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Additional details for the provider…"
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-800 placeholder-gray-400 resize-none focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </div>

          {/* Due date */}
          <div className="flex flex-col gap-1">
            <label htmlFor="at-due" className="text-sm font-medium text-gray-700">
              Due date <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <Input unstyled
              id="at-due"
              type="date"
              value={dueDate}
              onChange={(v) => setDueDate(v)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-3 pt-1">
            <Button unstyled
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-gray-400"
            >
              Cancel
            </Button>
            <Button unstyled
              type="submit"
              disabled={submitting}
              className="px-4 py-2 text-sm font-medium text-white bg-navy-800 hover:bg-navy-900 disabled:opacity-60 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400"
            >
              {submitting ? "Assigning…" : "Assign Task"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function ProviderRowSkeleton() {
  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden bg-gray-50 shadow-sm animate-pulse">
      <div className="flex items-center gap-3 px-4 py-3">
        <div className="w-7 h-7 bg-gray-200 rounded-full" />
        <div className="h-4 bg-gray-200 rounded w-32" />
        <div className="h-4 bg-gray-200 rounded w-16" />
      </div>
      <div className="px-4 pb-4 grid grid-cols-1 md:grid-cols-2 gap-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-white border border-gray-200 rounded-lg p-3 flex flex-col gap-2">
            <div className="h-3 bg-gray-200 rounded w-3/4" />
            <div className="h-3 bg-gray-200 rounded w-1/2" />
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ProviderCoordinationPanel — main export
// ---------------------------------------------------------------------------

interface ProviderCoordinationPanelProps {
  caseId: string
}

export function ProviderCoordinationPanel({ caseId }: ProviderCoordinationPanelProps) {
  const [providers, setProviders] = useState<CaseProvider[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)

  const fetchProviders = useCallback(async () => {
    setFetchError(null)
    try {
      const data = await getCaseProviders(caseId)
      setProviders(data)
    } catch (err) {
      setFetchError(err instanceof Error ? err.message : "Failed to load providers.")
    } finally {
      setLoading(false)
    }
  }, [caseId])

  // Initial fetch
  useEffect(() => {
    setLoading(true)
    void fetchProviders()
  }, [fetchProviders])

  // Supabase Realtime subscription
  useEffect(() => {
    const channel = supabase
      .channel(`case-providers-${caseId}`)
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "provider_tasks",
          filter: `case_id=eq.${caseId}`,
        },
        () => {
          void fetchProviders()
        }
      )
      .subscribe()

    return () => {
      void supabase.removeChannel(channel)
    }
  }, [caseId, fetchProviders])

  return (
    <div className="w-full max-w-4xl mx-auto px-0 sm:px-2">
      {/* Panel header */}
      <div className="flex items-center justify-between mb-4 px-1">
        <h1 className="text-xl font-bold text-gray-900">Provider Coordination</h1>
        {!loading && providers.length > 0 && (
          <Button unstyled
            type="button"
            onClick={() => setShowModal(true)}
            className="flex items-center gap-1.5 px-4 py-2 bg-navy-800 hover:bg-navy-900 text-white text-sm font-medium rounded-xl shadow transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400"
          >
            <span aria-hidden>+</span> Assign Task
          </Button>
        )}
      </div>

      {/* Error state */}
      {fetchError && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl">
          {fetchError}
          <Button unstyled
            type="button"
            onClick={fetchProviders}
            className="ml-3 underline hover:no-underline font-medium"
          >
            Retry
          </Button>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="flex flex-col gap-4">
          <ProviderRowSkeleton />
          <ProviderRowSkeleton />
        </div>
      )}

      {/* Empty state */}
      {!loading && !fetchError && providers.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <span className="text-4xl mb-3" aria-hidden>
            📋
          </span>
          <p className="text-gray-600 font-medium">No providers assigned yet</p>
          <p className="text-gray-400 text-sm mt-1">
            Use &ldquo;Invite Provider&rdquo; to add one, then assign tasks here.
          </p>
        </div>
      )}

      {/* Provider list */}
      {!loading && providers.length > 0 && (
        <div className="flex flex-col gap-4">
          {providers.map((provider) => (
            <ProviderRow
              key={provider.id}
              provider={provider}
              onUpdated={fetchProviders}
            />
          ))}
        </div>
      )}

      {/* Floating assign button (visible when scrolled down on mobile) */}
      {!loading && providers.length > 0 && (
        <div className="fixed bottom-6 right-4 sm:hidden z-40">
          <Button unstyled
            type="button"
            onClick={() => setShowModal(true)}
            className="flex items-center gap-1.5 px-5 py-3 bg-navy-800 hover:bg-navy-900 text-white text-sm font-semibold rounded-full shadow-lg transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400"
          >
            <span aria-hidden>+</span> Assign Task
          </Button>
        </div>
      )}

      {/* Assign Task modal */}
      {showModal && (
        <AssignTaskModal
          caseId={caseId}
          providers={providers}
          onClose={() => setShowModal(false)}
          onAssigned={fetchProviders}
        />
      )}
    </div>
  )
}

export default ProviderCoordinationPanel

