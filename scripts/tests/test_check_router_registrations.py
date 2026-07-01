"""Unit tests for check_router_registrations.py — both the existing
modular-only check and the new neither-registered check.

Cases covered:
  (a) Router in NEITHER entrypoint, not allowlisted → guard fails
  (b) Router in NEITHER entrypoint but IS allowlisted → guard passes
  (c) Existing modular-only and both-registered cases still behave correctly
      (no regression in the original check)
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_router_registrations as crr  # noqa: E402

# ── synthetic source fragments ────────────────────────────────────────────────

_ACTIVE_ROUTER = """\
    from fastapi import APIRouter
    router = APIRouter()

    @router.get("/items")
    def list_items():
        return []

    @router.post("/items")
    def create_item():
        return {}
    """

_EMPTY_ROUTER = """\
    from fastapi import APIRouter
    router = APIRouter()
    """

_MULTI_VAR_ROUTER = """\
    from fastapi import APIRouter
    read_router = APIRouter()
    admin_router = APIRouter()

    @read_router.get("/things")
    def list_things():
        return []

    @admin_router.delete("/things/{id}")
    def delete_thing(id: str):
        return {}
    """

_UTILITY_FILE = "def helper(): pass\n"


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(text))
    return p


def _make_routers_dir(tmp_path: Path, files: dict[str, str]) -> Path:
    d = tmp_path / "routers"
    d.mkdir()
    (d / "__init__.py").write_text("")
    for name, content in files.items():
        (d / name).write_text(textwrap.dedent(content))
    return d


def _minimal_entrypoints(tmp_path: Path) -> tuple[Path, Path]:
    """Write bare entrypoint stubs (no include_router calls)."""
    prod = tmp_path / "main_prod.py"
    prod.write_text("from fastapi import FastAPI\napp = FastAPI()\n")
    modular = tmp_path / "main_modular.py"
    modular.write_text("from fastapi import FastAPI\napp = FastAPI()\n")
    return prod, modular


# ── _router_names_and_routes ──────────────────────────────────────────────────


def test_active_router_detected(tmp_path: Path) -> None:
    p = _write(tmp_path, "things.py", _ACTIVE_ROUTER)
    result = crr._router_names_and_routes(p)
    assert "router" in result
    routes = result["router"]
    assert any("GET" in r for r in routes)
    assert any("POST" in r for r in routes)


def test_router_without_routes_returns_empty(tmp_path: Path) -> None:
    p = _write(tmp_path, "stub.py", _EMPTY_ROUTER)
    assert crr._router_names_and_routes(p) == {}


def test_non_router_file_returns_empty(tmp_path: Path) -> None:
    p = _write(tmp_path, "util.py", _UTILITY_FILE)
    assert crr._router_names_and_routes(p) == {}


def test_multi_var_router_detects_both_vars(tmp_path: Path) -> None:
    p = _write(tmp_path, "multi.py", _MULTI_VAR_ROUTER)
    result = crr._router_names_and_routes(p)
    assert "read_router" in result
    assert "admin_router" in result
    assert any("GET" in r for r in result["read_router"])
    assert any("DELETE" in r for r in result["admin_router"])


# ── _neither_registered_routers ───────────────────────────────────────────────
#  (a) Neither + not allowlisted → fails


def test_neither_registered_not_allowlisted_is_flagged(tmp_path: Path) -> None:
    routers_dir = _make_routers_dir(tmp_path, {"ghost.py": _ACTIVE_ROUTER})
    problems = crr._neither_registered_routers(
        routers_dir=routers_dir,
        prod={},
        modular={},
        allowed=set(),
    )
    assert len(problems) == 1
    module_name, routes = problems[0]
    assert module_name == "routers.ghost"
    assert len(routes) >= 1


def test_neither_registered_reports_routes(tmp_path: Path) -> None:
    routers_dir = _make_routers_dir(tmp_path, {"ghost.py": _ACTIVE_ROUTER})
    problems = crr._neither_registered_routers(
        routers_dir=routers_dir,
        prod={},
        modular={},
        allowed=set(),
    )
    routes = problems[0][1]
    assert any("/items" in r for r in routes)


#  (b) Neither + IS allowlisted → passes


def test_neither_registered_but_allowlisted_passes(tmp_path: Path) -> None:
    routers_dir = _make_routers_dir(tmp_path, {"ghost.py": _ACTIVE_ROUTER})
    problems = crr._neither_registered_routers(
        routers_dir=routers_dir,
        prod={},
        modular={},
        allowed={"routers.ghost.router"},
    )
    assert problems == []


#  (c) Regression — existing cases still pass


def test_modular_only_router_not_flagged_by_neither_check(tmp_path: Path) -> None:
    """A router in modular but not prod is caught by the OLD check, not this one."""
    routers_dir = _make_routers_dir(tmp_path, {"things.py": _ACTIVE_ROUTER})
    problems = crr._neither_registered_routers(
        routers_dir=routers_dir,
        prod={},
        modular={"routers.things.router": "things.router"},
        allowed=set(),
    )
    assert problems == []


def test_both_registered_router_not_flagged(tmp_path: Path) -> None:
    routers_dir = _make_routers_dir(tmp_path, {"things.py": _ACTIVE_ROUTER})
    prod = {"routers.things.router": "things_router.router"}
    modular = {"routers.things.router": "things.router"}
    assert crr._neither_registered_routers(routers_dir, prod, modular, allowed=set()) == []


def test_prod_only_router_not_flagged(tmp_path: Path) -> None:
    """Registered in prod but not modular — atypical but should not be flagged here."""
    routers_dir = _make_routers_dir(tmp_path, {"things.py": _ACTIVE_ROUTER})
    prod = {"routers.things.router": "things_router.router"}
    assert crr._neither_registered_routers(routers_dir, prod, modular={}, allowed=set()) == []


def test_empty_router_not_flagged_even_when_unregistered(tmp_path: Path) -> None:
    """An APIRouter with no routes is never a live 404 risk — skip it."""
    routers_dir = _make_routers_dir(tmp_path, {"stub.py": _EMPTY_ROUTER})
    assert crr._neither_registered_routers(routers_dir, {}, {}, set()) == []


def test_multi_var_file_partially_registered_not_flagged(tmp_path: Path) -> None:
    """If ANY var from the file is registered, the file is not a 'neither' case."""
    routers_dir = _make_routers_dir(tmp_path, {"multi.py": _MULTI_VAR_ROUTER})
    # Only read_router is registered — admin_router is not, but the file itself is known
    modular = {"routers.multi.read_router": "multi.read_router"}
    problems = crr._neither_registered_routers(routers_dir, {}, modular, allowed=set())
    assert problems == []


def test_init_py_skipped(tmp_path: Path) -> None:
    """__init__.py in the routers dir is always skipped."""
    d = tmp_path / "routers"
    d.mkdir()
    (d / "__init__.py").write_text(textwrap.dedent(_ACTIVE_ROUTER))  # unusual but must be safe
    assert crr._neither_registered_routers(d, {}, {}, set()) == []


# ── main() exit codes ─────────────────────────────────────────────────────────


def test_main_exits_1_on_neither_registered(monkeypatch: object, tmp_path: Path) -> None:
    """End-to-end: a router in neither entrypoint makes main() return 1."""
    routers_dir = _make_routers_dir(tmp_path, {"ghost.py": _ACTIVE_ROUTER})
    prod_file, modular_file = _minimal_entrypoints(tmp_path)
    allowlist_file = tmp_path / "allowlist.txt"
    allowlist_file.write_text("# empty\n")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_router_registrations.py",
            "--prod", str(prod_file),
            "--modular", str(modular_file),
            "--allowlist", str(allowlist_file),
            "--routers-dir", str(routers_dir),
        ],
    )
    assert crr.main() == 1


def test_main_exits_0_when_neither_registered_is_allowlisted(
    monkeypatch: object, tmp_path: Path
) -> None:
    routers_dir = _make_routers_dir(tmp_path, {"ghost.py": _ACTIVE_ROUTER})
    prod_file, modular_file = _minimal_entrypoints(tmp_path)
    allowlist_file = tmp_path / "allowlist.txt"
    allowlist_file.write_text("routers.ghost.router  # TEMP: grandfathered\n")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_router_registrations.py",
            "--prod", str(prod_file),
            "--modular", str(modular_file),
            "--allowlist", str(allowlist_file),
            "--routers-dir", str(routers_dir),
        ],
    )
    assert crr.main() == 0


def test_main_still_catches_modular_only_regression(
    monkeypatch: object, tmp_path: Path
) -> None:
    """The existing modular-only check must still fire (no regression)."""
    routers_dir = _make_routers_dir(tmp_path, {"things.py": _ACTIVE_ROUTER})
    allowlist_file = tmp_path / "allowlist.txt"
    allowlist_file.write_text("# empty\n")

    # Write a modular main.py that includes 'things', but prod main.py doesn't.
    # Use the same import style as the real app/main.py: `from .routers import <name>`.
    # This produces identity 'routers.things.router' in the modular dict, so the
    # neither-registered check correctly sees the router as modular-registered and
    # does NOT double-flag it — only the existing modular-only check fires.
    modular_file = tmp_path / "main_modular.py"
    modular_file.write_text(
        "from fastapi import FastAPI\n"
        "from .routers import things\n"
        "app = FastAPI()\n"
        "app.include_router(things.router)\n"
    )
    prod_file = tmp_path / "main_prod.py"
    prod_file.write_text("from fastapi import FastAPI\napp = FastAPI()\n")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_router_registrations.py",
            "--prod", str(prod_file),
            "--modular", str(modular_file),
            "--allowlist", str(allowlist_file),
            "--routers-dir", str(routers_dir),
        ],
    )
    assert crr.main() == 1
