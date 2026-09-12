# Changelog

Notable changes to the ReloPass backend. Newest first.

## [Unreleased]

### Added
- Norway UDI GP7028 (skilled worker) is a fillable AcroForm. Vault `civil_partnership` ticks Married / civil partner.

### Changed
- **AUDIT-C1 — `backend/database.py` monolith decomposition (AIQ-664 → AIQ-669).**
  The single ~17,900-line `Database` class was progressively split into
  domain-scoped mixin modules under `backend/db/`, each inherited by `Database`
  so every `db.<method>(...)` caller keeps working unchanged via MRO. No behaviour
  change — every method was relocated verbatim.

  `backend/database.py` line count across the series:

  | Stage | What moved | `database.py` lines |
  |---|---|---:|
  | C1.1 baseline (AIQ-664) | inventory only | 17,906 |
  | C1.2/C1.3 (cases, policies) | `db/cases.py`, `db/policies.py` | ~13,159 |
  | C1.4 (AIQ-667) | `db/users.py`, `db/auth.py` | 11,854 |
  | C1.5 (AIQ-668) | `db/intake.py`, `db/hr.py` | 10,504 |
  | C1.6a (AIQ-669) | `db/companies.py`, `db/support.py`, `db/vendors.py`, `db/audit.py` + policies/cases remainders | 5,606 |
  | **C1.6b (AIQ-669)** | `db/misc.py` (incl. `init_db`); only `Database.__init__` remains | **1,270** |

  After C1.6b, `backend/database.py` holds only module-level helpers, the
  `Database` class shell, and `__init__`; all 465 original methods live in the
  11 `backend/db/*.py` mixins.

  **Cold-start (`time python -c 'import backend.main'`, cold `__pycache__`,
  SQLite, median of 3):**
  - Before C1.6b (`database.py` = 5,606 lines): **2.01s**
  - After C1.6b (`database.py` = 1,270 lines): **1.88s**

  A modest (~6%) and somewhat noise-bounded import-time improvement — the
  dominant win is structural (the 17.9k-line monolith is gone), since the mixin
  modules are still imported eagerly by `backend.database`. Further cold-start
  gains would require lazy module loading, which the mixin split now enables as a
  follow-up.
