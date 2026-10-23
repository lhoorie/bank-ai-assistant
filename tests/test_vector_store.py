import os
import uuid
import pytest
from pymilvus import MilvusException
from app.vector_store import VectorStore
from app.model import ModelError


def test_milvus_failure_is_controlled(monkeypatch):
    class Unavailable:
        def has_collection(self, **kwargs):
            raise MilvusException(message='unavailable')
    store = VectorStore()
    store._client = Unavailable()
    with pytest.raises(ModelError, match='Milvus'):
        store.search('test', [], [1., 0.], 8, .35)


@pytest.mark.skipif(os.getenv('TEST_MILVUS') != '1', reason='Requires running Milvus')
def test_real_milvus_search_and_reconnect():
    fingerprint = uuid.uuid4().hex
    store = VectorStore()
    chunks = [
        dict(text='Account opening', source='accounts.pdf', page=1, vector=[1., 0.]),
        dict(text='Replacement cards', source='cards.pdf', page=2, vector=[0., 1.])]
    try:
        hits = store.search(fingerprint, chunks, [1., 0.], 8, .8)
        assert len(hits) == 1
        assert hits[0]['source'] == 'accounts.pdf'
        assert hits[0]['page'] == 1
        assert hits[0]['score'] == pytest.approx(1.)
        reconnected = VectorStore()
        assert reconnected.search(fingerprint, chunks, [1., 0.], 1, .8) == hits
        assert store.search(fingerprint, chunks, [-1., 0.], 8, .8) == []
        # The globally best match is accounts.pdf, but the requested source
        # must be filtered before limit=1 is applied.
        scoped = store.search(fingerprint, chunks, [1., .1], 1, 0,
                              source_names=['CARDS.PDF'])
        assert [hit['source'] for hit in scoped] == ['cards.pdf']
        assert store.search(fingerprint, chunks, [1., 0.], 1, 0,
                            source_names=['missing.pdf']) == []
    finally:
        store.client.drop_collection(collection_name='bank_docs_' + fingerprint)
