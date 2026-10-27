"""Business models for research memory.

Defines the four research memory types, evidence references,
and the research-memory.v1 business JSON structure that gets
serialized into PowerContext Atomic Memory text field.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MemoryType(str, Enum):
    """Four research memory types."""

    GOAL = "goal"
    CONCLUSION = "conclusion"
    OPEN_QUESTION = "open_question"
    NEXT_STEP = "next_step"


# Mapping to PowerContext Atomic Memory kind
MEMORY_TYPE_TO_KIND: Dict[str, str] = {
    "goal": "research.goal",
    "conclusion": "research.conclusion",
    "open_question": "research.open_question",
    "next_step": "research.next_step",
}

KIND_TO_MEMORY_TYPE: Dict[str, str] = {v: k for k, v in MEMORY_TYPE_TO_KIND.items()}


class EpistemicStatus(str, Enum):
    """How the claim is supported."""

    SUPPORTED = "supported"  # has checkable evidence (not scientific proof)
    HYPOTHESIS = "hypothesis"
    USER_STATEMENT = "user_statement"


class WorkflowStatus(str, Enum):
    """Business progress for questions and plans."""

    OPEN = "open"
    COMPLETED = "completed"
    NOT_APPLICABLE = "not_applicable"


class DraftStatus(str, Enum):
    """Lifecycle of a memory candidate."""

    DRAFT = "draft"
    CONFIRMING = "confirming"
    COMMITTED = "committed"
    REJECTED = "rejected"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


class OperationType(str, Enum):
    """Types of operations we log."""

    CREATE_SCOPE = "create_scope"
    CAPTURE_SOURCE = "capture_source"
    CREATE_MEMORY = "create_memory"
    UPDATE_MEMORY = "update_memory"
    FORGET_MEMORY = "forget_memory"
    READ_MEMORIES = "read_memories"
    SEARCH_MEMORIES = "search_memories"


class OperationStatus(str, Enum):
    """Outcome of an operation."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


class BindingStatus(str, Enum):
    """Scope binding lifecycle."""

    PROVISIONING = "provisioning"
    READY = "ready"
    FAILED = "failed"


class EvidenceKind(str, Enum):
    """Where the evidence comes from."""

    SOURCE = "source"
    NOTE = "note"
    CHAT_MESSAGE = "chat_message"
    MANUAL_INPUT = "manual_input"


class Locator(BaseModel):
    """Position within source text."""

    char_start: Optional[int] = None
    char_end: Optional[int] = None
    chunk_id: Optional[str] = None


class EvidenceRef(BaseModel):
    """A piece of evidence supporting a memory claim."""

    kind: EvidenceKind
    resource_id: str  # e.g. "source:abc123", "note:xyz"
    content_sha256: Optional[str] = None
    locator: Optional[Locator] = None
    quote: Optional[str] = None

    @classmethod
    def compute_sha256(cls, text: str) -> str:
        """Compute NFC-normalised SHA-256 fingerprint."""
        normalised = unicodedata.normalize("NFC", text)
        return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


class ConfirmationSourceRef(BaseModel):
    """Reference to the PowerContext content source for the confirmation event."""

    source_type: Literal["content"] = "content"
    source_id: str


class ResearchMemoryItem(BaseModel):
    """The research-memory.v1 business JSON structure.

    This is what gets serialized into PowerContext Atomic Memory text field.
    """

    schema_version: Literal["research-memory.v1"] = "research-memory.v1"
    item_id: str = Field(default_factory=lambda: f"mem-{uuid4().hex[:12]}")
    operation_id: str
    type: MemoryType
    content: str
    epistemic_status: EpistemicStatus = EpistemicStatus.USER_STATEMENT
    workflow_status: WorkflowStatus = WorkflowStatus.NOT_APPLICABLE
    evidence_refs: List[EvidenceRef] = Field(default_factory=list)
    confirmation_source_ref: Optional[ConfirmationSourceRef] = None
    confirmed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_text(self) -> str:
        """Serialize to JSON string for PowerContext text field."""
        return self.model_dump_json(exclude_none=True)

    @classmethod
    def from_text(cls, text: str) -> "ResearchMemoryItem":
        """Deserialize from PowerContext text field."""
        data = json.loads(text)
        return cls.model_validate(data)

    def validate_byte_size(self, max_bytes: int = 8192) -> None:
        """Check NFC-normalised text fits within byte limit."""
        text = self.to_text()
        normalised = unicodedata.normalize("NFC", text)
        byte_len = len(normalised.encode("utf-8"))
        if byte_len > max_bytes:
            raise ValueError(
                f"Memory text exceeds {max_bytes} bytes after NFC normalization "
                f"(actual: {byte_len}). Please shorten or split the entry."
            )


# --- API request/response models ---


class EnableResearchRequest(BaseModel):
    """Request to enable research memory for a notebook."""

    pass  # No additional fields needed; uses notebook_id from path


class CreateDraftRequest(BaseModel):
    """Create a memory draft (manual or extract mode)."""

    mode: Literal["manual", "extract"] = "manual"
    draft_type: MemoryType
    content: str
    epistemic_status: EpistemicStatus = EpistemicStatus.USER_STATEMENT
    workflow_status: WorkflowStatus = WorkflowStatus.NOT_APPLICABLE
    evidence_refs: List[EvidenceRef] = Field(default_factory=list)
    # For extract mode
    source_ids: List[str] = Field(default_factory=list)
    note_ids: List[str] = Field(default_factory=list)
    session_id: Optional[str] = None
    message_range: Optional[Dict[str, Any]] = None


class UpdateDraftRequest(BaseModel):
    """Update a memory draft."""

    content: Optional[str] = None
    draft_type: Optional[MemoryType] = None
    epistemic_status: Optional[EpistemicStatus] = None
    workflow_status: Optional[WorkflowStatus] = None
    evidence_refs: Optional[List[EvidenceRef]] = None
    expected_draft_version: int


class ConfirmItemRequest(BaseModel):
    """One item in a confirmation batch."""

    draft_id: str
    draft_version: int
    operation_id: str = Field(default_factory=lambda: f"op-{uuid4().hex[:12]}")


class ConfirmMemoriesRequest(BaseModel):
    """Batch confirmation request."""

    items: List[ConfirmItemRequest]


class UpdateMemoryRequest(BaseModel):
    """Update a confirmed memory (maps to PowerContext artifact replace)."""

    content: str
    epistemic_status: Optional[EpistemicStatus] = None
    workflow_status: Optional[WorkflowStatus] = None
    evidence_refs: Optional[List[EvidenceRef]] = None
    if_match: str  # ETag from PowerContext


class ResumeRequest(BaseModel):
    """Request to resume research from a new session."""

    session_id: Optional[str] = None
    query: Optional[str] = None


class ReportRequest(BaseModel):
    """Request to generate a meeting report."""

    title: Optional[str] = None
    session_id: Optional[str] = None


# --- Response models ---


class ScopeBindingResponse(BaseModel):
    """Scope binding status."""

    notebook_id: str
    scope_id: Optional[str] = None
    status: str
    created_at: Optional[str] = None


class DraftResponse(BaseModel):
    """Draft response."""

    draft_id: str
    notebook_id: str
    draft_type: str
    content: str
    epistemic_status: str
    workflow_status: str
    evidence_refs: List[Dict[str, Any]]
    draft_version: int
    status: str
    mode: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ConfirmItemResult(BaseModel):
    """Result of confirming one draft."""

    draft_id: str
    status: str  # committed / failed / uncertain
    item_id: Optional[str] = None
    artifact_id: Optional[str] = None
    revision: Optional[int] = None
    error: Optional[str] = None


class ConfirmMemoriesResponse(BaseModel):
    """Batch confirmation result."""

    trace_id: str
    items: List[ConfirmItemResult]


class MemoryItemResponse(BaseModel):
    """A single active memory from PowerContext."""

    item_id: str
    type: str
    content: str
    epistemic_status: str
    workflow_status: str
    evidence_refs: List[Dict[str, Any]]
    artifact_id: str
    revision: int
    state: str
    state_version: int
    etag: Optional[str] = None
    confirmed_at: Optional[str] = None


class MemoriesResponse(BaseModel):
    """List of current memories grouped by type."""

    scope_id: str
    memories: List[MemoryItemResponse]
    trace_id: str


class MemoryDetailResponse(BaseModel):
    """Detailed view of one memory."""

    item_id: str
    type: str
    content: str
    epistemic_status: str
    workflow_status: str
    evidence_refs: List[Dict[str, Any]]
    artifact_id: str
    revision: int
    state: str
    state_version: int
    etag: Optional[str] = None
    confirmed_at: Optional[str] = None
    confirmation_source_ref: Optional[Dict[str, Any]] = None


class RevisionInfo(BaseModel):
    """Info about one revision."""

    revision: int
    updated_at: Optional[str] = None


class RevisionsResponse(BaseModel):
    """List of revisions for a memory."""

    item_id: str
    artifact_id: str
    revisions: List[RevisionInfo]


class ResumeResponse(BaseModel):
    """Response from resume (cross-session continuation)."""

    trace_id: str
    session_id: Optional[str] = None
    reply: str
    goal: Optional[str] = None
    conclusions: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    memory_refs: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_refs: List[Dict[str, Any]] = Field(default_factory=list)


class TraceResponse(BaseModel):
    """Trace details."""

    trace_id: str
    events: List[Dict[str, Any]]
    memory_refs: List[Dict[str, Any]]
    evidence_refs: List[Dict[str, Any]]
    duration_ms: Optional[int] = None
    error_code: Optional[str] = None


class ResearchHealthResponse(BaseModel):
    """Research feature health status."""

    enabled: bool
    powercontext_available: bool
    binding_status: Optional[str] = None
    scope_id: Optional[str] = None


class ExtractCandidateRequest(BaseModel):
    """Request to extract candidates from sources/notes."""

    source_ids: List[str] = Field(default_factory=list)
    note_ids: List[str] = Field(default_factory=list)
    session_id: Optional[str] = None
    user_instruction: Optional[str] = None
    model_id: Optional[str] = None


class ExtractCandidateItem(BaseModel):
    """A single extracted candidate."""

    type: str
    content: str
    epistemic_status: str
    evidence_refs: List[Dict[str, Any]] = Field(default_factory=list)
    validation_error: Optional[str] = None


class ExtractCandidateResponse(BaseModel):
    """Response from candidate extraction."""

    trace_id: str
    candidates: List[ExtractCandidateItem]
    fragment_count: int
    model_used: Optional[str] = None


class ReportResponse(BaseModel):
    """Response from report generation."""

    report_id: str
    trace_id: str
    title: str
    content: str
    memory_refs: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_refs: List[Dict[str, Any]] = Field(default_factory=list)
    omitted_items: List[Dict[str, Any]] = Field(default_factory=list)
    note_id: Optional[str] = None
