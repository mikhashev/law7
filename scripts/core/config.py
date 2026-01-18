"""
Law7 Data Pipeline Configuration
Centralized configuration based on yandex-games-bi-suite patterns
"""
import os
from dotenv import load_dotenv
from pathlib import Path

# Load from .env file with UTF-8 encoding (Windows compatibility)
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path, encoding='utf-8')

# =============================================================================
# Database Configuration
# =============================================================================
DB_USER = os.getenv("DB_USER", "law7")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5433"))
DB_NAME = os.getenv("DB_NAME", "law7")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# =============================================================================
# Pravo.gov.ru API Configuration
# =============================================================================
PRAVO_API_BASE_URL = os.getenv("PRAVO_API_BASE_URL", "http://publication.pravo.gov.ru/api")
PRAVO_API_TIMEOUT = int(os.getenv("PRAVO_API_TIMEOUT", "30"))
PRAVO_MAX_RETRIES = int(os.getenv("PRAVO_MAX_RETRIES", "3"))

# Retry configuration (from ygbis pattern)
BACKOFF_BASE_DELAY = int(os.getenv("BACKOFF_BASE_DELAY", "1"))  # 1 second
BACKOFF_MULTIPLIER = int(os.getenv("BACKOFF_MULTIPLIER", "2"))
BACKOFF_MAX_DELAY = int(os.getenv("BACKOFF_MAX_DELAY", "60"))  # 60 seconds

# =============================================================================
# Qdrant Configuration
# =============================================================================
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "law_chunks")
QDRANT_VECTOR_SIZE = int(os.getenv("QDRANT_VECTOR_SIZE", "1024"))

# =============================================================================
# Sync Configuration
# =============================================================================
SYNC_BATCH_SIZE = int(os.getenv("SYNC_BATCH_SIZE", "100"))
DAILY_SYNC_TIME = os.getenv("DAILY_SYNC_TIME", "02:00")

# Initial sync settings
INITIAL_SYNC_START_DATE = os.getenv("INITIAL_SYNC_START_DATE", "2020-01-01")
INITIAL_SYNC_BLOCK = os.getenv("INITIAL_SYNC_BLOCK", "all")  # 'all', 'president', 'government', etc.

# =============================================================================
# Embedding Configuration
# =============================================================================
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")  # 'cpu' or 'cuda'
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))

# =============================================================================
# Logging Configuration
# =============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "text")  # 'text' or 'json'

# =============================================================================
# Progress Bar Configuration (from ygbis pattern)
# =============================================================================
PROGRESS_BAR_ENABLED = os.getenv("PROGRESS_BAR_ENABLED", "true").lower() == "true"

# =============================================================================
# Paths
# =============================================================================
DATA_DIR = Path(__file__).parent.parent / "data"
CACHE_DIR = DATA_DIR / "cache"
EXPORTS_DIR = DATA_DIR / "exports"

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)
EXPORTS_DIR.mkdir(exist_ok=True)


def get_database_url() -> str:
    """Get the database connection URL."""
    return DATABASE_URL


def get_pravo_api_url(endpoint: str = "") -> str:
    """Get the full Pravo.gov.ru API URL for an endpoint."""
    base = PRAVO_API_BASE_URL.rstrip("/")
    endpoint = endpoint.lstrip("/")
    return f"{base}/{endpoint}"


def calculate_backoff_delay(attempt: int) -> int:
    """
    Calculate exponential backoff delay (from ygbis pattern).

    Args:
        attempt: The retry attempt number (0-indexed)

    Returns:
        Delay in seconds
    """
    delay = min(BACKOFF_BASE_DELAY * (BACKOFF_MULTIPLIER ** attempt), BACKOFF_MAX_DELAY)
    return delay


# Configuration class for type safety
class Config:
    """Configuration class for type-safe access to settings."""

    # Database
    db_user: str = DB_USER
    db_host: str = DB_HOST
    db_port: int = DB_PORT
    db_name: str = DB_NAME
    database_url: str = DATABASE_URL

    # Pravo.gov.ru API
    pravo_api_base_url: str = PRAVO_API_BASE_URL
    pravo_api_timeout: int = PRAVO_API_TIMEOUT
    pravo_max_retries: int = PRAVO_MAX_RETRIES

    # Retry
    backoff_base_delay: int = BACKOFF_BASE_DELAY
    backoff_multiplier: int = BACKOFF_MULTIPLIER
    backoff_max_delay: int = BACKOFF_MAX_DELAY

    # Qdrant
    qdrant_url: str = QDRANT_URL
    qdrant_collection: str = QDRANT_COLLECTION
    qdrant_vector_size: int = QDRANT_VECTOR_SIZE

    # Sync
    sync_batch_size: int = SYNC_BATCH_SIZE
    daily_sync_time: str = DAILY_SYNC_TIME

    # Embeddings
    embedding_model: str = EMBEDDING_MODEL
    embedding_device: str = EMBEDDING_DEVICE
    embedding_batch_size: int = EMBEDDING_BATCH_SIZE

    # Logging
    log_level: str = LOG_LEVEL
    log_format: str = LOG_FORMAT

    # Progress
    progress_bar_enabled: bool = PROGRESS_BAR_ENABLED


# Export configuration instance
config = Config()
