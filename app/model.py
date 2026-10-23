from app.timing import timed
import json
import os
import logging
from app.logging_utils import event
from urllib.request import Request, urlopen
from urllib.error import URLError

log = logging.getLogger(__name__)

class ModelError(Exception):
    pass

def validate_tool_calls(message, fields, *, max_calls):
    """Reject malformed provider calls before routing or executing any tool."""
    try:
        if not isinstance(message, dict):
            raise ValueError()
        calls = message.get('tool_calls')
        if calls is None:
            calls = []
        if not isinstance(calls, list) or len(calls) > max_calls:
            raise ValueError()
        ids = set()
        for call in calls:
            if call['type'] != 'function':
                raise ValueError()
            ident = call['id']
            if not isinstance(ident, str) or not ident.strip() or ident in ids:
                raise ValueError()
            ids.add(ident)
            function = call['function']
            field = fields[function['name']]
            args = json.loads(function['arguments'])
            if (not isinstance(args, dict) or set(args) != {field}
                    or not isinstance(args[field], str) or not args[field].strip()):
                raise ValueError()
        return calls
    except (KeyError, TypeError, ValueError) as exc:
        raise ModelError('Invalid tool call returned by model provider.') from exc

class Model:
    @timed('provider_request', metadata=lambda self, path, payload, **kw: {'endpoint':path, 'model':payload.get('model')})
    def post(self, path, payload, *, base_url=None):
        base = (base_url or os.getenv('MODEL_BASE_URL', '')).rstrip('/')
        key = os.getenv('MODEL_API_KEY', '')
        if not base or not key:
            raise ModelError('Set MODEL_BASE_URL and MODEL_API_KEY before asking questions.')
        req = Request(base + path, data=json.dumps(payload).encode(), headers={
            'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
        try:
            with urlopen(req, timeout=45) as response:
                return json.load(response)
        except (URLError, TimeoutError, ValueError) as exc:
            event(log, 'provider_request_failed', level=logging.WARNING, endpoint=path,
                  model=payload.get('model'), http_status=getattr(exc, 'code', None),
                  error_type=type(exc).__name__)
            raise ModelError('Model provider request failed; check configuration or retry.') from exc

    def chat(self, messages, tools=None, *, tool_choice='auto'):
        payload = dict(model=os.getenv('CHAT_MODEL', ''), messages=messages, temperature=0,
                       max_tokens=int(os.getenv('CHAT_MAX_TOKENS', '4096')))
        if tools:
            payload.update(tools=tools, tool_choice=tool_choice)
            # Alibaba Qwen rejects forced tool calls while thinking is enabled.
            if tool_choice == 'required' and payload['model'].startswith('qwen/'):
                payload['reasoning'] = {'enabled': False}
        try:
            message = self.post('/chat/completions', payload)['choices'][0]['message']
            if not isinstance(message, dict):
                raise TypeError()
            return message
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelError('Unexpected chat response from provider.') from exc

    def embed(self, texts):
        try:
            rows = self.post('/embeddings', dict(
                model=os.getenv('EMBEDDING_MODEL', ''), input=texts))['data']
            indices = [r['index'] for r in rows]
            if (any(type(i) is not int for i in indices)
                    or sorted(indices) != list(range(len(texts)))):
                raise ValueError()
            vectors = [r['embedding'] for r in sorted(rows, key=lambda r: r['index'])]
            if len(vectors) != len(texts) or not vectors or not vectors[0]:
                raise ValueError()
            import math
            if any(len(v) != len(vectors[0]) or not all(math.isfinite(x) for x in v) for v in vectors):
                raise ValueError()
            return vectors
        except (KeyError, TypeError, ValueError) as exc:
            raise ModelError('Unexpected embedding response from provider.') from exc
