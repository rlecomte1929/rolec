# Identity & assignment model — code audit

Evidence is from the ReloPass **Python backend** (`backend/main.py`, `backend/database.py`) unless noted. Production may use Postgres (e.g. Supabase) with the same SQLAlchemy layer; **unique semantics on `users` match the DDL in `init_db`**.

---

## 1. What tables/entities represent what?

| Concern | Primary store | Notes |
|--------|----------------|--------|
| **Auth / login account** | `users` | `id`, optional `username` (**UNIQUE**), optional `email` (**UNIQUE**), `password_hash`, `role`, `name`, `created_at`. Sessions use `sessions.token` → `user_id`. |
| **Extended profile / company link** | `profiles` | `id` **equals** `users.id` (same UUID). `role`, `email`, `full_name`, `company_id`. Used for HR/Admin company scoping; **not** a second login identity. |
| **Company-scoped “employee roster” row** | `employees` | `profile_id` → `profiles.id`, `company_id`. Ensured when HR assigns (`ensure_employee_for_profile`). One row per profile is updated/inserted, not one per assignment. |
| **Company-scoped HR row** | `hr_users` | `profile_id`, `company_id`. |
| **Relocation case (wizard/case record)** | `relocation_cases` (+ related wizard tables as used elsewhere) | Created by HR via `POST /api/hr/cases` (`create_case` → `db.create_case`). |
| **Assignment (HR ↔ employee on a case)** | `case_assignments` | `id`, `case_id`, `canonical_case_id`, `hr_user_id`, `employee_user_id` (nullable), `employee_identifier` (string: email or username), status, optional name columns. |
| **Invitation / claim helper** | `assignment_invites` | `case_id`, `hr_user_id`, `employee_identifier`, `token`, `status` (`ACTIVE` / updated to `CLAIMED`). Only used when **no** `users` row could be linked at assign time. |
| **Messages / comms** | `messages` | Draft invitation copy; not identity. |

There is **no separate “contact” table** for the employee email on an assignment: the string lives on `case_assignments.employee_identifier`, and optionally a **full `users` row** is created for that email.

---

## 2. When HR creates an assignment with an email — what happens?

**Endpoint:** `POST /api/hr/cases/{case_id}/assign` → `assign_case` in `backend/main.py` (≈2994–3180).

1. **Resolve existing auth user**  
   `employee_user = db.get_user_by_identifier(employee_identifier)`  
   - If identifier contains `@`, this resolves via **`get_user_by_email`** (normalized lowercased email).  
   - Else username, then email fallback (`backend/database.py`, `get_user_by_identifier`).

2. **If no user and identifier looks like an email (`"@" in employee_identifier`)**  
   The code **auto-provisions a real auth user**:
   - New UUID `employee_user_id`
   - `db.create_user(..., username=None, email=employee_identifier.lower(), password_hash=hash("Passw0rd!"), role=EMPLOYEE, ...)`
   - `db.ensure_profile_record(..., company_id=hr_company_id)`
   - `db.ensure_employee_for_profile(employee_user["id"], hr_company_id)`
   - `created_new_employee = True`  
   See `backend/main.py` ≈3051–3076.

3. **Create assignment row**  
   `db.create_assignment(..., employee_user_id=employee_user["id"] if employee_user else None, employee_identifier=employee_identifier, ...)`  
   So after auto-provision, **`employee_user_id` is set** to the new user.

4. **Invite row**  
   `assignment_invites` is created **only if** `employee_user` is still falsy (`backend/main.py` ≈3130–3145).  
   After email auto-provision, **`employee_user` is set**, so **no invite token** is created for that path.

5. **HR message body**  
   Includes temp password line when `created_new_employee` (`backend/main.py` ≈3153–3161).

**Conclusion:** For email identifiers, HR assignment **does not** only “reserve” an email — it **creates a row in `users` with that email**, which is exactly what blocks self-service **register** later.

---

## 3. When signup runs — what causes “Email already in use”?

**Endpoint:** `POST /api/auth/register` → `register` in `backend/main.py` (≈979–1000).

After normalizing email to lowercase:

```python
if db.get_user_by_email(email):
    raise HTTPException(status_code=400, detail="Email already in use")
```

`get_user_by_email` selects from **`users`** (`backend/database.py` ≈1763–1771).

**Root cause of the screenshot conflict:**  
HR `assign_case` has already inserted into **`users`** with that email (auto-register path). `register` then finds that row and returns **400** with `"Email already in use"`.

This is **not** a collision with `assignment_invites`, `profiles` alone, or `employees` — the gate is **`users.email` uniqueness + pre-existing row**.

---

## 4. Admin vs HR assignment flows — same logic?

**No.**

| Flow | Endpoint | Creates `users` row for unknown email? |
|------|-----------|----------------------------------------|
| **HR** | `POST /api/hr/cases/{case_id}/assign` | **Yes**, if `"@" in employee_identifier` and no existing user (`main.py` ≈3051–3076). |
| **Admin** | `POST /api/admin/assignments` (`admin_create_assignment`, ≈1749–1796) | **No**. Only sets `employee_user_id` if `body.employee_user_id` or `get_user_by_identifier(employee_identifier)` finds someone. Otherwise assignment is created with **`employee_user_id=None`** and a string `employee_identifier` (defaults to `"admin-created"` if nothing passed). |

So the **Jane Doe** scenario (HR dashboard + email) hits the **HR** path and triggers auto-user creation. An admin-created assignment with only an email string **without** an existing user would leave `employee_user_id` null (and would rely on post-login linking — see below).

---

## 5. Multiple assignments for the same employee — reuse or duplicate person records?

- **`users`:** At most **one** row per email (`UNIQUE` on `email` in `users` DDL, `backend/database.py` ≈1713–1721). Second HR assign with same email calls `get_user_by_identifier` → finds existing user → **reuses** same `employee_user_id`.
- **`case_assignments`:** Each assign creates a **new assignment row** (new UUID) on the given case flow; multiple rows can reference the **same** `employee_user_id`.
- **`employees`:** `ensure_employee_for_profile` updates or inserts **one** row per `profile_id` (`backend/database.py` ≈6041–6067); it does not create duplicate employees for the same profile on each assignment.

---

## Post-signin / post-login linking (unassigned assignments)

**Endpoint:** `GET /api/employee/assignments/current` (`main.py` ≈3206+).

If the employee is logged in but their assignment has `employee_user_id IS NULL`, the code tries:

- `db.get_unassigned_assignment_by_identifier(identifier)` where `identifier` is `effective.get("username") or effective.get("email")`  
- Match is **`case_assignments.employee_identifier = :ident`** (exact string, `database.py` ≈3027–3041).

If found, it **`attach_employee_to_assignment`**, **`mark_invites_claimed`**, etc.

**Implication:** Order-of-operations and **exact** `employee_identifier` matching matter for the **no-user** provisioning path. This is orthogonal to the “email already in use” bug, but is part of the same identity story.

---

## Bad assumptions (current design)

1. **Treating HR email entry as “create auth user + temp password”** blurs **workflow contact** with **credential lifecycle**. Employees naturally choose **Create account** in the UI; the platform already created `users` for them.
2. **`users.email` is both** global login identity **and** the HR invite key — no separate “pending invite” identity without a `users` row for the email path.
3. **UX copy** (“sign up”) vs **server behavior** (already registered) are misaligned for the auto-provision path.
4. **`profiles.email`** is not the uniqueness enforcer for signup; **`users.email`** is. Documentation/UI that only mention “profile” understate the issue.

---

## Recommended canonical separation of concerns (directional — no code change in this doc)

1. **Credential account** (`users` + sessions): created only by explicit registration (or a controlled admin “invite accept” flow that either links or creates once).
2. **Assignment participant / contact**: `case_assignments.employee_identifier` + optional `employee_user_id` **nullable until claim**.
3. **Claim**: Idempotent link when the real user logs in or completes invite — update `employee_user_id`, never require a second `users` row for the same email.
4. **Company roster** (`employees`): derived from linked `profiles` / assignments, not from preemptive `users` creation.

Until then, the **documented workaround** for HR-auto-provisioned users is **login** with the emailed credentials (temp password), **not** self-service register again — but the product should not rely on users reading that.

---

## File reference index

| Area | Location |
|------|-----------|
| Register / email check | `backend/main.py` `register` |
| Login | `backend/main.py` `login` |
| HR assign + auto user | `backend/main.py` `assign_case` |
| Admin assign | `backend/main.py` `admin_create_assignment` |
| Employee assignment fetch + attach | `backend/main.py` `get_employee_assignment` |
| `users` DDL + CRUD | `backend/database.py` `_create_users_table`, `create_user`, `get_user_by_email`, `get_user_by_identifier` |
| Assignments + invites | `backend/database.py` `create_assignment`, `get_unassigned_assignment_by_identifier`, `create_assignment_invite`, `mark_invites_claimed` |
| Profiles / employees | `backend/database.py` `ensure_profile_record`, `ensure_employee_for_profile` |
