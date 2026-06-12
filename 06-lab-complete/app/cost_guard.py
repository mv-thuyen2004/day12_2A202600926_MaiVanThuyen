import time
import redis
from datetime import datetime
from fastapi import HTTPException, status
from app.config import settings

# Price per 1k tokens (GPT-4o-mini rates)
PRICE_PER_1K_INPUT_TOKENS = 0.00015
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006

try:
    _redis = redis.from_url(settings.redis_url, decode_responses=True)
    _redis.ping()
    USE_REDIS = True
except Exception:
    USE_REDIS = False
    _memory_cost = {}

def get_current_cost(user_id: str) -> float:
    month_key = datetime.now().strftime("%Y-%m")
    key = f"budget:{user_id}:{month_key}"
    if USE_REDIS:
        val = _redis.get(key)
        return float(val) if val else 0.0
    else:
        return _memory_cost.get(key, 0.0)

def check_budget(user_id: str, estimated_cost: float = 0.0):
    limit = settings.daily_budget_usd
    current = get_current_cost(user_id)
    if current + estimated_cost > limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "Budget exceeded",
                "used_usd": current,
                "budget_usd": limit,
            }
        )

def record_cost(user_id: str, cost: float):
    month_key = datetime.now().strftime("%Y-%m")
    key = f"budget:{user_id}:{month_key}"
    if USE_REDIS:
        _redis.incrbyfloat(key, cost)
        _redis.expire(key, 32 * 24 * 3600)  # 32 days
    else:
        _memory_cost[key] = _memory_cost.get(key, 0.0) + cost
