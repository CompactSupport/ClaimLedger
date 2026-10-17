from pathlib import Path

import pytest

from claimledger.ingest import load_pages, split_into_units
from claimledger.pipeline import verify_documents

from pdfutil import make_text_pdf


SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "aurora.md"


def _assert_offsets(pages) -> None:
    by_page = {(page.source, page.sha256, page.page): page for page in pages}
    units = split_into_units(pages, max_chars=120)
    assert units
    last_end = {}
    for unit in units:
        page = by_page[(unit.source, unit.sha256, unit.page)]
        assert page.text[unit.start:unit.end] == unit.text
        assert unit.text.strip() == unit.text
        key = (unit.source, unit.page)
        assert unit.start >= last_end.get(key, 0)
        last_end[key] = unit.end


def test_load_and_source_spans():
    pages = load_pages([SAMPLE])
    assert len(pages) == 1
    assert pages[0].source == "aurora.md"
    _assert_offsets(pages)


def test_unsupported_type(tmp_path):
    path = tmp_path / "file.exe"
    path.write_text("hi")
    with pytest.raises(ValueError, match="Unsupported"):
        load_pages([path])


def test_empty_files_rejected(tmp_path):
    path = tmp_path / "empty.md"
    path.write_text("\n\n  \n")
    with pytest.raises(ValueError, match="No extractable"):
        load_pages([path])


def test_chunk_split_preserves_offsets(tmp_path):
    path = tmp_path / "long.txt"
    path.write_text("Hello world. " * 250)
    pages = load_pages([path])
    units = split_into_units(pages, max_chars=150)
    assert len(units) > 3
    assert all(pages[0].text[u.start:u.end] == u.text for u in units)
    assert all(units[i].end <= units[i + 1].start for i in range(len(units) - 1))


def test_long_unspaced_paragraph_splits_on_character_boundary(tmp_path):
    path = tmp_path / "cjk-long.md"
    text = "研究" * 1000
    path.write_text(text, encoding="utf-8")
    pages = load_pages([path])
    units = split_into_units(pages, max_chars=100)
    assert len(units) > 5
    assert "".join(unit.text for unit in units) == text
    assert all(pages[0].text[unit.start:unit.end] == unit.text for unit in units)


def test_blank_chunks_are_not_evidence(tmp_path):
    path = tmp_path / "gaps.md"
    path.write_text("第一段。\n\n   \n\n\u3000\u3000\n\n第二段。\n", encoding="utf-8")
    units = split_into_units(load_pages([path]))
    assert [unit.text for unit in units] == ["第一段。", "第二段。"]


def test_unicode_offsets_and_crlf(tmp_path):
    path = tmp_path / "中文.md"
    path.write_bytes("研究結果：成功率為百分之八十。\r\n\r\n沒有額外樣本。\r\n".encode("utf-8"))
    pages = load_pages([path])
    units = split_into_units(pages)
    assert [unit.text for unit in units] == ["研究結果：成功率為百分之八十。", "沒有額外樣本。"]
    for unit in units:
        assert pages[0].text[unit.start:unit.end] == unit.text
    report = verify_documents([path], ["成功率為百分之八十"])
    quote = report["results"][0]["evidence"][0]
    assert report["results"][0]["verdict"] == "supported"
    assert pages[0].text[quote["start"]:quote["end"]] == quote["quote"]


def test_pdf_two_pages_offsets():
    path = SAMPLE.parent / "two-page-fixture.pdf"
    pages = load_pages([path])
    by_page = {page.page: page for page in pages}
    assert set(by_page) == {1, 2}
    assert "40 samples" in by_page[1].text
    assert "60 samples" in by_page[2].text
    units = split_into_units(pages)
    for unit in units:
        assert by_page[unit.page].text[unit.start:unit.end] == unit.text
    assert {unit.page for unit in units} == {1, 2}


def test_pdf_blank_middle_page_keeps_original_page_numbers(tmp_path):
    path = tmp_path / "three.pdf"
    path.write_bytes(make_text_pdf([
        "Page one has 40 samples.",
        "",
        "Page three has 60 samples.",
    ]))
    pages = load_pages([path])
    by_page = {page.page: page for page in pages}
    assert sorted(by_page) == [1, 3]
    units = split_into_units(pages)
    for unit in units:
        assert by_page[unit.page].text[unit.start:unit.end] == unit.text
    report = verify_documents([path], ["Page three has 60 samples."])
    quote = report["results"][0]["evidence"][0]
    assert quote["page"] == 3
    assert by_page[3].text[quote["start"]:quote["end"]] == "Page three has 60 samples."


def test_duplicate_source_names_stay_distinct(tmp_path):
    left = tmp_path / "left" / "notes.md"
    right = tmp_path / "right" / "notes.md"
    left.parent.mkdir()
    right.parent.mkdir()
    left.write_text("左文件記載甲組有 3 人。\n", encoding="utf-8")
    right.write_text("右文件記載乙組有 9 人。\n", encoding="utf-8")
    pages = load_pages([left, right])
    assert {page.source for page in pages} == {"left/notes.md", "right/notes.md"}
    by_source = {page.source: page for page in pages}
    units = split_into_units(pages)
    assert len({unit.id for unit in units}) == len(units)
    for unit in units:
        assert by_source[unit.source].text[unit.start:unit.end] == unit.text
    report = verify_documents(
        [left, right],
        ["左文件記載甲組有 3 人。"],
    )
    quote = report["results"][0]["evidence"][0]
    assert quote["source"] == "left/notes.md"
    assert by_source[quote["source"]].text[quote["start"]:quote["end"]] == quote["quote"]


def test_identical_copies_keep_separate_provenance(tmp_path):
    left = tmp_path / "left" / "notes.md"
    right = tmp_path / "right" / "notes.md"
    left.parent.mkdir()
    right.parent.mkdir()
    left.write_text("同一句話出現在副本中。\n", encoding="utf-8")
    right.write_text("同一句話出現在副本中。\n", encoding="utf-8")
    pages = load_pages([left, right])
    units = split_into_units(pages)
    assert len({unit.id for unit in units}) == 2
    assert {unit.source for unit in units} == {"left/notes.md", "right/notes.md"}


def test_duplicate_path_is_rejected(tmp_path):
    path = tmp_path / "notes.md"
    path.write_text("只有一份。\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        load_pages([path, path])
