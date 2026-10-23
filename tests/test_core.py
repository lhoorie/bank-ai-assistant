import json
import sqlite3
import pytest
from fastapi.testclient import TestClient
from app import seed as seed_module
from app import tools
from app.agents import Coordinator
from app.api import app
from app.rag import preprocess, Documents

@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    db = tmp_path / 'test.db'
    monkeypatch.setattr(seed_module, 'DB', db)
    monkeypatch.setattr(tools, 'DB', db)
    monkeypatch.setattr(seed_module, 'DOCS', tmp_path / 'documents')
    monkeypatch.setattr('app.rag.DOCS', tmp_path / 'documents')
    monkeypatch.setattr('app.reranker.RemoteReranker.score', lambda self, question, passages: [0.9] * len(passages))
    seed_module.seed()

def test_join_and_aggregation():
    result = tools.query("SELECT c.city, SUM(t.amount_irr) FROM customers c JOIN accounts a ON c.id=a.customer_id JOIN transactions t "
                         "ON a.id=t.account_id WHERE t.status='completed' AND t.direction='debit' GROUP BY c.city ORDER BY c.city")
    assert result['rows'] == [('Shiraz', 2000000), ('Tehran', 5500000)]

@pytest.mark.parametrize('sql', [
    'DROP TABLE transactions', 'DELETE FROM transactions', 'SELECT 1; DELETE FROM transactions',
    'PRAGMA table_info(transactions)', "ATTACH DATABASE 'other.db' AS other",
    'SELECT * FROM sqlite_master', "SELECT load_extension('bad')",
    'SELECT randomblob(1000000000)', 'SELECT * FROM missing', 'SELEC invalid',
    'WITH x AS (SELECT * FROM sqlite_master) SELECT * FROM x',
])
def test_unsafe_sql(sql):
    with pytest.raises((ValueError, sqlite3.Error)):
        tools.query(sql)
    assert tools.query('SELECT COUNT(*) FROM transactions')['rows'] == [(7,)]

def test_row_limit():
    assert tools.query('SELECT a.id FROM transactions a, transactions b, transactions c, transactions d')['truncated']

def test_account_balances_exclude_failed_pending():
    result = tools.query("SELECT a.id, a.opening_balance_irr + COALESCE(SUM(CASE "
        "WHEN t.status='completed' AND t.direction='credit' THEN t.amount_irr "
        "WHEN t.status='completed' AND t.direction='debit' THEN -t.amount_irr ELSE 0 END),0) "
        "FROM accounts a LEFT JOIN transactions t ON a.id=t.account_id "
        "GROUP BY a.id ORDER BY a.id")
    assert result['rows'] == [(1, 12200000), (2, 18000000), (3, 12300000)]

def test_seed_is_idempotent():
    seed_module.seed()
    assert tools.query('SELECT COUNT(*) FROM transactions')['rows'] == [(7,)]
    assert tools.query('SELECT COUNT(*) FROM accounts')['rows'] == [(3,)]

def test_calculator():
    assert tools.calculate('(4500000-3000000)/3000000*100')['result'] == 50

@pytest.mark.parametrize('expression', ['1/0', '__import__("os")', '2**999999', 'True+1', '1e309'])
def test_calculator_rejects(expression):
    with pytest.raises((ValueError, ArithmeticError)):
        tools.calculate(expression)

def test_preprocessing():
    assert preprocess('ADAN DEMO BANK\nReplacement\n takes   3 days\n12') == 'Replacement takes 3 days 12'

def call(name, args, ident='1'):
    return dict(role='assistant', content=None, tool_calls=[dict(
        id=ident, type='function', function=dict(name=name, arguments=json.dumps(args)))])

class ScriptedModel:
    """Test double only: production always calls the configured provider."""
    def __init__(self, responses):
        self.responses = iter(responses)
    def chat(self, messages, tools=None, **kwargs):
        return next(self.responses)

def test_sql_then_calculator():
    model = ScriptedModel([
        call('database_agent', {'question': 'September and October completed debit totals?'}),
        call('run_sql', {'sql': "SELECT substr(transaction_date,1,7),SUM(amount_irr) FROM transactions "
             "WHERE status='completed' AND direction='debit' GROUP BY substr(transaction_date,1,7) ORDER BY 1"}),
        call('calculator', {'expression': '(4500000-3000000)/3000000*100'}, '2'),
        dict(role='assistant', content='Expenses increased by 50%.')])
    result = Coordinator(model).answer('Expense growth?')
    assert [t['component'] for t in result['trace']] == ['database_agent', 'calculator']
    assert result['trace'][0]['result']['rows'] == [('2026-09', 3000000), ('2026-10', 4500000)]
    assert result['trace'][1]['result']['result'] == 50

def test_insufficient_documents(monkeypatch):
    docs = Documents(ScriptedModel([]))
    monkeypatch.setattr(docs, 'search', lambda question, **kwargs: [])
    assert docs.answer('unknown')['sources'] == []

def test_rag_source_propagation(monkeypatch):
    evidence = [dict(source='accounts.pdf', page=1, text='Minimum opening balance is 1000000 IRR.', score=.9)]
    docs = Documents(ScriptedModel([dict(content='1000000 IRR [accounts.pdf, page 1]')]))
    monkeypatch.setattr(docs, 'search', lambda question, **kwargs: evidence)
    assert docs.answer('Minimum opening balance?')['sources'] == [{**evidence[0], 'rerank_score': 0.9}]

def test_pdf_index_and_milvus_retrieval(tmp_path, monkeypatch):
    from app import rag
    monkeypatch.setattr(rag, 'DATA', tmp_path)
    monkeypatch.setenv('RETRIEVAL_MIN_SCORE', '0.8')
    class Embeddings:
        def embed(self, texts):
            return [[1., 0.] if 'opening' in t.lower() else [0., 1.] for t in texts]
    docs = Documents(Embeddings())
    calls = []
    def search(fingerprint, chunks, vector, top_k, threshold, **kwargs):
        calls.append(fingerprint)
        assert len(fingerprint) == 64
        assert vector == [1., 0.]
        assert threshold == 0.8
        return [dict(source=c['source'], page=c['page'], text=c['text'], score=1.)
                for c in chunks if 'opening' in c['text'].lower()]
    monkeypatch.setattr(docs.vector_store, 'search', search)
    sources = docs.search('opening balance')
    assert sources and all(s['source'] == 'accounts.pdf' for s in sources)
    assert sources[0]['page'] == 1
    assert (tmp_path / 'index.json').exists()
    assert docs.search('opening balance') == sources
    assert calls[0] == calls[1]

def test_api_validation(monkeypatch):
    monkeypatch.delenv('MODEL_BASE_URL', raising=False)
    with TestClient(app) as client:
        assert client.get('/health').status_code == 200
        assert client.post('/ask', json={'question': ''}).status_code == 422
        assert client.post('/ask', json={'question': '  '}).status_code == 422
        assert client.post('/ask', json={'question': 'x'*2001}).status_code == 422
        assert client.post('/ask', json={'question': 'hello'}).status_code == 502


def test_jev_mixed_route_then_calculator(monkeypatch):
    from app.router import ROUTES
    monkeypatch.setenv('ROUTER_MODEL', 'typesafe/jev-1.14')
    routes = iter(['both', 'calculator', 'final'])
    class RoutedModel:
        def __init__(self):
            self.tools_seen = []
        def post(self, path, payload, **kwargs):
            route = next(routes)
            return {'answers': {'route': {'type': 'choice', 'choice': route,
                    'probabilities': {r: float(r == route) for r in ROUTES}}}}
        def chat(self, messages, tools=None, **kwargs):
            names = [t['function']['name'] for t in tools or []]
            self.tools_seen.append(names)
            if kwargs.get('tool_choice') == 'none':
                return {'content': '12.2 times'}
            if 'database_agent' in names:
                one = call('database_agent', {'question': 'Sara balance'})
                two = call('documents_agent', {'question': 'Minimum opening balance'}, '2')
                one['tool_calls'] += two['tool_calls']
                assert kwargs['tool_choice'] == 'required'
                return one
            if 'calculator' in names:
                return call('calculator', {'expression': '12200000/1000000'}, '3')
            return {'content': '12.2 times'}
    model = RoutedModel()
    coordinator = Coordinator(model)
    monkeypatch.setattr(coordinator.database, 'answer', lambda q, **kwargs: {'rows': [[12200000]]})
    monkeypatch.setattr(coordinator.documents, 'answer', lambda q, **kw: {'answer': '1000000 IRR'})
    result = coordinator.answer('Compare Sara balance to opening minimum')
    assert [r['route'] for r in result['router_trace']] == ['both', 'calculator', 'final']
    assert [r['component'] for r in result['trace']] == ['database_agent', 'documents_agent', 'calculator']
    assert result['trace'][-1]['result']['result'] == 12.2
    assert set(model.tools_seen[-1]) == {'documents_agent','database_agent','calculator'}


def test_jev_rejects_tool_outside_selected_route(monkeypatch):
    from app.model import ModelError
    monkeypatch.setenv('ROUTER_MODEL', 'typesafe/jev-1.14')
    coordinator = Coordinator(ScriptedModel([call('calculator', {'expression': '1+1'})]))
    monkeypatch.setattr(coordinator.router, 'select', lambda messages: {'route': 'final'})
    with pytest.raises(ModelError, match='Jev tool route'):
        coordinator.answer('test')


def test_parallel_retrieval_preserves_order_and_waits_for_results(monkeypatch):
    import threading
    monkeypatch.delenv('ROUTER_MODEL', raising=False)
    monkeypatch.setenv('PARALLEL_RETRIEVAL', 'true')
    barrier = threading.Barrier(2)
    finished = set()
    first = call('database_agent', {'question': 'balance'}, 'db')
    first['tool_calls'] += call('documents_agent', {'question': 'minimum'}, 'docs')['tool_calls']
    class CheckingModel(ScriptedModel):
        def chat(self, messages, tools=None, **kwargs):
            if finished:
                assert finished == {'db', 'docs'}
                results = [m for m in messages if m['role'] == 'tool']
                assert [m['tool_call_id'] for m in results] == ['db', 'docs']
            return super().chat(messages, tools)
    coordinator = Coordinator(CheckingModel([first, {'content': 'done'}]))
    def database(q):
        barrier.wait(timeout=3)
        finished.add('db')
        return {'rows': [[12200000]]}
    def documents(q, **kwargs):
        barrier.wait(timeout=3)
        finished.add('docs')
        return {'answer': '1000000 IRR'}
    monkeypatch.setattr(coordinator.database, 'answer', database)
    monkeypatch.setattr(coordinator.documents, 'answer', documents)
    result = coordinator.answer('mixed')
    assert [t['component'] for t in result['trace']] == ['database_agent', 'documents_agent']
    assert all(t['execution'] == 'parallel' for t in result['trace'])


def test_parallel_tool_error_keeps_other_result(monkeypatch):
    monkeypatch.delenv('ROUTER_MODEL', raising=False)
    monkeypatch.setenv('PARALLEL_RETRIEVAL', 'true')
    first = call('database_agent', {'question': 'balance'}, 'db')
    first['tool_calls'] += call('documents_agent', {'question': 'minimum'}, 'docs')['tool_calls']
    coordinator = Coordinator(ScriptedModel([first, {'content': 'explain error'}]))
    def broken(q):
        raise ValueError('invalid query')
    monkeypatch.setattr(coordinator.database, 'answer', broken)
    monkeypatch.setattr(coordinator.documents, 'answer', lambda q, **kw: {'answer': 'evidence'})
    result = coordinator.answer('mixed')
    assert result['trace'][0]['result'] == {'error': 'invalid query'}
    assert result['trace'][1]['result'] == {'answer': 'evidence'}


@pytest.mark.parametrize('enabled', ['true', 'false'])
def test_retrieval_execution_timing(monkeypatch, enabled):
    import time
    monkeypatch.delenv('ROUTER_MODEL', raising=False)
    monkeypatch.setenv('PARALLEL_RETRIEVAL', enabled)
    first = call('database_agent', {'question': 'balance'}, 'db')
    first['tool_calls'] += call('documents_agent', {'question': 'minimum'}, 'docs')['tool_calls']
    coordinator = Coordinator(ScriptedModel([first, {'content': 'done'}]))
    def delayed(q, **kwargs):
        time.sleep(.2)
        return {'answer': 'evidence'}
    monkeypatch.setattr(coordinator.database, 'answer', delayed)
    monkeypatch.setattr(coordinator.documents, 'answer', delayed)
    result = coordinator.answer('mixed')
    expected = 'parallel' if enabled == 'true' else 'sequential'
    assert all(t['execution'] == expected for t in result['trace'])
    print(f"\n{expected}: {result['trace'][0]['batch_duration_ms']} ms (two 200 ms tools)")


def test_calculator_batch_remains_sequential(monkeypatch):
    import threading
    monkeypatch.delenv('ROUTER_MODEL', raising=False)
    monkeypatch.setenv('PARALLEL_RETRIEVAL', 'true')
    first = call('database_agent', {'question': 'balance'}, 'db')
    first['tool_calls'] += call('calculator', {'expression': '2+2'}, 'calc')['tool_calls']
    coordinator = Coordinator(ScriptedModel([first, {'content': 'done'}]))
    owner = threading.get_ident()
    def database(q):
        assert threading.get_ident() == owner
        return {'rows': [[4]]}
    monkeypatch.setattr(coordinator.database, 'answer', database)
    result = coordinator.answer('mixed')
    assert all(t['execution'] == 'sequential' for t in result['trace'])
    assert result['trace'][1]['result']['result'] == 4


def test_chat_ui_and_static_assets():
    with TestClient(app) as client:
        page = client.get('/')
        assert page.status_code == 200
        assert 'text/html' in page.headers['content-type']
        assert 'dir="rtl"' in page.text
        for path in ('/static/chat.js', '/static/style.css'):
            assert client.get(path).status_code == 200
        assert client.get('/docs').status_code == 200
        assert client.get('/static/../.env').status_code == 404


def test_request_timings_include_parallel_tools_and_are_isolated(monkeypatch):
    from app.timing import span
    monkeypatch.delenv('ROUTER_MODEL', raising=False)
    monkeypatch.setenv('PARALLEL_RETRIEVAL','true')
    first=call('database_agent', {'question':'balance'}, 'db')
    first['tool_calls']+=call('documents_agent', {'question':'minimum'}, 'docs')['tool_calls']
    coordinator=Coordinator(ScriptedModel([first, {'content':'done'}, {'content':'next request'}]))
    def documents(q, **kwargs):
        assert kwargs['evidence_only'] is True
        with span('test_document_fetch'):
            return {'answer':None, 'sources':[dict(source='accounts.pdf',page=1,text='1000000 IRR')]}
    def database(q):
        with span('test_database_fetch'):
            return {'rows':[[12200000]]}
    monkeypatch.setattr(coordinator.documents,'answer',documents)
    monkeypatch.setattr(coordinator.database,'answer',database)
    result=coordinator.answer('mixed')
    events=result['timings']['events']
    assert {'coordinator_chat','tool_call','test_database_fetch','test_document_fetch'} <= {e['stage'] for e in events}
    assert all(e['duration_ms']>=0 and e['start_ms']>=0 for e in events)
    assert result['timings']['total_ms']>=0
    second=coordinator.answer('another question')
    assert all(e['stage']=='coordinator_chat' for e in second['timings']['events'])


def test_mixed_request_skips_document_generation_across_separate_rounds(monkeypatch):
    from app.router import ROUTES
    monkeypatch.setenv('ROUTER_MODEL','typesafe/jev-1.14')
    routes=iter(['both','documents','final'])
    class Model:
        def post(self,*args,**kwargs):
            route=next(routes)
            return {'answers':{'route':{'type':'choice','choice':route,
                    'probabilities':{r:float(r==route) for r in ROUTES}}}}
        def chat(self,messages,tools=None,**kwargs):
            if kwargs.get('tool_choice')=='none':return {'content':'answer'}
            names={t['function']['name'] for t in tools or []}
            if 'database_agent' in names:return call('database_agent',{'question':'balance'})
            return call('documents_agent',{'question':'minimum'},'2')
    coordinator=Coordinator(Model())
    monkeypatch.setattr(coordinator.database,'answer',lambda q, **kwargs:{'rows':[[12200000]]})
    def evidence(q,**kwargs):
        assert kwargs['evidence_only'] is True
        return {'answer':None,'sources':[{'source':'accounts.pdf','page':1,'text':'1000000 IRR'}]}
    monkeypatch.setattr(coordinator.documents,'answer',evidence)
    result=coordinator.answer('Compare balance and minimum from accounts.pdf')
    assert len(result['trace'])==2
    assert result['trace'][1]['result']['answer'] is None


@pytest.mark.parametrize('sources', [[], [{'source':'accounts.pdf','page':1,'text':'Identity document and verified mobile number.'}]])
def test_documents_only_route_returns_evidence_without_intermediate_generation(monkeypatch, sources):
    from app.router import ROUTES
    monkeypatch.setenv('ROUTER_MODEL','typesafe/jev-1.14')
    routes=iter(['documents','final'])
    seen=[]
    class Model:
        def post(self,*args,**kwargs):
            route=next(routes)
            return {'answers':{'route':{'type':'choice','choice':route,
                    'probabilities':{r:float(r==route) for r in ROUTES}}}}
        def chat(self,messages,tools=None,**kwargs):
            if kwargs.get('tool_choice')=='none':
                result=json.loads([m for m in messages if m['role']=='tool'][-1]['content'])
                assert result['sources']==sources and result['answer'] is None
                return {'content':'Answer with source' if sources else 'Insufficient evidence'}
            return call('documents_agent',{'question':'opening requirements'},'docs')
    coordinator=Coordinator(Model())
    def evidence(question,**kwargs):
        seen.append(kwargs)
        return {'answer':None,'sources':sources}
    monkeypatch.setattr(coordinator.documents,'answer',evidence)
    result=coordinator.answer('Requirements from accounts.pdf')
    assert seen==[{'evidence_only':True}]
    assert result['trace'][0]['result']['sources']==sources
    assert result['answer']==('Answer with source' if sources else 'Insufficient evidence')
