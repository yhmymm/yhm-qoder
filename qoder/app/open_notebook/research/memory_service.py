"""Memory service for research memory.

Handles scope binding, draft management, confirmation, revision,
forgetting, and deduplication. All PowerContext interactions go through
the adapter client.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.research.models import (
    BindingStatus,
    ConfirmItemResult,
    ConfirmMemoriesResponse,
    DraftStatus,
    EvidenceRef,
    MemoryType,
    MEMORY_TYPE_TO_KIND,
    KIND_TO_MEMORY_TYPE,
    OperationStatus,
    OperationType,
    ResearchMemoryItem,
    WorkflowStatus,
)
from open_notebook.research.powercontext_client import (
    PowerContextClient,
    PowerContextError,
    get_powercontext_client,
)


async def get_deployment_uuid() -> str:
    """Get or create the deployment UUID for idempotency keys."""
    results = await repo_query("SELECT * FROM research_deployment_config LIMIT 1")
    if results:
        return results[0].get("deployment_uuid", str(uuid.uuid4()))
    # Create if missing
    new_uuid = str(uuid.uuid4())
    await repo_query(
        "CREATE research_deployment_config SET deployment_uuid = $uuid, created_at = time::now()",
        {"uuid": new_uuid},
    )
    return new_uuid


async def get_or_create_scope_binding(notebook_id: str) -> Dict[str, Any]:
    """Get existing scope binding or create a new one.

    Uses stable idempotency_key = deployment_uuid + notebook_id.
    """
    nb_record = ensure_record_id(notebook_id)

    # Check existing binding
    existing = await repo_query(
        "SELECT * FROM research_scope_binding WHERE notebook_id = $nb_id LIMIT 1",
        {"nb_id": nb_record},
    )
    if existing:
        binding = existing[0]
        if binding.get("status") == BindingStatus.READY:
            return binding
        # If failed, retry with same idempotency key
        if binding.get("status") == BindingStatus.FAILED:
            return await _retry_scope_binding(binding)
        return binding

    # Create new binding
    deployment_uuid = await get_deployment_uuid()
    idempotency_key = f"{deployment_uuid}:{notebook_id}"

    client = get_powercontext_client()

    # Get notebook details for title
    nb_info = await repo_query("SELECT name, description FROM $nb_id", {"nb_id": nb_record})
    title = "Research Topic"
    summary = ""
    if nb_info:
        title = nb_info[0].get("name") or title
        summary = nb_info[0].get("description") or summary

    try:
        scope_result = await client.create_scope(
            title=f"Research: {title}",
            summary=summary or f"Research memory for {title}",
            idempotency_key=idempotency_key,
        )
        scope_id = scope_result.get("scope_id")
        if not scope_id:
            raise PowerContextError("PowerContext did not return scope_id")

        # Store binding
        result = await repo_query(
            """
            CREATE research_scope_binding SET
                notebook_id = $nb_id,
                deployment_uuid = $dep_uuid,
                scope_id = $scope_id,
                status = 'ready',
                created_at = time::now(),
                updated_at = time::now()
            """,
            {
                "nb_id": nb_record,
                "dep_uuid": deployment_uuid,
                "scope_id": scope_id,
            },
        )
        logger.info(f"Created scope binding: notebook={notebook_id}, scope={scope_id}")
        return result[0] if result else {"scope_id": scope_id, "status": "ready"}

    except PowerContextError as e:
        logger.error(f"Failed to create scope: {e}")
        # Store failed binding for retry
        await repo_query(
            """
            CREATE research_scope_binding SET
                notebook_id = $nb_id,
                deployment_uuid = $dep_uuid,
                scope_id = '',
                status = 'failed',
                created_at = time::now(),
                updated_at = time::now()
            """,
            {"nb_id": nb_record, "dep_uuid": deployment_uuid},
        )
        raise


async def _retry_scope_binding(binding: Dict[str, Any]) -> Dict[str, Any]:
    """Retry a failed scope binding."""
    notebook_id = str(binding.get("notebook_id", ""))
    deployment_uuid = binding.get("deployment_uuid", await get_deployment_uuid())
    idempotency_key = f"{deployment_uuid}:{notebook_id}"

    client = get_powercontext_client()
    nb_record = ensure_record_id(notebook_id)

    nb_info = await repo_query("SELECT name FROM $nb_id", {"nb_id": nb_record})
    title = nb_info[0].get("name", "Research Topic") if nb_info else "Research Topic"

    scope_result = await client.create_scope(
        title=f"Research: {title}",
        summary=f"Research memory for {title}",
        idempotency_key=idempotency_key,
    )
    scope_id = scope_result.get("scope_id")

    await repo_query(
        """
        UPDATE research_scope_binding SET
            scope_id = $scope_id,
            status = 'ready',
            updated_at = time::now()
        WHERE notebook_id = $nb_id
        """,
        {"nb_id": nb_record, "scope_id": scope_id},
    )
    return {"scope_id": scope_id, "status": "ready", "notebook_id": notebook_id}


async def get_scope_id(notebook_id: str) -> Optional[str]:
    """Get the scope_id for a notebook, or None if not bound."""
    nb_record = ensure_record_id(notebook_id)
    results = await repo_query(
        "SELECT scope_id, status FROM research_scope_binding WHERE notebook_id = $nb_id LIMIT 1",
        {"nb_id": nb_record},
    )
    if results and results[0].get("status") == "ready":
        return results[0].get("scope_id")
    return None


# --- Draft operations ---


async def create_draft(
    notebook_id: str,
    draft_type: MemoryType,
    content: str,
    epistemic_status: str = "user_statement",
    workflow_status: str = "not_applicable",
    evidence_refs: Optional[List[Dict]] = None,
    mode: str = "manual",
) -> Dict[str, Any]:
    """Create a memory draft."""
    nb_record = ensure_record_id(notebook_id)
    result = await repo_query(
        """
        CREATE research_memory_draft SET
            notebook_id = $nb_id,
            draft_type = $dtype,
            content = $content,
            epistemic_status = $epist,
            workflow_status = $wfstat,
            evidence_refs = $erefs,
            draft_version = 1,
            status = 'draft',
            mode = $mode,
            created_at = time::now(),
            updated_at = time::now()
        """,
        {
            "nb_id": nb_record,
            "dtype": draft_type.value,
            "content": content,
            "epist": epistemic_status,
            "wfstat": workflow_status,
            "erefs": evidence_refs or [],
            "mode": mode,
        },
    )
    draft = result[0] if result else {}
    draft["draft_id"] = str(draft.get("id", ""))
    return draft


async def update_draft(
    notebook_id: str,
    draft_id: str,
    expected_draft_version: int,
    content: Optional[str] = None,
    draft_type: Optional[str] = None,
    epistemic_status: Optional[str] = None,
    workflow_status: Optional[str] = None,
    evidence_refs: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """Update a draft with optimistic concurrency."""
    nb_record = ensure_record_id(notebook_id)
    draft_record = ensure_record_id(draft_id)

    # Check current version
    existing = await repo_query(
        "SELECT * FROM $draft_id WHERE notebook_id = $nb_id",
        {"draft_id": draft_record, "nb_id": nb_record},
    )
    if not existing:
        raise ValueError("Draft not found or does not belong to this notebook")
    current = existing[0]
    if current.get("draft_version") != expected_draft_version:
        raise ValueError(
            f"Draft version mismatch: expected {expected_draft_version}, "
            f"got {current.get('draft_version')}"
        )

    new_version = current.get("draft_version", 1) + 1
    updates = ["draft_version = $new_ver", "updated_at = time::now()"]
    params: Dict[str, Any] = {"draft_id": draft_record, "new_ver": new_version}

    if content is not None:
        updates.append("content = $content")
        params["content"] = content
    if draft_type is not None:
        updates.append("draft_type = $dtype")
        params["dtype"] = draft_type
    if epistemic_status is not None:
        updates.append("epistemic_status = $epist")
        params["epist"] = epistemic_status
    if workflow_status is not None:
        updates.append("workflow_status = $wfstat")
        params["wfstat"] = workflow_status
    if evidence_refs is not None:
        updates.append("evidence_refs = $erefs")
        params["erefs"] = evidence_refs

    set_clause = ", ".join(updates)
    result = await repo_query(
        f"UPDATE $draft_id SET {set_clause}",
        params,
    )
    updated = result[0] if result else {}
    updated["draft_id"] = str(updated.get("id", draft_id))
    return updated


# --- Confirmation ---


async def confirm_memories(
    notebook_id: str, items: List[Dict[str, Any]]
) -> ConfirmMemoriesResponse:
    """Confirm selected drafts, writing them to PowerContext.

    Each item: {draft_id, draft_version, operation_id}
    Returns per-item status (committed/failed/uncertain).
    """
    nb_record = ensure_record_id(notebook_id)
    trace_id = f"trace-{uuid.uuid4().hex[:12]}"
    results: List[ConfirmItemResult] = []

    # Ensure scope binding
    binding = await get_or_create_scope_binding(notebook_id)
    scope_id = binding.get("scope_id")
    if not scope_id:
        return ConfirmMemoriesResponse(
            trace_id=trace_id,
            items=[
                ConfirmItemResult(
                    draft_id=item["draft_id"],
                    status="failed",
                    error="Scope not ready",
                )
                for item in items
            ],
        )

    client = get_powercontext_client()

    # Capture confirmation event source
    source_id = f"confirm-{trace_id}"
    try:
        await client.capture_content_source(
            scope_id=scope_id,
            source_id=source_id,
            content=f"User confirmed research memories at {datetime.now(timezone.utc).isoformat()}",
            metadata={"trace_id": trace_id, "notebook_id": notebook_id},
        )
    except PowerContextError as e:
        logger.warning(f"Source capture failed (non-fatal): {e}")

    for item in items:
        draft_id = item["draft_id"]
        draft_version = item["draft_version"]
        operation_id = item["operation_id"]

        try:
            result = await _confirm_single(
                notebook_id=notebook_id,
                nb_record=nb_record,
                scope_id=scope_id,
                draft_id=draft_id,
                draft_version=draft_version,
                operation_id=operation_id,
                source_id=source_id,
                client=client,
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to confirm draft {draft_id}: {e}")
            results.append(
                ConfirmItemResult(draft_id=draft_id, status="failed", error=str(e))
            )

    # Record trace
    await _save_trace(trace_id, notebook_id, results)

    return ConfirmMemoriesResponse(trace_id=trace_id, items=results)


async def _confirm_single(
    notebook_id: str,
    nb_record: Any,
    scope_id: str,
    draft_id: str,
    draft_version: int,
    operation_id: str,
    source_id: str,
    client: PowerContextClient,
) -> ConfirmItemResult:
    """Confirm a single draft item."""
    draft_record = ensure_record_id(draft_id)

    # Check for duplicate operation_id
    existing_op = await repo_query(
        "SELECT * FROM research_memory_operation WHERE operation_id = $op_id LIMIT 1",
        {"op_id": operation_id},
    )
    if existing_op:
        prev = existing_op[0]
        if prev.get("status") == OperationStatus.SUCCESS:
            # Already committed, return previous result
            refs = prev.get("result_refs", {})
            return ConfirmItemResult(
                draft_id=draft_id,
                status="committed",
                item_id=refs.get("item_id"),
                artifact_id=refs.get("artifact_id"),
                revision=refs.get("revision"),
            )
        elif prev.get("status") == OperationStatus.UNCERTAIN:
            return ConfirmItemResult(
                draft_id=draft_id, status="uncertain", error="Previous result unknown"
            )

    # Read draft
    drafts = await repo_query(
        "SELECT * FROM $draft_id WHERE notebook_id = $nb_id",
        {"draft_id": draft_record, "nb_id": nb_record},
    )
    if not drafts:
        return ConfirmItemResult(draft_id=draft_id, status="failed", error="Draft not found")
    draft = drafts[0]

    if draft.get("draft_version") != draft_version:
        return ConfirmItemResult(
            draft_id=draft_id,
            status="failed",
            error=f"Draft version mismatch: expected {draft_version}, got {draft.get('draft_version')}",
        )

    if draft.get("status") == DraftStatus.COMMITTED:
        return ConfirmItemResult(
            draft_id=draft_id, status="failed", error="Draft already committed"
        )

    # Mark as confirming
    await repo_query(
        "UPDATE $draft_id SET status = 'confirming', updated_at = time::now()",
        {"draft_id": draft_record},
    )

    # Create operation record
    fingerprint = hashlib.sha256(
        f"{operation_id}:{draft.get('content', '')}".encode()
    ).hexdigest()[:16]
    await repo_query(
        """
        CREATE research_memory_operation SET
            operation_id = $op_id,
            request_fingerprint = $fp,
            draft_id = $draft_rec,
            notebook_id = $nb_id,
            operation_type = 'create_memory',
            status = 'pending',
            created_at = time::now()
        """,
        {
            "op_id": operation_id,
            "fp": fingerprint,
            "draft_rec": draft_record,
            "nb_id": nb_record,
        },
    )

    # Build research memory item
    memory_type = MemoryType(draft["draft_type"])
    kind = MEMORY_TYPE_TO_KIND[memory_type.value]

    evidence_refs = []
    for ref in draft.get("evidence_refs", []):
        evidence_refs.append(ref)

    item = ResearchMemoryItem(
        operation_id=operation_id,
        type=memory_type,
        content=draft["content"],
        epistemic_status=draft.get("epistemic_status", "user_statement"),
        workflow_status=draft.get("workflow_status", "not_applicable"),
        evidence_refs=evidence_refs,
        confirmation_source_ref={"source_type": "content", "source_id": source_id},
    )

    # Validate byte size
    try:
        item.validate_byte_size()
    except ValueError as e:
        await _update_operation(operation_id, OperationStatus.FAILED, error=str(e))
        await repo_query(
            "UPDATE $draft_id SET status = 'failed', updated_at = time::now()",
            {"draft_id": draft_record},
        )
        return ConfirmItemResult(draft_id=draft_id, status="failed", error=str(e))

    # Write to PowerContext
    try:
        text = item.to_text()
        result = await client.create_atomic_memory(
            scope_id=scope_id, kind=kind, text=text
        )
        artifact_id = result.get("artifact_id")
        revision = result.get("revision", 1)
        item_id = item.item_id

        if not artifact_id:
            raise PowerContextError("PowerContext did not return artifact_id")

        # Store link
        await repo_query(
            """
            CREATE research_memory_link SET
                item_id = $item_id,
                notebook_id = $nb_id,
                scope_id = $scope_id,
                artifact_id = $artifact_id,
                kind = $kind,
                latest_revision = $revision,
                latest_state_version = 0,
                created_at = time::now(),
                updated_at = time::now()
            """,
            {
                "item_id": item_id,
                "nb_id": nb_record,
                "scope_id": scope_id,
                "artifact_id": artifact_id,
                "kind": kind,
                "revision": revision,
            },
        )

        # Update draft and operation
        await repo_query(
            "UPDATE $draft_id SET status = 'committed', updated_at = time::now()",
            {"draft_id": draft_record},
        )
        await _update_operation(
            operation_id,
            OperationStatus.SUCCESS,
            result_refs={
                "item_id": item_id,
                "artifact_id": artifact_id,
                "revision": revision,
            },
        )

        logger.info(f"Confirmed memory: item={item_id}, artifact={artifact_id}")
        return ConfirmItemResult(
            draft_id=draft_id,
            status="committed",
            item_id=item_id,
            artifact_id=artifact_id,
            revision=revision,
        )

    except PowerContextError as e:
        logger.error(f"PowerContext error confirming {draft_id}: {e}")
        await _update_operation(operation_id, OperationStatus.FAILED, error=str(e))
        await repo_query(
            "UPDATE $draft_id SET status = 'failed', updated_at = time::now()",
            {"draft_id": draft_record},
        )
        return ConfirmItemResult(draft_id=draft_id, status="failed", error=str(e))

    except Exception as e:
        # Unknown error → uncertain
        logger.error(f"Unknown error confirming {draft_id}: {e}")
        await _update_operation(operation_id, OperationStatus.UNCERTAIN, error=str(e))
        await repo_query(
            "UPDATE $draft_id SET status = 'uncertain', updated_at = time::now()",
            {"draft_id": draft_record},
        )
        return ConfirmItemResult(draft_id=draft_id, status="uncertain", error=str(e))


async def _update_operation(
    operation_id: str,
    status: OperationStatus,
    result_refs: Optional[Dict] = None,
    error: Optional[str] = None,
) -> None:
    """Update operation record."""
    await repo_query(
        """
        UPDATE research_memory_operation SET
            status = $status,
            result_refs = $refs,
            error_message = $error
        WHERE operation_id = $op_id
        """,
        {
            "status": status.value,
            "refs": result_refs,
            "error": error,
            "op_id": operation_id,
        },
    )


async def _save_trace(
    trace_id: str, notebook_id: str, results: List[ConfirmItemResult]
) -> None:
    """Save trace record."""
    nb_record = ensure_record_id(notebook_id)
    memory_refs = [
        {"item_id": r.item_id, "artifact_id": r.artifact_id, "status": r.status}
        for r in results
        if r.item_id
    ]
    await repo_query(
        """
        CREATE research_trace SET
            trace_id = $trace_id,
            notebook_id = $nb_id,
            events = $events,
            memory_refs = $mrefs,
            created_at = time::now()
        """,
        {
            "trace_id": trace_id,
            "nb_id": nb_record,
            "events": [{"type": "confirm", "results": [r.model_dump() for r in results]}],
            "mrefs": memory_refs,
        },
    )


# --- Read memories ---


async def list_memories(notebook_id: str) -> Dict[str, Any]:
    """List all active memories for a notebook from PowerContext."""
    scope_id = await get_scope_id(notebook_id)
    if not scope_id:
        return {"scope_id": None, "memories": [], "trace_id": f"trace-{uuid.uuid4().hex[:12]}"}

    client = get_powercontext_client()
    trace_id = f"trace-{uuid.uuid4().hex[:12]}"

    try:
        items = await client.list_all_atomic_memories(scope_id, states=["active"])
        memories = []
        for item in items:
            text = item.get("text", "")
            try:
                business = ResearchMemoryItem.from_text(text)
                artifact_id = item.get("artifact", {}).get("artifact_id", item.get("artifact_id", ""))
                memories.append({
                    "item_id": business.item_id,
                    "type": business.type.value,
                    "content": business.content,
                    "epistemic_status": business.epistemic_status.value,
                    "workflow_status": business.workflow_status.value,
                    "evidence_refs": [e.model_dump() for e in business.evidence_refs],
                    "artifact_id": artifact_id,
                    "revision": item.get("revision", 1),
                    "state": item.get("state", "active"),
                    "state_version": item.get("state_version", 0),
                    "confirmed_at": business.confirmed_at,
                })
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Skipping malformed memory text: {e}")
                continue

        # Save trace
        nb_record = ensure_record_id(notebook_id)
        await repo_query(
            """
            CREATE research_trace SET
                trace_id = $trace_id,
                notebook_id = $nb_id,
                events = [{'type': 'list_memories', 'count': $count}],
                memory_refs = [],
                created_at = time::now()
            """,
            {"trace_id": trace_id, "nb_id": nb_record, "count": len(memories)},
        )

        return {"scope_id": scope_id, "memories": memories, "trace_id": trace_id}

    except PowerContextError as e:
        logger.error(f"Failed to list memories: {e}")
        raise


async def get_memory_detail(notebook_id: str, item_id: str) -> Dict[str, Any]:
    """Get detailed view of one memory including ETag."""
    scope_id = await get_scope_id(notebook_id)
    if not scope_id:
        raise ValueError("Scope not bound")

    # Find link
    links = await repo_query(
        "SELECT * FROM research_memory_link WHERE item_id = $item_id AND notebook_id = $nb_id",
        {"item_id": item_id, "nb_id": ensure_record_id(notebook_id)},
    )
    if not links:
        raise ValueError(f"Memory link not found: {item_id}")
    link = links[0]
    artifact_id = link["artifact_id"]

    client = get_powercontext_client()
    record, etag = await client.read_artifact(scope_id, artifact_id)

    text = record.get("text", "") or record.get("content", {}).get("text", "")
    business = ResearchMemoryItem.from_text(text)

    return {
        "item_id": business.item_id,
        "type": business.type.value,
        "content": business.content,
        "epistemic_status": business.epistemic_status.value,
        "workflow_status": business.workflow_status.value,
        "evidence_refs": [e.model_dump() for e in business.evidence_refs],
        "artifact_id": artifact_id,
        "revision": record.get("revision", 1),
        "state": record.get("state", "active"),
        "state_version": record.get("state_version", 0),
        "etag": etag,
        "confirmed_at": business.confirmed_at,
        "confirmation_source_ref": business.confirmation_source_ref.model_dump()
        if business.confirmation_source_ref
        else None,
    }


# --- Update memory ---


async def update_memory(
    notebook_id: str,
    item_id: str,
    content: str,
    if_match: str,
    epistemic_status: Optional[str] = None,
    workflow_status: Optional[str] = None,
    evidence_refs: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """Update a confirmed memory in PowerContext."""
    scope_id = await get_scope_id(notebook_id)
    if not scope_id:
        raise ValueError("Scope not bound")

    links = await repo_query(
        "SELECT * FROM research_memory_link WHERE item_id = $item_id AND notebook_id = $nb_id",
        {"item_id": item_id, "nb_id": ensure_record_id(notebook_id)},
    )
    if not links:
        raise ValueError(f"Memory link not found: {item_id}")
    link = links[0]
    artifact_id = link["artifact_id"]
    kind = link["kind"]

    # Read current to get existing business data
    client = get_powercontext_client()
    current_record, _ = await client.read_artifact(scope_id, artifact_id)
    current_text = current_record.get("text", "")
    try:
        current_business = ResearchMemoryItem.from_text(current_text)
    except Exception:
        current_business = None

    # Build new item
    new_item = ResearchMemoryItem(
        item_id=item_id,
        operation_id=f"update-{uuid.uuid4().hex[:8]}",
        type=MemoryType(KIND_TO_MEMORY_TYPE.get(kind, "goal")),
        content=content,
        epistemic_status=epistemic_status or (
            current_business.epistemic_status.value if current_business else "user_statement"
        ),
        workflow_status=workflow_status or (
            current_business.workflow_status.value if current_business else "not_applicable"
        ),
        evidence_refs=evidence_refs or (
            [e.model_dump() for e in current_business.evidence_refs]
            if current_business
            else []
        ),
        confirmed_at=datetime.now(timezone.utc).isoformat(),
    )
    new_item.validate_byte_size()

    # Replace in PowerContext
    result = await client.replace_artifact(
        scope_id=scope_id,
        artifact_id=artifact_id,
        kind=kind,
        text=new_item.to_text(),
        if_match=if_match,
    )

    new_revision = result.get("revision", link.get("latest_revision", 1) + 1)
    new_etag = result.get("etag")

    # Update link
    await repo_query(
        """
        UPDATE research_memory_link SET
            latest_revision = $rev,
            latest_etag = $etag,
            updated_at = time::now()
        WHERE item_id = $item_id
        """,
        {"rev": new_revision, "etag": new_etag, "item_id": item_id},
    )

    return {
        "item_id": item_id,
        "artifact_id": artifact_id,
        "revision": new_revision,
        "etag": new_etag,
    }


# --- Forget memory ---


async def forget_memory(notebook_id: str, item_id: str) -> Dict[str, Any]:
    """Forget a memory (remove from active recall)."""
    scope_id = await get_scope_id(notebook_id)
    if not scope_id:
        raise ValueError("Scope not bound")

    links = await repo_query(
        "SELECT * FROM research_memory_link WHERE item_id = $item_id AND notebook_id = $nb_id",
        {"item_id": item_id, "nb_id": ensure_record_id(notebook_id)},
    )
    if not links:
        raise ValueError(f"Memory link not found: {item_id}")
    link = links[0]
    artifact_id = link["artifact_id"]
    revision = link.get("latest_revision", 1)
    state_version = link.get("latest_state_version", 0)

    client = get_powercontext_client()
    result = await client.forget_artifact(
        scope_id=scope_id,
        artifact_id=artifact_id,
        revision=revision,
        state_version=state_version,
    )

    # Update link state version
    new_state_version = result.get("state_version", state_version + 1)
    await repo_query(
        """
        UPDATE research_memory_link SET
            latest_state_version = $sv,
            updated_at = time::now()
        WHERE item_id = $item_id
        """,
        {"sv": new_state_version, "item_id": item_id},
    )

    return {
        "item_id": item_id,
        "artifact_id": artifact_id,
        "state": "forgotten",
        "state_version": new_state_version,
    }


# --- Revisions ---


async def list_revisions(notebook_id: str, item_id: str) -> List[Dict[str, Any]]:
    """List all revisions of a memory."""
    scope_id = await get_scope_id(notebook_id)
    if not scope_id:
        raise ValueError("Scope not bound")

    links = await repo_query(
        "SELECT artifact_id FROM research_memory_link WHERE item_id = $item_id AND notebook_id = $nb_id",
        {"item_id": item_id, "nb_id": ensure_record_id(notebook_id)},
    )
    if not links:
        raise ValueError(f"Memory link not found: {item_id}")
    artifact_id = links[0]["artifact_id"]

    client = get_powercontext_client()
    revisions = await client.list_revisions(scope_id, artifact_id)
    return revisions


async def get_revision(
    notebook_id: str, item_id: str, revision: int
) -> Dict[str, Any]:
    """Get a specific revision of a memory."""
    scope_id = await get_scope_id(notebook_id)
    if not scope_id:
        raise ValueError("Scope not bound")

    links = await repo_query(
        "SELECT artifact_id FROM research_memory_link WHERE item_id = $item_id AND notebook_id = $nb_id",
        {"item_id": item_id, "nb_id": ensure_record_id(notebook_id)},
    )
    if not links:
        raise ValueError(f"Memory link not found: {item_id}")
    artifact_id = links[0]["artifact_id"]

    client = get_powercontext_client()
    record = await client.read_revision(scope_id, artifact_id, revision)

    text = record.get("text", "") or record.get("content", {}).get("text", "")
    try:
        business = ResearchMemoryItem.from_text(text)
        return {
            "item_id": business.item_id,
            "type": business.type.value,
            "content": business.content,
            "revision": revision,
        }
    except Exception:
        return {"content": text, "revision": revision}
