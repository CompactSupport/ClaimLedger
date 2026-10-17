"""Build a tiny text PDF for provenance tests. ASCII page text only; no extra dependencies."""


def make_text_pdf(pages: list[str]) -> bytes:
    """Return a PDF whose extracted page text matches ``pages``.

    An empty string becomes a blank page. Callers should assert offsets against
    ``pypdf`` output, because a future extractor could still change spacing.
    """
    parts: list[bytes] = []
    offsets: dict[int, int] = {}

    def write(data: bytes) -> None:
        parts.append(data)

    def add(number: int, body: bytes) -> None:
        offsets[number] = sum(len(part) for part in parts)
        write(f"{number} 0 obj\n".encode("ascii"))
        write(body)
        if not body.endswith(b"\n"):
            write(b"\n")
        write(b"endobj\n")

    next_id = 4
    content_ids: list[int] = []
    page_ids: list[int] = []
    for _page in pages:
        content_ids.append(next_id)
        page_ids.append(next_id + 1)
        next_id += 2

    write(b"%PDF-1.4\n")
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    add(1, b"<< /Type /Catalog /Pages 2 0 R >>")
    add(2, f"<< /Type /Pages /Count {len(pages)} /Kids [{kids}] >>".encode("ascii"))
    add(3, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for text, content_id, page_id in zip(pages, content_ids, page_ids, strict=True):
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1") if text else b""
        header = f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
        add(content_id, header + stream + b"\nendstream")
        add(
            page_id,
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Contents {content_id} 0 R /Resources << /Font << /F1 3 0 R >> >> >>"
            ).encode("ascii"),
        )
    startxref = sum(len(part) for part in parts)
    write(b"xref\n")
    write(f"0 {next_id}\n".encode("ascii"))
    write(b"0000000000 65535 f \n")
    for number in range(1, next_id):
        write(f"{offsets[number]:010d} 00000 n \n".encode("ascii"))
    write(b"trailer\n")
    write(f"<< /Size {next_id} /Root 1 0 R >>\n".encode("ascii"))
    write(b"startxref\n")
    write(f"{startxref}\n".encode("ascii"))
    write(b"%%EOF\n")
    return b"".join(parts)
