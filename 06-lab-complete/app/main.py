import os
import time
import signal
import logging
import json
import redis
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Security, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import uvicorn

from app.config import settings
from app.auth import verify_api_key
from app.rate_limiter import check_rate_limit
from app.cost_guard import check_budget, record_cost, get_current_cost, PRICE_PER_1K_INPUT_TOKENS, PRICE_PER_1K_OUTPUT_TOKENS
from app.agent_runner import run_agent

# Logging — JSON structured
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0

# Connect to Redis for conversation history
try:
    _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    _redis_client.ping()
    USE_REDIS = True
except Exception:
    USE_REDIS = False
    _memory_history = {}

def load_history(user_id: str) -> list:
    if USE_REDIS:
        try:
            data = _redis_client.get(f"history:{user_id}")
            return json.loads(data) if data else []
        except Exception:
            return []
    return _memory_history.get(user_id, [])

def save_history(user_id: str, history: list):
    if USE_REDIS:
        try:
            _redis_client.setex(f"history:{user_id}", 3600, json.dumps(history))
        except Exception:
            pass
    else:
        _memory_history[user_id] = history

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }))
    time.sleep(0.1)  # simulate init
    _is_ready = True
    logger.info(json.dumps({"event": "ready"}))
    yield
    _is_ready = False
    logger.info(json.dumps({"event": "shutdown"}))

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

# Cấu hình phục vụ các tệp tĩnh static
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if "server" in response.headers:
            del response.headers["server"]
        duration = round((time.time() - start) * 1000, 1)
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": duration,
        }))
        return response
    except Exception as e:
        _error_count += 1
        raise

class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="Your question for the agent")
    user_id: str | None = Field(default="default_user", description="Unique user identifier")

class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    timestamp: str
    trace: list | None = None
    metrics: dict | None = None

@app.get("/", response_class=HTMLResponse, tags=["Info"])
def root():
    """Trả về giao diện chat HTML/CSS thay vì JSON raw"""
    try:
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading index.html: {str(e)}</h1>")

@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    _key: str = Depends(verify_api_key),
):
    user_id = body.user_id or "default_user"
    
    # 1. Rate Limit
    check_rate_limit(user_id)

    # 2. Cost Guard Check
    input_tokens = len(body.question.split()) * 2
    estimated_cost = (input_tokens / 1000) * PRICE_PER_1K_INPUT_TOKENS
    check_budget(user_id, estimated_cost)

    logger.info(json.dumps({
        "event": "agent_call",
        "user_id": user_id,
        "q_len": len(body.question),
        "client": str(request.client.host) if request.client else "unknown",
    }))

    # 3. Chạy ReAct Agent (chạy thật hoặc chạy giả lập mock offline)
    result = run_agent(body.question)
    answer = result.get("final_answer", "")

    # 4. Save history
    history = load_history(user_id)
    history.append({"role": "user", "content": body.question})
    history.append({"role": "assistant", "content": answer})
    if len(history) > 20:
        history = history[-20:]
    save_history(user_id, history)

    # 5. Record final cost
    output_tokens = len(answer.split()) * 2
    actual_cost = estimated_cost + (output_tokens / 1000) * PRICE_PER_1K_OUTPUT_TOKENS
    record_cost(user_id, actual_cost)

    return AskResponse(
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
        trace=result.get("trace", []),
        metrics=result.get("metrics", {"steps": 0, "latency_ms": 0})
    )

@app.get("/health", tags=["Operations"])
def health():
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "checks": {"llm": "mock" if not settings.openai_api_key else "openai"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/ready", tags=["Operations"])
def ready():
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    if USE_REDIS:
        try:
            _redis_client.ping()
        except Exception:
            raise HTTPException(503, "Redis connection failed")
    return {"ready": True}

@app.get("/metrics", tags=["Operations"])
def metrics(_key: str = Depends(verify_api_key), user_id: str = "default_user"):
    cost = get_current_cost(user_id)
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "daily_cost_usd": cost,
    }

def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "signal", "signum": signum}))

signal.signal(signal.SIGTERM, _handle_signal)

if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} on {settings.host}:{settings.port}")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
