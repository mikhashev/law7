"""
Retry utilities with exponential backoff pattern.
Based on yandex-games-bi-suite retry pattern.
"""
import logging
import time
from typing import Callable, TypeVar, Optional

from core.config import BACKOFF_BASE_DELAY, BACKOFF_MAX_DELAY, BACKOFF_MULTIPLIER

logger = logging.getLogger(__name__)

T = TypeVar("T")


def calculate_backoff_delay(attempt: int) -> int:
    """
    Calculate exponential backoff delay (ygbis pattern).

    Args:
        attempt: The retry attempt number (0-indexed)

    Returns:
        Delay in seconds
    """
    delay = min(BACKOFF_BASE_DELAY * (BACKOFF_MULTIPLIER ** attempt), BACKOFF_MAX_DELAY)
    return int(delay)


def fetch_with_retry(
    fetch_fn: Callable[[], T],
    max_retries: int = 3,
    operation_name: str = "operation",
) -> Optional[T]:
    """
    Execute a function with exponential backoff retry logic.

    Args:
        fetch_fn: Function to execute (should return data or raise exception)
        max_retries: Maximum number of retry attempts
        operation_name: Name of the operation for logging

    Returns:
        Result of fetch_fn() or None if all retries fail

    Raises:
        Exception: Re-raises the last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            return fetch_fn()
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = calculate_backoff_delay(attempt)
                logger.warning(
                    f"{operation_name} failed (attempt {attempt + 1}/{max_retries}): {e}"
                )
                logger.info(f"Exponential backoff: {delay}s...")
                time.sleep(delay)
            else:
                logger.error(
                    f"{operation_name} failed after {max_retries} attempts: {e}"
                )

    if last_exception:
        raise last_exception

    return None


class RetryHandler:
    """
    Context manager for retry operations with logging.

    Usage:
        with RetryHandler("fetch_documents") as retry:
            retry.execute(lambda: requests.get(url))
    """

    def __init__(self, operation_name: str, max_retries: int = 3):
        """
        Initialize retry handler.

        Args:
            operation_name: Name of the operation for logging
            max_retries: Maximum number of retry attempts
        """
        self.operation_name = operation_name
        self.max_retries = max_retries
        self.attempt_count = 0

    def execute(self, fetch_fn: Callable[[], T]) -> Optional[T]:
        """
        Execute function with retry logic.

        Args:
            fetch_fn: Function to execute

        Returns:
            Result of fetch_fn() or None if all retries fail
        """
        return fetch_with_retry(
            fetch_fn,
            max_retries=self.max_retries,
            operation_name=self.operation_name,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
