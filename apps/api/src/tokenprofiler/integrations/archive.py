"""Where traces go when retention removes them: gzip NDJSON objects, one per batch.

- `LocalArchive` writes under a directory (a volume, a disk on a single box).
- `S3Archive` writes to S3 with SSE-KMS (on AWS, or on the Floci emulator locally).

Keys are built from the project slug and a UTC date, never from request text, so a name can
never leave the store; `safe_key` still refuses anything that is not a plain relative path.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

import anyio
from botocore.exceptions import ClientError

from tokenprofiler.core.config import Settings
from tokenprofiler.core.errors import NotFoundError, ServiceUnavailableError
from tokenprofiler.integrations import aws

_SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/=-]{0,300}$")


def safe_key(key: str) -> str:
    if not _SAFE_KEY.match(key) or ".." in key.split("/") or "//" in key:
        raise ValueError(f"not a valid archive key: {key!r}")
    return key


class ArchiveStore(Protocol):
    kind: str

    async def put(self, key: str, data: bytes) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def list(self, prefix: str, limit: int) -> list[tuple[str, int]]: ...

    async def check(self) -> None: ...


class LocalArchive:
    kind = "local"

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / safe_key(key)).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("archive key escapes the archive directory")
        return path

    async def put(self, key: str, data: bytes) -> None:
        path = self._path(key)

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            partial = path.with_suffix(".partial")
            partial.write_bytes(data)
            partial.replace(path)

        await anyio.to_thread.run_sync(write)

    async def get(self, key: str) -> bytes:
        path = self._path(key)
        if not await anyio.Path(path).exists():
            raise NotFoundError("That archive object does not exist.")
        return await anyio.Path(path).read_bytes()

    async def list(self, prefix: str, limit: int) -> list[tuple[str, int]]:
        def walk() -> list[tuple[str, int]]:
            base = self._path(prefix.rstrip("/")) if prefix else self.root
            if not base.exists():
                return []
            files = sorted(p for p in base.rglob("*.ndjson.gz") if p.is_file())
            return [(str(p.relative_to(self.root)), p.stat().st_size) for p in files[-limit:]]

        return await anyio.to_thread.run_sync(walk)

    async def check(self) -> None:
        await anyio.to_thread.run_sync(lambda: self.root.mkdir(parents=True, exist_ok=True))


class S3Archive:
    kind = "s3"

    def __init__(self, settings: Settings) -> None:
        if not settings.s3_bucket:
            raise ValueError("S3_BUCKET is required for ARCHIVE_STORE=s3")
        self.bucket = settings.s3_bucket
        self.prefix = settings.s3_prefix.strip("/")
        self.kms_key_id = settings.s3_kms_key_id
        self._client = aws.s3_client(settings)

    def _key(self, key: str) -> str:
        key = safe_key(key)
        return f"{self.prefix}/{key}" if self.prefix else key

    async def put(self, key: str, data: bytes) -> None:
        extra: dict[str, str] = {}
        if self.kms_key_id:
            extra = {"ServerSideEncryption": "aws:kms", "SSEKMSKeyId": self.kms_key_id}
        await anyio.to_thread.run_sync(
            lambda: self._client.put_object(
                Bucket=self.bucket,
                Key=self._key(key),
                Body=data,
                ContentType="application/gzip",
                **extra,  # type: ignore[arg-type]
            )
        )

    async def get(self, key: str) -> bytes:
        try:
            response = await anyio.to_thread.run_sync(
                lambda: self._client.get_object(Bucket=self.bucket, Key=self._key(key))
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
                raise NotFoundError("That archive object does not exist.") from exc
            raise
        body: bytes = await anyio.to_thread.run_sync(response["Body"].read)
        return body

    async def list(self, prefix: str, limit: int) -> list[tuple[str, int]]:
        full = self._key(prefix.rstrip("/")) if prefix else self.prefix
        response = await anyio.to_thread.run_sync(
            lambda: self._client.list_objects_v2(
                Bucket=self.bucket, Prefix=full, MaxKeys=min(limit, 1000)
            )
        )
        strip = len(self.prefix) + 1 if self.prefix else 0
        return [
            (str(item["Key"])[strip:], int(item["Size"])) for item in response.get("Contents", [])
        ]

    async def check(self) -> None:
        try:
            await anyio.to_thread.run_sync(lambda: self._client.head_bucket(Bucket=self.bucket))
        except ClientError as exc:
            raise ServiceUnavailableError("The archive bucket is not reachable.") from exc


def build_archive(settings: Settings) -> ArchiveStore:
    if settings.archive_store == "s3":
        return S3Archive(settings)
    return LocalArchive(settings.archive_dir)
