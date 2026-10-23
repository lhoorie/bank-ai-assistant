import pytest
from fastapi.testclient import TestClient
from pymilvus import MilvusException
from app.api import app
from app import seed, explorer

NAME = 'bank_docs_' + 'a' * 64

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(seed, 'DB', tmp_path / 'bank.db')
    monkeypatch.setattr(seed, 'DOCS', tmp_path / 'docs')
    with TestClient(app) as c:
        yield c


def test_database_pagination_and_validation(client):
    tables = client.get('/inspect/database').json()['tables']
    assert {t['name']: t['count'] for t in tables} == {'customers':3, 'accounts':3, 'transactions':7}
    first = client.get('/inspect/database/customers?limit=2').json()
    second = client.get('/inspect/database/customers?offset=2&limit=2').json()
    assert first['total'] == 3 and len(first['rows']) == 2
    assert second['rows'][0][1] == 'Mina'
    assert client.get('/inspect/database/sqlite_master').status_code == 422
    assert client.get('/inspect/database/customers?limit=1000').status_code == 422
    assert client.get('/inspect/database/customers?offset=-1').status_code == 422
    assert client.post('/inspect/database/customers',json={}).status_code == 405
    assert client.get('/explorer').status_code == 200
    assert client.get('/static/explorer.js').status_code == 200


def test_milvus_pagination_vectors_and_cleanup(client, monkeypatch):
    class Iterator:
        def __init__(self): self.index = 0; self.closed = False
        def next(self):
            start = self.index;self.index += 2
            return [{'id': i, 'text':'متن', 'source':'test.pdf', 'page':1} for i in range(start,min(start+2,5))]
        def close(self): self.closed = True
    class FakeClient:
        def __init__(self): self.closed = False;self.iterator = None;self.fields = []
        def list_collections(self): return [NAME, 'unrelated_collection']
        def has_collection(self, **kw): return kw['collection_name'] == NAME
        def query(self, **kw): return [{'count(*)':5}]
        def query_iterator(self, **kw):
            self.fields = kw['output_fields'];self.iterator = Iterator();return self.iterator
        def close(self): self.closed = True
    fake = FakeClient()
    class Store:
        def __init__(self): self._client = fake
        @property
        def client(self): return self._client
    monkeypatch.setattr(app.state.coordinator.documents, 'vector_store', Store())
    assert client.get('/inspect/collections').json()['collections'] == [NAME]
    result = client.get(f'/inspect/collections/{NAME}?offset=2&limit=2').json()
    assert [r['id'] for r in result['rows']] == [2,3]
    assert 'vector' not in fake.fields
    assert not fake.closed and fake.iterator.closed
    client.get(f'/inspect/collections/{NAME}?include_vectors=true')
    assert 'vector' in fake.fields
    # Browsing repeatedly must never invalidate the client's shared SDK alias.
    client.get('/inspect/collections')
    assert not fake.closed
    assert client.get('/inspect/collections/unrelated_collection').status_code == 404


def test_milvus_failure_shown_without_breaking_database(client, monkeypatch):
    class Store:
        _client = None
        @property
        def client(self): raise MilvusException(message='offline')
    monkeypatch.setattr(app.state.coordinator.documents, 'vector_store', Store())
    assert client.get('/inspect/collections').status_code == 502
    assert client.get('/inspect/database').status_code == 200
