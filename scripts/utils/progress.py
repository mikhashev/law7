"""
Progress tracking utilities.
Based on ygbis patterns for progress tracking.
"""
import logging
import sys
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class ProgressTracker:
    """
    Simple progress tracker for long-running operations.

    Can be extended to use tqdm if needed.
    """

    def __init__(self, enabled: bool = True):
        """
        Initialize progress tracker.

        Args:
            enabled: Whether progress tracking is enabled
        """
        self.enabled = enabled
        self.start_time: Optional[datetime] = None
        self.current_item = 0
        self.total_items = 0

    def start(self, total: int):
        """
        Start tracking progress.

        Args:
            total: Total number of items to process
        """
        if not self.enabled:
            return

        self.total_items = total
        self.current_item = 0
        self.start_time = datetime.now()

        logger.info(f"Starting processing of {total} items...")

    def update(self, increment: int = 1):
        """
        Update progress.

        Args:
            increment: Number of items completed since last update
        """
        if not self.enabled:
            return

        self.current_item += increment

        # Log progress at milestones
        if self.total_items > 0:
            percentage = (self.current_item / self.total_items) * 100

            # Log at 0%, 25%, 50%, 75%, 100%
            if self.current_item == 0 or self.current_item == self.total_items:
                self._log_progress(percentage)

            elif percentage >= 75 and self.current_item - increment < self.total_items * 0.75:
                self._log_progress(percentage)

            elif percentage >= 50 and self.current_item - increment < self.total_items * 0.50:
                self._log_progress(percentage)

            elif percentage >= 25 and self.current_item - increment < self.total_items * 0.25:
                self._log_progress(percentage)

    def _log_progress(self, percentage: float):
        """Log progress at percentage milestone."""
        elapsed = self._get_elapsed_seconds()
        logger.info(
            f"  Progress: {self.current_item}/{self.total_items} "
            f"({percentage:.1f}%) - {elapsed:.1f}s elapsed"
        )

    def finish(self):
        """Finish tracking progress."""
        if not self.enabled:
            return

        elapsed = self._get_elapsed_seconds()
        logger.info(
            f"Completed {self.current_item}/{self.total_items} items "
            f"in {elapsed:.1f}s"
        )

    def _get_elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        if self.start_time:
            return (datetime.now() - self.start_time).total_seconds()
        return 0.0

    def get_estimated_time_remaining(self) -> float:
        """
        Estimate time remaining based on current progress.

        Returns:
            Estimated seconds remaining
        """
        if not self.enabled or self.current_item == 0:
            return 0.0

        elapsed = self._get_elapsed_seconds()
        items_per_second = self.current_item / elapsed if elapsed > 0 else 0
        items_remaining = self.total_items - self.current_item

        if items_per_second > 0:
            return items_remaining / items_per_second

        return 0.0


class SimpleProgressBar:
    """
    Simple console progress bar.

    Example:
        >>> bar = SimpleProgressBar(total=100)
        >>> for i in range(100):
        ...     bar.update()
        >>> bar.finish()
    """

    def __init__(self, total: int, width: int = 50):
        """
        Initialize progress bar.

        Args:
            total: Total number of items
            width: Width of progress bar in characters
        """
        self.total = total
        self.width = width
        self.current = 0
        self.start_time = datetime.now()

    def update(self, increment: int = 1):
        """
        Update progress bar.

        Args:
            increment: Number of items completed since last update
        """
        self.current += increment
        self._draw()

    def _draw(self):
        """Draw the progress bar."""
        if self.total == 0:
            return

        percentage = self.current / self.total
        filled = int(self.width * percentage)
        bar = "=" * filled + ">" * min(1, self.width - filled) + " " * (self.width - filled - 1)

        elapsed = self._get_elapsed_seconds()
        eta = self._get_eta()

        sys.stdout.write(
            f"\r[{bar}] {percentage*100:.1f}% "
            f"({self.current}/{self.total}) "
            f"Elapsed: {self._format_time(elapsed)} "
            f"ETA: {self._format_time(eta)}"
        )
        sys.stdout.flush()

    def finish(self):
        """Finish progress bar and add newline."""
        self._draw()
        sys.stdout.write("\n")
        sys.stdout.flush()

    def _get_elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        return (datetime.now() - self.start_time).total_seconds()

    def _get_eta(self) -> float:
        """Get estimated time remaining in seconds."""
        if self.current == 0:
            return 0.0

        elapsed = self._get_elapsed_seconds()
        items_per_second = self.current / elapsed if elapsed > 0 else 0
        items_remaining = self.total - self.current

        if items_per_second > 0:
            return items_remaining / items_per_second

        return 0.0

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds as HH:MM:SS."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
