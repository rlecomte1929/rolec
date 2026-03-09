"""
Main crawler pipeline: fetch -> parse -> chunk -> extract -> dedupe -> stage.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .chunkers.chunker import Chunk, chunk_document
from .config.models import CrawlConfig, CrawlSource
from .dedupe.dedupe import check_event_duplicate, check_resource_duplicate
from .extractors.event_extractor import extract_event_candidates
from .extractors.models import StagedEventCandidate, StagedResourceCandidate
from .extractors.resource_extractor import extract_resource_candidates
from .fetchers.http_fetcher import fetch_page, FetchResult
from .parsers.html_parser import parse_html, ParsedDocument
from .staging.writer import (
    update_crawl_run,
    write_chunk,
    write_crawl_run,
    write_document,
    write_event_candidate,
    write_resource_candidate,
)

log = logging.getLogger(__name__)


@dataclass
class PipelineReport:
    """Run report."""

    run_id: str
    documents_fetched: int = 0
    documents_failed: int = 0
    chunks_created: int = 0
    resources_staged: int = 0
    events_staged: int = 0
    duplicates_detected: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "documents_fetched": self.documents_fetched,
            "documents_failed": self.documents_failed,
            "chunks_created": self.chunks_created,
            "resources_staged": self.resources_staged,
            "events_staged": self.events_staged,
            "duplicates_detected": self.duplicates_detected,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def run_pipeline(
    config: CrawlConfig,
    *,
    source_name: Optional[str] = None,
    country_code: Optional[str] = None,
    city_name: Optional[str] = None,
    content_domain: Optional[str] = None,
    initiated_by: Optional[str] = None,
) -> PipelineReport:
    """
    Run full pipeline: fetch, parse, chunk, extract, dedupe, stage.
    """
    from .config.registry import get_sources_for_scope

    sources = get_sources_for_scope(
        config.sources,
        source_name=source_name,
        country_code=country_code,
        city_name=city_name,
        content_domain=content_domain,
    )

    scope_parts = []
    if source_name:
        scope_parts.append(f"source={source_name}")
    if country_code:
        scope_parts.append(f"country={country_code}")
    if city_name:
        scope_parts.append(f"city={city_name}")
    if content_domain:
        scope_parts.append(f"domain={content_domain}")
    scope_str = ",".join(scope_parts) if scope_parts else "all"

    run_id: str
    if config.dry_run:
        import uuid
        run_id = f"dry-run-{uuid.uuid4().hex[:8]}"
        report = PipelineReport(run_id=run_id)
        log.info("Dry run: would crawl %d sources", len(sources))
        report.warnings.append("Dry run - no DB writes")
        for source in sources:
            log.info("  Would fetch: %s %s", source.source_name, source.base_url)
        return report

    run_id = write_crawl_run(
        source_scope=scope_str,
        config_snapshot={"dry_run": config.dry_run, "sources_count": len(sources)},
        initiated_by=initiated_by,
    )
    report = PipelineReport(run_id=run_id)

    for source in sources:
        try:
            _crawl_source(source, config, run_id, report)
        except Exception as e:
            log.exception("Crawl source %s failed: %s", source.source_name, e)
            report.errors.append(f"{source.source_name}: {e}")
            report.documents_failed += 1

    summary = (
        f"Fetched: {report.documents_fetched}, failed: {report.documents_failed}, "
        f"chunks: {report.chunks_created}, resources: {report.resources_staged}, "
        f"events: {report.events_staged}, duplicates: {report.duplicates_detected}"
    )
    update_crawl_run(
        run_id,
        status="completed" if not report.errors else "completed",
        summary=summary,
        errors_count=len(report.errors),
        warnings_count=len(report.warnings),
        documents_fetched=report.documents_fetched,
        chunks_created=report.chunks_created,
        resources_staged=report.resources_staged,
        events_staged=report.events_staged,
        duplicates_detected=report.duplicates_detected,
    )
    return report


def _crawl_source(source: CrawlSource, config: CrawlConfig, run_id: str, report: PipelineReport) -> None:
    """Crawl single source: fetch base URL, parse, chunk, extract, stage."""
    url = source.base_url.rstrip("/")
    log.info("Fetching %s: %s", source.source_name, url)

    fetch_result = fetch_page(
        url,
        user_agent=config.user_agent,
        timeout=config.timeout_seconds,
        retry_count=config.retry_count,
    )

    if not fetch_result.success:
        report.documents_failed += 1
        report.errors.append(f"{source.source_name}: {fetch_result.error or fetch_result.http_status}")
        return

    report.documents_fetched += 1

    if config.parse_only:
        return

    doc = parse_html(fetch_result.content, url)
    doc_id = write_document(
        run_id,
        source.source_name,
        fetch_result,
        country_code=source.country_code,
        city_name=source.city_name,
        source_type=source.source_type,
        trust_tier=source.trust_tier,
        parsed=doc,
    )

    chunks = chunk_document(
        doc,
        source_url=fetch_result.final_url,
        page_title=doc.page_title,
        country_code=source.country_code,
        city_name=source.city_name or "",
    )
    report.chunks_created += len(chunks)

    chunk_ids: Dict[int, str] = {}
    for chunk in chunks:
        cid = write_chunk(doc_id, chunk)
        chunk_ids[chunk.chunk_index] = cid

    if config.extract_only:
        return

    resource_candidates = extract_resource_candidates(
        chunks,
        source,
        fetch_result.final_url,
        doc.page_title or url,
    )
    for rc in resource_candidates:
        is_dup, _ = check_resource_duplicate(
            rc.country_code,
            rc.city_name,
            rc.title,
            rc.source_url,
        )
        if is_dup:
            report.duplicates_detected += 1
            continue
        chunk_idx = rc.provenance.get("document_chunk_index", 0)
        chunk_id = chunk_ids.get(chunk_idx) if chunk_ids else None
        write_resource_candidate(run_id, doc_id, chunk_id, rc)
        report.resources_staged += 1

    event_candidates = extract_event_candidates(
        chunks,
        doc,
        source,
        fetch_result.final_url,
        doc.page_title or url,
    )
    for ec in event_candidates:
        is_dup, _ = check_event_duplicate(
            ec.country_code,
            ec.city_name,
            ec.title,
            ec.start_datetime,
        )
        if is_dup:
            report.duplicates_detected += 1
            continue
        chunk_idx = ec.provenance.get("chunk_index", 0)
        chunk_id = chunk_ids.get(chunk_idx) if chunk_ids else None
        write_event_candidate(run_id, doc_id, chunk_id, ec)
        report.events_staged += 1
