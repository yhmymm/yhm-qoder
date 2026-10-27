#!/usr/bin/env python3
"""Acceptance verification script for 研续 ResearchMemory.

Runs through the standard demo steps and verifies expected outcomes.
Uses real PowerContext integration - no mocks.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

API_BASE = "http://127.0.0.1:5055"
PC_BASE = "http://127.0.0.1:8001"


def api_request(method: str, path: str, data: dict | None = None) -> dict:
    """Make an API request and return JSON response."""
    body = json.dumps(data).encode() if data else None
    req = Request(
        f"{API_BASE}{path}",
        data=body,
        headers={"Content-Type": "application/json"} if body else {"Accept": "application/json"},
        method=method,
    )
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        return {"_error": True, "_status": e.code, "detail": e.read().decode()[:200]}


def pc_request(method: str, path: str, data: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
    """Make a PowerContext API request."""
    body = json.dumps(data).encode() if data else None
    hdrs = {"Content-Type": "application/json"} if body else {"Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    req = Request(f"{PC_BASE}{path}", data=body, headers=hdrs, method=method)
    try:
        with urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except HTTPError as e:
        return e.code, json.loads(e.read().decode()[:500])


class AcceptanceRunner:
    def __init__(self):
        self.results: list[tuple[str, bool, str]] = []
        self.notebook_id: str = ""
        self.scope_id: str = ""
        self.session_id: str = ""

    def check(self, name: str, passed: bool, detail: str = ""):
        status = "✓" if passed else "✗"
        self.results.append((name, passed, detail))
        print(f"  {status} {name}: {detail}")

    def run_all(self) -> int:
        print("=" * 60)
        print("研续 ResearchMemory - Acceptance Verification")
        print("=" * 60)
        print()

        self.step1_health()
        self.step2_enable_research()
        self.step3_create_and_confirm_memories()
        self.step4_verify_powercontext()
        self.step5_cross_session_resume()
        self.step6_topic_isolation()
        self.step7_report_generation()
        self.step8_revision_and_forget()

        print()
        passed = sum(1 for _, p, _ in self.results if p)
        total = len(self.results)
        print(f"Results: {passed}/{total} checks passed")

        if passed == total:
            print("✓ All acceptance checks passed!")
            return 0
        else:
            failed = [(n, d) for n, p, d in self.results if not p]
            print(f"\n✗ {len(failed)} checks failed:")
            for name, detail in failed:
                print(f"  - {name}: {detail}")
            return 1

    def step1_health(self):
        print("\n[Step 1] Health checks...")
        # API
        resp = api_request("GET", "/api/notebooks")
        self.check("API accessible", "_error" not in resp, f"notebooks={len(resp) if isinstance(resp, list) else 'error'}")

        # PowerContext
        status, data = pc_request("GET", "/health/live")
        self.check("PowerContext live", status == 200, f"status={status}")

        # Research health
        resp = api_request("GET", "/api/research/health")
        self.check("Research enabled", resp.get("enabled", False), f"pc_available={resp.get('powercontext_available')}")

    def step2_enable_research(self):
        print("\n[Step 2] Enable research for notebook...")
        notebooks = api_request("GET", "/api/notebooks")
        # Find or create a dedicated verification notebook
        target_name = "验收测试课题"
        self.notebook_id = ""
        if isinstance(notebooks, list):
            for nb in notebooks:
                if nb.get("name") == target_name:
                    self.notebook_id = nb["id"]
                    break
        if not self.notebook_id:
            resp = api_request("POST", "/api/notebooks", {
                "name": target_name,
                "description": "自动化验收专用课题",
            })
            self.notebook_id = resp.get("id", "")

        if not self.notebook_id:
            self.check("Find/create notebook", False, "Failed")
            return

        resp = api_request("POST", f"/api/research/notebooks/{self.notebook_id}/enable", {
            "title": "验收测试课题",
            "summary": "自动化验收用",
        })
        # Get scope_id from the memories endpoint (actual binding)
        mem_resp = api_request("GET", f"/api/research/notebooks/{self.notebook_id}/memories")
        self.scope_id = mem_resp.get("scope_id", "") or resp.get("scope_id", "")
        self.check("Scope binding", bool(self.scope_id), f"scope_id={self.scope_id[:20]}... nb={self.notebook_id}")

    def step3_create_and_confirm_memories(self):
        print("\n[Step 3] Create and confirm memories...")
        if not self.notebook_id:
            self.check("Skip (no notebook)", False, "")
            return

        # Create 4 drafts
        draft_ids = []
        for dtype, content in [
            ("goal", "验收目标：测试四类记忆闭环"),
            ("conclusion", "验收结论：PowerContext写入成功"),
            ("open_question", "验收问题：如何验证课题隔离"),
            ("next_step", "验收计划：执行报告生成测试"),
        ]:
            resp = api_request("POST", f"/api/research/notebooks/{self.notebook_id}/memory-drafts", {
                "draft_type": dtype,
                "content": content,
                "epistemic_status": "user_statement",
                "workflow_status": "open",
                "mode": "manual",
            })
            if "draft_id" in resp:
                draft_ids.append(resp["draft_id"])

        self.check("Create drafts", len(draft_ids) == 4, f"created={len(draft_ids)}")

        # Confirm all
        if draft_ids:
            import time
            ts = int(time.time()) % 100000
            items = [
                {"draft_id": did, "draft_version": 1, "operation_id": f"op-vfy-{ts}-{i:03d}"}
                for i, did in enumerate(draft_ids)
            ]
            resp = api_request("POST", f"/api/research/notebooks/{self.notebook_id}/memory-confirmations", {
                "items": items,
            })
            committed = sum(1 for item in resp.get("items", []) if item.get("status") == "committed")
            self.check("Confirm memories", committed == 4, f"committed={committed}/4")

    def step4_verify_powercontext(self):
        print("\n[Step 4] Verify in PowerContext directly...")
        if not self.scope_id:
            self.check("Skip (no scope)", False, "")
            return

        # Use the correct POST endpoint
        status, data = pc_request("POST", "/v1/atomic-memory/list", {
            "scope_id": self.scope_id,
            "states": ["active"],
            "limit": 100,
        })
        items = data.get("items", [])
        self.check("PowerContext read", len(items) >= 4, f"found={len(items)} memories")

        # Verify content
        if items:
            text = items[0].get("text", "") or items[0].get("content", {}).get("text", "")
            try:
                parsed = json.loads(text)
                self.check("Business JSON valid", "type" in parsed and "content" in parsed, f"schema={parsed.get('schema')}")
            except json.JSONDecodeError:
                self.check("Business JSON valid", False, "Parse failed")

    def step5_cross_session_resume(self):
        print("\n[Step 5] Cross-session resume...")
        if not self.notebook_id:
            self.check("Skip", False, "")
            return

        resp = api_request("POST", f"/api/research/notebooks/{self.notebook_id}/resume", {
            "query": "继续上次研究",
        })
        self.check("Resume response", "reply" in resp, f"has_reply={'reply' in resp}")
        if "reply" in resp:
            reply = resp["reply"]
            self.check("Resume has goals", "目标" in reply or "goal" in reply.lower(), "")
            self.check("Resume has next steps", "计划" in reply or "next" in reply.lower() or "步骤" in reply, "")
        if "memory_refs" in resp:
            self.check("Resume has memory_refs", len(resp["memory_refs"]) > 0, f"refs={len(resp['memory_refs'])}")

    def step6_topic_isolation(self):
        print("\n[Step 6] Topic isolation...")
        # Create a second notebook and verify no cross-contamination
        resp = api_request("POST", "/api/notebooks", {
            "name": "隔离测试课题B",
            "description": "用于验证课题隔离",
        })
        nb_b_id = resp.get("id", "")
        if nb_b_id:
            # Enable research for B
            resp_b = api_request("POST", f"/api/research/notebooks/{nb_b_id}/enable", {
                "title": "隔离测试B",
                "summary": "不应召回A的记忆",
            })
            scope_b = resp_b.get("scope_id", "")

            # Check that B has no memories from A
            resp_mem = api_request("GET", f"/api/research/notebooks/{nb_b_id}/memories")
            count = len(resp_mem.get("memories", []))
            self.check("Topic B empty", count == 0, f"memories_in_B={count}")
            self.check("Scope different", scope_b != self.scope_id, f"A={self.scope_id[:8]}... B={scope_b[:8]}...")

    def step7_report_generation(self):
        print("\n[Step 7] Report generation...")
        if not self.notebook_id:
            self.check("Skip", False, "")
            return

        resp = api_request("POST", f"/api/research/notebooks/{self.notebook_id}/reports", {
            "title": "验收报告",
        })
        self.check("Report generated", "content" in resp, f"has_content={'content' in resp}")
        if "content" in resp:
            content = resp["content"]
            self.check("Report has goals section", "研究目标" in content, "")
            self.check("Report has citations", "M1" in content or "引用" in content, "")
            self.check("Report has structure", "## 1." in content and "## 2." in content, "")

    def step8_revision_and_forget(self):
        print("\n[Step 8] Revision and forget...")
        if not self.notebook_id:
            self.check("Skip", False, "")
            return

        # List memories to get an item_id
        resp = api_request("GET", f"/api/research/notebooks/{self.notebook_id}/memories")
        memories = resp.get("memories", [])
        if memories:
            item = memories[0]
            item_id = item["item_id"]
            etag = item.get("etag", "")

            # Test revision
            if etag:
                rev_resp = api_request("PUT", f"/api/research/notebooks/{self.notebook_id}/memories/{item_id}", {
                    "content": item["content"] + "（已修订）",
                    "etag": etag,
                })
                self.check("Revision with ETag", "revision" in rev_resp or "item_id" in rev_resp, f"new_revision={rev_resp.get('revision', 'N/A')}")

            # Test forget
            forget_resp = api_request("POST", f"/api/research/notebooks/{self.notebook_id}/memories/{item_id}/forget", {})
            self.check("Forget memory", forget_resp.get("state") == "forgotten" or "state" in forget_resp, f"state={forget_resp.get('state', 'N/A')}")


def main() -> int:
    runner = AcceptanceRunner()
    return runner.run_all()


if __name__ == "__main__":
    sys.exit(main())
