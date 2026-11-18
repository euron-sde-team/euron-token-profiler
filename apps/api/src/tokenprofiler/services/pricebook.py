"""Price books per project, cached in the process for a short time.

Ingest prices every metered span, so the table is loaded once and reused: a shared book plus
one per project that has overrides. An edit invalidates this process at once; other replicas
pick it up within the cache TTL, which is why the TTL is short.
"""

from __future__ import annotations

import time
import uuid

from tokenprofiler.db.session import Database
from tokenprofiler.ingest.pricing import PriceBook, PriceEntry, compile_pattern
from tokenprofiler.models import ModelPrice
from tokenprofiler.repositories.prices import PriceRepository


def entry_of(row: ModelPrice) -> PriceEntry:
    return PriceEntry(
        model=row.model,
        pattern=compile_pattern(row.match_pattern),
        input_per_mtok=row.input_per_mtok,
        output_per_mtok=row.output_per_mtok,
        cached_input_per_mtok=row.cached_input_per_mtok,
        provider=row.provider,
        project_scoped=row.project_id is not None,
    )


class PriceBooks:
    def __init__(self, db: Database, ttl_s: float) -> None:
        self._db = db
        self._ttl = ttl_s
        self._books: dict[uuid.UUID, tuple[float, PriceBook]] = {}

    async def get(self, project_id: uuid.UUID) -> PriceBook:
        cached = self._books.get(project_id)
        if cached is not None and time.monotonic() - cached[0] < self._ttl:
            return cached[1]
        async with self._db.session() as session:
            rows = await PriceRepository(session).for_project(project_id)
        book = PriceBook(entry_of(row) for row in rows)
        self._books[project_id] = (time.monotonic(), book)
        return book

    def invalidate(self, project_id: uuid.UUID | None = None) -> None:
        if project_id is None:
            self._books.clear()
        else:
            self._books.pop(project_id, None)
