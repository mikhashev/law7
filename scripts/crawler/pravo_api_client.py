"""
Pravo.gov.ru API Client.
Handles communication with the pravo.gov.ru API with retry logic.
Based on yandex-games-bi-suite patterns.
"""
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import requests

from core.config import (
    PRAVO_API_BASE_URL,
    PRAVO_API_MAX_RETRIES,
    PRAVO_API_TIMEOUT,
    get_pravo_api_url,
)
from utils.retry import fetch_with_retry

logger = logging.getLogger(__name__)


class PravoApiClient:
    """
    Client for the pravo.gov.ru API.

    Handles fetching documents, public blocks, and other API resources
    with exponential backoff retry logic.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        """
        Initialize the API client.

        Args:
            base_url: API base URL (defaults to config)
            timeout: Request timeout in seconds (defaults to config)
            max_retries: Maximum retry attempts (defaults to config)
        """
        self.base_url = (base_url or PRAVO_API_BASE_URL).rstrip("/")
        self.timeout = timeout or PRAVO_API_TIMEOUT
        self.max_retries = max_retries or PRAVO_API_MAX_RETRIES
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Law7/0.1.0"})

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a GET request to the API with retry logic.

        Args:
            endpoint: API endpoint (e.g., "/PublicBlocks/")
            params: Query parameters

        Returns:
            JSON response as dictionary

        Raises:
            requests.RequestException: If all retries fail
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        def fetch_fn() -> Dict[str, Any]:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()

        return fetch_with_retry(
            fetch_fn,
            max_retries=self.max_retries,
            operation_name=f"GET {endpoint}",
        )

    def get_public_blocks(self) -> List[Dict[str, Any]]:
        """
        Get publication blocks (categories of legal documents).

        Returns:
            List of public blocks

        Example:
            >>> client = PravoApiClient()
            >>> blocks = client.get_public_blocks()
            >>> for block in blocks:
            ...     print(block["code"], block["name"])
        """
        logger.info("Fetching public blocks")
        result = self._make_request("PublicBlocks/")
        return result if isinstance(result, list) else []

    def get_categories(self) -> List[Dict[str, Any]]:
        """
        Get categories of signing authorities.

        Returns:
            List of categories
        """
        logger.info("Fetching categories")
        result = self._make_request("Categories")
        return result if isinstance(result, list) else []

    def get_document_types(self) -> List[Dict[str, Any]]:
        """
        Get document types.

        Returns:
            List of document types
        """
        logger.info("Fetching document types")
        result = self._make_request("DocumentTypes")
        return result if isinstance(result, list) else []

    def get_signatory_authorities(self) -> List[Dict[str, Any]]:
        """
        Get signatory authorities (organizations that sign documents).

        Returns:
            List of signatory authorities
        """
        logger.info("Fetching signatory authorities")
        result = self._make_request("SignatoryAuthorities")
        return result if isinstance(result, list) else []

    def search_documents(
        self,
        page: int = 1,
        page_size: int = 100,
        search: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        doc_type: Optional[str] = None,
        block: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search for documents with pagination.

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page (max 1000)
            search: Full-text search query
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            doc_type: Filter by document type
            block: Filter by publication block code

        Returns:
            Dictionary with keys:
                - items: List of documents
                - itemsTotalCount: Total number of documents
                - itemsPerPage: Items per page
                - currentPage: Current page number
                - pagesTotalCount: Total number of pages

        Example:
            >>> client = PravoApiClient()
            >>> result = client.search_documents(page=1, page_size=10, search="труд")
            >>> print(f"Found {result['itemsTotalCount']} documents")
            >>> for doc in result['items']:
            ...     print(doc['title'])
        """
        logger.info(f"Searching documents (page={page}, page_size={page_size})")

        params = {
            "page": page,
            "pageSize": min(page_size, 1000),  # Max 1000 per page
        }

        if search:
            params["search"] = search
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        if doc_type:
            params["docType"] = doc_type
        if block:
            params["block"] = block

        return self._make_request("Documents", params=params)

    def get_documents_by_date_range(
        self,
        start_date: str,
        end_date: Optional[str] = None,
        block: Optional[str] = None,
        page_size: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get all documents for a date range, handling pagination automatically.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (defaults to today)
            block: Filter by publication block code
            page_size: Number of items per page

        Returns:
            List of all documents in the date range

        Example:
            >>> client = PravoApiClient()
            >>> docs = client.get_documents_by_date_range("2024-01-01", "2024-01-31")
            >>> print(f"Found {len(docs)} documents")
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"Fetching documents from {start_date} to {end_date}")

        all_documents = []
        page = 1

        while True:
            result = self.search_documents(
                page=page,
                page_size=page_size,
                start_date=start_date,
                end_date=end_date,
                block=block,
            )

            documents = result.get("items", [])
            all_documents.extend(documents)

            logger.info(f"  Fetched page {page}: {len(documents)} documents")

            # Check if we've fetched all pages
            total_pages = result.get("pagesTotalCount", 1)
            if page >= total_pages or len(documents) == 0:
                break

            page += 1

        logger.info(f"Total documents fetched: {len(all_documents)}")
        return all_documents

    def get_document_detail(self, eo_number: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific document.

        Note: This endpoint may return HTML instead of JSON.
        The exact format needs to be determined from API documentation.

        Args:
            eo_number: Document eoNumber (e.g., "0001202601170001")

        Returns:
            Document detail or None if not found

        Example:
            >>> client = PravoApiClient()
            >>> detail = client.get_document_detail("0001202601170001")
        """
        logger.info(f"Fetching document detail: {eo_number}")

        try:
            # Try the documented endpoint first
            result = self._make_request(f"Document/{eo_number}")
            return result
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch document detail: {e}")
            logger.info("Note: Document detail endpoint may require different format")
            return None

    def close(self):
        """Close the HTTP session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Convenience function for quick usage
def fetch_documents_for_date(
    target_date: str,
    block: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Convenience function to fetch all documents for a specific date.

    Args:
        target_date: Date in YYYY-MM-DD format
        block: Optional publication block filter

    Returns:
        List of documents
    """
    with PravoApiClient() as client:
        return client.get_documents_by_date_range(
            start_date=target_date,
            end_date=target_date,
            block=block,
        )
