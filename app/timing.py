"""Request-local, in-memory timing spans, propagated to retrieval threads."""
import logging
from app.logging_utils import event as log_event
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from threading import Lock
from time import perf_counter
from app.observability import instrument, request_context, current_trace_id

log = logging.getLogger(__name__)

_current = ContextVar('request_timings', default=None)

@contextmanager
def span(stage, **metadata):
    recorder = _current.get()
    if recorder is None:
        yield
        return
    start = perf_counter()
    outcome = 'ok'
    error_type = None
    try:
        yield
    except BaseException as exc:
        error_type = type(exc).__name__
        outcome = 'error'
        raise
    finally:
        event = dict(stage=stage, duration_ms=round((perf_counter()-start)*1000, 1),
                     start_ms=round((start-recorder['start'])*1000,1),
                     status=outcome, **metadata)
        with recorder['lock']:
            recorder['events'].append(event)
        log_event(log, 'stage_finished',
                  level=logging.WARNING if outcome == 'error' else logging.DEBUG,
                  stage=stage, duration_ms=event['duration_ms'], status=outcome,
                  error_type=error_type, **metadata)


def timed(stage, metadata=None):
    def decorate(function):
        traced_function = instrument(function, stage)
        @wraps(function)
        def wrapped(*args, **kwargs):
            details = metadata(*args, **kwargs) if metadata else {}
            with span(stage, **details):
                return traced_function(*args, **kwargs)
        return wrapped
    return decorate


def measure_request(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        recorder = {'start':perf_counter(), 'events':[], 'lock':Lock()}
        token = _current.set(recorder)
        try:
            result = function(*args, **kwargs)
            result['timings'] = {
                'total_ms':round((perf_counter()-recorder['start'])*1000,1),
                'events':sorted(recorder['events'],key=lambda event:event['start_ms'])}
            trace_id = current_trace_id()
            if trace_id:
                result['langsmith_trace_id'] = trace_id
            return result
        finally:
            _current.reset(token)
    traced_request = instrument(wrapped, 'banking_assistant')
    @wraps(function)
    def controlled(*args, **kwargs):
        with request_context():
            return traced_request(*args, **kwargs)
    return controlled
