"""Research report generation service.

Generates structured Markdown reports from current PowerContext memories
and Open Notebook sources, with citation validation and export.
"""

from __future__ import annotations

import json
import os
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from open_notebook.research.models import (
    KIND_TO_MEMORY_TYPE,
    MemoryType,
    ResearchMemoryItem,
)
from open_notebook.research.powercontext_client import (
    PowerContextClient,
    PowerContextError,
    get_powercontext_client,
)
from open_notebook.research.memory_service import get_scope_id

# Type labels
TYPE_LABELS = {
    "goal": "研究目标",
    "conclusion": "阅读结论",
    "open_question": "未解决问题",
    "next_step": "下一步计划",
}

EPISTEMIC_LABELS = {
    "supported": "有依据",
    "hypothesis": "待验证假设",
    "user_statement": "用户陈述",
}

WORKFLOW_LABELS = {
    "open": "进行中",
    "completed": "已完成",
    "not_applicable": "",
}


async def generate_report(
    notebook_id: str,
    title: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Generate a structured Markdown report.

    Returns:
        (markdown_content, metadata)
    """
    scope_id = await get_scope_id(notebook_id)
    if not scope_id:
        raise ReportError("课题尚未启用研究记忆功能")

    client = get_powercontext_client()
    trace_id = f"trace-{uuid.uuid4().hex[:12]}"
    report_id = f"report-{uuid.uuid4().hex[:8]}"
    metadata: Dict[str, Any] = {
        "report_id": report_id,
        "trace_id": trace_id,
        "scope_id": scope_id,
        "notebook_id": notebook_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "memory_refs": [],
        "evidence_refs": [],
        "omitted_items": [],
        "status": "ok",
    }

    try:
        # 1. Read all active memories
        items = await client.list_all_atomic_memories(scope_id, states=["active"])
        if not items:
            raise ReportError("当前课题尚无已确认的研究记忆，无法生成报告")

        # 2. Categorize memories
        memories_by_type: Dict[str, List[Dict[str, Any]]] = {
            "goal": [],
            "conclusion": [],
            "open_question": [],
            "next_step": [],
        }

        for item in items:
            text = item.get("text", "")
            artifact_ref = item.get("artifact", {})
            artifact_id = artifact_ref.get("artifact_id", item.get("artifact_id", ""))
            revision = artifact_ref.get("revision", item.get("revision", 1))

            try:
                business = ResearchMemoryItem.from_text(text)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Skipping malformed memory in report: {e}")
                metadata["omitted_items"].append({
                    "reason": "malformed",
                    "artifact_id": artifact_id,
                })
                continue

            mtype = business.type.value
            entry = {
                "item_id": business.item_id,
                "content": business.content,
                "epistemic_status": business.epistemic_status.value,
                "workflow_status": business.workflow_status.value,
                "artifact_id": artifact_id,
                "revision": revision,
                "evidence_refs": [e.model_dump() for e in business.evidence_refs],
                "confirmed_at": business.confirmed_at,
            }

            memories_by_type.setdefault(mtype, []).append(entry)
            metadata["memory_refs"].append({
                "item_id": business.item_id,
                "artifact_id": artifact_id,
                "type": mtype,
                "revision": revision,
            })

        # 3. Build report sections
        report_title = title or "研究进展报告"
        sections = []

        # Header
        sections.append(f"# {report_title}")
        sections.append("")
        sections.append(f"*生成时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*")
        sections.append("")

        # Section 1: Goals
        sections.append("## 1. 当前研究目标与范围")
        sections.append("")
        goals = memories_by_type.get("goal", [])
        if goals:
            for i, g in enumerate(goals, 1):
                label = EPISTEMIC_LABELS.get(g["epistemic_status"], "")
                prefix = f"[{label}] " if label else ""
                sections.append(f"{i}. {prefix}{g['content']} [M{i}]")
        else:
            sections.append("*未记录研究目标。*")
        sections.append("")

        # Section 2: Reading materials and findings
        sections.append("## 2. 本次阅读材料及主要发现")
        sections.append("")
        conclusions = memories_by_type.get("conclusion", [])
        if conclusions:
            mem_idx = len(goals)
            for c in conclusions:
                mem_idx += 1
                epistemic = EPISTEMIC_LABELS.get(c["epistemic_status"], "")
                wf = WORKFLOW_LABELS.get(c["workflow_status"], "")
                tags = []
                if epistemic:
                    tags.append(epistemic)
                if wf:
                    tags.append(wf)
                tag_str = f" [{' | '.join(tags)}] " if tags else " "
                sections.append(f"- {tag_str}{c['content']} [M{mem_idx}]")
                # Add evidence quotes
                for ev in c.get("evidence_refs", []):
                    quote = ev.get("quote", "")
                    if quote:
                        sections.append(f"  > \"{quote[:100]}\"")
        else:
            sections.append("*暂无已确认的阅读结论。*")
        sections.append("")

        # Section 3: Confirmed progress
        sections.append("## 3. 已确认的阶段进展")
        sections.append("")
        completed_items = []
        for mtype in ["goal", "conclusion", "next_step"]:
            for entry in memories_by_type.get(mtype, []):
                if entry["workflow_status"] == "completed":
                    completed_items.append(entry)
        if completed_items:
            for item in completed_items:
                sections.append(f"- ✅ {item['content']}")
        else:
            sections.append("*尚无标记为已完成的进展记录。*")
        sections.append("")

        # Section 4: Hypotheses and open questions
        sections.append("## 4. 待验证假设与未解决问题")
        sections.append("")
        hypotheses = [
            e for entries in memories_by_type.values()
            for e in entries
            if e["epistemic_status"] == "hypothesis"
        ]
        open_questions = memories_by_type.get("open_question", [])

        if hypotheses:
            sections.append("**待验证假设：**")
            for h in hypotheses:
                sections.append(f"- ⚠️ {h['content']}")
            sections.append("")

        if open_questions:
            sections.append("**未解决问题：**")
            for q in open_questions:
                sections.append(f"- ❓ {q['content']}")
            sections.append("")

        if not hypotheses and not open_questions:
            sections.append("*暂无待验证假设或未解决问题。*")
            sections.append("")

        # Section 5: Next steps
        sections.append("## 5. 下一步计划")
        sections.append("")
        open_next_steps = [
            ns for ns in memories_by_type.get("next_step", [])
            if ns["workflow_status"] != "completed"
        ]
        if open_next_steps:
            for ns in open_next_steps:
                sections.append(f"- 🔜 {ns['content']}")
        else:
            sections.append("*暂无待执行的下一步计划。*")
        sections.append("")

        # Section 6: Citation manifest
        sections.append("## 6. 引用清单")
        sections.append("")
        sections.append("### 记忆引用")
        sections.append("")
        sections.append("| 编号 | 类型 | 认知状态 | 工作流状态 | Artifact ID | Revision |")
        sections.append("|------|------|----------|------------|-------------|----------|")
        mem_counter = 0
        for mtype in ["goal", "conclusion", "open_question", "next_step"]:
            for entry in memories_by_type.get(mtype, []):
                mem_counter += 1
                type_label = TYPE_LABELS.get(mtype, mtype)
                ep_label = EPISTEMIC_LABELS.get(entry["epistemic_status"], "-")
                wf_label = WORKFLOW_LABELS.get(entry["workflow_status"], "-")
                sections.append(
                    f"| M{mem_counter} | {type_label} | {ep_label} | "
                    f"{wf_label} | `{entry['artifact_id'][:12]}...` | {entry['revision']} |"
                )
        sections.append("")

        # Evidence refs
        all_evidence = []
        ev_counter = 0
        for entries in memories_by_type.values():
            for entry in entries:
                for ev in entry.get("evidence_refs", []):
                    ev_counter += 1
                    all_evidence.append({
                        "index": ev_counter,
                        **ev,
                    })

        if all_evidence:
            sections.append("### 资料证据")
            sections.append("")
            sections.append("| 编号 | 类型 | 来源 | 摘录 |")
            sections.append("|------|------|------|------|")
            for ev in all_evidence:
                quote = ev.get("quote", "")[:60]
                sections.append(
                    f"| S{ev['index']} | {ev.get('kind', '-')} | "
                    f"`{ev.get('resource_id', '-')[:16]}` | {quote} |"
                )
            metadata["evidence_refs"] = all_evidence
            sections.append("")

        # Omitted items
        if metadata["omitted_items"]:
            sections.append("### 本次省略项")
            sections.append("")
            for om in metadata["omitted_items"]:
                sections.append(f"- {om.get('reason', 'unknown')}: {om.get('artifact_id', 'N/A')}")
            sections.append("")

        markdown = "\n".join(sections)
        return markdown, metadata

    except PowerContextError as e:
        metadata["status"] = "unavailable"
        raise ReportError(f"PowerContext 不可用: {e}") from e
    except Exception as e:
        metadata["status"] = "error"
        raise ReportError(f"报告生成失败: {e}") from e


async def save_report_as_note(
    notebook_id: str,
    report_content: str,
    report_metadata: Dict[str, Any],
    title: Optional[str] = None,
) -> str:
    """Save the report as an Open Notebook Note.

    Returns the note ID.
    """
    from open_notebook.domain.notebook import Note

    note_title = title or f"研究报告 - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

    # Add metadata header to the note content
    metadata_header = (
        f"<!-- report_id: {report_metadata.get('report_id', 'N/A')} -->\n"
        f"<!-- trace_id: {report_metadata.get('trace_id', 'N/A')} -->\n"
        f"<!-- generated_at: {report_metadata.get('generated_at', 'N/A')} -->\n\n"
    )

    full_content = metadata_header + report_content

    try:
        note = await Note.create(
            notebook_id=notebook_id,
            title=note_title,
            content=full_content,
        )
        return str(note.id)
    except Exception as e:
        logger.error(f"Failed to save report as note: {e}")
        raise ReportError(f"保存报告为笔记失败: {e}") from e


class ReportError(Exception):
    """Raised when report generation or saving fails."""
    pass
