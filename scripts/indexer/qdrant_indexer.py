"""
Qdrant Vector Indexer for semantic search.
Stores and retrieves document embeddings using Qdrant.
Based on ygbis patterns for batch processing and error handling.
"""
import logging
from typing import Any, Dict, List, Optional, Union

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, PointStruct
import numpy as np

from scripts.core.config import QDRANT_COLLECTION, QDRANT_URL, QDRANT_VECTOR_SIZE

logger = logging.getLogger(__name__)


class QdrantIndexer:
    """
    Vector database indexer using Qdrant for semantic search.

    Handles:
    - Collection management (create, recreate, delete)
    - Batch upsert of embeddings
    - Similarity search
    - Hybrid keyword + semantic search (optional)
    """

    # Default batch size for upsert operations
    DEFAULT_BATCH_SIZE = 100

    def __init__(
        self,
        url: Optional[str] = None,
        collection_name: Optional[str] = None,
        vector_size: Optional[int] = None,
        batch_size: Optional[int] = None,
    ):
        """
        Initialize the Qdrant indexer.

        Args:
            url: Qdrant server URL (defaults to config)
            collection_name: Name of the collection (defaults to config)
            vector_size: Vector dimension size (defaults to config)
            batch_size: Batch size for upserts
        """
        self.url = url or QDRANT_URL
        self.collection_name = collection_name or QDRANT_COLLECTION
        self.vector_size = vector_size or QDRANT_VECTOR_SIZE
        self.batch_size = batch_size or self.DEFAULT_BATCH_SIZE

        logger.info(f"Connecting to Qdrant at {self.url}")
        self.client = QdrantClient(url=self.url)

    def create_collection(
        self,
        recreate: bool = False,
    ) -> bool:
        """
        Create the Qdrant collection for storing embeddings.

        Args:
            recreate: If True, delete existing collection first

        Returns:
            True if successful, False otherwise

        Example:
            >>> indexer = QdrantIndexer()
            >>> indexer.create_collection(recreate=True)
        """
        # Check if collection exists
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.collection_name in collection_names:
            if recreate:
                logger.info(f"Deleting existing collection: {self.collection_name}")
                self.client.delete_collection(self.collection_name)
            else:
                logger.info(f"Collection {self.collection_name} already exists")
                return True

        # Create new collection
        logger.info(f"Creating collection: {self.collection_name}")
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.vector_size,
                distance=Distance.COSINE,
            ),
        )

        logger.info(f"Collection {self.collection_name} created successfully")
        return True

    def delete_collection(self) -> bool:
        """Delete the collection."""
        try:
            self.client.delete_collection(self.collection_name)
            logger.info(f"Collection {self.collection_name} deleted")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            return False

    def collection_exists(self) -> bool:
        """Check if the collection exists."""
        collections = self.client.get_collections().collections
        return any(c.name == self.collection_name for c in collections)

    def get_collection_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the collection.

        Returns:
            Collection info dict or None if not found
        """
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": info.config.params.vectors.size,
                "points_count": info.points_count,
                "segments_count": info.segments_count,
                "status": info.status,
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return None

    def upsert_points(
        self,
        points: List[PointStruct],
        batch_size: Optional[int] = None,
    ) -> int:
        """
        Upsert points to the collection in batches.

        Args:
            points: List of Qdrant PointStruct objects
            batch_size: Batch size (defaults to instance batch_size)

        Returns:
            Number of points upserted

        Example:
            >>> from qdrant_client.http.models import PointStruct
            >>> points = [
            ...     PointStruct(id=1, vector=[0.1, 0.2], payload={"text": "hello"}),
            ... ]
            >>> indexer = QdrantIndexer()
            >>> count = indexer.upsert_points(points)
        """
        batch_size = batch_size or self.batch_size
        total_upserted = 0

        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )
            total_upserted += len(batch)
            logger.debug(f"Upserted batch: {len(batch)} points")

        logger.info(f"Total points upserted: {total_upserted}")
        return total_upserted

    def upsert_embeddings(
        self,
        embeddings: List[Dict[str, Any]],
        batch_size: Optional[int] = None,
    ) -> int:
        """
        Upsert embeddings from the embeddings generator format.

        Args:
            embeddings: List of dicts with keys:
                       - chunk_id: Unique identifier
                       - embedding: Vector as list
                       - chunk_text: Text content
                       - document_id: Parent document ID
                       - chunk_index: Position in document
                       - embedding_size: Vector dimension
            batch_size: Batch size for upsert

        Returns:
            Number of points upserted

        Example:
            >>> generator = EmbeddingsGenerator()
            >>> chunks = generator.encode_chunks("Long document...")
            >>> indexer = QdrantIndexer()
            >>> count = indexer.upsert_embeddings(chunks)
        """
        points = []

        for chunk in embeddings:
            chunk_id = chunk.get("chunk_id", chunk.get("id", ""))
            embedding = chunk.get("embedding", chunk.get("vector", []))

            if not chunk_id or not embedding:
                logger.warning(f"Skipping chunk with missing id or embedding: {chunk.get('chunk_text', '')[:50]}")
                continue

            # Build payload with metadata
            payload = {
                "chunk_text": chunk.get("chunk_text", ""),
                "document_id": chunk.get("document_id", ""),
                "chunk_index": chunk.get("chunk_index", 0),
                "embedding_size": chunk.get("embedding_size", len(embedding)),
            }

            # Add any additional fields
            for key, value in chunk.items():
                if key not in payload and key not in ("embedding", "vector"):
                    payload[key] = value

            points.append(
                PointStruct(
                    id=chunk_id,
                    vector=embedding,
                    payload=payload,
                )
            )

        return self.upsert_points(points, batch_size)

    def upsert_documents(
        self,
        documents: List[Dict[str, Any]],
        embeddings_list: np.ndarray,
        batch_size: Optional[int] = None,
    ) -> int:
        """
        Upsert documents with their embeddings.

        Args:
            documents: List of document dicts
            embeddings_list: Numpy array of embeddings (n_docs, vector_size)
            batch_size: Batch size for upsert

        Returns:
            Number of points upserted

        Example:
            >>> generator = EmbeddingsGenerator()
            >>> docs = [{"id": "1", "full_text": "..."}]
            >>> embeddings = generator.encode_documents(docs)
            >>> indexer = QdrantIndexer()
            >>> count = indexer.upsert_documents(docs, embeddings)
        """
        points = []

        for doc, embedding in zip(documents, embeddings_list):
            doc_id = doc.get("id", doc.get("eo_number", ""))
            if not doc_id:
                logger.warning("Skipping document with no id")
                continue

            # Build payload with all document fields
            payload = {
                "document_id": doc_id,
            }
            for key, value in doc.items():
                if key not in ("embedding", "vector", "id"):
                    payload[key] = value

            points.append(
                PointStruct(
                    id=doc_id,
                    vector=embedding.tolist(),
                    payload=payload,
                )
            )

        return self.upsert_points(points, batch_size)

    def search(
        self,
        query_embedding: np.ndarray,
        limit: int = 10,
        score_threshold: Optional[float] = None,
        filter_condition: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents by embedding.

        Args:
            query_embedding: Query vector
            limit: Maximum number of results
            score_threshold: Minimum similarity score (0-1)
            filter_condition: Optional filter on payload fields

        Returns:
            List of search results with score and payload

        Example:
            >>> generator = EmbeddingsGenerator()
            >>> query = "трудовой договор"
            >>> embedding = generator.encode(query)[0]
            >>> indexer = QdrantIndexer()
            >>> results = indexer.search(embedding, limit=5)
        """
        search_params = {
            "collection_name": self.collection_name,
            "query_vector": query_embedding.tolist(),
            "limit": limit,
        }

        if score_threshold is not None:
            search_params["score_threshold"] = score_threshold

        if filter_condition:
            search_params["query_filter"] = models.Filter(
                must=[
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value),
                    )
                    for key, value in filter_condition.items()
                ]
            )

        results = self.client.search(**search_params)

        return [
            {
                "id": result.id,
                "score": result.score,
                "payload": result.payload,
            }
            for result in results
        ]

    def search_text(
        self,
        query_text: str,
        embeddings_generator,
        limit: int = 10,
        score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents by text query.

        Args:
            query_text: Query text string
            embeddings_generator: EmbeddingsGenerator instance
            limit: Maximum number of results
            score_threshold: Minimum similarity score

        Returns:
            List of search results

        Example:
            >>> from indexer.embeddings import EmbeddingsGenerator
            >>> generator = EmbeddingsGenerator()
            >>> indexer = QdrantIndexer()
            >>> results = indexer.search_text("трудовой договор", generator)
        """
        query_embedding = embeddings_generator.encode(query_text)[0]
        return self.search(query_embedding, limit, score_threshold)

    def delete_points(
        self,
        point_ids: Union[List[str], str],
    ) -> int:
        """
        Delete points by ID.

        Args:
            point_ids: Single ID or list of IDs to delete

        Returns:
            Number of points deleted
        """
        if isinstance(point_ids, str):
            point_ids = [point_ids]

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.PointIdsList(
                points=point_ids,
            ),
        )

        logger.info(f"Deleted {len(point_ids)} points")
        return len(point_ids)

    def delete_by_filter(
        self,
        filter_key: str,
        filter_value: Any,
    ) -> int:
        """
        Delete points by payload filter.

        Args:
            filter_key: Payload field key
            filter_value: Value to match

        Returns:
            Number of points deleted

        Example:
            >>> indexer = QdrantIndexer()
            >>> count = indexer.delete_by_filter("document_id", "doc123")
        """
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key=filter_key,
                            match=models.MatchValue(value=filter_value),
                        )
                    ]
                )
            ),
        )

        logger.info(f"Deleted points with {filter_key}={filter_value}")
        return 1  # Qdrant doesn't return count

    def get_count(self) -> int:
        """Get the total number of points in the collection."""
        try:
            count = self.client.count(collection_name=self.collection_name)
            return count
        except Exception as e:
            logger.error(f"Failed to get count: {e}")
            return 0

    def clear_collection(self) -> bool:
        """Delete all points from the collection."""
        try:
            # Get all point IDs and delete
            # Note: This is not efficient for large collections
            # Consider using scroll API for production
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.MatchValue(key="any", value=True),
                        ]
                    )
                ),
            )
            logger.info("Collection cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
            return False


# Convenience function for quick usage
def create_qdrant_indexer(
    url: Optional[str] = None,
    collection_name: Optional[str] = None,
) -> QdrantIndexer:
    """
    Convenience function to create a Qdrant indexer.

    Args:
        url: Qdrant server URL
        collection_name: Name of the collection

    Returns:
        QdrantIndexer instance

    Example:
        >>> from indexer.qdrant_indexer import create_qdrant_indexer
        >>> indexer = create_qdrant_indexer()
        >>> indexer.create_collection(recreate=True)
    """
    return QdrantIndexer(url=url, collection_name=collection_name)
