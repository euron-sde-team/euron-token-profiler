from __future__ import annotations

import contextlib
import gzip
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from tests.integration.conftest import AWS_ENDPOINT, RUN, People, aws_client, make_settings
from tests.integration.factories import generation, span, trace_id
from tests.integration.support import Project
from tokenprofiler.integrations.archive import S3Archive
from tokenprofiler.repositories.projects import ProjectRepository
from tokenprofiler.services.container import Container
from tokenprofiler.services.retention import purge_project


async def old_and_new(project: Project) -> tuple[str, str]:
    old, new = trace_id(), trace_id()
    long_ago = datetime.now(UTC) - timedelta(days=10)
    await project.send(
        [
            span(old, "agent", kind="agent", span_id="a", started=long_ago),
            generation(old, parent="a", started=long_ago, input="hello"),
            span(new, "fresh"),
        ]
    )
    return old, new


async def run(container: Container, project: Project) -> int:
    async with container.db.session() as session:
        row = await ProjectRepository(session).get(uuid.UUID(project.id))
        assert row is not None
    return await purge_project(container, row, now=datetime.now(UTC))


async def test_expired_traces_are_deleted_with_their_spans(
    people: People, project: Project, container: Container
) -> None:
    await people.admin.ok(await people.admin.patch(project.base, {"retention_days": 7}))
    old, new = await old_and_new(project)
    assert await run(container, project) == 1
    assert (await people.admin.get(f"{project.base}/traces/{old}")).status_code == 404
    assert (await people.admin.get(f"{project.base}/traces/{new}")).status_code == 200
    assert await run(container, project) == 0
    assert (await project.get("/archives")) == []


async def test_archive_before_delete_writes_a_readable_local_archive(
    people: People, project: Project, container: Container
) -> None:
    await people.admin.ok(
        await people.admin.patch(project.base, {"retention_days": 7, "archive_before_delete": True})
    )
    old, _ = await old_and_new(project)
    assert await run(container, project) == 1
    listing = await project.get("/archives")
    assert len(listing) == 1
    assert listing[0]["key"].startswith(f"{project.slug}/")
    download = await people.admin.get(f"{project.base}/archives/download", key=listing[0]["key"])
    assert download.status_code == 200
    document = json.loads(gzip.decompress(download.content).splitlines()[0])
    assert document["id"] == old
    assert len(document["spans"]) == 2
    other = await people.admin.get(
        f"{project.base}/archives/download", key="someone-else/x.ndjson.gz"
    )
    assert other.status_code == 422
    assert (await people.member.get(f"{project.base}/archives")).status_code == 403


async def test_archive_failure_keeps_the_data(
    people: People, project: Project, container: Container, monkeypatch: Any
) -> None:
    await people.admin.ok(
        await people.admin.patch(project.base, {"retention_days": 7, "archive_before_delete": True})
    )
    old, _ = await old_and_new(project)

    class Broken:
        kind = "broken"

        async def put(self, key: str, data: bytes) -> None:
            raise RuntimeError("bucket unreachable")

    monkeypatch.setattr(container, "archive", Broken())
    with contextlib.suppress(RuntimeError):
        await run(container, project)
    assert (await people.admin.get(f"{project.base}/traces/{old}")).status_code == 200


async def test_s3_archive_on_the_emulator(
    people: People, project: Project, container: Container, monkeypatch: Any, tmp_path: Path
) -> None:
    bucket = f"tp-archive-{RUN}"
    aws_client("s3").create_bucket(Bucket=bucket)
    settings = make_settings(
        tmp_path,
        archive_store="s3",
        s3_bucket=bucket,
        aws_endpoint_url=AWS_ENDPOINT,
        aws_region="us-east-1",
    )
    archive = S3Archive(settings)
    await archive.check()
    monkeypatch.setattr(container, "archive", archive)
    await people.admin.ok(
        await people.admin.patch(project.base, {"retention_days": 7, "archive_before_delete": True})
    )
    old, _ = await old_and_new(project)
    assert await run(container, project) == 1
    listing = await project.get("/archives")
    assert len(listing) == 1
    key = listing[0]["key"]
    stored = aws_client("s3").get_object(Bucket=bucket, Key=f"archive/{key}")
    assert json.loads(gzip.decompress(stored["Body"].read()).splitlines()[0])["id"] == old
    assert gzip.decompress(await archive.get(key)).splitlines()[0]
