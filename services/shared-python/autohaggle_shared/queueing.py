from rq import Queue
from redis import Redis

from autohaggle_shared.config import settings

QUEUE_NAME = "autohaggle-negotiation"


def get_queue() -> Queue:
    redis_client = Redis.from_url(settings.redis_url)
    return Queue(QUEUE_NAME, connection=redis_client)
