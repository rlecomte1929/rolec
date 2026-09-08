"""ReloPass deterministic primitives — pure-Python, no SDK deps.

This sub-package (under `backend/`) houses domain primitives that are
independent of any OCR vendor, web framework, or DB layer. Modules here
MUST NOT import from `backend/app/`, `fastapi`, `sqlalchemy`, or any
vendor SDK — they are the building blocks the higher layers compose
against. Living under `backend/` keeps all server-side Python in one
folder; the namespace is `backend.relopass.*` for imports.

Created as part of C1-02 (MRZ parser). Future C1-* tasks will extend this
package with additional document parsing and validation primitives.
"""
