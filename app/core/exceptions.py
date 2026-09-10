class ServiceUnavailableError(Exception):
    """Raised in a view when something the request depends on is missing, and
    waiting will not help. Turned into a 503 by the middleware.

    Deliberately raised before anything is written, so the answer is true: the
    request did nothing and can simply be repeated.
    """


class QueueUnavailableError(ServiceUnavailableError):
    """The broker is not reachable, so no background work can be scheduled.

    Everything a person starts here ends in a task - the welcome email, the
    thumbnails, the download behind a bookmarked link. Letting the write
    through without one leaves work that nothing will ever pick up: a picture
    with no thumbnails, a link that never downloads.
    """


class RedisUnavailableError(Exception):
    """Raised where losing Redis means the work cannot go on at all.

    Only the view-flushing task is in that position: it reads the buffered
    counts from Redis and has nothing to write without them, so it fails and
    the next run picks the counts up. Everything a person waits for reads
    around an outage instead — the stored count from the database.
    """
