import time
import os
import redis


RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))  
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60")) 


class RateLimiter:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    # Check if user is within rate limits
    def is_allowed(self, user_id: str, rate_limit_counter, limit: int = RATE_LIMIT_REQUESTS, window: int = RATE_LIMIT_WINDOW) -> bool:
        key = f"rate_limit:{user_id}"
        current_time = int(time.time())

        pipeline = self.redis.pipeline()     
        pipeline.zremrangebyscore(key, 0, current_time - window)
        pipeline.zcard(key)
        pipeline.zadd(key, {str(current_time): current_time})
        pipeline.expire(key, window)
        
        results = pipeline.execute()
        current_requests = results[1]
        
        if current_requests >= limit:
            rate_limit_counter.labels(user=user_id).inc()
            return False
        
        return True
