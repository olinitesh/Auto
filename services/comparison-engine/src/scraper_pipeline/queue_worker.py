from __future__ import annotations

from collections import deque

from .deduper import ListingDeduper
from .normalizer import ListingNormalizer
from .parser import ListingParser
from .types import NormalizedListing, ScrapeJob


class InMemoryScrapeQueue:
    """Simple queue abstraction for local development and tests."""

    def __init__(self) -> None:
        self._jobs: deque[ScrapeJob] = deque()

    def enqueue(self, job: ScrapeJob) -> None:
        self._jobs.append(job)

    def dequeue(self) -> ScrapeJob | None:
        if not self._jobs:
            return None
        return self._jobs.popleft()

    def __len__(self) -> int:
        return len(self._jobs)


class ScraperWorker:
    """Queue worker that runs parser -> normalizer -> deduper pipeline."""

    def __init__(
        self,
        queue: InMemoryScrapeQueue,
        parser: ListingParser,
        normalizer: ListingNormalizer,
        deduper: ListingDeduper,
    ) -> None:
        self.queue = queue
        self.parser = parser
        self.normalizer = normalizer
        self.deduper = deduper

    def run_batch(self) -> list[NormalizedListing]:
        normalized: list[NormalizedListing] = []

        while True:
            job = self.queue.dequeue()
            if job is None:
                break

            parsed = self.parser.parse(job)
            normalized.append(self.normalizer.normalize(parsed))

        return self.deduper.dedupe(normalized)
