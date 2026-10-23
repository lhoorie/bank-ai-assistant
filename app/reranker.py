"""Dedicated remote reranking through the OpenRouter-compatible /rerank API."""
import math
import os
from app.model import Model, ModelError

class RemoteReranker:
    def __init__(self, client=None):
        self.model_name = os.getenv('RERANK_MODEL', 'qwen/qwen3-reranker-8b')
        self.client = client or Model()

    def score(self, question, passages):
        if not passages:
            return []
        try:
            response = self.client.post('/rerank', {
                'model': self.model_name, 'query': question,
                'documents': passages, 'top_n': len(passages)})
            rows = response['results']
            scores = [None] * len(passages)
            for row in rows:
                index, score = row['index'], row['relevance_score']
                if type(index) is not int or not 0 <= index < len(passages) or scores[index] is not None:
                    raise ValueError('Invalid or duplicate document index')
                if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
                    raise ValueError('Invalid relevance score')
                scores[index] = score
            if any(score is None for score in scores):
                raise ValueError('Missing document scores')
            return scores
        except (KeyError, TypeError, ValueError) as exc:
            raise ModelError('Reranker returned an invalid response.') from exc
