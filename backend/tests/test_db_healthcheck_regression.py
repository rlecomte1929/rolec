"""Regression: MiscMixin._db_healthcheck referenced an undefined `Database`.

The [AUDIT-C1.6b] mixin extraction (#643) moved init_db/_db_healthcheck into
backend/db/misc.py but left `info = Database.get_db_info()`. `Database` is the
class in backend/database.py and is NOT imported into the extracted module, so
_db_healthcheck raised `NameError: name 'Database' is not defined`. Because
_db_healthcheck runs inside init_db()/ensure_initialized(), every endpoint that
calls ensure_initialized() (e.g. GET /api/hr/assignments via
_list_assignments_for_company_core) returned a 500 on every request.

Same failure class as test_cases_is_sqlite.py from the earlier C1 extraction.
"""
import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from backend.db.misc import MiscMixin  # noqa: E402


def test_db_healthcheck_resolves_get_db_info_without_nameerror():
    """Exercise the real method via a stub self that inherits the mixin.
    Before the fix this raised NameError('name \\'Database\\' is not defined')."""

    class _Conn:
        def execute(self, *a, **k):
            return None

    class _StubDB(MiscMixin):
        pass

    # get_db_info is a @staticmethod on MiscMixin; must resolve via self.
    MiscMixin._db_healthcheck(_StubDB(), _Conn())  # no exception == pass
