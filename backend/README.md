# backend

## System dependencies

### libmagic (SEC-006 upload validation)

`backend/app/services/upload_validator.py` uses **python-magic** for
content-based MIME detection on file uploads (never the client-supplied
Content-Type or extension). python-magic wraps the system **libmagic** C
library, which must be present at runtime:

- **Render** (`python:3.11-slim`): ships libmagic via apt - no action needed.
- **Local macOS dev**: `brew install libmagic`.
- **Local Debian/Ubuntu**: `apt-get install libmagic1`.

If libmagic is missing, `import magic` raises `ImportError: failed to find
libmagic`. The unit tests skip gracefully via `pytest.importorskip`.
