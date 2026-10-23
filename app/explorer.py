"""Read-only, paginated inspection of this demo's SQLite and Milvus data."""
import re
import sqlite3
from typing import Literal
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from pymilvus import MilvusException
from app import seed
from app.vector_store import VectorStore

router = APIRouter(prefix='/inspect', tags=['Data explorer'])
TABLES = ('customers', 'accounts', 'transactions')
COLLECTION = re.compile(r'bank_docs_[0-9a-f]{32,64}\Z')

@router.get('/database')
def database_tables():
    with sqlite3.connect(seed.DB.as_uri() + '?mode=ro', uri=True) as conn:
        return {'tables': [{'name': name, 'count': conn.execute(
            f'SELECT COUNT(*) FROM {name}').fetchone()[0]} for name in TABLES]}

@router.get('/database/{table}')
def database_rows(table: Literal['customers', 'accounts', 'transactions'],
                  offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100)):
    with sqlite3.connect(seed.DB.as_uri() + '?mode=ro', uri=True) as conn:
        total = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        cursor = conn.execute(f'SELECT * FROM {table} ORDER BY id LIMIT ? OFFSET ?', (limit, offset))
        return {'columns': [c[0] for c in cursor.description], 'rows': cursor.fetchall(),
                'total': total, 'offset': offset, 'limit': limit}

def get_vector_store(request: Request):
    # Reuse the application's long-lived client. SDK aliases are shared by URI;
    # closing a temporary inspector client also disconnects the chat client.
    return request.app.state.coordinator.documents.vector_store

@router.get('/collections')
def collections(store: VectorStore = Depends(get_vector_store)):
    try:
        return {'collections': sorted(n for n in store.client.list_collections() if COLLECTION.fullmatch(n))}
    except (MilvusException, ConnectionError) as exc:
        raise HTTPException(502, 'اتصال به Milvus برقرار نشد.') from exc

@router.get('/collections/{name}')
def chunks(name: str, offset: int = Query(0, ge=0),
           limit: int = Query(25, ge=1, le=100), include_vectors: bool = False,
           store: VectorStore = Depends(get_vector_store)):
    if not COLLECTION.fullmatch(name):
        raise HTTPException(404, 'Collection معتبر نیست.')
    iterator = None
    try:
        client = store.client
        if not client.has_collection(collection_name=name):
            raise HTTPException(404, 'Collection پیدا نشد.')
        total = client.query(collection_name=name, filter='', output_fields=['count(*)'],
                             consistency_level='Strong')[0]['count(*)']
        fields = ['id', 'source', 'page', 'text'] + (['vector'] if include_vectors else [])
        # Iterator avoids Milvus's query offset+limit window and bounds RAM per batch.
        iterator = client.query_iterator(collection_name=name, batch_size=limit,
                                         filter='', output_fields=fields,
                                         consistency_level='Strong')
        skipped = 0
        rows = []
        while len(rows) < limit:
            batch = iterator.next()
            if not batch: break
            for row in batch:
                if skipped < offset:
                    skipped += 1
                elif len(rows) < limit:
                    rows.append(row)
        return {'rows': rows, 'total': total, 'offset': offset, 'limit': limit}
    except (MilvusException, ConnectionError) as exc:
        raise HTTPException(502, 'خواندن چانک‌ها از Milvus ناموفق بود.') from exc
    finally:
        if iterator is not None: iterator.close()
