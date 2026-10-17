from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable

from .models import DocumentPage, EvidenceUnit

SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}


def _reject_duplicate_paths(paths: list[Path]) -> None:
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            raise ValueError(f"Duplicate document: {path}")
        seen.add(resolved)


def _source_labels(paths: list[Path]) -> list[str]:
    """Use the file name when it is unique. Otherwise add parent folders until it is unique.

    Labels always use forward slashes so reports stay stable across operating systems.
    Identical resolved paths are rejected before this runs, so a last-resort full path
    cannot collide.
    """
    labels = [path.name for path in paths]
    ambiguous = {label for label in labels if labels.count(label) > 1}
    if not ambiguous:
        return labels
    for depth in range(2, 33):
        updated = list(labels)
        for index, path in enumerate(paths):
            if labels[index] not in ambiguous:
                continue
            updated[index] = "/".join(path.parts[-depth:])
        if len(set(updated)) == len(updated):
            return updated
    return [path.resolve().as_posix() for path in paths]


def load_pages(paths: Iterable[str | Path], max_file_bytes: int = 8_000_000,
               max_pdf_pages: int = 30) -> list[DocumentPage]:
    """Extract pages with provenance. PDF offsets refer to extracted text, not visual coordinates.

    Blank PDF pages are omitted, and the stored page number remains the original PDF page
    number. Character offsets are indexes into that page's extracted string.
    """
    path_list = [Path(raw_path) for raw_path in paths]
    for path in path_list:
        if not path.is_file():
            raise ValueError(f"Document not found: {path}")
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ValueError(f"Unsupported document type: {path.suffix}")
        if path.stat().st_size > max_file_bytes:
            raise ValueError(f"Document exceeds {max_file_bytes:,} byte limit: {path.name}")
    _reject_duplicate_paths(path_list)
    labels = _source_labels(path_list)
    pages: list[DocumentPage] = []
    for path, label in zip(path_list, labels, strict=True):
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if path.suffix.lower() == ".pdf":
            from pypdf import PdfReader

            try:
                reader = PdfReader(path)
                if len(reader.pages) > max_pdf_pages:
                    raise ValueError(f"PDF exceeds {max_pdf_pages} page limit: {path.name}")
                for page_number, page in enumerate(reader.pages, start=1):
                    text = page.extract_text() or ""
                    if text.strip():
                        pages.append(DocumentPage(label, digest, page_number, text))
            except ValueError:
                raise
            except Exception as exc:
                raise ValueError(f"PDF extraction failed for {path.name}: {exc}") from exc
        else:
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise ValueError(f"Document must be UTF-8: {path.name}") from exc
            if text.strip():
                pages.append(DocumentPage(label, digest, 1, text))
    if not pages:
        raise ValueError("No extractable text found. Scanned PDFs require external OCR (not in MVP).")
    return pages


def split_into_units(pages: list[DocumentPage], max_chars: int = 1400) -> list[EvidenceUnit]:
    """Paragraph-first deterministic chunking, retaining exact page-text offsets."""
    if max_chars < 100:
        raise ValueError("max_chars must be >= 100")
    units: list[EvidenceUnit] = []
    for page in pages:
        unit_number = 0
        # Blank lines delimit paragraphs. A long paragraph is split at whitespace when possible.
        for match in re.finditer(r"[^\n]+(?:\n(?!\s*\n)[^\n]+)*", page.text):
            para_start, para_end = match.span()
            cursor = para_start
            while cursor < para_end:
                stop = min(cursor + max_chars, para_end)
                if stop < para_end:
                    boundary = max(page.text.rfind(" ", cursor, stop),
                                   page.text.rfind("\n", cursor, stop))
                    if boundary > cursor + max_chars // 2:
                        stop = boundary
                raw_slice = page.text[cursor:stop]
                leading = len(raw_slice) - len(raw_slice.lstrip())
                trailing = len(raw_slice) - len(raw_slice.rstrip())
                start = cursor + leading
                end = stop - trailing
                if end > start and page.text[start:end].strip():
                    # Include a source tag so two copies of the same bytes still get distinct IDs.
                    source_tag = hashlib.sha256(page.source.encode("utf-8")).hexdigest()[:8]
                    unit_number += 1
                    unit_id = f"{page.sha256[:12]}:{source_tag}:p{page.page}:u{unit_number}"
                    text = page.text[start:end]
                    units.append(EvidenceUnit(unit_id, page.source, page.sha256, page.page,
                                              start, end, text))
                cursor = max(stop, cursor + 1)
    return units
