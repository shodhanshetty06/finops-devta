"""
Bounded file-upload reading (Phase 10 security review finding).

`POST /api/v1/intake/excel` and `POST /api/v1/projects/{id}/intake/excel`
used to call `await file.read()` with no size limit. The first of those has
no authentication requirement at all, which made it an unauthenticated
memory-exhaustion DoS vector: any caller could upload an arbitrarily large
file and the whole thing would be buffered into worker memory before the
Excel parser ever got a chance to reject it as invalid. `read_upload_bounded`
reads in chunks and aborts as soon as the configured limit is exceeded,
so an oversized upload never fully lands in memory.
"""
from fastapi import UploadFile

from app.core.exceptions import PayloadTooLargeError

_CHUNK_SIZE_BYTES = 1024 * 1024  # 1 MB per read


async def read_upload_bounded(file: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_CHUNK_SIZE_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise PayloadTooLargeError(
                f"Uploaded file exceeds the {max_bytes // (1024 * 1024)} MB limit."
            )
        chunks.append(chunk)
    return b"".join(chunks)
