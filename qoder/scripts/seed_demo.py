#!/usr/bin/env python3
"""Seed demo data for 研续 ResearchMemory.

Creates a demo notebook with synthetic research materials and memory candidates.
All demo data is clearly marked as synthetic - not real papers or experiments.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

API_BASE = "http://127.0.0.1:5055"
EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def api_post(path: str, data: dict) -> dict:
    """POST to API and return JSON response."""
    body = json.dumps(data).encode()
    req = Request(
        f"{API_BASE}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def api_get(path: str) -> dict:
    """GET from API and return JSON response."""
    req = Request(path, headers={"Accept": "application/json"})
    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def create_demo_notebook() -> str:
    """Create or find the demo notebook."""
    # Check if demo notebook already exists
    notebooks = api_get(f"{API_BASE}/api/notebooks")
    for nb in notebooks:
        if "Schema选择" in nb.get("name", ""):
            print(f"  Found existing notebook: {nb['id']} - {nb['name']}")
            return nb["id"]

    # Create new demo notebook
    result = api_post(f"{API_BASE}/api/notebooks", {
        "name": "Schema选择研究（演示）",
        "description": "[合成数据] 用于演示 Text-to-SQL Schema 选择研究的课题记忆功能。非真实论文。",
    })
    nb_id = result.get("id", "")
    print(f"  Created notebook: {nb_id}")
    return nb_id


def enable_research(notebook_id: str) -> dict:
    """Enable research memory for the notebook."""
    result = api_post(f"{API_BASE}/api/research/notebooks/{notebook_id}/enable", {
        "title": "Schema选择研究",
        "summary": "研究Schema选择对Text-to-SQL准确率的影响",
    })
    print(f"  Research enabled, scope_id: {result.get('scope_id', 'N/A')}")
    return result


def create_demo_drafts(notebook_id: str) -> list[str]:
    """Create the four types of demo memory drafts."""
    drafts = [
        {
            "draft_type": "goal",
            "content": "本阶段分析Schema选择对Text-to-SQL准确率的影响（演示目标）",
            "epistemic_status": "user_statement",
            "workflow_status": "open",
            "mode": "manual",
        },
        {
            "draft_type": "conclusion",
            "content": "需要检查冗余候选Schema是否影响生成（演示假设）",
            "epistemic_status": "hypothesis",
            "workflow_status": "open",
            "mode": "manual",
        },
        {
            "draft_type": "open_question",
            "content": "如何保留高召回同时减少冗余Schema候选（演示问题）",
            "epistemic_status": "user_statement",
            "workflow_status": "open",
            "mode": "manual",
        },
        {
            "draft_type": "next_step",
            "content": "检查JOIN条件相关的失败案例（演示计划）",
            "epistemic_status": "user_statement",
            "workflow_status": "open",
            "mode": "manual",
        },
    ]

    draft_ids = []
    for d in drafts:
        result = api_post(
            f"{API_BASE}/api/research/notebooks/{notebook_id}/memory-drafts",
            d,
        )
        draft_id = result.get("draft_id", "")
        draft_ids.append(draft_id)
        print(f"  Created draft: [{d['draft_type']}] {draft_id}")

    return draft_ids


def confirm_all_drafts(notebook_id: str, draft_ids: list[str]) -> dict:
    """Confirm all drafts in a single batch."""
    items = [
        {
            "draft_id": did,
            "draft_version": 1,
            "operation_id": f"op-seed-{i:03d}",
        }
        for i, did in enumerate(draft_ids)
    ]

    result = api_post(
        f"{API_BASE}/api/research/notebooks/{notebook_id}/memory-confirmations",
        {"items": items},
    )

    committed = sum(1 for item in result.get("items", []) if item.get("status") == "committed")
    print(f"  Confirmed {committed}/{len(items)} memories")
    return result


def main() -> int:
    print("=" * 60)
    print("研续 ResearchMemory - Seed Demo Data")
    print("=" * 60)
    print()
    print("⚠️  All demo data is synthetic. Not real papers or experiments.")
    print()

    try:
        # Step 1: Create/find demo notebook
        print("[1/4] Creating demo notebook...")
        notebook_id = create_demo_notebook()
        print()

        # Step 2: Enable research
        print("[2/4] Enabling research memory...")
        enable_research(notebook_id)
        print()

        # Step 3: Create drafts
        print("[3/4] Creating demo memory drafts...")
        draft_ids = create_demo_drafts(notebook_id)
        print()

        # Step 4: Confirm all
        print("[4/4] Confirming memories to PowerContext...")
        confirm_all_drafts(notebook_id, draft_ids)
        print()

        # Save expected checks
        checks = {
            "notebook_id": notebook_id,
            "expected_memory_count": 4,
            "memory_types": ["goal", "conclusion", "open_question", "next_step"],
            "isolation_marker": "TOPIC_A_DEMO",
            "synthetic": True,
        }
        checks_file = EXAMPLES_DIR / "expected_checks.json"
        checks_file.parent.mkdir(parents=True, exist_ok=True)
        with open(checks_file, "w") as f:
            json.dump(checks, f, indent=2, ensure_ascii=False)
        print(f"  Saved expected checks to {checks_file}")
        print()

        print("✓ Demo data seeded successfully!")
        print()
        print("You can now:")
        print(f"  - Open the frontend and view notebook: {notebook_id}")
        print("  - Create a new session and type '继续上次研究'")
        print("  - Generate a report via POST /api/research/notebooks/{id}/reports")
        return 0

    except Exception as e:
        print(f"\n✗ Seeding failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
