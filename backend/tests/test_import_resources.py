"""
Tests for Resources import pipeline: parsers, validators, transformers.
Does not require DB; executor tests need integration env.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.imports.resources.parsers import (
    _parse_bool,
    _parse_int,
    _parse_tags,
    parse_csv_categories,
    parse_csv_tags,
    parse_json_bundle,
    parse_json_categories,
    parse_json_tags,
)
from backend.imports.resources.schemas import ImportBundle, ImportCategory, ImportTag
from backend.imports.resources.validators import (
    validate_bundle,
    validate_category,
    validate_tag,
)


class TestParseHelpers(unittest.TestCase):
    def test_parse_bool(self) -> None:
        assert _parse_bool(True) is True
        assert _parse_bool(False) is False
        assert _parse_bool("true") is True
        assert _parse_bool("yes") is True
        assert _parse_bool("1") is True
        assert _parse_bool("false") is False
        assert _parse_bool("no") is False
        assert _parse_bool("") is False
        assert _parse_bool(None) is False

    def test_parse_int(self) -> None:
        assert _parse_int(42) == 42
        assert _parse_int("42") == 42
        assert _parse_int(3.14) == 3
        assert _parse_int(None) is None
        assert _parse_int("") is None

    def test_parse_tags(self) -> None:
        assert _parse_tags(None) == []
        assert _parse_tags("") == []
        assert _parse_tags("a,b,c") == ["a", "b", "c"]
        assert _parse_tags("a|b|c") == ["a", "b", "c"]
        assert _parse_tags('["x","y"]') == ["x", "y"]
        assert _parse_tags(["a", "b"]) == ["a", "b"]


class TestParsers(unittest.TestCase):
    def test_parse_csv_categories(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("key,label,description,sort_order\n")
            f.write("housing,Housing,Homes,1\n")
            f.write("schools,Schools,Education,2\n")
            f.flush()
            path = Path(f.name)
        try:
            items = parse_csv_categories(path)
            assert len(items) == 2
            assert items[0].key == "housing"
            assert items[0].label == "Housing"
            assert items[0].sort_order == 1
        finally:
            path.unlink()

    def test_parse_json_categories(self) -> None:
        data = [
            {"key": "admin", "label": "Admin", "sort_order": 0},
            {"key": "housing", "label": "Housing", "description": "Homes"},
        ]
        items = parse_json_categories(data)
        assert len(items) == 2
        assert items[0].key == "admin"
        assert items[1].description == "Homes"

    def test_parse_json_bundle(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({
                "categories": [{"key": "c1", "label": "C1"}],
                "tags": [{"key": "t1", "label": "T1"}],
                "sources": [{"source_name": "S1", "source_type": "community"}],
                "resources": [],
                "events": [],
            }, f)
            f.flush()
            path = Path(f.name)
        try:
            bundle = parse_json_bundle(path)
            assert len(bundle.categories) == 1
            assert len(bundle.tags) == 1
            assert len(bundle.sources) == 1
            assert bundle.categories[0].key == "c1"
        finally:
            path.unlink()


class TestValidators(unittest.TestCase):
    def test_validate_category_ok(self) -> None:
        c = ImportCategory(key="housing", label="Housing", row_num=1)
        assert validate_category(c) == []

    def test_validate_category_missing_key(self) -> None:
        c = ImportCategory(key="", label="Housing", row_num=1)
        errs = validate_category(c)
        assert len(errs) > 0

    def test_validate_tag_ok(self) -> None:
        t = ImportTag(key="free", label="Free", tag_group="free_paid", row_num=1)
        assert validate_tag(t) == []

    def test_validate_tag_invalid_group(self) -> None:
        t = ImportTag(key="x", label="X", tag_group="invalid_group", row_num=1)
        errs = validate_tag(t)
        assert len(errs) > 0

    def test_validate_bundle_empty(self) -> None:
        bundle = ImportBundle()
        errs = validate_bundle(bundle, set(), set())
        assert errs == []

    def test_validate_bundle_categories_and_resources(self) -> None:
        bundle = ImportBundle(
            categories=[ImportCategory(key="housing", label="Housing", row_num=1)],
            resources=[],
        )
        errs = validate_bundle(bundle, set(), set())
        assert errs == []


if __name__ == "__main__":
    unittest.main()
