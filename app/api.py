import logging
import uuid
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from app.agents import Coordinator
from app.model import Model, ModelError
from app.seed import seed
from app.explorer import router as explorer_router
from app.evaluation import router as evaluation_router
from app.logging_utils import event, request_id_context

logging.basicConfig(level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper(), logging.INFO),
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
log = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app):
    event(log, 'service_starting')
    seed()
    app.state.coordinator = Coordinator(Model())
    event(log, 'service_ready')
    try:
        yield
    finally:
        event(log, 'service_stopping')

app = FastAPI(title='Adan Demo Banking Assistant', version='0.2.0', lifespan=lifespan)
STATIC = Path(__file__).resolve().parent / 'static'
app.mount('/static', StaticFiles(directory=STATIC), name='static')
app.include_router(explorer_router)
app.include_router(evaluation_router)

@app.middleware('http')
async def log_ask_request(request: Request, call_next):
    if request.url.path != '/ask':
        return await call_next(request)
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    token = request_id_context.set(request_id)
    start = time.perf_counter()
    status = 500
    event(log, 'request_started', method=request.method, path='/ask')
    try:
        try:
            response = await call_next(request)
        except Exception as exc:
            response = await unexpected_error(request, exc)
        status = response.status_code
        response.headers['X-Request-ID'] = request_id
        return response
    finally:
        event(log, 'request_finished', level=logging.WARNING if status >= 400 else logging.INFO,
              status=status, duration_ms=round((time.perf_counter()-start)*1000, 1))
        request_id_context.reset(token)


@app.get('/evaluation', include_in_schema=False)
def evaluation_page():
    return FileResponse(STATIC / 'evaluation.html')

@app.get('/explorer', include_in_schema=False)
def explorer_page():
    return FileResponse(STATIC / 'explorer.html')

@app.get('/', include_in_schema=False)
def home():
    return FileResponse(STATIC / 'index.html')

class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2000)

@app.exception_handler(ModelError)
async def model_error(request: Request, exc: ModelError):
    event(log, 'model_error', level=logging.WARNING, error_type=type(exc).__name__)
    return JSONResponse(status_code=502, content={'error': str(exc)})

@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    event(log, 'unexpected_error', level=logging.ERROR, error_type=type(exc).__name__)
    return JSONResponse(status_code=500, content={'error': 'Internal processing error; see server logs.'})

@app.get('/health')
def health():
    return {'status': 'ok', 'note': 'Liveness only; does not validate model credentials.'}

@app.post('/ask')
def ask(body: Question, request: Request):
    if not body.question.strip():
        return JSONResponse(status_code=422, content={'error': 'Question cannot be blank.'})
    return {'request_id': request.state.request_id, **request.app.state.coordinator.answer(body.question)}
