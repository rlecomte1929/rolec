"""
[AIQ-1879 / T18-04] PATCH /api/cases/{id}/relocationBasics returned 500 on every call.

Reproduced in prod 2026-08-20, request_id 9f8ef924-6781-471d-8536-35505d554124. The
Render log gives the cause exactly:

    AttributeError("'Depends' object has no attribute 'get'")

`patch_case` is declared `(case_id, patch, background_tasks, user=Depends(...))`. The
alias called it positionally as `patch_case(case_id, wrapped, user)`, so the user DICT
bound to `background_tasks` and `user` kept its unresolved `Depends` sentinel; the
first `user.get(...)` inside patch_case blew up.

Calling a FastAPI handler as a plain Python function does NOT resolve its Depends
defaults. #1177 inserted `background_tasks` ahead of `user` on 2026-06-29 and never
updated this caller, so the route had been dead for roughly seven weeks while still
being advertised in the public OpenAPI schema.

`test_alias_signature_stays_compatible_with_patch_case` is the durable guard: it fails
on the NEXT parameter reorder, which is the actual failure mode, rather than only on
this particular instance of it.
"""
from __future__ import annotations

import inspect
import os
import sys
import unittest
from unittest import mock

from fastapi import BackgroundTasks
from fastapi.params import Depends as DependsParam

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app import schemas  # noqa: E402
from backend.app.routers import cases_write  # noqa: E402

BASICS = schemas.RelocationBasicsDTO(
    originCountry="ES",
    originCity="Madrid",
    destCountry="IE",
    destCity="Dublin",
    purpose="employment",
)


class AliasDelegationTests(unittest.TestCase):
    def test_alias_passes_a_real_user_not_a_depends_sentinel(self) -> None:
        """THE regression. Before the fix, `user` arrived as an unresolved Depends
        and `patch_case` raised 'Depends' object has no attribute 'get'."""
        captured = {}

        def _fake_patch_case(**kwargs):
            captured.update(kwargs)
            return "ok"

        with mock.patch.object(cases_write, "patch_case", _fake_patch_case):
            cases_write.patch_case_relocation_basics(
                case_id="case-1",
                basics=BASICS,
                background_tasks=BackgroundTasks(),
                user={"id": "u1", "role": "HR"},
            )

        self.assertNotIsInstance(
            captured.get("user"), DependsParam,
            "user arrived as an unresolved Depends — the AIQ-1879 bug",
        )
        self.assertEqual(captured["user"], {"id": "u1", "role": "HR"})

    def test_alias_passes_a_real_background_tasks(self) -> None:
        """The user dict used to land here. If it does again, patch_case's
        `background_tasks.add_task(...)` breaks instead."""
        captured = {}

        def _fake_patch_case(**kwargs):
            captured.update(kwargs)
            return "ok"

        with mock.patch.object(cases_write, "patch_case", _fake_patch_case):
            cases_write.patch_case_relocation_basics(
                case_id="case-1", basics=BASICS,
                background_tasks=BackgroundTasks(), user={"id": "u1"},
            )
        self.assertIsInstance(captured.get("background_tasks"), BackgroundTasks)

    def test_alias_wraps_the_basics_into_a_case_draft(self) -> None:
        captured = {}

        def _fake_patch_case(**kwargs):
            captured.update(kwargs)
            return "ok"

        with mock.patch.object(cases_write, "patch_case", _fake_patch_case):
            cases_write.patch_case_relocation_basics(
                case_id="case-1", basics=BASICS,
                background_tasks=BackgroundTasks(), user={"id": "u1"},
            )
        patch = captured["patch"]
        self.assertIsInstance(patch, schemas.CaseDraftDTO)
        self.assertEqual(patch.relocationBasics.destCountry, "IE")
        self.assertEqual(patch.relocationBasics.destCity, "Dublin")

    def test_alias_delegates_by_keyword_not_position(self) -> None:
        """Positional delegation is what broke this. A keyword call cannot silently
        rebind when patch_case's parameter ORDER changes."""
        seen = {}

        def _fake_patch_case(*args, **kwargs):
            seen["args"] = args
            seen["kwargs"] = kwargs
            return "ok"

        with mock.patch.object(cases_write, "patch_case", _fake_patch_case):
            cases_write.patch_case_relocation_basics(
                case_id="case-1", basics=BASICS,
                background_tasks=BackgroundTasks(), user={"id": "u1"},
            )
        self.assertEqual(seen["args"], (), "alias still delegates positionally")
        self.assertEqual(
            set(seen["kwargs"]), {"case_id", "patch", "background_tasks", "user"}
        )


class SignatureDriftGuardTests(unittest.TestCase):
    """The durable guard. #1177 added a parameter to patch_case and left this caller
    behind; nothing failed until a user hit the route in prod seven weeks later."""

    def test_alias_signature_stays_compatible_with_patch_case(self) -> None:
        target = inspect.signature(cases_write.patch_case)
        alias = inspect.signature(cases_write.patch_case_relocation_basics)

        required = {
            name for name, p in target.parameters.items()
            if p.default is inspect.Parameter.empty and name != "patch"
        }
        missing = required - set(alias.parameters)
        self.assertFalse(
            missing,
            f"patch_case requires {sorted(missing)} which the alias cannot supply — "
            "declare them on the alias and forward them by keyword (AIQ-1879)",
        )

    def test_alias_can_actually_call_patch_case(self) -> None:
        """Bind the alias's forwarded arguments against patch_case's real signature.
        Raises TypeError on any incompatibility, without executing either handler."""
        inspect.signature(cases_write.patch_case).bind(
            case_id="case-1",
            patch=schemas.CaseDraftDTO(relocationBasics=BASICS),
            background_tasks=BackgroundTasks(),
            user={"id": "u1"},
        )


if __name__ == "__main__":
    unittest.main()
