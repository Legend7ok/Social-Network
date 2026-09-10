import logging

from django.conf import settings
from kombu.exceptions import OperationalError

from config import celery_app
from core.exceptions import QueueUnavailableError

logger = logging.getLogger(__name__)


def ensure_queue_available():
    """Refuse the request before it writes anything, if the queue is down.

    Tasks are handed over after the transaction commits, which is right - a
    worker must not pick up a row that is not there yet - but it means a broker
    failure surfaces once the write is already done. Answering "unavailable"
    then would be a lie: the account exists, the picture is stored, and asking
    the person to try again only earns them "this name is taken".

    So the question is asked first. It costs one round trip to Redis, a few
    milliseconds against a request that is about to store a file, and while
    Redis is known to be down the guard on the connection makes it instant.
    """
    try:
        connection = celery_app.connection_for_write()
        connection.ensure_connection(max_retries=0, timeout=settings.REDIS_TIMEOUT)
    except (OperationalError, OSError) as error:
        logger.error("queue unreachable, refusing the request", exc_info=True)
        raise QueueUnavailableError("the queue is not reachable") from error
