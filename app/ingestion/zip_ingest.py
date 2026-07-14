from __future__ import annotations

import zipfile
from pathlib import Path

from app.ingestion.errors import IngestionError

MAX_TOTAL_UNCOMPRESSED_BYTES = 200 * 1024 * 1024  # 200 MB
MAX_FILE_COUNT = 5000
MAX_SINGLE_FILE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_COMPRESSION_RATIO = 100  # uncompressed/compressed above this looks like a bomb


def extract_zip(zip_bytes: bytes, dest: Path) -> None:
    """Safely extract an uploaded ZIP into dest, guarding against zip bombs
    and zip-slip path traversal. Raises IngestionError on any violation."""
    import io

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise IngestionError("File yang diupload bukan ZIP yang valid") from exc

    infos = zf.infolist()
    if len(infos) > MAX_FILE_COUNT:
        raise IngestionError(f"ZIP berisi terlalu banyak file (>{MAX_FILE_COUNT})")

    total_uncompressed = 0
    dest_resolved = dest.resolve()

    for info in infos:
        if info.file_size > MAX_SINGLE_FILE_BYTES:
            raise IngestionError(f"File '{info.filename}' di dalam ZIP terlalu besar")

        total_uncompressed += info.file_size
        if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES:
            raise IngestionError("Total ukuran ZIP setelah diekstrak melebihi batas (200MB)")

        if info.compress_size > 0:
            ratio = info.file_size / info.compress_size
            if ratio > MAX_COMPRESSION_RATIO:
                raise IngestionError("ZIP terdeteksi mencurigakan (rasio kompresi tidak wajar, kemungkinan zip bomb)")

        # zip-slip guard: resolved target must stay inside dest
        target = (dest / info.filename).resolve()
        if not str(target).startswith(str(dest_resolved)):
            raise IngestionError(f"Nama file di ZIP mencurigakan (path traversal): {info.filename}")

    dest.mkdir(parents=True, exist_ok=True)
    zf.extractall(dest)
