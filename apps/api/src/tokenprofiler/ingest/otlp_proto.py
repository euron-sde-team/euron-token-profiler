"""OTLP/HTTP with a protobuf body (`application/x-protobuf`).

The standard OpenTelemetry SDKs for Python, Java and Go send protobuf by default, so a
collector-free setup only works if protobuf is accepted next to JSON. The message is turned
into the JSON mapping and then handled by the same parser, so both encodings behave alike.
"""

from __future__ import annotations

from typing import Any

from google.protobuf.json_format import MessageToDict
from google.protobuf.message import DecodeError
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest


def decode_protobuf(body: bytes) -> dict[str, Any]:
    message = ExportTraceServiceRequest()
    try:
        message.ParseFromString(body)
    except DecodeError as exc:
        raise ValueError("The body is not a valid OTLP trace export request.") from exc
    return MessageToDict(message, use_integers_for_enums=True)
