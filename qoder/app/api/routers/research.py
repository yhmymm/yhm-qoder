"""Research memory API router.

Provides endpoints for scope binding, draft management, memory confirmation,
revision, forgetting, and cross-session continuation.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from open_notebook.research.models import (
    ConfirmItemResult,
    ConfirmMemoriesRequest,
    ConfirmMemoriesResponse,
    CreateDraftRequest,
    DraftResponse,
    EnableResearchRequest,
    MemoryDetailResponse,
    MemoryItemResponse,
    MemoriesResponse,
    MemoryType,
    ReportRequest,
    ResumeRequest,
    ResumeResponse,
    RevisionsResponse,
    RevisionInfo,
    ScopeBindingResponse,
    UpdateDraftRequest,
    UpdateMemoryRequest,
    ResearchHealthResponse,
    TraceResponse,
)
from open_notebook.research.powercontext_client import (
    PowerContextError,
    get_powercontext_client,
)
from open_notebook.research import memory_service

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/health", response_model=ResearchHealthResponse)
async def research_health():
    """Check research feature readiness."""
    client = get_powercontext_client()
    pc_available = await client.health_check()
    return ResearchHealthResponse(
        enabled=True,
        powercontext_available=pc_available,
    )


@router.post("/notebooks/{notebook_id}/enable", response_model=ScopeBindingResponse)
async def enable_research(notebook_id: str):
    """Create or reuse a PowerContext scope binding for this notebook."""
    try:
        binding = await memory_service.get_or_create_scope_binding(notebook_id)
        return ScopeBindingResponse(
            notebook_id=notebook_id,
            scope_id=binding.get("scope_id"),
            status=binding.get("status", "ready"),
            created_at=str(binding.get("created_at", "")),
        )
    except PowerContextError as e:
        raise HTTPException(status_code=502, detail=f"PowerContext error: {e}")
    except Exception as e:
        logger.error(f"Failed to enable research for {notebook_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notebooks/{notebook_id}/memory-drafts", response_model=DraftResponse)
async def create_memory_draft(notebook_id: str, request: CreateDraftRequest):
    """Create a memory draft (manual or extract mode)."""
    try:
        # Validate scope binding exists
        scope_id = await memory_service.get_scope_id(notebook_id)
        if not scope_id:
            # Auto-create binding
            await memory_service.get_or_create_scope_binding(notebook_id)

        draft = await memory_service.create_draft(
            notebook_id=notebook_id,
            draft_type=request.draft_type,
            content=request.content,
            epistemic_status=request.epistemic_status.value,
            workflow_status=request.workflow_status.value,
            evidence_refs=[e.model_dump() for e in request.evidence_refs],
            mode=request.mode,
        )
        return DraftResponse(
            draft_id=draft.get("draft_id", str(draft.get("id", ""))),
            notebook_id=notebook_id,
            draft_type=draft.get("draft_type", request.draft_type.value),
            content=draft.get("content", request.content),
            epistemic_status=draft.get("epistemic_status", request.epistemic_status.value),
            workflow_status=draft.get("workflow_status", request.workflow_status.value),
            evidence_refs=draft.get("evidence_refs", []),
            draft_version=draft.get("draft_version", 1),
            status=draft.get("status", "draft"),
            mode=draft.get("mode", request.mode),
            created_at=str(draft.get("created_at", "")),
            updated_at=str(draft.get("updated_at", "")),
        )
    except Exception as e:
        logger.error(f"Failed to create draft: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/notebooks/{notebook_id}/memory-drafts/{draft_id}",
    response_model=DraftResponse,
)
async def update_memory_draft(
    notebook_id: str, draft_id: str, request: UpdateDraftRequest
):
    """Update a memory draft with optimistic concurrency."""
    try:
        updated = await memory_service.update_draft(
            notebook_id=notebook_id,
            draft_id=draft_id,
            expected_draft_version=request.expected_draft_version,
            content=request.content,
            draft_type=request.draft_type.value if request.draft_type else None,
            epistemic_status=request.epistemic_status.value if request.epistemic_status else None,
            workflow_status=request.workflow_status.value if request.workflow_status else None,
            evidence_refs=[e.model_dump() for e in request.evidence_refs]
            if request.evidence_refs is not None
            else None,
        )
        return DraftResponse(
            draft_id=updated.get("draft_id", draft_id),
            notebook_id=notebook_id,
            draft_type=updated.get("draft_type", ""),
            content=updated.get("content", ""),
            epistemic_status=updated.get("epistemic_status", ""),
            workflow_status=updated.get("workflow_status", ""),
            evidence_refs=updated.get("evidence_refs", []),
            draft_version=updated.get("draft_version", 1),
            status=updated.get("status", "draft"),
            mode=updated.get("mode", "manual"),
            created_at=str(updated.get("created_at", "")),
            updated_at=str(updated.get("updated_at", "")),
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update draft: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/notebooks/{notebook_id}/memory-confirmations",
    response_model=ConfirmMemoriesResponse,
)
async def confirm_memories(notebook_id: str, request: ConfirmMemoriesRequest):
    """Confirm selected drafts, writing them to PowerContext."""
    try:
        items = [item.model_dump() for item in request.items]
        result = await memory_service.confirm_memories(notebook_id, items)
        return result
    except PowerContextError as e:
        raise HTTPException(status_code=502, detail=f"PowerContext error: {e}")
    except Exception as e:
        logger.error(f"Failed to confirm memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notebooks/{notebook_id}/memories", response_model=MemoriesResponse)
async def list_memories(notebook_id: str):
    """List all active memories for a notebook from PowerContext."""
    try:
        result = await memory_service.list_memories(notebook_id)
        memories = [MemoryItemResponse(**m) for m in result["memories"]]
        return MemoriesResponse(
            scope_id=result["scope_id"] or "",
            memories=memories,
            trace_id=result["trace_id"],
        )
    except PowerContextError as e:
        raise HTTPException(status_code=502, detail=f"PowerContext error: {e}")
    except Exception as e:
        logger.error(f"Failed to list memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/notebooks/{notebook_id}/memories/{item_id}",
    response_model=MemoryDetailResponse,
)
async def get_memory_detail(notebook_id: str, item_id: str):
    """Get detailed view of one memory including ETag."""
    try:
        detail = await memory_service.get_memory_detail(notebook_id, item_id)
        return MemoryDetailResponse(**detail)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PowerContextError as e:
        raise HTTPException(status_code=502, detail=f"PowerContext error: {e}")
    except Exception as e:
        logger.error(f"Failed to get memory detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/notebooks/{notebook_id}/memories/{item_id}/revisions",
    response_model=RevisionsResponse,
)
async def list_memory_revisions(notebook_id: str, item_id: str):
    """List all revisions of a memory."""
    try:
        revisions = await memory_service.list_revisions(notebook_id, item_id)
        rev_infos = [
            RevisionInfo(
                revision=r.get("revision", 1),
                updated_at=r.get("updated_at"),
            )
            for r in revisions
        ]
        return RevisionsResponse(
            item_id=item_id,
            artifact_id=revisions[0].get("artifact_id", "") if revisions else "",
            revisions=rev_infos,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PowerContextError as e:
        raise HTTPException(status_code=502, detail=f"PowerContext error: {e}")
    except Exception as e:
        logger.error(f"Failed to list revisions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/notebooks/{notebook_id}/memories/{item_id}/revisions/{revision}",
)
async def get_memory_revision(notebook_id: str, item_id: str, revision: int):
    """Get a specific revision of a memory."""
    try:
        result = await memory_service.get_revision(notebook_id, item_id, revision)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PowerContextError as e:
        raise HTTPException(status_code=502, detail=f"PowerContext error: {e}")
    except Exception as e:
        logger.error(f"Failed to get revision: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/notebooks/{notebook_id}/memories/{item_id}")
async def update_memory(
    notebook_id: str, item_id: str, request: UpdateMemoryRequest
):
    """Update a confirmed memory (replaces PowerContext artifact)."""
    try:
        result = await memory_service.update_memory(
            notebook_id=notebook_id,
            item_id=item_id,
            content=request.content,
            if_match=request.if_match,
            epistemic_status=request.epistemic_status.value if request.epistemic_status else None,
            workflow_status=request.workflow_status.value if request.workflow_status else None,
            evidence_refs=[e.model_dump() for e in request.evidence_refs]
            if request.evidence_refs
            else None,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PowerContextError as e:
        status = 412 if e.status_code == 412 else 502
        raise HTTPException(status_code=status, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notebooks/{notebook_id}/memories/{item_id}/forget")
async def forget_memory(notebook_id: str, item_id: str):
    """Forget a memory (remove from active recall)."""
    try:
        result = await memory_service.forget_memory(notebook_id, item_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PowerContextError as e:
        raise HTTPException(status_code=502, detail=f"PowerContext error: {e}")
    except Exception as e:
        logger.error(f"Failed to forget memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notebooks/{notebook_id}/resume", response_model=ResumeResponse)
async def resume_research(notebook_id: str, request: ResumeRequest):
    """Create a new session and resume research from PowerContext memories."""
    trace_id = f"trace-{uuid.uuid4().hex[:12]}"

    try:
        # Get current memories
        memories_result = await memory_service.list_memories(notebook_id)
        memories = memories_result.get("memories", [])
        scope_id = memories_result.get("scope_id")

        if not scope_id:
            return ResumeResponse(
                trace_id=trace_id,
                reply="研究记忆尚未启用。请先为课题启用研究记忆功能。",
            )

        # Categorize memories
        goal = None
        conclusions = []
        open_questions = []
        next_steps = []
        memory_refs = []

        for m in memories:
            mtype = m.get("type", "")
            content = m.get("content", "")
            wf_status = m.get("workflow_status", "")

            memory_refs.append({
                "item_id": m.get("item_id"),
                "artifact_id": m.get("artifact_id"),
                "type": mtype,
                "revision": m.get("revision"),
            })

            if mtype == "goal":
                goal = content
            elif mtype == "conclusion":
                conclusions.append(content)
            elif mtype == "open_question":
                open_questions.append(content)
            elif mtype == "next_step":
                if wf_status != "completed":
                    next_steps.append(content)

        # Build reply
        parts = []
        if goal:
            parts.append(f"📌 当前研究目标：{goal}")
        else:
            parts.append("📌 尚未设定研究目标。")

        if conclusions:
            parts.append(f"\n📝 已记录的结论（{len(conclusions)} 条）：")
            for i, c in enumerate(conclusions[:5], 1):
                parts.append(f"  {i}. {c}")

        if open_questions:
            parts.append(f"\n❓ 未解决问题（{len(open_questions)} 条）：")
            for i, q in enumerate(open_questions[:5], 1):
                parts.append(f"  {i}. {q}")

        if next_steps:
            parts.append(f"\n🎯 建议的下一步（{len(next_steps)} 条）：")
            for i, s in enumerate(next_steps[:5], 1):
                parts.append(f"  {i}. {s}")
        elif not open_questions:
            parts.append("\n✅ 当前没有待解决的问题或计划。")

        if not memories:
            parts.append("\n💡 尚未保存任何研究记忆。请先导入资料并记录研究进展。")

        reply = "\n".join(parts)

        return ResumeResponse(
            trace_id=trace_id,
            session_id=request.session_id,
            reply=reply,
            goal=goal,
            conclusions=conclusions,
            open_questions=open_questions,
            next_steps=next_steps,
            memory_refs=memory_refs,
        )

    except PowerContextError as e:
        raise HTTPException(status_code=503, detail=f"记忆服务不可用：{e}")
    except Exception as e:
        logger.error(f"Failed to resume research: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/traces/{trace_id}", response_model=TraceResponse)
async def get_trace(trace_id: str):
    """Get trace details for audit."""
    from open_notebook.database.repository import repo_query

    results = await repo_query(
        "SELECT * FROM research_trace WHERE trace_id = $tid LIMIT 1",
        {"tid": trace_id},
    )
    if not results:
        raise HTTPException(status_code=404, detail="Trace not found")
    trace = results[0]
    return TraceResponse(
        trace_id=trace.get("trace_id", trace_id),
        events=trace.get("events", []),
        memory_refs=trace.get("memory_refs", []),
        evidence_refs=trace.get("evidence_refs", []),
        duration_ms=trace.get("duration_ms"),
        error_code=trace.get("error_code"),
    )
