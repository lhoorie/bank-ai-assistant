"""Optional LangSmith instrumentation. No credentials or vector arrays in traces."""
import os
from functools import lru_cache
from langsmith import Client, traceable, tracing_context, get_current_run_tree

SECRET_FIELDS = {'api_key','authorization','password','token','headers','secret',
                 'model_api_key','langsmith_api_key','milvus_token'}
VECTOR_FIELDS = {'vector','vectors','embedding','embeddings'}


def sanitize(value, depth=0):
    if depth>12: return '[nested data omitted]'
    if isinstance(value,dict):
        return {str(k): ('[redacted]' if str(k).lower() in SECRET_FIELDS
                        else '[vector omitted]' if str(k).lower() in VECTOR_FIELDS
                        else sanitize(v,depth+1))
                for k,v in value.items() if str(k) not in ('self','cls')}
    if isinstance(value,(list,tuple)):
        if len(value)>16 and all(type(v) in (int,float) for v in value):
            return {'vector_dimensions':len(value)}
        return [sanitize(v,depth+1) for v in value[:100]]
    if isinstance(value,str):
        for name in ('MODEL_API_KEY','LANGSMITH_API_KEY','MILVUS_TOKEN'):
            secret=os.getenv(name,'')
            if secret:value=value.replace(secret,'[redacted]')
        return value[:20000]
    if value is None or isinstance(value,(bool,int,float)):return value
    # LangChain Documents retain evidence, but not arbitrary client object internals.
    if hasattr(value,'page_content') and hasattr(value,'metadata'):
        return {'text':sanitize(value.page_content,depth+1),'metadata':sanitize(value.metadata,depth+1)}
    return f'[{type(value).__name__}]'


def tracing_enabled():
    return os.getenv('LANGSMITH_TRACING','false').lower()=='true' and bool(os.getenv('LANGSMITH_API_KEY','').strip())


def trace_inputs(value):
    return {} if os.getenv('LANGSMITH_HIDE_INPUTS','false').lower()=='true' else sanitize(value)


def trace_outputs(value):
    return {} if os.getenv('LANGSMITH_HIDE_OUTPUTS','false').lower()=='true' else sanitize(value)


@lru_cache(maxsize=2)
def tracing_client(endpoint, key):
    return Client(api_url=endpoint,api_key=key,hide_inputs=trace_inputs,hide_outputs=trace_outputs)


def instrument(function, name):
    types={'tool_call':'tool','database_agent':'tool','sql_execution':'tool',
           'retriever':'retriever','milvus_search':'retriever'}
    return traceable(name=name,run_type=types.get(name,'chain'),
                     process_inputs=sanitize,process_outputs=sanitize)(function)


def request_context():
    enabled=tracing_enabled()
    options={'enabled':enabled}
    if enabled:
        options.update(client=tracing_client(os.getenv('LANGSMITH_ENDPOINT','https://api.smith.langchain.com'),
                                            os.environ['LANGSMITH_API_KEY']),
                       project_name=os.getenv('LANGSMITH_PROJECT','adan-banking'))
    return tracing_context(**options)


def current_trace_id():
    tree=get_current_run_tree()
    return str(tree.trace_id) if tree is not None else None
