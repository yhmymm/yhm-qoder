#!/usr/bin/env python3
"""Health check script for 研续 ResearchMemory.

Verifies that all services are running and accessible.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

API_BASE = "http://127.0.0.1:5055"
PC_BASE = "http://127.0.0.1:8001"


def check_service(name: str, url: str, timeout: float = 5.0) -> bool:
    """Check if a service is responding."""
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except (URLError, ConnectionError, OSError) as e:
        print(f"  ✗ {name}: {e}")
        return False


def check_api_health() -> dict:
    """Check the research health endpoint."""
    try:
        req = Request(
            f"{API_BASE}/api/research/health",
            headers={"Accept": "application/json"},
        )
        with urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def main() -> int:
    print("=" * 60)
    print("研续 ResearchMemory - Health Check")
    print("=" * 60)
    print()

    results = {}

    # Check SurrealDB (via API)
    print("[1/4] SurrealDB (via API)...")
    results["surrealdb"] = check_service("SurrealDB", f"{API_BASE}/api/notebooks")
    if results["surrealdb"]:
        print("  ✓ SurrealDB accessible via API")
    print()

    # Check PowerContext
    print("[2/4] PowerContext...")
    results["powercontext"] = check_service("PowerContext", f"{PC_BASE}/health/live")
    if results["powercontext"]:
        print("  ✓ PowerContext responding")
    print()

    # Check API
    print("[3/4] Open Notebook API...")
    results["api"] = check_service("API", f"{API_BASE}/api/notebooks")
    if results["api"]:
        print("  ✓ API responding")
    print()

    # Check research feature
    print("[4/4] Research Feature...")
    health = check_api_health()
    results["research"] = "error" not in health
    if results["research"]:
        print(f"  ✓ Research enabled: {health.get('enabled')}")
        print(f"  ✓ PowerContext available: {health.get('powercontext_available')}")
    else:
        print(f"  ✗ Research health: {health.get('error', 'unknown')}")
    print()

    # Summary
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"Results: {passed}/{total} checks passed")

    if passed == total:
        print("✓ All services healthy!")
        return 0
    else:
        print("✗ Some services are not responding")
        return 1


if __name__ == "__main__":
    sys.exit(main())
