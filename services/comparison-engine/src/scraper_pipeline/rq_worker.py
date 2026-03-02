from __future__ import annotations

from dataclasses import asdict

from redis import Redis
from rq import Queue, Worker

from autohaggle_shared.config import settings

from .deduper import ListingDeduper
from .normalizer import ListingNormalizer
from .parser import ListingParser
from .sources import sample_jobs
from .types import ScrapeJob

SCRAPER_QUEUE_NAME = "autohaggle-scraper"


def get_scraper_queue() -> Queue:
    redis_client = Redis.from_url(settings.redis_url)
    return Queue(SCRAPER_QUEUE_NAME, connection=redis_client)


def process_scrape_job(job_payload: dict) -> dict:
    parser = ListingParser()
    normalizer = ListingNormalizer()
    deduper = ListingDeduper()

    parsed = parser.parse(ScrapeJob(source=str(job_payload["source"]), payload=job_payload["payload"]))
    normalized = normalizer.normalize(parsed)
    deduped = deduper.dedupe([normalized])[0]
    return asdict(deduped)


def enqueue_sample_jobs() -> list[str]:
    queue = get_scraper_queue()
    job_ids: list[str] = []

    for item in sample_jobs():
        job = queue.enqueue(process_scrape_job, {"source": item.source, "payload": item.payload})
        job_ids.append(job.id)

    return job_ids


def run_worker() -> None:
    queue = get_scraper_queue()
    worker = Worker([queue], connection=queue.connection)
    worker.work()
