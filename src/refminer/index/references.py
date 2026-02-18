from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from refminer.analysis.citations import CitationItem, ReferenceParser
from refminer.crawler.models import CrawlerConfig, RefIdentMode
from refminer.settings import SettingsManager
from refminer.utils.paths import get_index_dir

REFERENCES_FILE = "references.jsonl"
PARSER_VERSION = "reference_parser_v1"


@dataclass
class ReferenceRecord:
    source_rel_path: str
    source_sha256: str
    source_file_type: str
    ref_number: int | None
    raw_text: str
    title: str | None = None
    authors: list[str] | None = None
    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    url: str | None = None
    source_type: str = "unknown"
    availability: str = "unavailable"
    needs_metadata_fetch: bool = False
    normalized_key: str | None = None
    parser_version: str = PARSER_VERSION
    extracted_at: float = 0.0


def references_index_path(
    root: Path | None = None, index_dir: Path | None = None
) -> Path:
    idx_dir = index_dir or get_index_dir(root)
    return idx_dir / REFERENCES_FILE


def load_reference_records(
    root: Path | None = None, index_dir: Path | None = None
) -> list[ReferenceRecord]:
    path = references_index_path(root, index_dir=index_dir)
    if not path.exists():
        return []
    records: list[ReferenceRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue
            try:
                records.append(ReferenceRecord(**item))
            except TypeError:
                continue
    return records


def load_reference_records_for_file(
    source_rel_path: str,
    source_sha256: str | None = None,
    root: Path | None = None,
    index_dir: Path | None = None,
) -> list[ReferenceRecord]:
    items = [
        rec
        for rec in load_reference_records(root, index_dir=index_dir)
        if rec.source_rel_path == source_rel_path
    ]
    if source_sha256:
        items = [rec for rec in items if rec.source_sha256 == source_sha256]
    items.sort(key=lambda rec: rec.ref_number or 999999)
    return items


def upsert_reference_records(
    source_rel_path: str,
    records: list[ReferenceRecord],
    root: Path | None = None,
    index_dir: Path | None = None,
) -> None:
    idx_dir = index_dir or get_index_dir(root)
    idx_dir.mkdir(parents=True, exist_ok=True)
    path = references_index_path(root, index_dir=idx_dir)

    existing = load_reference_records(root, index_dir=idx_dir)
    kept = [rec for rec in existing if rec.source_rel_path != source_rel_path]
    merged = kept + records
    merged.sort(key=lambda rec: (rec.source_rel_path, rec.ref_number or 999999))

    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for record in merged:
            handle.write(json.dumps(asdict(record), ensure_ascii=True) + "\n")
    tmp_path.replace(path)


def remove_reference_records(
    source_rel_path: str,
    root: Path | None = None,
    index_dir: Path | None = None,
) -> int:
    idx_dir = index_dir or get_index_dir(root)
    path = references_index_path(root, index_dir=idx_dir)
    if not path.exists():
        return 0

    existing = load_reference_records(root, index_dir=idx_dir)
    kept = [rec for rec in existing if rec.source_rel_path != source_rel_path]
    removed = len(existing) - len(kept)

    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for record in kept:
            handle.write(json.dumps(asdict(record), ensure_ascii=True) + "\n")
    tmp_path.replace(path)

    return removed


def load_reference_ident_mode(index_dir: Path) -> RefIdentMode:
    settings = SettingsManager(index_dir)
    crawler_data = settings.get_crawler_config()
    crawler_cfg = (
        CrawlerConfig.from_dict(crawler_data) if crawler_data else CrawlerConfig()
    )
    return crawler_cfg.ref_ident_mode


def _get_ocr_model_dir(index_dir: Path) -> Path | None:
    settings = SettingsManager(index_dir)
    ocr_cfg = settings.get_ocr_config()
    model_key = str(ocr_cfg.get("model", "paddle-mobile"))
    model_dir = index_dir / "models" / "ocr" / model_key
    if model_dir.is_dir():
        return model_dir
    return None


def _ocr_extract_text(file_path: Path, index_dir: Path) -> str:
    from refminer.analysis.ocr import OcrEngine

    model_dir = _get_ocr_model_dir(index_dir)
    engine = OcrEngine(model_dir)
    page_texts = engine.recognize_pdf_pages(file_path)
    return "\n".join(page_texts)


def _normalize_key(item: CitationItem) -> str | None:
    if item.doi:
        return f"doi:{item.doi.lower()}"
    if item.arxiv_id:
        return f"arxiv:{item.arxiv_id.lower()}"
    if item.url:
        return f"url:{item.url.lower()}"
    if item.title:
        collapsed = " ".join(item.title.lower().split())
        if collapsed:
            return f"title:{collapsed}"
    return None


def extract_reference_records_for_pdf(
    file_path: Path,
    source_rel_path: str,
    source_sha256: str,
    text_blocks: list[str],
    index_dir: Path,
    mode: RefIdentMode | None = None,
) -> list[ReferenceRecord]:
    parser = ReferenceParser()
    selected_mode = mode or load_reference_ident_mode(index_dir)

    if selected_mode == "ocr_only":
        full_text = _ocr_extract_text(file_path, index_dir)
    else:
        full_text = "\n".join(text_blocks)
        if selected_mode == "string_then_ocr":
            string_refs = parser.extract_references(full_text)
            if len(string_refs) <= 2:
                full_text = _ocr_extract_text(file_path, index_dir)

    parsed = parser.extract_references(full_text)
    now = time.time()
    records: list[ReferenceRecord] = []
    for item in parsed:
        records.append(
            ReferenceRecord(
                source_rel_path=source_rel_path,
                source_sha256=source_sha256,
                source_file_type="pdf",
                ref_number=item.ref_number,
                raw_text=item.raw_text,
                title=item.title,
                authors=item.authors,
                year=item.year,
                doi=item.doi,
                arxiv_id=item.arxiv_id,
                url=item.url,
                source_type=item.source_type,
                availability=item.availability,
                needs_metadata_fetch=item.needs_metadata_fetch,
                normalized_key=_normalize_key(item),
                parser_version=PARSER_VERSION,
                extracted_at=now,
            )
        )
    return records


def refresh_reference_records_for_pdf(
    file_path: Path,
    source_rel_path: str,
    source_sha256: str,
    text_blocks: list[str],
    index_dir: Path,
    mode: RefIdentMode | None = None,
) -> list[ReferenceRecord]:
    records = extract_reference_records_for_pdf(
        file_path=file_path,
        source_rel_path=source_rel_path,
        source_sha256=source_sha256,
        text_blocks=text_blocks,
        index_dir=index_dir,
        mode=mode,
    )
    upsert_reference_records(source_rel_path, records, index_dir=index_dir)
    return records


def to_citation_items(records: list[ReferenceRecord]) -> list[CitationItem]:
    items = [
        CitationItem(
            raw_text=record.raw_text,
            ref_number=record.ref_number,
            title=record.title,
            authors=record.authors,
            year=record.year,
            doi=record.doi,
            arxiv_id=record.arxiv_id,
            url=record.url,
            source_type=record.source_type,
            availability=record.availability,
            needs_metadata_fetch=record.needs_metadata_fetch,
        )
        for record in records
    ]
    items.sort(key=lambda item: item.ref_number or 999999)
    return items
