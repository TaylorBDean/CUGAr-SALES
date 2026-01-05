"""
tests/unit/test_core_memory_real.py

Comprehensive tests for REAL core memory implementations per AGENTS.md requirements.
Tests actual MemoryStore ABC, InMemoryMemoryStore, VectorMemory (core) classes.

Target: 100% coverage of src/cuga/memory/*.py (74 lines, currently 0%)

Test Strategy:
- Test MemoryStore ABC contract enforcement
- Test InMemoryMemoryStore session/user state CRUD operations
- Test VectorMemory (core) async batching, TTL eviction, locking
- Validate state ownership boundaries (ephemeral session vs persistent user)
- Offline-first, deterministic testing (no external dependencies)
"""

import asyncio
import time
import pytest
from typing import Dict, Any

from cuga.memory.base import MemoryStore, SessionState, UserProfile, MemoryEvent
from cuga.memory.in_memory_store import InMemoryMemoryStore
from cuga.memory.vector import VectorMemory


# ============================================================================
# TestMemoryStoreABC: Abstract base class contract tests
# ============================================================================


class TestMemoryStoreABC:
    """Test MemoryStore ABC contract enforcement."""

    def test_cannot_instantiate_abc(self):
        """MemoryStore is abstract and cannot be instantiated."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            MemoryStore()

    def test_abstract_methods_enforced(self):
        """Subclass must implement all abstract methods."""
        
        # Incomplete implementation (missing methods)
        class IncompleteStore(MemoryStore):
            def load_session_state(self, session_id: str):
                return None
        
        # Should fail to instantiate
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteStore()

    def test_complete_implementation_allowed(self):
        """Complete implementation should instantiate successfully."""
        
        class CompleteStore(MemoryStore):
            def load_session_state(self, session_id: str):
                return None
            
            def save_session_state(self, session_id: str, state: SessionState):
                pass
            
            def append_event(self, session_id: str, event: MemoryEvent):
                pass
            
            def load_user_profile(self, user_id: str):
                return None
            
            def update_user_profile(self, user_id: str, patch: Dict[str, Any]):
                pass
            
            def delete_session_state(self, session_id: str):
                pass
            
            def delete_user_profile(self, user_id: str):
                pass
        
        # Should succeed
        store = CompleteStore()
        assert isinstance(store, MemoryStore)


# ============================================================================
# TestInMemoryMemoryStore: InMemoryMemoryStore implementation tests
# ============================================================================


class TestInMemoryMemoryStore:
    """Test InMemoryMemoryStore ephemeral storage implementation."""

    def test_initialization(self, capsys):
        """InMemoryMemoryStore should initialize with empty storage."""
        store = InMemoryMemoryStore()
        
        # Should print initialization message
        captured = capsys.readouterr()
        assert "Initialized InMemoryMemoryStore" in captured.out
        
        # Internal storage should be empty
        assert len(store._sessions) == 0
        assert len(store._users) == 0

    def test_save_and_load_session_state(self, capsys):
        """Session state should be saved and loaded correctly."""
        store = InMemoryMemoryStore()
        
        session_id = "session_123"
        state: SessionState = {
            "conversation": ["Hello", "Hi there"],
            "context": {"user_name": "Alice"},
        }
        
        # Save session state
        store.save_session_state(session_id, state)
        captured = capsys.readouterr()
        assert f"Saving state for session: {session_id}" in captured.out
        
        # Load session state
        loaded_state = store.load_session_state(session_id)
        captured = capsys.readouterr()
        assert f"Loading state for session: {session_id}" in captured.out
        
        # Should match saved state
        assert loaded_state == state
        assert loaded_state["conversation"] == ["Hello", "Hi there"]
        assert loaded_state["context"]["user_name"] == "Alice"

    def test_load_nonexistent_session_returns_none(self):
        """Loading nonexistent session should return None."""
        store = InMemoryMemoryStore()
        
        loaded = store.load_session_state("nonexistent_session")
        
        assert loaded is None

    def test_append_event_to_session(self):
        """Events should be appended to session history."""
        store = InMemoryMemoryStore()
        
        session_id = "session_456"
        event1: MemoryEvent = {"type": "user_message", "content": "Hello"}
        event2: MemoryEvent = {"type": "agent_response", "content": "Hi there"}
        
        # Append events
        store.append_event(session_id, event1)
        store.append_event(session_id, event2)
        
        # Check session state
        state = store.load_session_state(session_id)
        assert state is not None
        assert "history" in state
        assert len(state["history"]) == 2
        assert state["history"][0] == event1
        assert state["history"][1] == event2

    def test_append_event_creates_session_if_missing(self):
        """Appending event to nonexistent session should create session."""
        store = InMemoryMemoryStore()
        
        session_id = "new_session"
        event: MemoryEvent = {"type": "user_message", "content": "First message"}
        
        # Append event (session doesn't exist yet)
        store.append_event(session_id, event)
        
        # Session should now exist with history
        state = store.load_session_state(session_id)
        assert state is not None
        assert "history" in state
        assert len(state["history"]) == 1
        assert state["history"][0] == event

    def test_delete_session_state(self):
        """Session state should be deleted."""
        store = InMemoryMemoryStore()
        
        session_id = "session_to_delete"
        store.save_session_state(session_id, {"data": "test"})
        
        # Verify session exists
        assert store.load_session_state(session_id) is not None
        
        # Delete session
        store.delete_session_state(session_id)
        
        # Session should no longer exist
        assert store.load_session_state(session_id) is None

    def test_delete_nonexistent_session_noop(self):
        """Deleting nonexistent session should be a no-op."""
        store = InMemoryMemoryStore()
        
        # Should not raise
        store.delete_session_state("nonexistent_session")

    def test_load_and_update_user_profile(self):
        """User profile should be loaded and updated."""
        store = InMemoryMemoryStore()
        
        user_id = "user_789"
        
        # Load nonexistent profile (should return None)
        profile = store.load_user_profile(user_id)
        assert profile is None
        
        # Update profile (creates if missing)
        patch1 = {"name": "Bob", "preferences": {"theme": "dark"}}
        store.update_user_profile(user_id, patch1)
        
        # Load profile
        profile = store.load_user_profile(user_id)
        assert profile is not None
        assert profile["name"] == "Bob"
        assert profile["preferences"]["theme"] == "dark"
        
        # Update profile again (patches existing)
        patch2 = {"age": 30, "preferences": {"language": "en"}}
        store.update_user_profile(user_id, patch2)
        
        # Load updated profile
        profile = store.load_user_profile(user_id)
        assert profile["name"] == "Bob"  # Preserved
        assert profile["age"] == 30  # Added
        assert profile["preferences"]["language"] == "en"  # Patched

    def test_delete_user_profile(self):
        """User profile should be deleted."""
        store = InMemoryMemoryStore()
        
        user_id = "user_to_delete"
        store.update_user_profile(user_id, {"data": "test"})
        
        # Verify profile exists
        assert store.load_user_profile(user_id) is not None
        
        # Delete profile
        store.delete_user_profile(user_id)
        
        # Profile should no longer exist
        assert store.load_user_profile(user_id) is None

    def test_delete_nonexistent_user_noop(self):
        """Deleting nonexistent user should be a no-op."""
        store = InMemoryMemoryStore()
        
        # Should not raise
        store.delete_user_profile("nonexistent_user")

    def test_session_and_user_isolation(self):
        """Session state and user profiles should be isolated."""
        store = InMemoryMemoryStore()
        
        # Create session
        store.save_session_state("session_1", {"session_data": "test"})
        
        # Create user profile
        store.update_user_profile("user_1", {"user_data": "test"})
        
        # Deleting session should not affect user
        store.delete_session_state("session_1")
        assert store.load_user_profile("user_1") is not None
        
        # Deleting user should not affect session (if recreated)
        store.save_session_state("session_2", {"session_data": "test2"})
        store.delete_user_profile("user_1")
        assert store.load_session_state("session_2") is not None


# ============================================================================
# TestVectorMemoryCore: Async VectorMemory tests
# ============================================================================


class TestVectorMemoryCore:
    """Test VectorMemory (core) async batching and eviction."""

    def test_initialization_with_defaults(self):
        """VectorMemory should initialize with default TTL and max_items."""
        memory = VectorMemory()
        
        assert memory.ttl_seconds == 60
        assert memory.max_items == 100
        assert len(memory._items) == 0

    def test_initialization_with_custom_params(self):
        """VectorMemory should accept custom TTL and max_items."""
        memory = VectorMemory(ttl_seconds=30, max_items=50)
        
        assert memory.ttl_seconds == 30
        assert memory.max_items == 50

    @pytest.mark.asyncio
    async def test_batch_upsert(self):
        """batch_upsert should store items with timestamps."""
        memory = VectorMemory(ttl_seconds=60, max_items=100)
        
        items = [
            {"id": "item_1", "data": "test1"},
            {"id": "item_2", "data": "test2"},
            {"id": "item_3", "data": "test3"},
        ]
        
        await memory.batch_upsert(items)
        
        # Items should be stored
        assert len(memory._items) == 3
        
        # Items should have timestamps
        for ts, item in memory._items:
            assert isinstance(ts, float)
            assert ts > 0

    @pytest.mark.asyncio
    async def test_similarity_search(self):
        """similarity_search should return items (simple retrieval)."""
        memory = VectorMemory()
        
        items = [
            {"id": "item_1", "text": "Python programming"},
            {"id": "item_2", "text": "JavaScript development"},
            {"id": "item_3", "text": "Docker containers"},
        ]
        
        await memory.batch_upsert(items)
        
        # Search with k=2
        results = await memory.similarity_search(query="test query", k=2)
        
        # Should return top 2 items
        assert len(results) == 2
        assert results[0]["id"] == "item_1"
        assert results[1]["id"] == "item_2"

    @pytest.mark.asyncio
    async def test_similarity_search_respects_k(self):
        """similarity_search should respect k parameter."""
        memory = VectorMemory()
        
        items = [{"id": f"item_{i}"} for i in range(10)]
        await memory.batch_upsert(items)
        
        # Search with different k values
        results_5 = await memory.similarity_search("query", k=5)
        results_3 = await memory.similarity_search("query", k=3)
        results_10 = await memory.similarity_search("query", k=10)
        
        assert len(results_5) == 5
        assert len(results_3) == 3
        assert len(results_10) == 10

    @pytest.mark.asyncio
    async def test_ttl_eviction(self):
        """Items should be evicted after TTL expires."""
        memory = VectorMemory(ttl_seconds=1, max_items=100)  # 1 second TTL
        
        items = [{"id": "item_1", "data": "test"}]
        await memory.batch_upsert(items)
        
        # Item should exist
        assert len(memory._items) == 1
        
        # Wait for TTL to expire
        await asyncio.sleep(1.5)
        
        # Trigger eviction via search
        results = await memory.similarity_search("query", k=5)
        
        # Items should be evicted
        assert len(results) == 0
        assert len(memory._items) == 0

    @pytest.mark.asyncio
    async def test_max_items_eviction(self):
        """Items should be evicted when max_items exceeded."""
        memory = VectorMemory(ttl_seconds=60, max_items=5)
        
        # Add 10 items (exceeds max_items)
        items = [{"id": f"item_{i}"} for i in range(10)]
        await memory.batch_upsert(items)
        
        # Should only keep last 5 items
        assert len(memory._items) == 5
        
        # Should keep most recent items
        remaining_ids = [item["id"] for _, item in memory._items]
        assert "item_5" in remaining_ids
        assert "item_6" in remaining_ids
        assert "item_7" in remaining_ids
        assert "item_8" in remaining_ids
        assert "item_9" in remaining_ids
        assert "item_0" not in remaining_ids
        assert "item_1" not in remaining_ids

    @pytest.mark.asyncio
    async def test_concurrent_access_with_locking(self):
        """Concurrent access should be thread-safe with async locking."""
        memory = VectorMemory()
        
        async def add_items(start_id: int):
            items = [{"id": f"item_{start_id}_{i}"} for i in range(10)]
            await memory.batch_upsert(items)
        
        # Run concurrent upserts
        await asyncio.gather(
            add_items(0),
            add_items(100),
            add_items(200),
        )
        
        # All items should be stored (30 total)
        assert len(memory._items) == 30

    @pytest.mark.asyncio
    async def test_eviction_combines_ttl_and_max_items(self):
        """Eviction should apply both TTL and max_items constraints."""
        memory = VectorMemory(ttl_seconds=2, max_items=5)
        
        # Add 3 items
        items1 = [{"id": f"old_{i}"} for i in range(3)]
        await memory.batch_upsert(items1)
        
        # Wait 1 second
        await asyncio.sleep(1)
        
        # Add 5 more items (total 8, exceeds max_items)
        items2 = [{"id": f"new_{i}"} for i in range(5)]
        await memory.batch_upsert(items2)
        
        # Should only keep last 5 items
        assert len(memory._items) == 5
        
        # Should keep newest items
        remaining_ids = [item["id"] for _, item in memory._items]
        assert all(item_id.startswith("new_") for item_id in remaining_ids)

    @pytest.mark.asyncio
    async def test_empty_similarity_search(self):
        """similarity_search on empty memory should return empty list."""
        memory = VectorMemory()
        
        results = await memory.similarity_search("query", k=5)
        
        assert results == []


# ============================================================================
# TestStateOwnershipBoundaries: State ownership tests
# ============================================================================


class TestStateOwnershipBoundaries:
    """Test state ownership boundaries per AGENTS.md Section 9."""

    def test_session_state_ephemeral(self):
        """Session state should be ephemeral (agent-owned)."""
        store = InMemoryMemoryStore()
        
        session_id = "ephemeral_session"
        state = {"request_data": "temp", "agent_internal": "state"}
        
        # Save session state
        store.save_session_state(session_id, state)
        
        # Session state exists
        assert store.load_session_state(session_id) is not None
        
        # After deletion (simulating agent shutdown), state is gone
        store.delete_session_state(session_id)
        assert store.load_session_state(session_id) is None
        
        # This demonstrates ephemeral nature (not persisted)

    def test_user_profile_persistent(self):
        """User profile should be persistent (memory-owned)."""
        store = InMemoryMemoryStore()
        
        user_id = "persistent_user"
        profile = {"learned_facts": ["fact1", "fact2"], "preferences": {}}
        
        # Update user profile
        store.update_user_profile(user_id, profile)
        
        # Profile persists across "sessions" (simulated restarts)
        assert store.load_user_profile(user_id) is not None
        
        # Profile can be updated multiple times (persistent)
        store.update_user_profile(user_id, {"new_fact": "fact3"})
        updated = store.load_user_profile(user_id)
        assert updated is not None
        assert "new_fact" in updated


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
