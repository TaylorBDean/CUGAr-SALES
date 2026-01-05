"""
Canonical Audit Trail for Routing and Planning Decisions

This module provides persistent audit logging for all routing and planning
decisions with full traceability and reasoning.

Key Features:
1. Immutable decision records with timestamps
2. Persistent storage (JSON/SQLite backends)
3. Query interface for decision history
4. Integration with RoutingAuthority and PlanningAuthority

See docs/orchestrator/AUDIT_TRAIL.md for detailed architecture.
"""

from __future__ import annotations

import json
import os
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .planning import Plan, PlanStep, PlanningStage, ToolBudget
from .routing import RoutingDecision


@dataclass(frozen=True)
class DecisionRecord:
    """
    Immutable record of a single routing or planning decision.
    
    Captures who/what/when/why for complete auditability.
    """
    
    record_id: str                             # Unique record identifier
    timestamp: str                             # ISO 8601 timestamp
    trace_id: str                              # Execution trace ID
    decision_type: str                         # "routing" or "planning"
    stage: str                                 # Lifecycle stage
    target: str                                # Selected target (agent/worker/tool)
    reason: str                                # Human-readable justification
    alternatives: List[str] = field(default_factory=list)
    confidence: float = 1.0                    # Confidence score (0.0-1.0)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DecisionRecord:
        """Create record from dictionary."""
        return cls(**data)
    
    @classmethod
    def from_routing_decision(
        cls,
        decision: RoutingDecision,
        trace_id: str,
        stage: str = "route",
    ) -> DecisionRecord:
        """Create decision record from routing decision."""
        import uuid
        
        return cls(
            record_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            trace_id=trace_id,
            decision_type="routing",
            stage=stage,
            target=decision.selected.id,
            reason=decision.reason,
            alternatives=[c.id for c in decision.alternatives],
            confidence=decision.confidence,
            metadata={
                "strategy": decision.strategy.value,
                "decision_type": decision.decision_type.value,
                "selected_name": decision.selected.name,
                "selected_type": decision.selected.type,
                **decision.metadata,
            },
        )
    
    @classmethod
    def from_plan(
        cls,
        plan: Plan,
        stage: str = "plan",
    ) -> DecisionRecord:
        """Create decision record from plan."""
        import uuid
        
        return cls(
            record_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            trace_id=plan.trace_id,
            decision_type="planning",
            stage=stage,
            target=plan.plan_id,
            reason=f"Created plan with {len(plan.steps)} steps for goal: {plan.goal[:50]}...",
            alternatives=[],
            confidence=1.0,
            metadata={
                "plan_stage": plan.stage.value,
                "step_count": len(plan.steps),
                "estimated_cost": plan.estimated_total_cost(),
                "estimated_tokens": plan.estimated_total_tokens(),
                "budget_ceiling": plan.budget.cost_ceiling,
                **plan.metadata,
            },
        )
    
    @classmethod
    def from_plan_step(
        cls,
        plan_id: str,
        trace_id: str,
        step: PlanStep,
        stage: str = "plan_step",
    ) -> DecisionRecord:
        """Create decision record from plan step."""
        import uuid
        
        return cls(
            record_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            trace_id=trace_id,
            decision_type="planning",
            stage=stage,
            target=step.tool,
            reason=step.reason or f"Selected {step.tool} for step {step.index}",
            alternatives=[],
            confidence=1.0,
            metadata={
                "plan_id": plan_id,
                "step_name": step.name,
                "step_index": step.index,
                "estimated_cost": step.estimated_cost,
                "estimated_tokens": step.estimated_tokens,
                "worker": step.worker,
                **step.metadata,
            },
        )


class AuditBackend(ABC):
    """Abstract audit storage backend."""
    
    @abstractmethod
    def store_record(self, record: DecisionRecord) -> None:
        """Store decision record."""
        ...
    
    @abstractmethod
    def query_by_trace(self, trace_id: str) -> List[DecisionRecord]:
        """Query records by trace ID."""
        ...
    
    @abstractmethod
    def query_by_type(
        self,
        decision_type: str,
        limit: int = 100,
    ) -> List[DecisionRecord]:
        """Query records by decision type."""
        ...
    
    @abstractmethod
    def query_recent(self, limit: int = 100) -> List[DecisionRecord]:
        """Query most recent records."""
        ...


class JSONAuditBackend(AuditBackend):
    """
    JSON file-based audit backend.
    
    Stores decision records as JSON lines in a file. Simple but
    not suitable for high-volume production use.
    """
    
    def __init__(self, file_path: Path | str):
        """
        Initialize JSON audit backend.
        
        Args:
            file_path: Path to JSON audit file
        """
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
    
    def store_record(self, record: DecisionRecord) -> None:
        """Append record to JSON file."""
        with open(self.file_path, "a") as f:
            f.write(json.dumps(record.to_dict()) + "\n")
    
    def _read_records(self) -> List[DecisionRecord]:
        """Read all records from file."""
        if not self.file_path.exists():
            return []
        
        records: List[DecisionRecord] = []
        with open(self.file_path, "r") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    records.append(DecisionRecord.from_dict(data))
        return records
    
    def query_by_trace(self, trace_id: str) -> List[DecisionRecord]:
        """Query records by trace ID."""
        records = self._read_records()
        return [r for r in records if r.trace_id == trace_id]
    
    def query_by_type(
        self,
        decision_type: str,
        limit: int = 100,
    ) -> List[DecisionRecord]:
        """Query records by decision type."""
        records = self._read_records()
        filtered = [r for r in records if r.decision_type == decision_type]
        return filtered[-limit:]
    
    def query_recent(self, limit: int = 100) -> List[DecisionRecord]:
        """Query most recent records."""
        records = self._read_records()
        return records[-limit:]


class SQLiteAuditBackend(AuditBackend):
    """
    SQLite-based audit backend.
    
    Stores decision records in SQLite database with indexed queries.
    Suitable for production use with moderate volume.
    """
    
    def __init__(self, db_path: Path | str):
        """
        Initialize SQLite audit backend.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                record_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                stage TEXT NOT NULL,
                target TEXT NOT NULL,
                reason TEXT NOT NULL,
                alternatives TEXT,
                confidence REAL,
                metadata TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trace_id ON decisions(trace_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_decision_type ON decisions(decision_type)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON decisions(timestamp)
        """)
        
        conn.commit()
        conn.close()
    
    def store_record(self, record: DecisionRecord) -> None:
        """Store record in database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT INTO decisions (
                record_id, timestamp, trace_id, decision_type, stage,
                target, reason, alternatives, confidence, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                record.record_id,
                record.timestamp,
                record.trace_id,
                record.decision_type,
                record.stage,
                record.target,
                record.reason,
                json.dumps(record.alternatives),
                record.confidence,
                json.dumps(record.metadata),
            ),
        )
        
        conn.commit()
        conn.close()
    
    def _row_to_record(self, row: tuple) -> DecisionRecord:
        """Convert database row to DecisionRecord."""
        return DecisionRecord(
            record_id=row[0],
            timestamp=row[1],
            trace_id=row[2],
            decision_type=row[3],
            stage=row[4],
            target=row[5],
            reason=row[6],
            alternatives=json.loads(row[7]) if row[7] else [],
            confidence=row[8] if row[8] is not None else 1.0,
            metadata=json.loads(row[9]) if row[9] else {},
        )
    
    def query_by_trace(self, trace_id: str) -> List[DecisionRecord]:
        """Query records by trace ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT * FROM decisions WHERE trace_id = ? ORDER BY timestamp
        """,
            (trace_id,),
        )
        
        records = [self._row_to_record(row) for row in cursor.fetchall()]
        conn.close()
        return records
    
    def query_by_type(
        self,
        decision_type: str,
        limit: int = 100,
    ) -> List[DecisionRecord]:
        """Query records by decision type."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT * FROM decisions 
            WHERE decision_type = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """,
            (decision_type, limit),
        )
        
        records = [self._row_to_record(row) for row in cursor.fetchall()]
        conn.close()
        return records
    
    def query_recent(self, limit: int = 100) -> List[DecisionRecord]:
        """Query most recent records."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT * FROM decisions ORDER BY timestamp DESC LIMIT ?
        """,
            (limit,),
        )
        
        records = [self._row_to_record(row) for row in cursor.fetchall()]
        conn.close()
        return records


class AuditTrail:
    """
    High-level audit trail interface.
    
    Provides convenient methods for recording and querying routing
    and planning decisions with automatic backend management.
    """
    
    def __init__(
        self,
        backend: Optional[AuditBackend] = None,
        backend_type: str = "json",
        storage_path: Optional[Path | str] = None,
    ):
        """
        Initialize audit trail.
        
        Args:
            backend: Explicit backend instance (overrides backend_type/storage_path)
            backend_type: Backend type ("json" or "sqlite")
            storage_path: Storage path (default: ./audit/decisions.{json|db})
        """
        if backend is not None:
            self.backend = backend
        else:
            if storage_path is None:
                if backend_type == "sqlite":
                    storage_path = Path("audit/decisions.db")
                else:
                    storage_path = Path("audit/decisions.jsonl")
            
            if backend_type == "sqlite":
                self.backend = SQLiteAuditBackend(storage_path)
            else:
                self.backend = JSONAuditBackend(storage_path)
    
    def record_routing_decision(
        self,
        decision: RoutingDecision,
        trace_id: str,
        stage: str = "route",
    ) -> DecisionRecord:
        """Record routing decision to audit trail."""
        record = DecisionRecord.from_routing_decision(decision, trace_id, stage)
        self.backend.store_record(record)
        return record
    
    def record_plan(
        self,
        plan: Plan,
        stage: str = "plan",
    ) -> DecisionRecord:
        """Record plan creation to audit trail."""
        record = DecisionRecord.from_plan(plan, stage)
        self.backend.store_record(record)
        return record
    
    def record_plan_step(
        self,
        plan_id: str,
        trace_id: str,
        step: PlanStep,
        stage: str = "plan_step",
    ) -> DecisionRecord:
        """Record individual plan step to audit trail."""
        record = DecisionRecord.from_plan_step(plan_id, trace_id, step, stage)
        self.backend.store_record(record)
        return record
    
    def get_trace_history(self, trace_id: str) -> List[DecisionRecord]:
        """Get all decisions for a trace."""
        return self.backend.query_by_trace(trace_id)
    
    def get_routing_history(self, limit: int = 100) -> List[DecisionRecord]:
        """Get recent routing decisions."""
        return self.backend.query_by_type("routing", limit)
    
    def get_planning_history(self, limit: int = 100) -> List[DecisionRecord]:
        """Get recent planning decisions."""
        return self.backend.query_by_type("planning", limit)
    
    def get_recent(self, limit: int = 100) -> List[DecisionRecord]:
        """Get most recent decisions."""
        return self.backend.query_recent(limit)


# Convenience function for creating default audit trail
def create_audit_trail(
    backend_type: str = "sqlite",
    storage_path: Optional[Path | str] = None,
) -> AuditTrail:
    """
    Create audit trail with default configuration.
    
    Args:
        backend_type: Backend type ("json" or "sqlite")
        storage_path: Storage path (default based on backend_type)
        
    Returns:
        Configured AuditTrail instance
    """
    # Use environment variable if available
    env_path = os.environ.get("CUGA_AUDIT_PATH")
    if env_path:
        storage_path = Path(env_path)
    
    return AuditTrail(backend_type=backend_type, storage_path=storage_path)
