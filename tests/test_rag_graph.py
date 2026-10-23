import pytest
from app.rag import Documents
from app.reranker import RemoteReranker
from app.model import ModelError

class Model:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        return {'content': next(self.responses)}

def candidate(text, page):
    return dict(text=text, source='accounts.pdf', page=page, score=.9)

def scores(monkeypatch, values):
    monkeypatch.setattr(RemoteReranker, 'score', lambda self, question, passages: values)

def test_graph_reranks_then_generates(monkeypatch):
    scores(monkeypatch, [0.01, 0.95])
    model = Model(['Answer with evidence'])
    docs = Documents(model)
    monkeypatch.setenv('RERANK_TOP_K', '1')
    monkeypatch.setattr(docs, 'search', lambda q, **kwargs: [candidate('irrelevant', 1), candidate('relevant', 2)])
    result = docs.answer('question')
    assert result['sources'] == [{**candidate('relevant', 2), 'rerank_score': .95}]
    assert [t['node'] for t in result['rag_trace']] == ['retriever', 'reranker', 'generation']
    assert result['rag_trace'][1]['method'] == 'cross_encoder'
    assert len(model.calls) == 1
    assert 'relevant' in model.calls[0][0]['content']
    assert 'irrelevant' not in model.calls[0][0]['content']

def test_no_candidates_skips_model(monkeypatch):
    def unexpected(*args):
        raise AssertionError('Reranker must not run')
    monkeypatch.setattr(RemoteReranker, 'score', unexpected)
    model = Model([])
    docs = Documents(model)
    monkeypatch.setattr(docs, 'search', lambda q, **kwargs: [])
    assert docs.answer('question')['sources'] == []
    assert not model.calls

def test_reranker_can_reject_all(monkeypatch):
    scores(monkeypatch, [0.01])
    monkeypatch.setenv('RERANK_MIN_SCORE', '0.1')
    model = Model([])
    docs = Documents(model)
    monkeypatch.setattr(docs, 'search', lambda q, **kwargs: [candidate('unrelated', 1)])
    assert docs.answer('question')['sources'] == []
    assert not model.calls

@pytest.mark.parametrize('values', [[], [float('nan')], [float('inf')], [-1], [2]])
def test_invalid_reranker_output_fails_closed(monkeypatch, values):
    scores(monkeypatch, values)
    docs = Documents(Model([]))
    monkeypatch.setattr(docs, 'search', lambda q, **kwargs: [candidate('text', 1)])
    with pytest.raises(ModelError, match='Reranker'):
        docs.answer('question')

def test_reranker_environment(monkeypatch):
    monkeypatch.setenv('RERANK_MODEL', 'qwen/qwen3-reranker-0.6b')
    reranker = RemoteReranker()
    assert reranker.model_name == 'qwen/qwen3-reranker-0.6b'
    assert reranker.score('q', []) == []


def test_evidence_only_skips_document_llm_and_keeps_citations(monkeypatch):
    scores(monkeypatch, [.95])
    model = Model([])  # Any generation call would fail.
    docs = Documents(model)
    evidence = candidate('Minimum opening balance is 1000000 IRR.', 1)
    monkeypatch.setattr(docs, 'search', lambda q, **kwargs: [evidence])
    result = docs.answer('Compare minimum with customer balance', evidence_only=True)
    assert result['answer'] is None
    assert result['sources'][0]['text'] == evidence['text']
    assert result['sources'][0]['source'] == 'accounts.pdf'
    assert result['rag_trace'][-1]['skipped'] is True
    assert model.calls == []


def test_evidence_only_empty_sources_do_not_invent_answer(monkeypatch):
    model = Model([])
    docs = Documents(model)
    monkeypatch.setattr(docs, 'search', lambda q, **kwargs: [])
    result = docs.answer('unknown', evidence_only=True)
    assert result['sources'] == [] and result['answer'] is None
    assert model.calls == []


def test_explicit_pdf_scope_excludes_other_product_rules(monkeypatch):
    scores(monkeypatch, [.95])
    model = Model([])
    docs = Documents(model)
    english = dict(source='accounts.pdf',page=1,text='Minimum balance is 1000000 IRR.',score=.8)
    other = dict(source='persian_demo_rules.pdf',page=1,text='Different product minimum is 2000000 IRR.',score=.9)
    monkeypatch.setattr(docs,'search',lambda q, **kwargs:[other,english])
    result=docs.answer('Minimum in accounts.pdf?',evidence_only=True)
    assert result['sources'] == [{**english, 'rerank_score':.95}]
