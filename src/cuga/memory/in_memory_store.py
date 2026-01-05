from typing import Dict, Any, Optional

from .base import MemoryStore, SessionState, UserProfile, MemoryEvent


class InMemoryMemoryStore(MemoryStore):
    """
    A simple in-memory implementation of the MemoryStore.
    This store is ephemeral and will be cleared when the script exits. It is
    intended for use in examples, tests, and lightweight deployments.
    """

    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
        self._users: Dict[str, UserProfile] = {}
        print("--- Initialized InMemoryMemoryStore ---")

    def load_session_state(self, session_id: str) -> Optional[SessionState]:
        print(f"--- Loading state for session: {session_id} ---")
        return self._sessions.get(session_id)

    def save_session_state(self, session_id: str, state: SessionState) -> None:
        print(f"--- Saving state for session: {session_id} ---")
        self._sessions[session_id] = state

    def append_event(self, session_id: str, event: MemoryEvent) -> None:
        if session_id not in self._sessions:
            self._sessions[session_id] = {'history': []}
        self._sessions[session_id].setdefault('history', []).append(event)

    def load_user_profile(self, user_id: str) -> Optional[UserProfile]:
        return self._users.get(user_id)

    def update_user_profile(self, user_id: str, patch: Dict[str, Any]) -> None:
        if user_id not in self._users:
            self._users[user_id] = {}
        self._users[user_id].update(patch)

    def delete_session_state(self, session_id: str) -> None:
        if session_id in self._sessions:
            del self._sessions[session_id]

    def delete_user_profile(self, user_id: str) -> None:
        if user_id in self._users:
            del self._users[user_id]
