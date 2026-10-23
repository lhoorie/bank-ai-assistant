"""Small structured stdout logs with request correlation; no payload logging."""
import json
import logging
from contextvars import ContextVar

request_id_context = ContextVar('log_request_id', default='-')


def event(logger, name, *, level=logging.INFO, **fields):
    if logger.isEnabledFor(level):
        logger.log(level, json.dumps({'event':name, 'request_id':request_id_context.get(),
                                     **fields}, ensure_ascii=False, default=str))
