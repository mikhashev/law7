"""
Law7 Unified Logging Configuration

Provides consistent logging setup across all Law7 modules.
Configurable via environment variables and supports multiple outputs.
"""
import logging
import sys
from pathlib import Path
from typing import Optional

# Default configuration
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LOG_DIR = Path("logs")

# Environment variable names
ENV_LOG_LEVEL = "LAW7_LOG_LEVEL"
ENV_LOG_FORMAT = "LAW7_LOG_FORMAT"
ENV_LOG_FILE = "LAW7_LOG_FILE"
ENV_LOG_DIR = "LAW7_LOG_DIR"


def setup_logging(
    name: str,
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    log_dir: Optional[Path] = None,
    console: bool = True,
    format_string: Optional[str] = None,
    date_format: Optional[str] = None,
) -> logging.Logger:
    """
    Set up unified logging with consistent format.

    Args:
        name: Logger name (usually __name__ from calling module)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
               Defaults to LAW7_LOG_LEVEL env var or INFO
        log_file: Optional log file name (created in log_dir)
        log_dir: Directory for log files
                Defaults to LAW7_LOG_DIR env var or "./logs"
        console: Whether to output to console (default: True)
        format_string: Custom format string
        date_format: Custom date format string

    Returns:
        Configured logger instance

    Environment Variables:
        LAW7_LOG_LEVEL: Override default log level
        LAW7_LOG_FORMAT: Override default format string
        LAW7_LOG_FILE: Default log file name
        LAW7_LOG_DIR: Override default log directory

    Examples:
        >>> # Basic usage - console only
        >>> logger = setup_logging(__name__)

        >>> # With file logging
        >>> logger = setup_logging(__name__, log_file="app.log")

        >>> # Debug level with custom directory
        >>> logger = setup_logging(__name__, level="DEBUG", log_dir=Path("./var/log"))

        >>> # Console only, WARNING level
        >>> logger = setup_logging(__name__, level="WARNING", console=True, log_file=None)
    """
    # Get log level from env var or parameter
    if level is None:
        level = __import__("os").getenv(ENV_LOG_LEVEL, DEFAULT_LOG_LEVEL)

    # Get format from env var or parameter
    if format_string is None:
        format_string = __import__("os").getenv(ENV_LOG_FORMAT, DEFAULT_LOG_FORMAT)

    # Get date format
    if date_format is None:
        date_format = DEFAULT_DATE_FORMAT

    # Get log directory
    if log_dir is None:
        log_dir_str = __import__("os").getenv(ENV_LOG_DIR)
        log_dir = Path(log_dir_str) if log_dir_str else DEFAULT_LOG_DIR

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(format_string, datefmt=date_format)

    # Add console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(getattr(logging, level.upper()))
        logger.addHandler(console_handler)

    # Add file handler if log_file is specified
    if log_file:
        # Create log directory if it doesn't exist
        log_dir.mkdir(parents=True, exist_ok=True)

        log_path = log_dir / log_file
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(getattr(logging, level.upper()))
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with standard Law7 configuration.

    Shortcut for setup_logging with defaults.

    Args:
        name: Logger name (usually __name__ from calling module)

    Returns:
        Configured logger instance

    Examples:
        >>> from core.logging import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Application started")
    """
    # Check if logger already configured
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logging(name)
    return logger


class LoggerContext:
    """
    Context manager for temporary logging configuration.

    Useful for temporarily changing log level for a block of code.

    Examples:
        >>> logger = setup_logging(__name__, level="INFO")
        >>>
        >>> # Temporarily enable debug logging
        >>> with LoggerContext(logger, logging.DEBUG):
        ...     logger.debug("Detailed debug info here")
        >>>
        >>> # Back to INFO level
        >>> logger.info("Back to normal")
    """

    def __init__(self, logger: logging.Logger, level: int):
        """
        Initialize context manager.

        Args:
            logger: The logger to modify
            level: Temporary log level
        """
        self.logger = logger
        self.new_level = level
        self.old_level = None

    def __enter__(self):
        """Save current level and set new level."""
        self.old_level = self.logger.level
        self.logger.setLevel(self.new_level)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore original level."""
        if self.old_level is not None:
            self.logger.setLevel(self.old_level)
        return False
