import hashlib
import json
import re
import threading
from app.pdf_text import extract_pages, normalize, EXTRACTION_VERSION
from app.seed import DOCS, DATA
from app.model import ModelError
from langchain_core.embeddings import Embeddings
from langgraph.graph import StateGraph, START, END
from app.rag_nodes import RAGState, RetrieverNode, RerankerNode, GenerationNode
from app.vector_store import VectorStore
from app.timing import timed

class ProviderEmbeddings(Embeddings):
    """LangChain adapter retaining the existing provider and credential configuration."""
    def __init__(self, model):
        self.model = model

    def embed_documents(self, texts):
        return self.model.embed(texts)

    @timed('query_embedding')
    def embed_query(self, text):
        return self.model.embed([text])[0]

def preprocess(text):
    text = normalize(text).replace('\u200c', ' ')
    text = text.translate(str.maketrans({'ي': 'ی', 'ك': 'ک'}))
    # Remove repeated document furniture and join wrapped PDF lines.
    text = '\n'.join(line for line in text.splitlines()
                     if 'ADAN DEMO BANK' not in line )
    return re.sub(r'\s+', ' ', text).strip()

class Documents:
    def __init__(self, model):
        self.model = model
        self.embeddings = ProviderEmbeddings(model)
        self.lock = threading.Lock()
        self.vector_store = VectorStore()
        graph = StateGraph(RAGState)
        graph.add_node('retriever', RetrieverNode(lambda question, **kwargs: self.search(question, **kwargs)))
        graph.add_node('reranker', RerankerNode())
        graph.add_node('generation', GenerationNode(model))
        graph.add_edge(START, 'retriever')
        graph.add_edge('retriever', 'reranker')
        graph.add_edge('reranker', 'generation')
        graph.add_edge('generation', END)
        self.graph = graph.compile()

    @timed('document_index')
    def index(self):
        import os
        files = sorted(DOCS.glob('*.pdf'))
        digest = hashlib.sha256()
        for path in files:
            if path.stat().st_size > int(os.getenv('PDF_MAX_MB', '20')) * 1024 * 1024:
                raise ModelError(f'{path.name}: PDF exceeds PDF_MAX_MB.')
            digest.update(path.name.encode())
            with path.open('rb') as handle:
                for block in iter(lambda: handle.read(65536), b''):
                    digest.update(block)
        for setting in ('EMBEDDING_MODEL', 'MODEL_BASE_URL', 'PDF_FORCE_OCR', 'PDF_OCR_DPI'):
            digest.update(os.getenv(setting, '').encode())
        digest.update(EXTRACTION_VERSION.encode())
        digest.update(b'preprocess-v2-preserve-numeric-lines')
        fingerprint = digest.hexdigest()
        cache = DATA / 'index.json'
        with self.lock:
            if cache.exists():
                try:
                    saved = json.loads(cache.read_text())
                    if saved['fingerprint'] == fingerprint:
                        return fingerprint, saved['chunks']
                except (ValueError, KeyError):
                    pass
            chunks = []
            for path in files:
                for page_no, text, method in extract_pages(path):
                    words = preprocess(text).split()
                    for start in range(0, len(words), 150):
                        chunks.append(dict(source=path.name, page=page_no, extraction_method=method,
                                           text=' '.join(words[start:start+180])))
            if not chunks:
                raise ValueError('No extractable PDF text found.')
            for chunk, vector in zip(chunks, self.embeddings.embed_documents([c['text'] for c in chunks])):
                chunk['vector'] = vector
            cache.write_text(json.dumps(dict(fingerprint=fingerprint, chunks=chunks)))
            return fingerprint, chunks

    def search(self, question, *, source_names=None):
        import os
        fingerprint, chunks = self.index()
        vector = self.embeddings.embed_query(question)
        top_k = max(1, min(20, int(os.getenv('RETRIEVAL_TOP_K', '8'))))
        with self.lock:
            return self.vector_store.search(fingerprint, chunks, vector, top_k,
                float(os.getenv('RETRIEVAL_MIN_SCORE', '0.35')), source_names=source_names)

    def answer(self, question, *, evidence_only=False):
        result = self.graph.invoke({'question': question, 'evidence_only':evidence_only,
            'source_names': [name.lower() for name in re.findall(r'[\w.-]+\.pdf\b', question, re.IGNORECASE)]})
        return {key: result[key] for key in ('answer', 'sources', 'rag_trace')}
