"""Model-based candidate extraction service.

Uses the configured language model to extract structured research memory
candidates from selected sources, notes, or session messages.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, List, Optional

from loguru import logger

from open_notebook.research.models import (
    EvidenceRef,
    MemoryType,
    ResearchMemoryItem,
)


EXTRACTION_SYSTEM_PROMPT = """你是一个科研阅读助手的候选记忆提取模块。
你的任务是从提供的资料片段中提取结构化的研究记忆候选。

你必须输出严格的 JSON 数组，每个元素包含：
- type: 记忆类型，必须是 goal / conclusion / open_question / next_step 之一
- content: 记忆正文，简明扼要，不超过 500 字
- epistemic_status: supported（有资料依据）/ hypothesis（用户判断）/ user_statement（用户陈述）
- evidence_indices: 引用的资料片段编号列表（整数数组），只能从提供的编号中选择
- quote: 原文摘录（不超过 200 字），仅当 epistemic_status 为 supported 时必填

规则：
1. 研究目标(goal)和下一步(next_step)可以用用户输入作为来源，evidence_indices 可为空
2. 阅读结论(conclusion)必须关联实际资料依据，不能凭空生成
3. 未解决问题(open_question)应反映资料中的矛盾或空白
4. 不要编造资料中没有的实验数据或论文结论
5. 每个候选必须明确标注认知状态：有资料支持、用户假设还是用户陈述
6. 输出纯 JSON 数组，不要添加任何解释文字或 Markdown 标记"""


async def extract_candidates(
    fragments: List[Dict[str, Any]],
    user_instruction: Optional[str] = None,
    model_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Extract structured memory candidates from fragments using LLM.

    Args:
        fragments: List of {"index": int, "kind": str, "content": str, "source_id": str}
        user_instruction: Optional user guidance for extraction
        model_id: Optional model override

    Returns:
        List of candidate dicts ready for draft creation
    """
    # Build the fragment text with indices
    fragment_text_parts = []
    for frag in fragments:
        idx = frag.get("index", 0)
        kind = frag.get("kind", "unknown")
        content = frag.get("content", "")[:2000]  # Truncate long fragments
        fragment_text_parts.append(f"[片段 {idx}] ({kind})\n{content}")

    fragment_text = "\n\n---\n\n".join(fragment_text_parts)

    user_message_parts = []
    if user_instruction:
        user_message_parts.append(f"用户指示：{user_instruction}")
    user_message_parts.append(f"以下是选定的资料片段：\n\n{fragment_text}")
    user_message_parts.append("请从中提取结构化的研究记忆候选。")

    user_message = "\n\n".join(user_message_parts)

    # Call the language model
    try:
        response_text = await _call_model(
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_message=user_message,
            model_id=model_id,
        )
    except Exception as e:
        logger.error(f"Model extraction failed: {e}")
        raise ExtractionError(f"模型提取失败: {e}") from e

    # Parse the response
    candidates = _parse_extraction_response(response_text, fragments)

    # Validate each candidate
    validated = []
    for cand in candidates:
        try:
            _validate_candidate(cand, fragments)
            validated.append(cand)
        except ValidationError as e:
            logger.warning(f"Candidate validation failed: {e}")
            cand["validation_error"] = str(e)
            validated.append(cand)

    return validated


async def _call_model(
    system_prompt: str,
    user_message: str,
    model_id: Optional[str] = None,
) -> str:
    """Call the configured language model via Open Notebook's model provision."""
    from open_notebook.ai.provision import provision_langchain_model

    payload = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    model = await provision_langchain_model(
        str(payload), model_id, "chat", max_tokens=4096
    )

    from langchain_core.messages import HumanMessage, SystemMessage

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    result = model.invoke(messages)
    content = result.content if hasattr(result, "content") else str(result)

    # Clean thinking tags if present
    from open_notebook.utils import clean_thinking_content
    return clean_thinking_content(content)


def _parse_extraction_response(
    response_text: str,
    fragments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Parse the model's JSON response into candidate dicts."""
    # Try to extract JSON from the response
    text = response_text.strip()

    # Remove markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (``` markers)
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        elif lines[0].startswith("```"):
            lines = lines[1:]
        text = "\n".join(lines).strip()

    try:
        items = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON array in the text
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                items = json.loads(text[start:end])
            except json.JSONDecodeError:
                logger.warning(f"Could not parse extraction response as JSON")
                return []
        else:
            return []

    if not isinstance(items, list):
        return []

    candidates = []
    fragment_map = {f.get("index"): f for f in fragments}

    for item in items:
        if not isinstance(item, dict):
            continue

        # Build evidence refs
        evidence_refs = []
        for idx in item.get("evidence_indices", []):
            frag = fragment_map.get(idx)
            if frag:
                evidence_refs.append({
                    "kind": frag.get("kind", "unknown"),
                    "resource_id": frag.get("source_id", ""),
                    "quote": item.get("quote", ""),
                    "locator": f"片段 {idx}",
                })

        candidate = {
            "type": item.get("type", "goal"),
            "content": item.get("content", ""),
            "epistemic_status": item.get("epistemic_status", "user_statement"),
            "evidence_refs": evidence_refs,
            "quote": item.get("quote", ""),
            "source": "extract",
        }
        candidates.append(candidate)

    return candidates


def _validate_candidate(
    candidate: Dict[str, Any],
    fragments: List[Dict[str, Any]],
) -> None:
    """Validate a candidate against extraction rules."""
    # Check type
    valid_types = {"goal", "conclusion", "open_question", "next_step"}
    if candidate.get("type") not in valid_types:
        raise ValidationError(
            f"Invalid type: {candidate.get('type')}. Must be one of {valid_types}"
        )

    # Check content length
    content = candidate.get("content", "")
    if not content or len(content) > 2000:
        raise ValidationError("Content must be 1-2000 characters")

    # Check epistemic status
    valid_statuses = {"supported", "hypothesis", "user_statement"}
    if candidate.get("epistemic_status") not in valid_statuses:
        raise ValidationError(
            f"Invalid epistemic_status: {candidate.get('epistemic_status')}"
        )

    # Conclusions must have evidence
    if candidate["type"] == "conclusion" and candidate["epistemic_status"] == "supported":
        if not candidate.get("evidence_refs"):
            raise ValidationError(
                "Supported conclusions must have evidence refs"
            )

    # Check evidence indices are valid
    valid_indices = {f.get("index") for f in fragments}
    for ref in candidate.get("evidence_refs", []):
        # Extract index from locator
        locator = ref.get("locator", "")
        try:
            idx = int(locator.replace("片段 ", ""))
            if idx not in valid_indices:
                raise ValidationError(
                    f"Evidence index {idx} not in allowed set {valid_indices}"
                )
        except (ValueError, AttributeError):
            pass  # Non-numeric locators are allowed for user_statement type


class ExtractionError(Exception):
    """Raised when model extraction fails."""
    pass


class ValidationError(Exception):
    """Raised when candidate validation fails."""
    pass
