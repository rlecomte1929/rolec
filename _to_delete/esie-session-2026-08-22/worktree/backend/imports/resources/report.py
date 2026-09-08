"""
Import report generation.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class EntityReport:
    entity_type: str
    file_name: str = ""
    started_at: str = ""
    finished_at: str = ""
    mode: str = "draft_only"
    rows_read: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    warnings: List[str] = field(default_factory=list)
    row_errors: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "file_name": self.file_name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "mode": self.mode,
            "rows_read": self.rows_read,
            "inserted": self.inserted,
            "updated": self.updated,
            "skipped": self.skipped,
            "failed": self.failed,
            "warnings": self.warnings,
            "row_errors": self.row_errors,
        }


@dataclass
class ImportReport:
    started_at: str = ""
    finished_at: str = ""
    mode: str = "draft_only"
    entity_reports: List[EntityReport] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        total_inserted = sum(r.inserted for r in self.entity_reports)
        total_updated = sum(r.updated for r in self.entity_reports)
        total_failed = sum(r.failed for r in self.entity_reports)
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "mode": self.mode,
            "entity_reports": [r.to_dict() for r in self.entity_reports],
            "summary": self.summary or f"Inserted: {total_inserted}, Updated: {total_updated}, Failed: {total_failed}",
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def write_json(self, path: Path) -> None:
        path.write_text(self.to_json(), encoding="utf-8")

    def to_console(self) -> str:
        lines = [
            "--- Import Report ---",
            f"Started:  {self.started_at}",
            f"Finished: {self.finished_at}",
            f"Mode:     {self.mode}",
            "",
        ]
        for r in self.entity_reports:
            lines.append(f"[{r.entity_type}] {r.file_name}")
            lines.append(f"  Read: {r.rows_read} | Inserted: {r.inserted} | Updated: {r.updated} | Skipped: {r.skipped} | Failed: {r.failed}")
            for w in r.warnings:
                lines.append(f"  Warning: {w}")
            for e in r.row_errors[:10]:  # limit display
                lines.append(f"  Error row {e.get('row_num')}: {e.get('message', '')}")
            if len(r.row_errors) > 10:
                lines.append(f"  ... and {len(r.row_errors) - 10} more errors")
            lines.append("")
        lines.append(self.summary)
        return "\n".join(lines)
