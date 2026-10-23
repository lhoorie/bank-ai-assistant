from app.timing import timed
"""Persistent Milvus collections, versioned by document/embedding fingerprint."""
import os
import json
from pymilvus import MilvusClient, MilvusException
from app.model import ModelError


class VectorStore:
    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = MilvusClient(
                uri=os.getenv('MILVUS_URI', 'http://localhost:19530'),
                token=os.getenv('MILVUS_TOKEN', ''), timeout=30)
        return self._client

    @timed('milvus_search')
    def search(self, fingerprint, chunks, vector, top_k, threshold, *, source_names=None):
        # Separate collections prevent mixed dimensions and stale PDF results.
        name = 'bank_docs_' + fingerprint
        try:
            client = self.client
            if not client.has_collection(collection_name=name):
                client.create_collection(collection_name=name, dimension=len(vector),
                                         metric_type='COSINE', consistency_level='Strong')
            count = client.query(collection_name=name, filter='', output_fields=['count(*)'])[0]['count(*)']
            if count != len(chunks):
                client.upsert(collection_name=name, data=[
                    {'id': i, **chunk} for i, chunk in enumerate(chunks)])
                client.flush(collection_name=name)
            # Resolve case-insensitive user names to stored filenames before top-k.
            search_filter = ''
            if source_names:
                requested = {name.lower() for name in source_names}
                names = sorted({c['source'] for c in chunks if c['source'].lower() in requested})
                if not names:
                    return []
                search_filter = 'source in ' + json.dumps(names, ensure_ascii=False)
            hits = client.search(collection_name=name, data=[vector], limit=top_k, filter=search_filter,
                                 search_params={'metric_type': 'COSINE'},
                                 output_fields=['source', 'page', 'text'],
                                 consistency_level='Strong')[0]
            return [dict(hit['entity'], score=float(hit['distance']))
                    for hit in hits if hit['distance'] >= threshold]
        except (MilvusException, ConnectionError) as exc:
            raise ModelError('Milvus vector search failed; check the milvus service and MILVUS_URI.') from exc
