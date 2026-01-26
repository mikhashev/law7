"""
Law7 Exception Hierarchy

Centralized exception classes for Law7 project.
Provides specific exception types for different error categories.
"""
from typing import Optional, Any


class Law7Error(Exception):
    """
    Base exception for all Law7 errors.

    All custom exceptions in Law7 should inherit from this class
    to enable consistent error handling across the application.
    """

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        """
        Initialize Law7Error.

        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
        """
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return string representation of the error."""
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


class DatabaseError(Law7Error):
    """
    Database-related errors.

    Raised when database operations fail (PostgreSQL, Qdrant, Redis).
    """

    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        """
        Initialize DatabaseError.

        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
            original_error: The original exception that caused this error
        """
        super().__init__(message, details)
        self.original_error = original_error

    def __str__(self) -> str:
        """Return string representation including original error if present."""
        base = super().__str__()
        if self.original_error:
            return f"{base} | Caused by: {type(self.original_error).__name__}: {self.original_error}"
        return base


class APIError(Law7Error):
    """
    External API errors.

    Raised when external API calls fail (pravo.gov.ru, government.ru, etc.).
    """

    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        status_code: Optional[int] = None,
        url: Optional[str] = None,
    ):
        """
        Initialize APIError.

        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
            status_code: HTTP status code if applicable
            url: The URL that failed
        """
        super().__init__(message, details)
        self.status_code = status_code
        self.url = url

    def __str__(self) -> str:
        """Return string representation including status code and URL if present."""
        base = super().__str__()
        parts = [base]
        if self.status_code:
            parts.append(f"Status: {self.status_code}")
        if self.url:
            parts.append(f"URL: {self.url}")
        return " | ".join(parts) if len(parts) > 1 else base


class ParsingError(Law7Error):
    """
    Document parsing errors.

    Raised when document parsing fails (HTML, PDF, OCR).
    """

    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        document_id: Optional[str] = None,
        parser_type: Optional[str] = None,
    ):
        """
        Initialize ParsingError.

        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
            document_id: The document ID that failed to parse
            parser_type: The type of parser (html, pdf, ocr, etc.)
        """
        super().__init__(message, details)
        self.document_id = document_id
        self.parser_type = parser_type

    def __str__(self) -> str:
        """Return string representation including document ID and parser type if present."""
        base = super().__str__()
        parts = [base]
        if self.document_id:
            parts.append(f"Document: {self.document_id}")
        if self.parser_type:
            parts.append(f"Parser: {self.parser_type}")
        return " | ".join(parts) if len(parts) > 1 else base


class ConsolidationError(Law7Error):
    """
    Legal code consolidation errors.

    Raised when amendment application or consolidation fails.
    """

    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        code_id: Optional[str] = None,
        article_number: Optional[str] = None,
    ):
        """
        Initialize ConsolidationError.

        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
            code_id: The legal code identifier (e.g., 'TK_RF', 'GK_RF')
            article_number: The article number that failed
        """
        super().__init__(message, details)
        self.code_id = code_id
        self.article_number = article_number

    def __str__(self) -> str:
        """Return string representation including code and article if present."""
        base = super().__str__()
        parts = [base]
        if self.code_id:
            parts.append(f"Code: {self.code_id}")
        if self.article_number:
            parts.append(f"Article: {self.article_number}")
        return " | ".join(parts) if len(parts) > 1 else base


class EmbeddingError(Law7Error):
    """
    Embedding generation errors.

    Raised when embedding generation or indexing fails.
    """

    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        model_name: Optional[str] = None,
        batch_size: Optional[int] = None,
    ):
        """
        Initialize EmbeddingError.

        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
            model_name: The embedding model that failed
            batch_size: The batch size being processed
        """
        super().__init__(message, details)
        self.model_name = model_name
        self.batch_size = batch_size

    def __str__(self) -> str:
        """Return string representation including model and batch size if present."""
        base = super().__str__()
        parts = [base]
        if self.model_name:
            parts.append(f"Model: {self.model_name}")
        if self.batch_size:
            parts.append(f"Batch: {self.batch_size}")
        return " | ".join(parts) if len(parts) > 1 else base


class SyncError(Law7Error):
    """
    Document synchronization errors.

    Raised when document synchronization fails.
    """

    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        sync_type: Optional[str] = None,
        country_id: Optional[str] = None,
    ):
        """
        Initialize SyncError.

        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
            sync_type: The type of sync (initial, content, amendments)
            country_id: The country being synced
        """
        super().__init__(message, details)
        self.sync_type = sync_type
        self.country_id = country_id

    def __str__(self) -> str:
        """Return string representation including sync type and country if present."""
        base = super().__str__()
        parts = [base]
        if self.sync_type:
            parts.append(f"Sync: {self.sync_type}")
        if self.country_id:
            parts.append(f"Country: {self.country_id}")
        return " | ".join(parts) if len(parts) > 1 else base


class ValidationError(Law7Error):
    """
    Data validation errors.

    Raised when input data validation fails.
    """

    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        field_name: Optional[str] = None,
        field_value: Optional[Any] = None,
    ):
        """
        Initialize ValidationError.

        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
            field_name: The field that failed validation
            field_value: The value that failed validation
        """
        super().__init__(message, details)
        self.field_name = field_name
        self.field_value = field_value

    def __str__(self) -> str:
        """Return string representation including field and value if present."""
        base = super().__str__()
        parts = [base]
        if self.field_name:
            parts.append(f"Field: {self.field_name}")
        if self.field_value is not None:
            parts.append(f"Value: {self.field_value}")
        return " | ".join(parts) if len(parts) > 1 else base


class ConfigurationError(Law7Error):
    """
    Configuration errors.

    Raised when configuration is missing or invalid.
    """

    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        config_key: Optional[str] = None,
        config_file: Optional[str] = None,
    ):
        """
        Initialize ConfigurationError.

        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
            config_key: The configuration key that is problematic
            config_file: The configuration file being read
        """
        super().__init__(message, details)
        self.config_key = config_key
        self.config_file = config_file

    def __str__(self) -> str:
        """Return string representation including config key and file if present."""
        base = super().__str__()
        parts = [base]
        if self.config_key:
            parts.append(f"Key: {self.config_key}")
        if self.config_file:
            parts.append(f"File: {self.config_file}")
        return " | ".join(parts) if len(parts) > 1 else base
