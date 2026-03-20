import asyncio
import logging
from functools import wraps

logger = logging.getLogger(__name__)


def async_retry(max_attempts: int = 3, base_delay: float = 1.0, backoff: float = 2.0):
    """Exponential backoff retry decorator for async functions."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            delay = base_delay
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    if attempt == max_attempts - 1:
                        raise
                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_attempts} failed: {exc}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                    delay *= backoff
        return wrapper
    return decorator
