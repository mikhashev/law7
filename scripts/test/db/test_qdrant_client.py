"""
Tests for Qdrant vector database client (scripts/indexer/qdrant_indexer.py)
"""

import pytest
from unittest.mock import MagicMock, patch
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from qdrant_client.http import models
import numpy as np

from scripts.indexer.qdrant_indexer import QdrantIndexer


class TestQdrantIndexerInit:
    """Tests for QdrantIndexer initialization."""

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_init_with_defaults(self, mock_client):
        """Test initialization with default parameters."""
        mock_qdrant = MagicMock()
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
        )

        assert indexer.collection_name == "test_collection"
        assert indexer.vector_size == 768
        assert indexer.batch_size == 100  # DEFAULT_BATCH_SIZE
        mock_client.assert_called_once_with(url="http://localhost:6333")

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_init_with_custom_batch_size(self, mock_client):
        """Test initialization with custom batch size."""
        mock_qdrant = MagicMock()
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
            batch_size=50,
        )

        assert indexer.batch_size == 50


class TestCreateCollection:
    """Tests for create_collection method."""

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_create_collection_success(self, mock_client):
        """Test successful collection creation."""
        # Mock get_collections response
        mock_collections = MagicMock()
        mock_collections.collections = []  # No existing collections
        mock_qdrant = MagicMock()
        mock_qdrant.get_collections.return_value = mock_collections
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
        )

        result = indexer.create_collection()

        assert result is True
        mock_qdrant.create_collection.assert_called_once()
        call_args = mock_qdrant.create_collection.call_args
        assert call_args[1]["collection_name"] == "test_collection"
        vectors_config = call_args[1]["vectors_config"]
        assert vectors_config.size == 768
        assert vectors_config.distance == Distance.COSINE

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_create_collection_already_exists(self, mock_client):
        """Test create_collection when collection already exists."""
        # Mock get_collections response with existing collection
        mock_collections = MagicMock()
        mock_existing = MagicMock()
        mock_existing.name = "existing_collection"
        mock_collections.collections = [mock_existing]
        mock_qdrant = MagicMock()
        mock_qdrant.get_collections.return_value = mock_collections
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="existing_collection",
            vector_size=768,
        )

        result = indexer.create_collection()

        assert result is True
        mock_qdrant.create_collection.assert_not_called()

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_create_collection_recreate(self, mock_client):
        """Test create_collection with recreate=True."""
        # Mock get_collections response with existing collection
        mock_collections = MagicMock()
        mock_existing = MagicMock()
        mock_existing.name = "test_collection"
        mock_collections.collections = [mock_existing]
        mock_qdrant = MagicMock()
        mock_qdrant.get_collections.return_value = mock_collections
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
        )

        result = indexer.create_collection(recreate=True)

        assert result is True
        mock_qdrant.delete_collection.assert_called_once_with("test_collection")
        mock_qdrant.create_collection.assert_called_once()

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_create_collection_error(self, mock_client):
        """Test create_collection error handling - exception propagates."""
        mock_qdrant = MagicMock()
        mock_qdrant.get_collections.side_effect = Exception("Connection error")
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
        )

        # The exception will propagate, not return False
        with pytest.raises(Exception, match="Connection error"):
            indexer.create_collection()


class TestCollectionExists:
    """Tests for collection_exists method."""

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_collection_exists_true(self, mock_client):
        """Test collection_exists when collection exists."""
        mock_collections = MagicMock()
        mock_existing = MagicMock()
        mock_existing.name = "test_collection"
        mock_collections.collections = [mock_existing]
        mock_qdrant = MagicMock()
        mock_qdrant.get_collections.return_value = mock_collections
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
        )

        result = indexer.collection_exists()

        assert result is True

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_collection_exists_false(self, mock_client):
        """Test collection_exists when collection doesn't exist."""
        mock_collections = MagicMock()
        mock_collections.collections = []
        mock_qdrant = MagicMock()
        mock_qdrant.get_collections.return_value = mock_collections
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
        )

        result = indexer.collection_exists()

        assert result is False


class TestUpsertPoints:
    """Tests for upsert_points method."""

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_upsert_points_single_batch(self, mock_client):
        """Test upsert_points with points fitting in single batch."""
        mock_qdrant = MagicMock()
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
            batch_size=100,
        )

        points = [
            PointStruct(id="1", vector=[0.1] * 768, payload={}),
            PointStruct(id="2", vector=[0.2] * 768, payload={}),
        ]

        count = indexer.upsert_points(points)

        assert count == 2
        mock_qdrant.upsert.assert_called_once()

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_upsert_points_multiple_batches(self, mock_client):
        """Test upsert_points with multiple batches."""
        mock_qdrant = MagicMock()
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
            batch_size=2,
        )

        # Create 5 points, should result in 3 batches (2, 2, 1)
        points = [
            PointStruct(id=str(i), vector=[0.1] * 768, payload={})
            for i in range(5)
        ]

        count = indexer.upsert_points(points)

        assert count == 5
        assert mock_qdrant.upsert.call_count == 3

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_upsert_points_custom_batch_size(self, mock_client):
        """Test upsert_points with custom batch size."""
        mock_qdrant = MagicMock()
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
            batch_size=100,
        )

        points = [PointStruct(id=str(i), vector=[0.1] * 768, payload={}) for i in range(10)]

        count = indexer.upsert_points(points, batch_size=3)

        assert count == 10
        # 10 points with batch_size=3 -> 4 batches (3, 3, 3, 1)
        assert mock_qdrant.upsert.call_count == 4

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_upsert_points_empty_list(self, mock_client):
        """Test upsert_points with empty list."""
        mock_qdrant = MagicMock()
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
        )

        count = indexer.upsert_points([])

        assert count == 0
        mock_qdrant.upsert.assert_not_called()


class TestUpsertEmbeddings:
    """Tests for upsert_embeddings method."""

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_upsert_embeddings_from_generator_format(self, mock_client):
        """Test upsert_embeddings with embeddings from embeddings generator."""
        mock_qdrant = MagicMock()
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
        )

        embeddings = [
            {
                "chunk_id": "uuid-1",
                "chunk_text": "Test text 1",
                "embedding": [0.1] * 768,
                "document_id": "doc1",
            },
            {
                "chunk_id": "uuid-2",
                "chunk_text": "Test text 2",
                "embedding": [0.2] * 768,
                "document_id": "doc1",
            },
        ]

        count = indexer.upsert_embeddings(embeddings)

        assert count == 2
        mock_qdrant.upsert.assert_called_once()

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_upsert_embeddings_includes_payload(self, mock_client):
        """Test that upsert_embeddings includes document_id and chunk_text in payload."""
        mock_qdrant = MagicMock()
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
        )

        embeddings = [
            {
                "chunk_id": "uuid-1",
                "chunk_text": "Legal document text",
                "embedding": [0.1] * 768,
                "document_id": "doc123",
            },
        ]

        indexer.upsert_embeddings(embeddings)

        call_args = mock_qdrant.upsert.call_args
        points = call_args[1]["points"]
        assert len(points) == 1
        assert points[0].id == "uuid-1"
        assert points[0].payload["document_id"] == "doc123"
        assert points[0].payload["chunk_text"] == "Legal document text"


class TestSearch:
    """Tests for search method."""

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_search_returns_results(self, mock_client):
        """Test search returns matching documents."""
        mock_search_result = [
            MagicMock(id="uuid-1", score=0.95, payload={"document_id": "doc1", "chunk_text": "Text 1"}),
            MagicMock(id="uuid-2", score=0.85, payload={"document_id": "doc2", "chunk_text": "Text 2"}),
        ]
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = mock_search_result
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
        )

        query_embedding = np.array([0.1] * 768, dtype=np.float32)
        results = indexer.search(query_embedding, limit=10)

        assert len(results) == 2
        assert results[0]["id"] == "uuid-1"
        assert results[0]["score"] == 0.95
        assert results[0]["payload"]["document_id"] == "doc1"

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_search_with_score_threshold(self, mock_client):
        """Test search with score threshold - passes threshold to Qdrant."""
        mock_search_result = [
            MagicMock(id="uuid-1", score=0.95, payload={}),
            MagicMock(id="uuid-2", score=0.75, payload={}),
        ]
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = mock_search_result
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
        )

        query_embedding = np.array([0.1] * 768, dtype=np.float32)
        results = indexer.search(query_embedding, limit=10, score_threshold=0.70)

        # Verify score_threshold was passed to Qdrant
        call_kwargs = mock_qdrant.search.call_args[1]
        assert "score_threshold" in call_kwargs
        assert call_kwargs["score_threshold"] == 0.70
        assert len(results) == 2

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_search_with_filter_condition(self, mock_client):
        """Test search with filter condition."""
        mock_search_result = [MagicMock(id="uuid-1", score=0.95, payload={})]
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = mock_search_result
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
        )

        query_embedding = np.array([0.1] * 768, dtype=np.float32)
        filter_condition = {"document_id": "doc123"}
        results = indexer.search(query_embedding, limit=10, filter_condition=filter_condition)

        # Verify filter was passed to Qdrant client
        call_kwargs = mock_qdrant.search.call_args[1]
        assert "query_filter" in call_kwargs
        assert len(results) == 1

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_search_empty_results(self, mock_client):
        """Test search with no matching results."""
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = []
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
        )

        query_embedding = np.array([0.1] * 768, dtype=np.float32)
        results = indexer.search(query_embedding)

        assert results == []


class TestDeletePoints:
    """Tests for delete_points method."""

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_delete_points_single_id(self, mock_client):
        """Test deleting a single point by ID."""
        mock_qdrant = MagicMock()
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
        )

        count = indexer.delete_points("uuid-123")

        assert count == 1
        mock_qdrant.delete.assert_called_once()

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_delete_points_multiple_ids(self, mock_client):
        """Test deleting multiple points."""
        mock_qdrant = MagicMock()
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
        )

        ids_to_delete = ["uuid-1", "uuid-2", "uuid-3"]
        count = indexer.delete_points(ids_to_delete)

        assert count == 3
        mock_qdrant.delete.assert_called_once()

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_delete_points_empty_list(self, mock_client):
        """Test delete_points with empty list - calls delete with empty list."""
        mock_qdrant = MagicMock()
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
        )

        count = indexer.delete_points([])

        # Returns 0 for empty list, but delete is still called
        assert count == 0
        mock_qdrant.delete.assert_called_once()


class TestGetCollectionInfo:
    """Tests for get_collection_info method."""

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_get_collection_info(self, mock_client):
        """Test getting collection information."""
        mock_collection_info = MagicMock()
        mock_collection_info.points_count = 12345
        mock_collection_info.segments_count = 10
        mock_collection_info.status = "green"
        mock_collection_info.config.params.vectors.size = 768

        mock_qdrant = MagicMock()
        mock_qdrant.get_collection.return_value = mock_collection_info
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
        )

        info = indexer.get_collection_info()

        assert info is not None
        assert info["points_count"] == 12345
        assert info["segments_count"] == 10
        assert info["status"] == "green"
        mock_qdrant.get_collection.assert_called_once_with("test_collection")

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_get_collection_info_error(self, mock_client):
        """Test get_collection_info error handling."""
        mock_qdrant = MagicMock()
        mock_qdrant.get_collection.side_effect = Exception("Collection not found")
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="nonexistent_collection",
            vector_size=768,
        )

        info = indexer.get_collection_info()

        # Returns None on error
        assert info is None


class TestDeleteByFilter:
    """Tests for delete_by_filter method."""

    @patch("scripts.indexer.qdrant_indexer.QdrantClient")
    def test_delete_by_filter(self, mock_client):
        """Test deleting points by filter."""
        mock_qdrant = MagicMock()
        mock_client.return_value = mock_qdrant

        indexer = QdrantIndexer(
            url="http://localhost:6333",
            collection_name="test_collection",
            vector_size=768,
        )

        # Mock the delete call to return successfully
        mock_qdrant.delete.return_value = None

        count = indexer.delete_by_filter("document_id", "doc123")

        assert count == 1
        mock_qdrant.delete.assert_called_once()
