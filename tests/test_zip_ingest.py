from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from app.ingestion import zip_ingest
from app.ingestion.errors import IngestionError
from app.ingestion.zip_ingest import extract_zip


def _make_zip(entries: dict[str, bytes], compress_type: int = zipfile.ZIP_DEFLATED) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compress_type) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_extract_zip_normal_case(tmp_path: Path):
    zip_bytes = _make_zip({"pkg/__init__.py": b"", "pkg/main.py": b"print('hi')\n"})
    dest = tmp_path / "out"

    extract_zip(zip_bytes, dest)

    assert (dest / "pkg" / "main.py").read_text() == "print('hi')\n"


def test_extract_zip_rejects_invalid_zip(tmp_path: Path):
    with pytest.raises(IngestionError):
        extract_zip(b"this is not a zip file", tmp_path / "out")


def test_extract_zip_rejects_path_traversal(tmp_path: Path):
    zip_bytes = _make_zip({"../../evil.txt": b"pwned"})

    with pytest.raises(IngestionError, match="path traversal"):
        extract_zip(zip_bytes, tmp_path / "out")


def test_extract_zip_rejects_compression_bomb(tmp_path: Path):
    # Highly repetitive data compresses at a ratio far above MAX_COMPRESSION_RATIO.
    zip_bytes = _make_zip({"bomb.bin": b"\x00" * (5 * 1024 * 1024)})

    with pytest.raises(IngestionError, match="zip bomb"):
        extract_zip(zip_bytes, tmp_path / "out")


def test_extract_zip_rejects_too_many_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(zip_ingest, "MAX_FILE_COUNT", 2)
    zip_bytes = _make_zip({"a.py": b"1", "b.py": b"2", "c.py": b"3"})

    with pytest.raises(IngestionError, match="terlalu banyak file"):
        extract_zip(zip_bytes, tmp_path / "out")


def test_extract_zip_rejects_oversized_single_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(zip_ingest, "MAX_SINGLE_FILE_BYTES", 10)
    zip_bytes = _make_zip({"big.txt": b"x" * 100})

    with pytest.raises(IngestionError, match="terlalu besar"):
        extract_zip(zip_bytes, tmp_path / "out")
