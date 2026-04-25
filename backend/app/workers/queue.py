"""
RQ queue configuration.
Queues: default, normalization, reconciliation, exports.
"""
import redis
from rq import Queue

from app.config import get_settings

settings = get_settings()

_redis_conn = redis.from_url(settings.REDIS_URL)

default_queue = Queue("default", connection=_redis_conn)
normalization_queue = Queue("normalization", connection=_redis_conn)
reconciliation_queue = Queue("reconciliation", connection=_redis_conn)
exports_queue = Queue("exports", connection=_redis_conn)
