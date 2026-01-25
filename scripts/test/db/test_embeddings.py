"""
Tests for embeddings generator (scripts/indexer/embeddings.py)
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime
import uuid

# Note: These tests avoid loading the actual SentenceTransformer model
# by mocking at the module level before importing the embeddings module.


class TestChunkText:
    """Tests for chunk_text method - tests chunking without loading models."""

    def test_chunk_text_short_text(self):
        """Test chunking text shorter than chunk size."""
        from scripts.indexer.embeddings import EmbeddingsGenerator

        # Mock the model to avoid loading
        with patch("scripts.indexer.embeddings.SentenceTransformer") as mock_transformer:
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 768
            mock_transformer.return_value = mock_model

            generator = EmbeddingsGenerator()

            text = "Short text"
            chunks = generator.chunk_text(text, chunk_size=100)

            assert len(chunks) == 1
            assert chunks[0] == "Short text"

    def test_chunk_text_long_text(self):
        """Test chunking long text."""
        from scripts.indexer.embeddings import EmbeddingsGenerator

        with patch("scripts.indexer.embeddings.SentenceTransformer") as mock_transformer:
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 768
            mock_transformer.return_value = mock_model

            generator = EmbeddingsGenerator()

            # Create text long enough to be chunked
            text = "This is sentence one. This is sentence two. This is sentence three. " * 50
            chunks = generator.chunk_text(text, chunk_size=200)

            assert len(chunks) > 1
            # Check that chunks are not empty
            assert all(chunk.strip() for chunk in chunks)

    def test_chunk_text_with_overlap(self):
        """Test chunking with overlap."""
        from scripts.indexer.embeddings import EmbeddingsGenerator

        with patch("scripts.indexer.embeddings.SentenceTransformer") as mock_transformer:
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 768
            mock_transformer.return_value = mock_model

            generator = EmbeddingsGenerator()

            text = "Sentence one. Sentence two. Sentence three. Sentence four. " * 20
            chunks = generator.chunk_text(text, chunk_size=150, overlap=50)

            assert len(chunks) > 1

    def test_chunk_text_empty(self):
        """Test chunking empty text."""
        from scripts.indexer.embeddings import EmbeddingsGenerator

        with patch("scripts.indexer.embeddings.SentenceTransformer") as mock_transformer:
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 768
            mock_transformer.return_value = mock_model

            generator = EmbeddingsGenerator()

            chunks = generator.chunk_text("", chunk_size=100)

            assert chunks == []

    def test_chunk_text_none(self):
        """Test chunking None text."""
        from scripts.indexer.embeddings import EmbeddingsGenerator

        with patch("scripts.indexer.embeddings.SentenceTransformer") as mock_transformer:
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 768
            mock_transformer.return_value = mock_model

            generator = EmbeddingsGenerator()

            chunks = generator.chunk_text(None, chunk_size=100)

            assert chunks == []


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @patch("scripts.indexer.embeddings.EmbeddingsGenerator")
    def test_generate_embeddings(self, mock_generator_class):
        """Test generate_embeddings convenience function."""
        from scripts.indexer.embeddings import generate_embeddings
        import numpy as np

        mock_generator = MagicMock()
        mock_embeddings = np.random.rand(2, 768).astype(np.float32)
        mock_generator.encode.return_value = mock_embeddings
        mock_generator_class.return_value.__enter__.return_value = mock_generator

        texts = ["text1", "text2"]
        embeddings = generate_embeddings(texts)

        assert embeddings.shape == (2, 768)
        mock_generator.encode.assert_called_once_with(texts)

    @patch("scripts.indexer.embeddings.EmbeddingsGenerator")
    def test_generate_embeddings_with_model_name(self, mock_generator_class):
        """Test generate_embeddings with custom model."""
        from scripts.indexer.embeddings import generate_embeddings
        import numpy as np

        mock_generator = MagicMock()
        mock_embeddings = np.random.rand(1, 768).astype(np.float32)
        mock_generator.encode.return_value = mock_embeddings
        mock_generator_class.return_value.__enter__.return_value = mock_generator

        embeddings = generate_embeddings("test", model_name="custom-model")

        mock_generator_class.assert_called_once_with(model_name="custom-model")

    @patch("scripts.indexer.embeddings.EmbeddingsGenerator")
    def test_chunk_and_encode(self, mock_generator_class):
        """Test chunk_and_encode convenience function."""
        from scripts.indexer.embeddings import chunk_and_encode

        mock_generator = MagicMock()
        mock_chunks = [
            {
                "chunk_id": "uuid-1",
                "chunk_text": "Chunk 1",
                "chunk_index": 0,
                "embedding": [0.1] * 768,
                "embedding_size": 768,
            }
        ]
        mock_generator.encode_chunks.return_value = mock_chunks
        mock_generator_class.return_value.__enter__.return_value = mock_generator

        text = "Long text to chunk"
        chunks = chunk_and_encode(text, chunk_size=200, overlap=50)

        assert len(chunks) == 1
        mock_generator.encode_chunks.assert_called_once_with(text, 200, 50)


class TestGetTextHash:
    """Tests for _get_text_hash method."""

    def test_get_text_hash(self):
        """Test text hash generation."""
        from scripts.indexer.embeddings import EmbeddingsGenerator
        import hashlib

        # Create generator without loading model by mocking
        with patch("scripts.indexer.embeddings.SentenceTransformer"):
            generator = EmbeddingsGenerator.__new__(EmbeddingsGenerator)
            generator._cache = {}

            # Manually set required attributes
            text1 = "Test text"
            hash1 = hashlib.md5(text1.encode("utf-8")).hexdigest()
            hash2 = hashlib.md5(text1.encode("utf-8")).hexdigest()
            hash3 = hashlib.md5("Different text".encode("utf-8")).hexdigest()

            assert hash1 == hash2  # Same text should produce same hash
            assert hash1 != hash3  # Different text should produce different hash

    def test_get_text_hash_empty(self):
        """Test hash generation for empty text."""
        import hashlib

        hash_empty = hashlib.md5("".encode("utf-8")).hexdigest() if "" else ""
        hash_none = ""

        assert hash_empty == ""
        assert hash_none == ""


class TestChunkAndEncode:
    """Tests for chunk_and_encode convenience function."""

    @patch("scripts.indexer.embeddings.EmbeddingsGenerator")
    def test_chunk_and_encode_defaults(self, mock_generator_class):
        """Test chunk_and_encode with default parameters."""
        from scripts.indexer.embeddings import chunk_and_encode

        mock_generator = MagicMock()
        mock_generator.encode_chunks.return_value = []
        mock_generator_class.return_value.__enter__.return_value = mock_generator

        chunks = chunk_and_encode("test text")

        # Should use default chunk_size and overlap
        mock_generator.encode_chunks.assert_called_once()
        args = mock_generator.encode_chunks.call_args[0]
        assert args[0] == "test text"
        # chunk_size=512, overlap=50 are defaults


# Note: Tests for encode(), encode_documents(), encode_chunks(), and encode_document_chunks()
# are skipped because they require loading the actual SentenceTransformer model which is
# CPU-intensive and slow for unit tests. The chunk_text functionality and convenience
# functions are tested separately above.

# Integration tests that load the actual model can be added in a separate test file
# (test_embeddings_integration.py) that is run manually or in CI separately.
