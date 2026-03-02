from __future__ import annotations

from dataclasses import asdict
from json import dumps

from .deduper import ListingDeduper
from .normalizer import ListingNormalizer
from .parser import ListingParser
from .queue_worker import InMemoryScrapeQueue, ScraperWorker
from .sources import sample_jobs


def run_demo() -> list[dict]:
    queue = InMemoryScrapeQueue()
    for job in sample_jobs():
        queue.enqueue(job)

    worker = ScraperWorker(
        queue=queue,
        parser=ListingParser(),
        normalizer=ListingNormalizer(),
        deduper=ListingDeduper(),
    )

    deduped = worker.run_batch()
    return [asdict(item) for item in deduped]


def main() -> None:
    result = run_demo()
    print(dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
