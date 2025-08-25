import time
import logging
from functools import wraps
from typing import Callable, Any, List, Type
from django.utils import timezone

logger = logging.getLogger(__name__)


def retry_on_exceptions(
    exceptions: List[Type[Exception]], 
    max_retries: int = 3, 
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 60.0
):
    """
    Decorator to retry function calls on specific exceptions with exponential backoff
    
    Args:
        exceptions: List of exception types to retry on
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier for delay
        max_delay: Maximum delay between retries
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except tuple(exceptions) as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(
                            f"Function {func.__name__} failed after {max_retries} retries. "
                            f"Last error: {str(e)}"
                        )
                        raise
                    
                    logger.warning(
                        f"Function {func.__name__} failed on attempt {attempt + 1}/{max_retries + 1}. "
                        f"Error: {str(e)}. Retrying in {current_delay}s..."
                    )
                    
                    time.sleep(current_delay)
                    current_delay = min(current_delay * backoff, max_delay)
                except Exception as e:
                    # Don't retry on unexpected exceptions
                    logger.error(f"Function {func.__name__} failed with unexpected error: {str(e)}")
                    raise
            
            # This should never be reached, but just in case
            raise last_exception
        
        return wrapper
    return decorator


class APIRateLimitHandler:
    """Handle API rate limiting with smart delays"""
    
    def __init__(self):
        self.last_request_time = None
        self.requests_in_minute = []
        self.requests_in_day = []
    
    def wait_if_rate_limited(self, requests_per_minute: int = 60, requests_per_day: int = 5000):
        """Wait if we're approaching rate limits"""
        now = timezone.now()
        
        # Clean up old request timestamps
        minute_ago = now - timezone.timedelta(minutes=1)
        day_ago = now - timezone.timedelta(days=1)
        
        self.requests_in_minute = [t for t in self.requests_in_minute if t > minute_ago]
        self.requests_in_day = [t for t in self.requests_in_day if t > day_ago]
        
        # Check if we need to wait
        if len(self.requests_in_minute) >= requests_per_minute:
            # Wait until the oldest request in this minute expires
            wait_time = (self.requests_in_minute[0] + timezone.timedelta(minutes=1) - now).total_seconds()
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.2f}s...")
                time.sleep(wait_time)
        
        # Track this request
        self.requests_in_minute.append(now)
        self.requests_in_day.append(now)


class IntegrationError(Exception):
    """Base exception for integration errors"""
    pass


class TokenRefreshError(IntegrationError):
    """Token refresh failed"""
    pass


class APIConnectionError(IntegrationError):
    """API connection failed"""
    pass


class APIRateLimitError(IntegrationError):
    """API rate limit exceeded"""
    pass


class DataValidationError(IntegrationError):
    """Data validation failed"""
    pass