#!/usr/bin/env python3
"""Bootstrap script for 研续 ResearchMemory.

Generates local configuration, checks prerequisites, and prepares the
environment for first run. Does not hardcode real credentials.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEPLOY_DIR = PROJECT_ROOT / "deploy"
APP_DIR = PROJECT_ROOT / "app"


def check_prerequisites() -> list[str]:
    """Check that required tools are available."""
    errors = []

    # Python
    if sys.version_info < (3, 11):
        errors.append(f"Python >= 3.11 required, found {sys.version}")

    # uv
    if not shutil.which("uv"):
        errors.append("uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh")

    # Docker (optional for compose)
    if not shutil.which("docker"):
        errors.append("WARNING: docker not found. Compose deployment requires Docker.")

    # Node.js
    node_version = "unknown"
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        node_version = result.stdout.strip()
        major = int(node_version.lstrip("v").split(".")[0])
        if major < 18:
            errors.append(f"Node.js >= 18.18 required, found {node_version}")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        errors.append(f"Node.js not found or timed out (version: {node_version})")

    return errors


def setup_env_file() -> None:
    """Create .env from .env.example if it doesn't exist."""
    env_file = DEPLOY_DIR / ".env"
    example_file = DEPLOY_DIR / ".env.example"

    if env_file.exists():
        print(f"  .env already exists at {env_file}")
        return

    if example_file.exists():
        shutil.copy(example_file, env_file)
        print(f"  Created {env_file} from {example_file}")
        print("  ⚠️  Edit .env with your real credentials before deploying!")
    else:
        print(f"  WARNING: {example_file} not found")


def install_app_dependencies() -> bool:
    """Install Open Notebook app dependencies."""
    print("  Installing app dependencies with uv...")
    try:
        result = subprocess.run(
            ["uv", "sync"],
            cwd=APP_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            print(f"  ERROR: uv sync failed: {result.stderr[:200]}")
            return False
        print("  ✓ App dependencies installed")
        return True
    except subprocess.TimeoutExpired:
        print("  ERROR: uv sync timed out")
        return False


def install_powercontext() -> bool:
    """Install PowerContext 1.4.1 as a standalone tool."""
    print("  Checking PowerContext installation...")
    try:
        result = subprocess.run(
            ["powercontext", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if "1.4.1" in result.stdout:
            print("  ✓ PowerContext 1.4.1 already installed")
            return True
    except FileNotFoundError:
        pass

    print("  Installing PowerContext 1.4.1...")
    try:
        result = subprocess.run(
            ["uv", "tool", "install", "powercontext[cli,server]==1.4.1"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print("  ✓ PowerContext 1.4.1 installed")
            return True
        else:
            print(f"  ERROR: {result.stderr[:200]}")
            return False
    except subprocess.TimeoutExpired:
        print("  ERROR: PowerContext install timed out")
        return False


def main() -> int:
    print("=" * 60)
    print("研续 ResearchMemory - Bootstrap")
    print("=" * 60)
    print()

    # Step 1: Check prerequisites
    print("[1/4] Checking prerequisites...")
    errors = check_prerequisites()
    warnings = [e for e in errors if e.startswith("WARNING")]
    failures = [e for e in errors if not e.startswith("WARNING")]

    for w in warnings:
        print(f"  ⚠️  {w}")
    for f in failures:
        print(f"  ✗ {f}")

    if failures:
        print("\n  Bootstrap failed due to missing prerequisites.")
        return 1

    print("  ✓ Prerequisites OK")
    print()

    # Step 2: Setup .env
    print("[2/4] Setting up configuration...")
    setup_env_file()
    print()

    # Step 3: Install dependencies
    print("[3/4] Installing dependencies...")
    if not install_app_dependencies():
        return 1
    if not install_powercontext():
        return 1
    print()

    # Step 4: Summary
    print("[4/4] Bootstrap complete!")
    print()
    print("Next steps:")
    print("  1. Edit deploy/.env with your real credentials")
    print("  2. Start services:")
    print("     docker compose -f deploy/compose.yaml --env-file deploy/.env up -d")
    print("  3. Run health check:")
    print("     python scripts/healthcheck.py")
    print("  4. Seed demo data:")
    print("     python scripts/seed_demo.py")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
