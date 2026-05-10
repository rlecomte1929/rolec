import type { PolicyAssistantAnswer } from '../../types/policyAssistant';

const STORAGE_PREFIX = 'relopass_employee_policy_assistant_v1';
const MAX_STORED_TURNS = 20;

export type StoredEmployeePolicyTurn = {
  id: string;
  question: string;
  answer: PolicyAssistantAnswer;
  assistantRequestId?: string | null;
};

function storageKey(assignmentId: string): string {
  return `${STORAGE_PREFIX}:${assignmentId}`;
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function looksLikeAnswer(v: unknown): v is PolicyAssistantAnswer {
  if (!isPlainObject(v)) return false;
  const a = v as Record<string, unknown>;
  // Stored turns are produced by this app; require a minimal shape so tampered localStorage is ignored.
  return typeof a.answer_type === 'string' && typeof a.answer_text === 'string' && Array.isArray(a.evidence);
}

function looksLikeTurn(v: unknown): v is StoredEmployeePolicyTurn {
  if (!isPlainObject(v)) return false;
  return typeof v.id === 'string' && typeof v.question === 'string' && looksLikeAnswer(v.answer);
}

function normalizeStoredAnswer(raw: PolicyAssistantAnswer): PolicyAssistantAnswer {
  return {
    answer_type: raw.answer_type,
    canonical_topic: raw.canonical_topic ?? null,
    answer_text: raw.answer_text,
    policy_status: raw.policy_status ?? 'unknown',
    comparison_readiness: raw.comparison_readiness ?? 'not_applicable',
    evidence: raw.evidence ?? [],
    conditions: raw.conditions ?? [],
    approval_required: raw.approval_required ?? false,
    follow_up_options: raw.follow_up_options ?? [],
    refusal: raw.refusal ?? null,
    role_scope: raw.role_scope ?? 'employee',
    detected_intent: raw.detected_intent ?? null,
  };
}

export function loadEmployeePolicyAssistantTurns(assignmentId: string): StoredEmployeePolicyTurn[] {
  if (!assignmentId.trim()) return [];
  try {
    const raw = localStorage.getItem(storageKey(assignmentId));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    const turns = parsed.filter(looksLikeTurn).map((t) => ({
      ...t,
      answer: normalizeStoredAnswer(t.answer),
    }));
    return turns.slice(-MAX_STORED_TURNS);
  } catch {
    return [];
  }
}

export function saveEmployeePolicyAssistantTurns(assignmentId: string, turns: StoredEmployeePolicyTurn[]): void {
  if (!assignmentId.trim()) return;
  try {
    const trimmed = turns.slice(-MAX_STORED_TURNS);
    localStorage.setItem(storageKey(assignmentId), JSON.stringify(trimmed));
  } catch {
    // ignore quota / private mode
  }
}

export function clearEmployeePolicyAssistantTurns(assignmentId: string): void {
  if (!assignmentId.trim()) return;
  try {
    localStorage.removeItem(storageKey(assignmentId));
  } catch {
    // ignore
  }
}
