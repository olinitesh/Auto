from __future__ import annotations

from .deduper import ListingDeduper
from .normalizer import ListingNormalizer
from .parser import ListingParser
from .queue_worker import InMemoryScrapeQueue, ScraperWorker
from .types import NormalizedListing


def process_jobs(jobs: list) -> list[NormalizedListing]:
    queue = InMemoryScrapeQueue()
    for job in jobs:
        queue.enqueue(job)

    worker = ScraperWorker(
        queue=queue,
        parser=ListingParser(),
        normalizer=ListingNormalizer(),
        deduper=ListingDeduper(),
    )
    return worker.run_batch()
