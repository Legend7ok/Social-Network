class ServiceUnavailableError(Exception):
    pass


class RedisUnavailableError(ServiceUnavailableError):
    pass
