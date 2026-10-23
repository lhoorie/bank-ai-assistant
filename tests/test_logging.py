import json
import logging
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from fastapi.testclient import TestClient
from urllib.error import HTTPError
from app.api import app
from app.logging_utils import event
from app.model import Model, ModelError


def app_events(caplog):
    return [json.loads(r.message) for r in caplog.records
            if r.name.startswith('app.') and r.message.startswith('{')]


def test_request_ids_and_payload_is_not_logged(caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    with TestClient(app) as client:
        def answer(question):
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(copy_context().run, event, logging.getLogger('app.test'),
                            'worker_done', tool='documents_agent').result()
            return {'answer':'ok','trace':[]}
        monkeypatch.setattr(app.state.coordinator,'answer',answer)
        response=client.post('/ask',json={'question':'private_customer_data secret_api_key'})
        request_id=response.json()['request_id']
        assert response.headers['X-Request-ID']==request_id
        events=app_events(caplog)
        relevant=[e for e in events if e['event'] in ('request_started','worker_done','request_finished')]
        assert len(relevant)==3
        assert all(e['request_id']==request_id for e in relevant)
        assert relevant[-1]['status']==200 and relevant[-1]['duration_ms']>=0
        assert 'private_customer_data' not in caplog.text
        assert 'secret_api_key' not in caplog.text


def test_model_failure_is_correlated_and_request_context_is_reset(caplog,monkeypatch):
    caplog.set_level(logging.INFO)
    with TestClient(app) as client:
        def broken(question):raise ModelError('private diagnostic')
        monkeypatch.setattr(app.state.coordinator,'answer',broken)
        response=client.post('/ask',json={'question':'test'})
        assert response.status_code==502
        events=app_events(caplog)
        request_id=response.headers['X-Request-ID']
        assert any(e['event']=='model_error' and e['request_id']==request_id for e in events)
        assert any(e['event']=='request_finished' and e['status']==502 for e in events)
        assert 'private diagnostic' not in caplog.text
    event(logging.getLogger('app.test'),'after_request')
    assert app_events(caplog)[-1]['request_id']=='-'


def test_provider_error_logs_status_without_headers_or_body(caplog,monkeypatch):
    caplog.set_level(logging.WARNING)
    monkeypatch.setenv('MODEL_BASE_URL','https://example.invalid/v1')
    monkeypatch.setenv('MODEL_API_KEY','private-key')
    def fail(*args,**kwargs):
        raise HTTPError('https://example.invalid',402,'private-provider-message',{},None)
    monkeypatch.setattr('app.model.urlopen',fail)
    try:Model().post('/chat/completions',{'model':'test','messages':[{'content':'private question'}]})
    except ModelError:pass
    else:raise AssertionError('Expected failure')
    result=[e for e in app_events(caplog) if e['event']=='provider_request_failed'][0]
    assert result['http_status']==402
    assert result['endpoint']=='/chat/completions'
    for text in ('private-key','private-provider-message','private question'):
        assert text not in caplog.text
