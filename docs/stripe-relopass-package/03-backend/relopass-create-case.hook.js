/**
 * Server function: relopass-create-case
 * POST /api/workspaces/776786/hooks/relopass-create-case/execute
 *
 * Creates a corridor-check case for the ReloPass Case Command paid roadmap
 * gate. Accepts { corridor, employeeType, moveDate } and returns { caseId }.
 *
 * STORAGE NOTE: the build spec says "insert into relocation_cases", but the
 * live WorkspaceDB relocation_cases table is the GlobeIQ demo case table and
 * has none of the payment columns (and WorkspaceDB tables cannot be ALTERed).
 * Payment/access state lives in the sidecar table `case_access` (FK case_id →
 * relocation_cases.id), which has exactly the required columns:
 * corridor, employee_type, move_date, payment_status (default 'unpaid'),
 * access_tier (default 'free'), stripe_session_id, stripe_payment_intent_id,
 * paid_at, amount_cents. `caseId` in every relopass-* hook = case_access.id.
 */

const body = request.body || {};
const corridor =
  typeof body.corridor === 'string' && body.corridor.trim()
    ? body.corridor.trim().toLowerCase()
    : 'france-norway';
const employeeType = body.employeeType;
const moveDate = body.moveDate;
const sessionId = typeof body.sessionId === 'string' ? body.sessionId : null;

const validEmployee = employeeType === 'eea' || employeeType === 'non-eea';
const validDate = typeof moveDate === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(moveDate);

if (!validEmployee || !validDate) {
  respond(400, {
    error: "employeeType ('eea' | 'non-eea') and moveDate (YYYY-MM-DD) are required",
  });
} else {
  // case_key is required + unique on case_access. Namespaced 'relopass|…' with
  // a time/random suffix so every create call yields a fresh case row.
  const caseKey = [
    'relopass',
    corridor,
    employeeType,
    moveDate,
    Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8),
  ].join('|');

  const now = new Date().toISOString();
  const inserted = await db.insert('case_access', {
    case_key: caseKey,
    corridor: corridor,
    employee_type: employeeType,
    move_date: moveDate,
    access_tier: 'free',
    payment_status: 'unpaid',
    session_id: sessionId,
    created_at: now,
    updated_at: now,
  });

  const row = inserted.insertedRows && inserted.insertedRows[0];
  if (!row) {
    respond(500, { error: 'case row could not be created' });
  } else {
    respond(200, { caseId: row.id });
  }
}
