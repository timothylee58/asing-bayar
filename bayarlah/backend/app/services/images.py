"""Upload validation: trust the bytes, not the client-supplied filename/MIME."""
from fastapi import HTTPException, UploadFile

# SVG is intentionally absent: it can carry script.
_SIGNATURES: tuple[tuple[bytes, str, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"GIF87a", "image/gif", "gif"),
    (b"GIF89a", "image/gif", "gif"),
)


def detect_image(data: bytes) -> tuple[str, str] | None:
    """Return (mime, extension) for PNG/JPEG/GIF/WebP bytes, else None."""
    for magic, mime, ext in _SIGNATURES:
        if data.startswith(magic):
            return mime, ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


async def read_image(upload: UploadFile, max_bytes: int) -> tuple[bytes, str, str]:
    """Read at most `max_bytes` (never buffers an oversized upload) and validate
    it is a real raster image. Returns (data, mime, extension)."""
    chunks: list[bytes] = []
    size = 0
    while chunk := await upload.read(64 * 1024):
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File must be under {max_bytes // (1024 * 1024)}MB",
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    detected = detect_image(data)
    if detected is None:
        raise HTTPException(
            status_code=422, detail="File must be a PNG, JPEG, WebP or GIF image"
        )
    return data, detected[0], detected[1]
