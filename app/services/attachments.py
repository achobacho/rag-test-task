import csv
import hashlib
import re
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path

from pypdf import PdfReader


@dataclass
class StoredAttachment:
    filename: str
    content_type: str | None
    stored_path: Path
    text_content: str


def _safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return cleaned or "attachment"


def _extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    return "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()


def _extract_csv_text(content: bytes) -> str:
    raw = content.decode("utf-8", errors="replace")
    rows = csv.reader(StringIO(raw))
    return "\n".join(" | ".join(row) for row in rows).strip()


def extract_text(content: bytes, filename: str, content_type: str | None) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf_text(content)
    if suffix == ".csv":
        return _extract_csv_text(content)
    if suffix in {".txt", ".md"} or (content_type and content_type.startswith("text/")):
        return content.decode("utf-8", errors="replace").strip()
    return ""


def store_attachment(
    storage_dir: Path,
    content: bytes,
    filename: str,
    content_type: str | None,
) -> StoredAttachment:
    storage_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(content).hexdigest()[:12]
    safe_name = _safe_filename(filename)
    target = storage_dir / f"{fingerprint}_{safe_name}"
    target.write_bytes(content)
    text_content = extract_text(content, filename=filename, content_type=content_type)
    return StoredAttachment(
        filename=filename,
        content_type=content_type,
        stored_path=target,
        text_content=text_content,
    )

