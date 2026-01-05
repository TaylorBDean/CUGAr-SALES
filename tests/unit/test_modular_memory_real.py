"""
tests/unit/test_modular_memory_real.py

Comprehensive tests for REAL modular memory implementations per AGENTS.md requirements.
Tests actual VectorMemory, MemoryRecord, HashingEmbedder classes (not mocks).

Target: 100% coverage of src/cuga/modular/memory.py (92 lines, currently 0%)

Test Strategy:
- Test real VectorMemory class with local backend (deterministic, offline-first)
- Test backend connection (faiss/chroma/qdrant) with proper error handling
- Test profile isolation enforcement in real implementations
- Test HashingEmbedder deterministic embeddings
- Test MemoryRecord dataclass serialization
"""

import logging
import pytest
from typing import Dict, List
from unittest.mock import Mock, patch, MagicMock

from cuga.modular.memory import VectorMemory, _BACKEND_REGISTRY
from cuga.modular.types import MemoryRecord
from cuga.modular.embeddings.hashing import HashingEmbedder
from cuga.modular.vector_backends.base import SearchHit, EmbeddedRecord


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def clean_backend_registry():
    """Preserve and restore backend registry."""
    original = _BACKEND_REGISTRY.copy()
    yield
    _BACKEND_REGISTRY.clear()
    _BACKEND_REGISTRY.update(original)


# ============================================================================
# TestVectorMemoryLocal: Local backend tests (offline-first)
# ============================================================================


class TestVectorMemoryLocal:
    """Test VectorMemory with local backend (deterministic, offline-first)."""

    def test_remember_stores_record_with_profile(self):
        """VectorMemory.remember() should store record with profile metadata."""
        memory = VectorMemory(profile="test_profile")
        
        memory.remember(text="Python is a programming language", metadata={"source": "user"})
        
        # Check record stored locally
        assert len(memory.store) == 1
        record = memory.store[0]
        assert record.text == "Python is a programming language"
        assert record.metadata["profile"] == "test_profile"
        assert record.metadata["source"] == "user"

    def test_remember_merges_profile_metadata(self):
        """Profile metadata should be merged with user metadata."""
        memory = VectorMemory(profile="custom_profile")
        
        memory.remember(
            text="Test fact",
            metadata={"key": "value", "priority": "high"}
        )
        
        record = memory.store[0]
        assert record.metadata["profile"] == "custom_profile"
        assert record.metadata["key"] == "value"
        assert record.metadata["priority"] == "high"

    def test_search_local_with_term_overlap(self):
        """Local search should rank by term overlap."""
        memory = VectorMemory(profile="default")
        
        # Store facts with varying overlap
        memory.remember("Python programming language")
        memory.remember("JavaScript programming language")
        memory.remember("Docker containerization platform")
        
        # Search for Python (should rank Python first)
        results = memory.search(query="Python programming", top_k=2)
        
        assert len(results) == 2
        assert "Python" in results[0].text
        assert results[0].score > 0

    def test_normalize_words_tokenization(self):
        """_normalize_words should tokenize and lowercase text."""
        memory = VectorMemory()
        
        # Test tokenization
        tokens = memory._normalize_words("Python-3.12 and JavaScript_ES6")
        
        # Should extract alphanumeric tokens, lowercase
        assert "python" in tokens
        assert "3" in tokens
        assert "12" in tokens
        assert "and" in tokens
        assert "javascript" in tokens
        assert "es6" in tokens
        # Hyphens/underscores should be removed
        assert "Python-3.12" not in tokens

    def test_local_search_returns_top_k(self):
        """Local search should respect top_k parameter."""
        memory = VectorMemory(profile="default")
        
        # Store 5 facts
        for i in range(5):
            memory.remember(f"Python fact number {i}")
        
        # Search with top_k=3
        results = memory.search(query="Python fact", top_k=3)
        
        assert len(results) == 3
        # All results should have scores
        for result in results:
            assert result.score > 0

    def test_local_search_empty_query(self):
        """Local search with empty query should return empty results."""
        memory = VectorMemory()
        memory.remember("Python programming")
        
        # Search with empty/whitespace query
        results = memory.search(query="   ", top_k=5)
        
        assert len(results) == 0

    def test_local_backend_default(self):
        """VectorMemory should default to local backend."""
        memory = VectorMemory()
        
        assert memory.backend_name == "local"
        assert memory.backend is None  # No backend needed for local
        
        # Should not try to connect backend
        memory.remember("Test fact")
        assert memory.backend is None


# ============================================================================
# TestVectorMemoryBackends: Backend connection tests
# ============================================================================


class TestVectorMemoryBackends:
    """Test VectorMemory backend registry and connections."""

    def test_backend_registry_lookup(self, clean_backend_registry):
        """Backend registry should contain supported backends."""
        from cuga.modular.memory import _BACKEND_REGISTRY
        
        # Check expected backends are registered
        assert "faiss" in _BACKEND_REGISTRY
        assert "chroma" in _BACKEND_REGISTRY
        assert "qdrant" in _BACKEND_REGISTRY

    def test_unsupported_backend_raises(self):
        """Connecting unsupported backend should raise RuntimeError."""
        memory = VectorMemory(backend_name="unsupported_backend")
        
        with pytest.raises(RuntimeError, match="Unsupported backend unsupported_backend"):
            memory.connect_backend()

    def test_backend_connection_failure_handling(self):
        """Backend connection should handle ImportError gracefully."""
        memory = VectorMemory(backend_name="faiss")
        
        # Mock backend class that raises ImportError on instantiation
        mock_backend_cls = Mock(side_effect=ImportError("faiss not installed"))
        
        with patch.dict(_BACKEND_REGISTRY, {"faiss": mock_backend_cls}):
            with pytest.raises(RuntimeError, match="Backend faiss is not installed"):
                memory.connect_backend()

    def test_connect_backend_local_noop(self):
        """Connecting local backend should be a no-op."""
        memory = VectorMemory(backend_name="local")
        
        # Should not raise, should log
        memory.connect_backend()
        
        assert memory.backend is None

    def test_connect_backend_faiss(self):
        """Connecting faiss backend should initialize and connect."""
        memory = VectorMemory(backend_name="faiss", profile="test")
        
        # Mock the backend class at registry level
        mock_backend = Mock()
        mock_backend.connect = Mock()
        mock_backend_cls = Mock(return_value=mock_backend)
        
        with patch.dict(_BACKEND_REGISTRY, {"faiss": mock_backend_cls}, clear=False):
            memory.connect_backend()
        
            # Should create backend instance
            mock_backend_cls.assert_called_once()
            # Should call connect()
            mock_backend.connect.assert_called_once()
            # Should store backend
            assert memory.backend is mock_backend

    def test_connect_backend_chroma(self):
        """Connecting chroma backend should initialize and connect."""
        memory = VectorMemory(backend_name="chroma")
        
        mock_backend = Mock()
        mock_backend.connect = Mock()
        mock_backend_cls = Mock(return_value=mock_backend)
        
        with patch.dict(_BACKEND_REGISTRY, {"chroma": mock_backend_cls}, clear=False):
            memory.connect_backend()
        
            mock_backend_cls.assert_called_once()
            mock_backend.connect.assert_called_once()
            assert memory.backend is mock_backend

    def test_connect_backend_qdrant(self):
        """Connecting qdrant backend should initialize and connect."""
        memory = VectorMemory(backend_name="qdrant")
        
        mock_backend = Mock()
        mock_backend.connect = Mock()
        mock_backend_cls = Mock(return_value=mock_backend)
        
        with patch.dict(_BACKEND_REGISTRY, {"qdrant": mock_backend_cls}, clear=False):
            memory.connect_backend()
        
            mock_backend_cls.assert_called_once()
            mock_backend.connect.assert_called_once()
            assert memory.backend is mock_backend


# ============================================================================
# TestVectorMemorySearch: Search delegation tests
# ============================================================================


class TestVectorMemorySearch:
    """Test VectorMemory search behavior (local vs backend)."""

    def test_search_with_backend_delegates_to_backend(self):
        """Search with backend should delegate to backend.search()."""
        memory = VectorMemory(backend_name="faiss")
        
        # Mock backend
        mock_backend = Mock()
        mock_search_results = [
            SearchHit(text="Result 1", metadata={"profile": "default"}, score=0.9),
            SearchHit(text="Result 2", metadata={"profile": "default"}, score=0.8),
        ]
        mock_backend.search = Mock(return_value=mock_search_results)
        memory.backend = mock_backend
        
        # Mock embedder
        mock_embedder = Mock()
        mock_embedder.embed = Mock(return_value=[0.1, 0.2, 0.3])
        memory.embedder = mock_embedder
        
        # Search
        results = memory.search(query="test query", top_k=5)
        
        # Should embed query
        mock_embedder.embed.assert_called_once_with("test query")
        # Should call backend.search with embedding
        mock_backend.search.assert_called_once_with([0.1, 0.2, 0.3], 5)
        # Should return backend results
        assert results == mock_search_results

    def test_search_without_backend_uses_local(self):
        """Search without backend should use local search."""
        memory = VectorMemory(backend_name="local")
        memory.remember("Python programming")
        memory.remember("JavaScript programming")
        
        # Should use local search (no backend)
        results = memory.search(query="Python", top_k=5)
        
        assert len(results) > 0
        assert memory.backend is None

    def test_local_search_ranks_by_overlap(self):
        """Local search should rank results by term overlap score."""
        memory = VectorMemory()
        
        # Store facts with different overlap levels
        memory.remember("Python programming language interpreter")  # 2 matching terms
        memory.remember("Python language")  # 2 matching terms
        memory.remember("Programming language")  # 1 matching term
        
        # Search for "Python language"
        results = memory.search(query="Python language", top_k=3)
        
        # All should match
        assert len(results) == 3
        # Scores should be in descending order
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score


# ============================================================================
# TestMemoryRecord: MemoryRecord dataclass tests
# ============================================================================


class TestMemoryRecord:
    """Test MemoryRecord dataclass."""

    def test_memory_record_creation(self):
        """MemoryRecord should be created with text and metadata."""
        record = MemoryRecord(
            text="Test fact",
            metadata={"key": "value"}
        )
        
        assert record.text == "Test fact"
        assert record.metadata == {"key": "value"}

    def test_memory_record_with_metadata(self):
        """MemoryRecord should store complex metadata."""
        metadata = {
            "profile": "test",
            "timestamp": "2024-01-01T00:00:00",
            "source": "user",
            "priority": "high",
        }
        
        record = MemoryRecord(text="Complex fact", metadata=metadata)
        
        assert record.metadata["profile"] == "test"
        assert record.metadata["timestamp"] == "2024-01-01T00:00:00"
        assert record.metadata["source"] == "user"
        assert record.metadata["priority"] == "high"

    def test_memory_record_equality(self):
        """MemoryRecord should support equality comparison."""
        record1 = MemoryRecord(text="Test", metadata={"key": "value"})
        record2 = MemoryRecord(text="Test", metadata={"key": "value"})
        record3 = MemoryRecord(text="Different", metadata={"key": "value"})
        
        assert record1 == record2
        assert record1 != record3


# ============================================================================
# TestHashingEmbedder: HashingEmbedder tests
# ============================================================================


class TestHashingEmbedder:
    """Test HashingEmbedder deterministic embeddings."""

    def test_embedder_deterministic(self):
        """HashingEmbedder should produce deterministic embeddings."""
        embedder = HashingEmbedder()
        
        text = "Python programming language"
        embedding1 = embedder.embed(text)
        embedding2 = embedder.embed(text)
        
        assert embedding1 == embedding2

    def test_embedder_normalized(self):
        """HashingEmbedder should produce normalized embeddings."""
        embedder = HashingEmbedder()
        
        embedding = embedder.embed("Test text")
        
        # Check normalization (L2 norm should be ~1.0)
        norm = sum(v * v for v in embedding) ** 0.5
        assert abs(norm - 1.0) < 0.01  # Allow small floating point error

    def test_embedder_different_texts_different_embeddings(self):
        """Different texts should produce different embeddings."""
        embedder = HashingEmbedder()
        
        embedding1 = embedder.embed("Python")
        embedding2 = embedder.embed("JavaScript")
        
        assert embedding1 != embedding2

    def test_embedder_64_dimensions(self):
        """HashingEmbedder should produce 64-dimensional embeddings."""
        embedder = HashingEmbedder()
        
        embedding = embedder.embed("Test")
        
        assert len(embedding) == 64


# ============================================================================
# TestProfileIsolation: Profile isolation tests (real implementation)
# ============================================================================


class TestProfileIsolation:
    """Test profile isolation in real VectorMemory implementations."""

    def test_profile_scoped_storage(self):
        """Each profile should have isolated storage."""
        memory1 = VectorMemory(profile="profile_a")
        memory2 = VectorMemory(profile="profile_b")
        
        memory1.remember("Fact A")
        memory2.remember("Fact B")
        
        # Profiles should have separate stores
        assert len(memory1.store) == 1
        assert len(memory2.store) == 1
        assert memory1.store[0].text == "Fact A"
        assert memory2.store[0].text == "Fact B"

    def test_profile_scoped_search(self):
        """Search should be scoped to profile's storage."""
        memory1 = VectorMemory(profile="profile_a")
        memory2 = VectorMemory(profile="profile_b")
        
        memory1.remember("Python programming")
        memory2.remember("JavaScript programming")
        
        # Search in profile_a should only return profile_a facts
        results1 = memory1.search(query="programming", top_k=5)
        assert len(results1) == 1
        assert "Python" in results1[0].text
        
        # Search in profile_b should only return profile_b facts
        results2 = memory2.search(query="programming", top_k=5)
        assert len(results2) == 1
        assert "JavaScript" in results2[0].text

    def test_default_profile_fallback(self):
        """Unspecified profile should default to 'default'."""
        memory = VectorMemory()
        
        assert memory.profile == "default"
        
        memory.remember("Test fact")
        assert memory.store[0].metadata["profile"] == "default"


# ============================================================================
# TestBackendIntegration: Backend upsert integration
# ============================================================================


class TestBackendIntegration:
    """Test VectorMemory integration with backends (upsert)."""

    def test_remember_with_backend_upserts(self):
        """remember() with backend should embed and upsert to backend."""
        mock_backend = Mock()
        mock_backend.connect = Mock()
        mock_backend.upsert = Mock()
        mock_backend_cls = Mock(return_value=mock_backend)
        
        memory = VectorMemory(backend_name="faiss")
        
        with patch.dict(_BACKEND_REGISTRY, {"faiss": mock_backend_cls}, clear=False):
            memory.connect_backend()
            
            # Remember fact
            memory.remember("Python programming", metadata={"source": "test"})
            
            # Should upsert to backend
            mock_backend.upsert.assert_called_once()
            
            # Check upsert called with EmbeddedRecord
            call_args = mock_backend.upsert.call_args[0][0]
            assert len(call_args) == 1
            embedded_record = call_args[0]
            assert isinstance(embedded_record, EmbeddedRecord)
            assert embedded_record.record.text == "Python programming"
            assert embedded_record.record.metadata["source"] == "test"
            assert len(embedded_record.embedding) == 64  # HashingEmbedder dimension

    def test_remember_auto_connects_backend(self):
        """remember() should auto-connect backend if not connected."""
        mock_backend = Mock()
        mock_backend.connect = Mock()
        mock_backend.upsert = Mock()
        mock_backend_cls = Mock(return_value=mock_backend)
        
        memory = VectorMemory(backend_name="chroma")
        # Don't call connect_backend() explicitly
        
        with patch.dict(_BACKEND_REGISTRY, {"chroma": mock_backend_cls}, clear=False):
            # Remember should auto-connect
            memory.remember("Test fact")
            
            # Should have connected backend
            mock_backend_cls.assert_called_once()
            mock_backend.connect.assert_called_once()
            # Should have called upsert
            mock_backend.upsert.assert_called_once()

    def test_remember_local_backend_no_upsert(self):
        """remember() with local backend should not call upsert."""
        memory = VectorMemory(backend_name="local")
        
        # Remember fact
        memory.remember("Test fact")
        
        # Should store locally
        assert len(memory.store) == 1
        # Backend should still be None
        assert memory.backend is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
