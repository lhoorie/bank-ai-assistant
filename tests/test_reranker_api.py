from unittest.mock import Mock
import pytest
from app.reranker import RemoteReranker
from app.model import ModelError

def test_maps_ranked_response_back_to_original_order():
    client = Mock()
    client.post.return_value = {'results': [
        {'index': 1, 'relevance_score': .95}, {'index': 0, 'relevance_score': .2}]}
    reranker = RemoteReranker(client)
    assert reranker.score('question', ['first', 'second']) == [.2, .95]
    client.post.assert_called_once_with('/rerank', {
        'model': reranker.model_name, 'query': 'question',
        'documents': ['first', 'second'], 'top_n': 2})

@pytest.mark.parametrize('response', [
    {}, {'results': []},
    {'results': [{'index': 5, 'relevance_score': .9}]},
    {'results': [{'index': 0, 'relevance_score': .9}, {'index': 0, 'relevance_score': .8}]},
    {'results': [{'index': 0, 'relevance_score': float('nan')}]},
    {'results': [{'index': 0, 'relevance_score': True}]},
])
def test_rejects_invalid_response(response):
    client = Mock()
    client.post.return_value = response
    with pytest.raises(ModelError):
        RemoteReranker(client).score('question', ['passage'])

def test_empty_input_makes_no_request():
    client = Mock()
    assert RemoteReranker(client).score('question', []) == []
    client.post.assert_not_called()

def test_provider_failure_is_propagated():
    client = Mock()
    client.post.side_effect = ModelError('Provider unavailable')
    with pytest.raises(ModelError, match='Provider unavailable'):
        RemoteReranker(client).score('question', ['passage'])
