"""
Core Pydantic State Schema for PeerRing
Centralized state management with curriculum DAG, dialogue history, and policy levels
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Optional, Any, Union, Literal
from datetime import datetime
from enum import Enum
import uuid


class AgentType(str, Enum):
    """Agent types in the PeerRing system."""
    BOB_TUTOR = "bob-tutor"
    ALICE_ARITHMETIC = "alice-arithmetic"
    CHARLIE_CONCEPTUAL = "charlie-conceptual"
    LEAK_JUDGE = "leak-judge"
    HELP_JUDGE = "help-judge"
    POLICY_REWRITER = "policy-rewriter"


class MessageRole(str, Enum):
    """Message roles in dialogue history."""
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class RecoveryState(str, Enum):
    """Recovery state machine states."""
    NORMAL = "normal"
    SCAFFOLD = "scaffold"
    PREREQUISITE_REPAIR = "prerequisite_repair"
    MICRO_TEACHING = "micro_teaching"


class DialogueMessage(BaseModel):
    """Individual message in dialogue history."""
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: MessageRole
    agent_id: Optional[str] = None
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Agent-specific fields
    think_block: Optional[str] = None  # Pólya deliberation for agents
    blackboard_patch: Optional[str] = None  # KaTeX/SVG patches
    governance_flags: Dict[str, bool] = Field(default_factory=dict)  # Leak/help verdicts


class CandidateAction(BaseModel):
    """Agent candidate action for orchestrator scoring."""
    model_config = ConfigDict(frozen=True)

    agent_id: str
    action_type: Literal["respond", "question", "hint", "challenge"]
    pedagogical_utility: float = Field(ge=0.0, le=1.0)
    content_preview: str  # First 100 chars of proposed response
    cooldown_penalty: float = Field(ge=0.0, le=1.0, default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    """Complete agent response after generation."""
    model_config = ConfigDict(frozen=True)

    agent_id: str
    content: str
    think_block: Optional[str] = None
    blackboard_patch: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    tokens_used: int = 0
    generation_time_ms: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class JudgeVerdict(BaseModel):
    """Judge evaluation verdict for governance."""
    model_config = ConfigDict(frozen=True)

    judge_type: Literal["leak", "help", "adversarial"]
    verdict: bool  # True = passes, False = fails
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    violation_details: Optional[str] = None
    suggested_fixes: List[str] = Field(default_factory=list)
    evaluation_time_ms: int = 0


class CurriculumNode(BaseModel):
    """Individual concept node in curriculum DAG."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    concept_id: str
    name: str
    description: str
    mastery_score: float = Field(ge=0.0, le=1.0, default=0.0)

    # DAG relationships
    prerequisites: List[str] = Field(default_factory=list)  # concept_ids
    unlocks: List[str] = Field(default_factory=list)  # concept_ids

    # Learning metrics
    attempts: int = 0
    correct_attempts: int = 0
    last_practiced: Optional[datetime] = None
    struggle_indicators: Dict[str, float] = Field(default_factory=dict)


class AssistanceLevel(BaseModel):
    """6-level assistance ladder state."""
    current_level: int = Field(ge=1, le=6, default=1)
    level_names: List[str] = Field(default=[
        "Independent",
        "Gentle Nudge",
        "Guiding Question",
        "Worked Example",
        "Step-by-Step",
        "Direct Instruction"
    ])
    transitions_today: int = 0
    last_escalation: Optional[datetime] = None
    consecutive_errors: int = 0


class PolicyState(BaseModel):
    """Current policy and adaptive configuration."""
    assistance_level: AssistanceLevel = Field(default_factory=AssistanceLevel)
    recovery_state: RecoveryState = RecoveryState.NORMAL

    # Struggle detection
    struggle_score: float = Field(ge=0.0, le=1.0, default=0.0)
    stuck_threshold: float = Field(ge=0.0, le=1.0, default=0.7)

    # Agent cooldowns (prevents repetitive agent selection)
    agent_cooldowns: Dict[str, datetime] = Field(default_factory=dict)
    last_active_agent: Optional[str] = None

    # Governance settings
    strict_mode: bool = False  # Triggered by adversarial input detection
    leak_sensitivity: float = Field(ge=0.0, le=1.0, default=0.8)
    help_sensitivity: float = Field(ge=0.0, le=1.0, default=0.6)


class TurnLockStatus(BaseModel):
    """Redis turn lock state."""
    locked: bool = False
    lock_owner: Optional[str] = None
    lock_acquired_at: Optional[datetime] = None
    lock_ttl_seconds: int = 30


class PeerRingState(BaseModel):
    """
    Centralized state schema for the entire PeerRing system.
    This is the single source of truth, serialized to/from Redis.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Session identification
    session_id: str
    user_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    # Dialogue history
    messages: List[DialogueMessage] = Field(default_factory=list)
    current_step: int = 0  # Current step in curriculum

    # Curriculum and mastery tracking
    curriculum_dag: Dict[str, CurriculumNode] = Field(default_factory=dict)
    current_concept: Optional[str] = None
    target_solution: Optional[str] = None  # For leak detection

    # Policy and adaptive systems
    policy: PolicyState = Field(default_factory=PolicyState)

    # Turn management
    turn_lock: TurnLockStatus = Field(default_factory=TurnLockStatus)
    turn_count: int = 0

    # PRISM telemetry context
    prism_session_id: Optional[str] = None
    prism_trace_metadata: Dict[str, Any] = Field(default_factory=dict)

    # System metadata
    version: str = "0.1.0"
    foundation_layer: str = "core-contracts-and-state"

    def add_message(self, message: DialogueMessage) -> None:
        """Add a message to dialogue history and update timestamps."""
        self.messages.append(message)
        self.last_updated = datetime.utcnow()
        self.turn_count += 1

    def get_recent_messages(self, count: int = 5) -> List[DialogueMessage]:
        """Get the most recent N messages."""
        return self.messages[-count:] if self.messages else []

    def update_mastery(self, concept_id: str, success: bool) -> None:
        """Update mastery score for a curriculum concept."""
        if concept_id not in self.curriculum_dag:
            return

        node = self.curriculum_dag[concept_id]
        node.attempts += 1
        if success:
            node.correct_attempts += 1

        # Recalculate mastery score (simple success rate for now)
        node.mastery_score = node.correct_attempts / node.attempts
        node.last_practiced = datetime.utcnow()
        self.last_updated = datetime.utcnow()

    def calculate_struggle_score(self) -> float:
        """Calculate composite struggle score across active concepts."""
        if not self.curriculum_dag or not self.current_concept:
            return 0.0

        current_node = self.curriculum_dag.get(self.current_concept)
        if not current_node:
            return 0.0

        # Simple struggle calculation (can be enhanced by usm)
        if current_node.attempts == 0:
            return 0.0

        failure_rate = 1.0 - (current_node.correct_attempts / current_node.attempts)
        consecutive_failures = self.policy.assistance_level.consecutive_errors

        # Weight recent performance more heavily
        struggle = (failure_rate * 0.7) + (min(consecutive_failures / 3, 1.0) * 0.3)

        self.policy.struggle_score = min(struggle, 1.0)
        return self.policy.struggle_score

    def is_locked(self) -> bool:
        """Check if session is currently locked for turn processing."""
        return self.turn_lock.locked

    def acquire_lock(self, owner: str) -> bool:
        """Acquire turn lock (Redis implementation will override this)."""
        if self.turn_lock.locked:
            return False

        self.turn_lock.locked = True
        self.turn_lock.lock_owner = owner
        self.turn_lock.lock_acquired_at = datetime.utcnow()
        return True

    def release_lock(self) -> None:
        """Release turn lock."""
        self.turn_lock.locked = False
        self.turn_lock.lock_owner = None
        self.turn_lock.lock_acquired_at = None