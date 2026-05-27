"""ReloPass deterministic primitives — pure-Python, no SDK deps.

This top-level package houses domain primitives that are independent of any
OCR vendor, web framework, or DB layer. Modules here MUST NOT import from
`backend/`, `fastapi`, `sqlalchemy`, or any vendor SDK — they are the
building blocks the higher layers compose against.

Created as part of C1-02 (MRZ parser). Future C1-* tasks will extend this
package with additional document parsing and validation primitives.
"""
