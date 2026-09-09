"""Knowledge-layer gates: serving isolation still holds; no compliance-claim copy in the new UI."""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_scorecard_module_does_not_import_llm_gateways():
    src = (REPO / "backend/app/services/knowledge_layer_scorecard.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module.split(".")[0])
    banned = {"openai", "anthropic", "mistralai", "litellm"}
    assert banned.isdisjoint(imported)


def test_qbr_stub_does_not_invent_a_baseline_index():
    text = (REPO / "docs/corridors/fr-no/QBR-knowledge-layer.md").read_text(encoding="utf-8")
    assert "N/A" in text
    assert "300%" not in text
    assert "EU AI Act" not in text


def test_norway_seed_baseline_is_pending_only():
    path = REPO / "scripts/knowledge_layer_baseline.py"
    spec = importlib.util.spec_from_file_location("knowledge_layer_baseline", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = mod.score_norway_seed()
    assert out["seed_rows"] >= 5
    assert out["catalogReady"] is False
    assert out["approvedCount"] == 0
    assert out["pendingCount"] == out["seed_rows"]
