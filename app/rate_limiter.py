import time
import redis
from fastapi import HTTPException, status
from app.config import settings

# Initialize Redis connection
try:
    _redis = redis.from_url(settings.redis_url, decode_responses=True)
    _redis.ping()
    USE_REDIS = True
except Exception:
    USE_REDIS = False
    from collections import defaultdict, deque
    _memory_windows = defaultdict(deque)

def check_rate_limit(user_id: str):
    limit = settings.rate_limit_per_minute
    window_seconds = 60
    now = time.time()
    
    if USE_REDIS:
        key = f"rate_limit:{user_id}"
        pipe = _redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - window_seconds)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, window_seconds + 5)
        res = pipe.execute()
        current_requests = res[1]
        
        if current_requests >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {limit} req/min",
                headers={"Retry-After": "60"},
            )
    else:
        window = _memory_windows[user_id]
        while window and window[0] < now - window_seconds:
            window.popleft()
        if len(window) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {limit} req/min",
                headers={"Retry-After": "60"},
            )
        window.append(now)
