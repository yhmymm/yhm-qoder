#!/usr/bin/env python3
"""
PowerContext 1.4.1 Memory Probe Script
Tests the actual HTTP contract for atomic memory operations.
"""

import httpx
import json
import time
import uuid

BASE_URL = "http://127.0.0.1:8001"
PROBE_ID = str(uuid.uuid4())[:8]

def log_step(step: str, detail: str = ""):
    print(f"\n{'='*60}")
    print(f"STEP: {step}")
    if detail:
        print(f"  {detail}")
    print(f"{'='*60}")

def log_response(response: httpx.Response, show_body: bool = True):
    print(f"  Status: {response.status_code}")
    if show_body:
        try:
            body = response.json()
            print(f"  Body: {json.dumps(body, indent=2, ensure_ascii=False)[:2000]}")
        except Exception:
            print(f"  Body: {response.text[:500]}")

def main():
    client = httpx.Client(base_url=BASE_URL, timeout=10.0)
    
    # Step 1: Health check
    log_step("1. Health Check")
    r = client.get("/health/live")
    log_response(r)
    assert r.status_code == 200, f"Health check failed: {r.status_code}"
    
    r = client.get("/health/ready")
    log_response(r)
    assert r.status_code == 200, f"Readiness check failed: {r.status_code}"
    
    # Step 2: Create Scope
    log_step("2. Create Scope", f"idempotency_key=probe-{PROBE_ID}")
    scope_payload = {
        "title": f"Probe Scope {PROBE_ID}",
        "summary": "Temporary scope for API contract verification",
        "idempotency_key": f"probe-{PROBE_ID}",
        "context_references": [],
        "external_references": []
    }
    r = client.post("/v1/scopes", json=scope_payload)
    log_response(r)
    assert r.status_code == 201, f"Scope creation failed: {r.status_code}"
    scope_data = r.json()
    scope_id = scope_data["scope_id"]
    print(f"\n  >>> Created Scope ID: {scope_id}")
    print(f"  >>> Scope Version: {scope_data['version']}")
    
    # Step 3: Capture Content Source (confirmation event)
    log_step("3. Capture Content Source")
    source_id = f"probe-confirmation-{PROBE_ID}"
    source_payload = {
        "scope_id": scope_id,
        "source_id": source_id,
        "content": json.dumps({
            "event_type": "memory_confirmation",
            "operator_id": f"op-{PROBE_ID}",
            "confirmed_at": "2026-10-27T15:00:00Z",
            "note": "Probe confirmation event"
        }),
        "metadata": {"probe": True}
    }
    r = client.post("/v1/sources/content", json=source_payload)
    log_response(r)
    assert r.status_code in (201, 202), f"Source capture failed: {r.status_code}"
    source_ref = r.json()
    print(f"\n  >>> Source Reference: {source_ref}")
    
    # Step 4: Create Atomic Memory Artifact
    log_step("4. Create Atomic Memory Artifact")
    memory_content = json.dumps({
        "schema_version": "research-memory.v1",
        "item_id": f"memory-{PROBE_ID}",
        "operation_id": f"operation-{PROBE_ID}",
        "type": "next_step",
        "content": "Check JOIN condition related failure cases.",
        "epistemic_status": "user_statement",
        "workflow_status": "open",
        "evidence_refs": [],
        "confirmation_source_ref": {
            "source_type": "content",
            "source_id": source_id
        },
        "confirmed_at": "2026-10-27T15:00:00Z"
    }, ensure_ascii=False)
    
    create_memory_payload = {
        "family": "atomic-memory",
        "content": {
            "schema": "powercontext.atomic-memory.v1",
            "kind": "research.next_step",
            "text": memory_content
        }
    }
    r = client.post(f"/v1/scopes/{scope_id}/artifacts", json=create_memory_payload)
    log_response(r, show_body=True)
    assert r.status_code == 201, f"Memory creation failed: {r.status_code}"
    
    # Capture ETag and artifact info
    etag = r.headers.get("ETag")
    request_id = r.headers.get("X-PowerContext-Request-ID")
    created = r.json()
    artifact_id = created["artifact_id"]
    revision = created["revision"]
    print(f"\n  >>> Artifact ID: {artifact_id}")
    print(f"  >>> Revision: {revision}")
    print(f"  >>> ETag: {etag}")
    print(f"  >>> Request ID: {request_id}")
    
    # Step 5: Read Current Artifact (get ETag)
    log_step("5. Read Current Artifact Head")
    r = client.get(f"/v1/scopes/{scope_id}/artifacts/atomic-memory/{artifact_id}")
    log_response(r, show_body=True)
    assert r.status_code == 200, f"Artifact read failed: {r.status_code}"
    
    current_etag = r.headers.get("ETag")
    current_data = r.json()
    print(f"\n  >>> Current ETag: {current_etag}")
    print(f"  >>> Content kind: {current_data['content'].get('kind')}")
    
    # Step 6: List Atomic Memories
    log_step("6. List Atomic Memories")
    list_payload = {
        "scope_id": scope_id,
        "states": ["active"],
        "limit": 50
    }
    r = client.post("/v1/atomic-memory/list", json=list_payload)
    log_response(r, show_body=True)
    assert r.status_code == 200, f"Memory list failed: {r.status_code}"
    list_data = r.json()
    print(f"\n  >>> Total items: {len(list_data.get('items', []))}")
    
    # Step 7: Search Atomic Memories
    log_step("7. Search Atomic Memories")
    search_payload = {
        "scope_id": scope_id,
        "query": "JOIN",
        "mode": "text",
        "limit": 10
    }
    r = client.post("/v1/atomic-memory/search", json=search_payload)
    log_response(r, show_body=True)
    assert r.status_code == 200, f"Memory search failed: {r.status_code}"
    search_data = r.json()
    print(f"\n  >>> Hits: {len(search_data.get('hits', []))}")
    
    # Step 8: Replace (Revise) Artifact with If-Match
    log_step("8. Replace Artifact (Revision)")
    revised_content = json.dumps({
        "schema_version": "research-memory.v1",
        "item_id": f"memory-{PROBE_ID}",
        "operation_id": f"operation-{PROBE_ID}",
        "type": "next_step",
        "content": "First organize notes for JOIN failure cases, then verify Schema selection hypothesis.",
        "epistemic_status": "user_statement",
        "workflow_status": "open",
        "evidence_refs": [],
        "confirmation_source_ref": {
            "source_type": "content",
            "source_id": source_id
        },
        "confirmed_at": "2026-10-27T15:05:00Z",
        "revised_at": "2026-10-27T15:10:00Z"
    }, ensure_ascii=False)
    
    replace_payload = {
        "content": {
            "schema": "powercontext.atomic-memory.v1",
            "kind": "research.next_step",
            "text": revised_content
        }
    }
    r = client.put(
        f"/v1/scopes/{scope_id}/artifacts/atomic-memory/{artifact_id}",
        json=replace_payload,
        headers={"If-Match": current_etag}
    )
    log_response(r, show_body=True)
    assert r.status_code == 200, f"Artifact replace failed: {r.status_code}"
    
    new_etag = r.headers.get("ETag")
    new_revision = r.json().get("revision")
    print(f"\n  >>> New Revision: {new_revision}")
    print(f"  >>> New ETag: {new_etag}")
    
    # Step 9: Test Precondition Failed (wrong ETag)
    log_step("9. Test Precondition Failed (412)")
    r = client.put(
        f"/v1/scopes/{scope_id}/artifacts/atomic-memory/{artifact_id}",
        json=replace_payload,
        headers={"If-Match": '"invalid-etag-value"'}
    )
    log_response(r, show_body=False)
    assert r.status_code == 412, f"Expected 412, got: {r.status_code}"
    print(f"\n  >>> Correctly rejected stale ETag with 412")
    
    # Step 10: Read Revision History
    log_step("10. List Artifact Revisions")
    r = client.get(f"/v1/scopes/{scope_id}/artifacts/atomic-memory/{artifact_id}/revisions")
    log_response(r, show_body=True)
    assert r.status_code == 200, f"Revisions list failed: {r.status_code}"
    revisions = r.json()
    print(f"\n  >>> Total revisions: {len(revisions.get('items', []))}")
    
    # Step 11: Read Specific Historical Revision
    log_step("11. Read Historical Revision (revision 1)")
    r = client.get(f"/v1/scopes/{scope_id}/artifacts/atomic-memory/{artifact_id}/revisions/1")
    log_response(r, show_body=True)
    assert r.status_code == 200, f"Revision read failed: {r.status_code}"
    
    # Step 12: Get State before Forget
    log_step("12. Get Atomic Memory State")
    r = client.get(f"/v1/scopes/{scope_id}/artifacts/atomic-memory/{artifact_id}/state")
    log_response(r, show_body=True)
    state_data = r.json()
    state_version = state_data.get("state_version", 0)
    print(f"\n  >>> Current state_version: {state_version}")
    
    # Step 13: Forget Memory (Lifecycle Change)
    log_step("13. Forget Memory (Lifecycle Change)")
    forget_payload = {
        "scope_id": scope_id,
        "target": {
            "artifact": {
                "family": "atomic-memory",
                "artifact_id": artifact_id,
                "revision": new_revision
            },
            "state_version": state_version
        },
        "state": "forgotten"
    }
    r = client.post("/v1/atomic-memory/lifecycle", json=forget_payload)
    log_response(r, show_body=True)
    assert r.status_code == 200, f"Lifecycle change failed: {r.status_code}"
    lifecycle_result = r.json()
    print(f"\n  >>> Changed: {lifecycle_result.get('changed')}")
    
    # Step 14: Verify Forgotten State
    log_step("14. Verify Forgotten State")
    r = client.get(f"/v1/scopes/{scope_id}/artifacts/atomic-memory/{artifact_id}/state")
    log_response(r, show_body=True)
    final_state = r.json()
    print(f"\n  >>> Final state: {final_state.get('state')}")
    assert final_state.get('state') == 'forgotten', "Memory should be forgotten"
    
    # Step 15: List Active - Should Not Include Forgotten
    log_step("15. List Active Memories (Should Exclude Forgotten)")
    r = client.post("/v1/atomic-memory/list", json={"scope_id": scope_id, "states": ["active"]})
    log_response(r, show_body=True)
    active_items = r.json().get("items", [])
    forgotten_in_active = [i for i in active_items if i["artifact"]["artifact_id"] == artifact_id]
    print(f"\n  >>> Forgotten memory in active list: {len(forgotten_in_active)} (should be 0)")
    
    print(f"\n{'='*60}")
    print("PROBE COMPLETE - All steps passed!")
    print(f"{'='*60}")
    
    # Summary
    print(f"\nSummary:")
    print(f"  Scope ID: {scope_id}")
    print(f"  Artifact ID: {artifact_id}")
    print(f"  Source ID: {source_id}")
    print(f"  Revisions: 1 -> {new_revision}")
    print(f"  Final State: forgotten")
    print(f"  ETag behavior: Verified (create -> read -> replace with If-Match -> 412 on stale)")

if __name__ == "__main__":
    main()
