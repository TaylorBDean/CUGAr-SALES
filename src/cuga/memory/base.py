from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

# Placeholder data structures. These will be fleshed out with more specific fields.
SessionState = Dict[str, Any]
UserProfile = Dict[str, Any]
MemoryEvent = Dict[str, Any]


class MemoryStore(ABC):
    """
    Abstract base class for memory storage.

    This interface defines the contract for loading, saving, and managing
    session-level and long-term user state for the agent system.
    """

    @abstractmethod
    def load_session_state(self, session_id: str) -> Optional[SessionState]:
        """Loads the conversational state for a given session."""
        ...

    @abstractmethod
    def save_session_state(self, session_id: str, state: SessionState) -> None:
        """Saves the entire conversational state for a given session."""
        ...

    @abstractmethod
    def append_event(self, session_id: str, event: MemoryEvent) -> None:
        """Appends a new event to the session's history."""
        ...

    @abstractmethod
    def load_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """Loads the long-term profile for a given user."""
        ...

    @abstractmethod
    def update_user_profile(self, user_id: str, patch: Dict[str, Any]) -> None:
        """Updates (patches) the long-term profile for a given user."""
        ...

    @abstractmethod
    def delete_session_state(self, session_id: str) -> None:
        """Deletes the conversational state for a given session."""
        ...

    @abstractmethod
    def delete_user_profile(self, user_id: str) -> None:
        """Deletes the long-term profile for a given user."""
        ...
