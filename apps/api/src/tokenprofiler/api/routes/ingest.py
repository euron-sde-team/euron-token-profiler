"""The ingest plane: what SDKs and OpenTelemetry exporters call, authenticated by a project key."""

from __future__ import annotations

import gzip
import zlib
from typing import Annotated, Any

import orjson
from fastapi import APIRouter, Body, Query, Request

from tokenprofiler.api.deps import ContainerDep, IngestKeyDep, SessionDep
from tokenprofiler.core import metrics
from tokenprofiler.core.errors import AppError, NotFoundError, UnprocessableError
from tokenprofiler.ingest.native import parse_native
from tokenprofiler.ingest.otlp import parse_otlp
from tokenprofiler.ingest.otlp_proto import decode_protobuf
from tokenprofiler.ingest.types import Batch
from tokenprofiler.schemas.ingest import IngestBatch, IngestResult
from tokenprofiler.schemas.prompts import PromptFetch
from tokenprofiler.services.container import Container
from tokenprofiler.services.ingest import IngestService
from tokenprofiler.services.prompts import PromptService

router = APIRouter(prefix="/v1", tags=["ingest"])


class UnsupportedMediaError(AppError):
    status_code = 415
    code = "unsupported_media_type"
    message = "Send application/json or application/x-protobuf."


async def _body(request: Request, container: Container) -> bytes:
    """The request body, with gzip or deflate removed and the inflated size capped."""
    raw = await request.body()
    encoding = request.headers.get("content-encoding", "identity").lower()
    limit = container.settings.max_decompressed_mb * 1024 * 1024
    if encoding in {"", "identity"}:
        return raw
    if encoding not in {"gzip", "deflate"}:
        raise UnsupportedMediaError(f"Unsupported content-encoding: {encoding}.")
    # Bounded inflate: a small body must not be able to expand into gigabytes.
    inflater = zlib.decompressobj(16 + zlib.MAX_WBITS if encoding == "gzip" else zlib.MAX_WBITS)
    try:
        data = inflater.decompress(raw, limit + 1)
    except (zlib.error, gzip.BadGzipFile, EOFError) as exc:
        raise UnprocessableError("The body could not be decompressed.") from exc
    if len(data) > limit or inflater.unconsumed_tail:
        raise UnprocessableError(
            f"The decompressed body is larger than {container.settings.max_decompressed_mb} MB.",
            code="payload_too_large",
        )
    return data


def _check_size(batch: Batch, container: Container) -> None:
    if len(batch.spans) + len(batch.traces) > container.settings.max_batch_items:
        raise UnprocessableError(
            f"Send at most {container.settings.max_batch_items} items per request.",
            code="batch_too_large",
        )


@router.post(
    "/ingest",
    summary="Send traces and spans (native batch, used by the Python SDK)",
    description=(
        "Items are validated one by one: invalid ones are listed under `rejected` and the "
        "rest are stored. Spans and traces may arrive in any order and in any number of "
        "requests; a span sent again replaces the earlier copy."
    ),
)
async def ingest(
    body: Annotated[IngestBatch, Body()],
    auth: IngestKeyDep,
    container: ContainerDep,
    session: SessionDep,
) -> IngestResult:
    _, project = auth
    batch = parse_native(body)
    _check_size(batch, container)
    return await IngestService(container, session).ingest(project, batch, protocol="native")


@router.post(
    "/otlp/v1/traces",
    summary="OpenTelemetry OTLP/HTTP traces (JSON or protobuf, gzip accepted)",
    description=(
        "Set `OTEL_EXPORTER_OTLP_ENDPOINT` to `<api>/v1/otlp` and the header "
        "`Authorization=Bearer tp_...`. Spans follow the OpenTelemetry GenAI conventions "
        "(`gen_ai.*`); OpenInference and `tokenprofiler.*` attributes are understood too. "
        "The response is an OTLP `ExportTraceServiceResponse`."
    ),
)
async def otlp_traces(
    request: Request,
    auth: IngestKeyDep,
    container: ContainerDep,
    session: SessionDep,
) -> dict[str, Any]:
    _, project = auth
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    raw = await _body(request, container)
    if content_type == "application/x-protobuf":
        try:
            document = decode_protobuf(raw)
        except ValueError as exc:
            raise UnprocessableError(str(exc)) from exc
        batch = parse_otlp(document, base64_ids=True)
        protocol = "otlp-protobuf"
    elif content_type in {"application/json", ""}:
        try:
            document = orjson.loads(raw)
        except orjson.JSONDecodeError as exc:
            raise UnprocessableError("The body is not valid JSON.") from exc
        if not isinstance(document, dict):
            raise UnprocessableError("An OTLP request is a JSON object.")
        batch = parse_otlp(document)
        protocol = "otlp-json"
    else:
        raise UnsupportedMediaError()
    _check_size(batch, container)
    result = await IngestService(container, session).ingest(project, batch, protocol=protocol)
    response: dict[str, Any] = {}
    if result.rejected:
        # OTLP's partial success: the exporter logs it and does not retry.
        response["partialSuccess"] = {
            "rejectedSpans": len(result.rejected),
            "errorMessage": "; ".join(result.rejected[:3]),
        }
    return response


@router.get(
    "/prompts/{name:path}",
    summary="Fetch a managed prompt (a pinned version, a label, or production)",
)
async def fetch_prompt(
    name: str,
    auth: IngestKeyDep,
    session: SessionDep,
    version: Annotated[int | None, Query(ge=1)] = None,
    label: Annotated[str | None, Query(max_length=32)] = None,
) -> PromptFetch:
    _, project = auth
    try:
        return await PromptService(session).fetch(project.id, name, version=version, label=label)
    except NotFoundError:
        metrics.INGEST_BATCHES.labels("prompt-fetch", "not_found").inc()
        raise
