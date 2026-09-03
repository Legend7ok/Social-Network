class RedisUnavailableError(Exception):
    """Raised where losing Redis means the work cannot go on at all.

    Only the view-flushing task is in that position: it reads the buffered
    counts from Redis and has nothing to write without them, so it fails and
    the next run picks the counts up. Everything a person waits for reads
    around an outage instead — the stored count from the database.
    """
