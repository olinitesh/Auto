from redis import Redis
from rq import Connection, Worker

from autohaggle_shared.config import settings
from autohaggle_shared.queueing import QUEUE_NAME


def main() -> None:
    redis_conn = Redis.from_url(settings.redis_url)
    with Connection(redis_conn):
        worker = Worker([QUEUE_NAME])
        worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
