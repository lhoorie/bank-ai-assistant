import json
import logging
import pytest
from fastapi.testclient import TestClient
from app.api import app
from app.agents import Coordinator, DatabaseAgent
from app.model import Model, ModelError
from app.rag import preprocess
from app.vector_store import VectorStore


def test_standalone_amounts_survive_preprocessing():
    assert preprocess('Minimum balance\n1000000\nIRR') == 'Minimum balance 1000000 IRR'
    assert '۲۰۰۰۰۰۰' in preprocess('حداقل موجودی\n۲۰۰۰۰۰۰\nریال')


@pytest.mark.parametrize('indices', [[0, 0], [1, 2], [-1, 0], [False, 1], ['0', 1]])
def test_invalid_embedding_indices_rejected(monkeypatch, indices):
    model = Model()
    monkeypatch.setattr(model, 'post', lambda *args: {'data': [
        {'index': i, 'embedding': [1., 0.]} for i in indices]})
    with pytest.raises(ModelError, match='embedding'):
        model.embed(['a', 'b'])


def test_embedding_indices_restore_input_order(monkeypatch):
    model = Model()
    monkeypatch.setattr(model, 'post', lambda *args: {'data': [
        {'index': 1, 'embedding': [0., 1.]}, {'index': 0, 'embedding': [1., 0.]}]})
    assert model.embed(['a', 'b']) == [[1., 0.], [0., 1.]]


@pytest.mark.parametrize('calls', [
    {}, 'invalid', 0, [{'id': 'bad', 'function': {}}],
    [{'id': 'bad', 'type': 'function', 'function': {'name': 'calculator', 'arguments': '[]'}}],
    [{'id': 'bad', 'type': 'function', 'function': {'name': 'calculator', 'arguments': '{'}}],
    [{'id': 'bad', 'type': 'function', 'function': {'name': 'calculator', 'arguments': '{"expression": 4}'}}],
])
def test_malformed_calls_return_correlated_502(monkeypatch, calls):
    with TestClient(app) as client:
        app.state.coordinator.router.model = ''
        monkeypatch.setattr(app.state.coordinator.model, 'chat',
                            lambda *a, **kw: {'tool_calls': calls})
        response = client.post('/ask', json={'question': 'test'})
        assert response.status_code == 502
        assert response.headers['X-Request-ID']
        assert 'Invalid tool call' in response.json()['error']


def test_database_malformed_call_is_controlled(monkeypatch):
    model = Model()
    monkeypatch.setattr(model, 'chat', lambda *a, **kw: {'tool_calls': [{'function': {}}]})
    with pytest.raises(ModelError, match='Invalid tool call'):
        DatabaseAgent(model).answer('balance')


def test_unexpected_error_keeps_request_id_and_hides_detail(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    with TestClient(app) as client:
        def fail(question):
            raise RuntimeError('sensitive diagnostic')
        monkeypatch.setattr(app.state.coordinator, 'answer', fail)
        response = client.post('/ask', json={'question': 'test'})
        assert response.status_code == 500
        ident = response.headers['X-Request-ID']
        events = [json.loads(r.message) for r in caplog.records
                  if r.name == 'app.api' and r.message.startswith('{')]
        assert any(e['event'] == 'unexpected_error' and e['request_id'] == ident for e in events)
        assert 'sensitive diagnostic' not in response.text + caplog.text


def test_source_filter_applied_before_top_k():
    chunks = [dict(source='Other.pdf', text='other', page=1, vector=[1., 0.]),
              dict(source='Accounts.pdf', text='target', page=1, vector=[.9, .1])]
    class Client:
        def has_collection(self, **kwargs): return True
        def query(self, **kwargs): return [{'count(*)': 2}]
        def search(self, **kwargs):
            assert kwargs['limit'] == 1
            assert kwargs['filter'] == 'source in ["Accounts.pdf"]'
            return [[{'entity': chunks[1], 'distance': .9}]]
    store = VectorStore()
    store._client = Client()
    hits = store.search('test', chunks, [1., 0.], 1, .35, source_names=['ACCOUNTS.pdf'])
    assert hits[0]['source'] == 'Accounts.pdf'
    assert store.search('test', chunks, [1., 0.], 1, .35, source_names=['missing.pdf']) == []
