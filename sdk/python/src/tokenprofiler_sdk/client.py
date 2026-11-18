"""The client: configuration, the span factories, `@observe` and prompt fetching."""

from __future__ import annotations

import atexit
import functools
import inspect
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar, cast

import httpx

from tokenprofiler_sdk.handles import Span, Trace
from tokenprofiler_sdk.prompts import Prompt
from tokenprofiler_sdk.transport import Sender

F = TypeVar("F", bound=Callable[..., Any])

_default: TokenProfiler | None = None


def get_client() -> TokenProfiler:
    """The first client created in this process, for `@observe` and the module helpers."""
    if _default is None:
        raise RuntimeError("Create a TokenProfiler(...) client before using @observe.")
    return _default


class TokenProfiler:
    """Sends traces to a TokenProfiler server.

    Nothing here raises into your application: a full queue drops events (counted in
    `stats`), a failing server is retried with backoff and then given up on. Call `flush()`
    before a short-lived process exits (it also runs at interpreter exit).
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        environment: str = "default",
        release: str | None = None,
        flush_at: int = 100,
        flush_interval: float = 2.0,
        max_queue: int = 10_000,
        max_retries: int = 4,
        timeout: float = 10.0,
        enabled: bool = True,
        prompt_cache_ttl: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        global _default
        self.environment = environment
        self.release = release
        self.enabled = enabled
        self._prompt_ttl = prompt_cache_ttl
        self._prompts: dict[tuple[str, int | None, str | None], tuple[float, Prompt]] = {}
        self._prompt_lock = threading.Lock()
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"authorization": f"Bearer {api_key}", "user-agent": "tokenprofiler-sdk/0.1"},
            timeout=timeout,
            transport=transport,
        )
        self._sender = Sender(
            self._http,
            flush_at=flush_at,
            flush_interval=flush_interval,
            max_queue=max_queue,
            max_retries=max_retries,
        )
        if _default is None:
            _default = self
        atexit.register(self.shutdown)

    # --- building blocks --------------------------------------------------------------

    def trace(self, name: str, **fields: Any) -> Trace:
        return Trace(self, name, **fields)

    def span(self, name: str, **fields: Any) -> Span:
        return Span(self, name, "span", **fields)

    def generation(self, name: str, *, model: str, **fields: Any) -> Span:
        return Span(self, name, "generation", model=model, **fields)

    def embedding(self, name: str, *, model: str, **fields: Any) -> Span:
        return Span(self, name, "embedding", model=model, **fields)

    def agent(self, name: str, **fields: Any) -> Span:
        return Span(self, name, "agent", **fields)

    def tool(self, name: str, **fields: Any) -> Span:
        return Span(self, name, "tool", **fields)

    def retriever(self, name: str, **fields: Any) -> Span:
        return Span(self, name, "retriever", **fields)

    # --- decorator --------------------------------------------------------------------

    def observe(
        self,
        name: str | None = None,
        *,
        kind: str = "span",
        capture_input: bool = True,
        capture_output: bool = True,
        **fields: Any,
    ) -> Callable[[F], F]:
        """Trace a function (sync or async). Arguments and the return value are recorded."""

        def decorate(function: F) -> F:
            label = name or function.__name__

            def prepare(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Span:
                span = Span(self, label, kind, **fields)
                if capture_input:
                    try:
                        bound = inspect.signature(function).bind_partial(*args, **kwargs)
                        span.fields["input"] = {
                            key: value for key, value in bound.arguments.items() if key != "self"
                        }
                    except TypeError:
                        span.fields["input"] = {"args": list(args), "kwargs": kwargs}
                return span

            if inspect.iscoroutinefunction(function):

                @functools.wraps(function)
                async def awrapper(*args: Any, **kwargs: Any) -> Any:
                    with prepare(args, kwargs) as span:
                        result = await function(*args, **kwargs)
                        if capture_output:
                            span.update(output=result)
                        return result

                return cast(F, awrapper)

            @functools.wraps(function)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                with prepare(args, kwargs) as span:
                    result = function(*args, **kwargs)
                    if capture_output:
                        span.update(output=result)
                    return result

            return cast(F, wrapper)

        return decorate

    # --- prompts ----------------------------------------------------------------------

    def get_prompt(
        self, name: str, *, version: int | None = None, label: str | None = None
    ) -> Prompt:
        """Fetch a managed prompt (production by default), cached for `prompt_cache_ttl`.

        When the server cannot be reached a stale cached copy is used rather than failing
        your request; with nothing cached the error is raised.
        """
        key = (name, version, label)
        now = time.monotonic()
        with self._prompt_lock:
            cached = self._prompts.get(key)
        if cached and now - cached[0] < self._prompt_ttl:
            return cached[1]
        params: dict[str, Any] = {}
        if version is not None:
            params["version"] = version
        if label is not None:
            params["label"] = label
        try:
            response = self._http.get(f"/v1/prompts/{name}", params=params)
            response.raise_for_status()
        except httpx.HTTPError:
            if cached:
                return cached[1]
            raise
        data = response.json()
        prompt = Prompt(
            name=data["name"],
            version=int(data["version"]),
            template=data["template"],
            config=data.get("config") or {},
            labels=tuple(data.get("labels") or ()),
        )
        with self._prompt_lock:
            self._prompts[key] = (now, prompt)
        return prompt

    # --- lifecycle --------------------------------------------------------------------

    def flush(self, timeout: float = 30.0) -> bool:
        return self._sender.flush(timeout) if self.enabled else True

    def shutdown(self) -> None:
        if self._http.is_closed:
            return
        self._sender.shutdown()
        self._http.close()

    @property
    def stats(self) -> dict[str, int]:
        return {
            "sent": self._sender.sent,
            "dropped": self._sender.dropped,
            "failed": self._sender.failed,
        }

    # --- called by handles ------------------------------------------------------------

    def _emit_span(self, span: Span) -> None:
        if self.enabled:
            self._sender.add("span", span.to_payload())

    def _emit_trace(self, trace_id: str, **fields: Any) -> None:
        if not self.enabled:
            return
        body: dict[str, Any] = {"id": trace_id, "environment": self.environment}
        if self.release:
            body["release"] = self.release
        for key in ("name", "user_id", "session_id", "tags", "metadata", "input", "output"):
            value = fields.get(key)
            if value:
                body[key] = value
        self._sender.add("trace", body)


def observe(name: str | None = None, *, kind: str = "span", **fields: Any) -> Callable[[F], F]:
    """`@observe()` on the default client (the first `TokenProfiler(...)` created)."""

    def decorate(function: F) -> F:
        # Resolved at call time so the decorator can be applied before the client exists.
        @functools.wraps(function)
        def proxy(*args: Any, **kwargs: Any) -> Any:
            return get_client().observe(name, kind=kind, **fields)(function)(*args, **kwargs)

        if inspect.iscoroutinefunction(function):

            @functools.wraps(function)
            async def aproxy(*args: Any, **kwargs: Any) -> Any:
                return await get_client().observe(name, kind=kind, **fields)(function)(
                    *args, **kwargs
                )

            return cast(F, aproxy)
        return cast(F, proxy)

    return decorate
