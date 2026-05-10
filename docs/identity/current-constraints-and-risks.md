# Current constraints & risks — identity / assignment

This document lists **enforced constraints** and **behavioral risks** observed in code (`backend/database.py`, `backend/main.py`). It does not propose fixes.

---

## Unique constraints in play

### `users` (SQLite DDL in `init_db`)

- `username TEXT UNIQUE` — nullable; multiple rows can have `NULL` username in SQLite, but application logic usually sets email-only users with `username=None`.
- `email TEXT UNIQUE` — enforced at insert; **`create_user` catches `IntegrityError` and returns `False`** (`database.py` ≈1749–1761).

**Signup path:** `register` checks **`get_user_by_email`** before insert → **400 `"Email already in use"`** if any row exists (`main.py` ≈996–1000).

### `admin_allowlist`

- `email TEXT PRIMARY KEY` — unrelated to employee signup conflict unless same email is used in allowlist logic.

### `profiles`

- SQLite schema: **`email` has no UNIQUE constraint** (`database.py` ≈876–883). In practice, application uses `profiles.id = users.id`, so duplicate emails across **different** users would require a bug or manual SQL; normal app paths tie one profile per user.

### `employees`

- No unique on `(company_id, profile_id)` in the shown SQLite DDL (`database.py` ≈922–931). **`ensure_employee_for_profile`** selects by `profile_id` and updates or inserts one row (`database.py` ≈6048–6067), reducing duplicate risk at the application layer.

### `assignment_invites`

- No unique constraint on `(case_id, employee_identifier)` in the legacy DDL fragment (`database.py` ≈319+). Duplicate invite rows for the same case/identifier are theoretically possible if code paths double-insert.

---

## Order-of-operations hazards

### 1. HR assigns with email **before** employee self-registers (primary bug)

- **Order:** `assign_case` runs → **`users` row created** with that email → employee opens **Create account** → `register` → **`Email already in use`**.
- **Reverse order:** If employee `register`s first, HR `get_user_by_identifier` finds them → **no** second user; assignment gets `employee_user_id` set; **no** invite row.

### 2. Admin assignment without `users` row

- **Order:** Admin creates assignment with `employee_user_id=None` and meaningful `employee_identifier` → employee **can** `register` (email free) → login → `get_employee_assignment` may **attach** if `employee_identifier` **exactly** matches login identifier string.

### 3. Identifier string equality (`get_unassigned_assignment_by_identifier`)

- Query: `WHERE employee_user_id IS NULL AND employee_identifier = :ident` (`database.py` ≈3035–3037).
- `ident` comes from logged-in user’s **username or email** (`main.py` ≈3214–3217).
- **Risk:** HR typed `Jane@corp.com`, employee registers as `jane@corp.com` — email normalized on **register** for **`users.email`**, but **`case_assignments.employee_identifier`** may still hold the original casing/spacing. Mismatch → **no attach**, employee appears without assignment until data fixed.

### 4. HR auto-provision uses lowercase email for `users.email`

- `employee_identifier.lower()` on create (`main.py` ≈3062). HR’s raw `employee_identifier` is still stored on **`case_assignments`** as provided (`assign_case` uses stripped but not necessarily lowercased string for `employee_identifier` in `create_assignment` — compare lines 3026 vs 3062). Potential **identifier vs stored email** drift for non-normalized assignment strings.

---

## Places duplicate or conflicting records can appear

| Scenario | What can go wrong |
|----------|-------------------|
| **Double HR assign, same email** | **One** `users` row; **multiple** `case_assignments` (expected). |
| **Register + HR auto-provision race** | Unlikely double `users` if second insert hits `IntegrityError`; first wins. User-facing error is dominated by **pre-check** `get_user_by_email`. |
| **Same person, two emails** | Two `users` rows (different emails). Assignments keyed by one email won’t attach to the other without manual relink. |
| **Username signup vs email provisioned user** | HR created user with `username=None`, email set. Employee tries register with **new** username but **same email** → still **Email already in use** (email check runs). |
| **Invite unused** | If HR path created a **user**, invite is skipped; token-based claim is irrelevant for that path. |
| **`create_user` returns False** | `register` path: unlikely if `get_user_by_email` passed; could happen race. Message: **"Unable to create user (username or email may already exist)"** (`main.py` ≈1024–1025) vs explicit **Email already in use** earlier. |

---

## Security / operational notes (context)

- HR auto-provision uses a **hard-coded temp password** (`Passw0rd!`) in `assign_case` (`main.py` ≈3056, 3153). That is a separate risk from uniqueness but compounds the identity confusion (users are told to log in, not to “sign up”).
- **Sessions** are opaque tokens in `sessions` table; logout deletes by token.

---

## Related doc

- Full model and flow narrative: [`identity-assignment-audit.md`](./identity-assignment-audit.md)
