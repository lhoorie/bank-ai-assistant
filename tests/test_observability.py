from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
import pytest
from langsmith import get_current_run_tree, tracing_context
from app import observability, timing


def test_disabled_without_explicit_flag_and_key(monkeypatch):
    monkeypatch.delenv('LANGSMITH_API_KEY',raising=False)
    monkeypatch.setenv('LANGSMITH_TRACING','true')
    assert not observability.tracing_enabled()
    monkeypatch.setenv('LANGSMITH_API_KEY','test-secret')
    monkeypatch.setenv('LANGSMITH_TRACING','false')
    assert not observability.tracing_enabled()
    @timing.measure_request
    def request():return {'answer':'ok'}
    assert 'langsmith_trace_id' not in request()


def test_redaction_does_not_change_actual_inputs(monkeypatch):
    monkeypatch.setenv('MODEL_API_KEY','my-test-secret')
    data={'self':object(),'question':'hello my-test-secret',
          'headers':{'Authorization':'Bearer my-test-secret'},'vector':[.1]*1024,
          'sources':[{'text':'evidence','source':'accounts.pdf','page':1}]}
    clean=observability.sanitize(data)
    assert 'self' not in clean
    assert clean['headers']=='[redacted]' and clean['vector']=='[vector omitted]'
    assert clean['question']=='hello [redacted]'
    assert clean['sources'][0]['text']=='evidence'
    assert data['question']=='hello my-test-secret'
    assert len(data['vector'])==1024


def test_local_trace_root_and_parallel_child_parentage(monkeypatch):
    # Local SDK mode creates real run trees, sends nothing to LangSmith.
    monkeypatch.setattr(timing,'request_context',lambda:tracing_context(enabled='local'))
    parents=[]
    @timing.timed('test_tool')
    def child():
        run=get_current_run_tree()
        parents.append((str(run.parent_run_id),str(run.trace_id)))
        return 'ok'
    @timing.measure_request
    def request():
        root=get_current_run_tree()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(copy_context().run,child) for _ in range(2)]
            assert [f.result() for f in futures]==['ok','ok']
        return {'root_id':str(root.id)}
    result=request()
    assert len(parents)==2
    assert all(parent==result['root_id'] and trace==result['langsmith_trace_id'] for parent,trace in parents)
    assert len(result['timings']['events'])==2


def test_original_errors_propagate_with_local_tracing(monkeypatch):
    monkeypatch.setattr(timing,'request_context',lambda:tracing_context(enabled='local'))
    @timing.measure_request
    @timing.timed('broken_tool')
    def request():raise ValueError('original failure')
    with pytest.raises(ValueError,match='original failure'):request()


def test_hide_all_inputs_and_outputs(monkeypatch):
    monkeypatch.setenv('LANGSMITH_HIDE_INPUTS','true')
    monkeypatch.setenv('LANGSMITH_HIDE_OUTPUTS','true')
    assert observability.trace_inputs({'question':'private'})=={}
    assert observability.trace_outputs({'answer':'private'})=={}
