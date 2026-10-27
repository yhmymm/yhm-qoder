"""PowerContext HTTP adapter for research memory.

Wraps the real PowerContext 1.4.1 HTTP API using httpx.AsyncClient.
All calls use the actual contract verified in M0 probe.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import httpx
from loguru import logger


class PowerContextError(Exception):
    """Base error for PowerContext operations."""

    def __init__(self, message: str, status_code: Optional[int] = None, detail: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class PowerContextClient:
    """Async HTTP client for PowerContext 1.4.1.

    Uses the actual API contract verified in M0:
    - Source capture returns 202 Accepted
    - ETag is an opaque string from response headers
    - state_version starts at 0
    - Lifecycle only supports 'forgotten'
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
    ):
        self.base_url = (
            base_url
            or os.getenv("RESEARCH_POWERCONTEXT_BASE_URL")
            or "http://127.0.0.1:8001"
        ).rstrip("/")
        self.token = token or os.getenv("RESEARCH_POWERCONTEXT_TOKEN")
        self.connect_timeout = connect_timeout or float(
            os.getenv("RESEARCH_POWERCONTEXT_CONNECT_TIMEOUT_SECONDS", "2")
        )
        self.read_timeout = read_timeout or float(
            os.getenv("RESEARCH_POWERCONTEXT_READ_TIMEOUT_SECONDS", "8")
        )
        self._client: Optional[httpx.AsyncClient] = None

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._headers(),
                timeout=httpx.Timeout(self.read_timeout, connect=self.connect_timeout),
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def health_check(self) -> bool:
        """Check if PowerContext is reachable."""
        try:
            client = await self._get_client()
            r = await client.get("/health/live")
            return r.status_code == 200
        except Exception as e:
            logger.warning(f"PowerContext health check failed: {e}")
            return False

    # --- Scope operations ---

    async def create_scope(
        self, title: str, summary: str, idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new scope. Returns {scope_id, title, summary, version}."""
        client = await self._get_client()
        body = {
            "title": title,
            "summary": summary,
            "idempotency_key": idempotency_key or f"idem-{uuid4().hex[:16]}",
        }
        r = await client.post("/v1/scopes", json=body)
        if r.status_code not in (200, 201):
            raise PowerContextError(
                f"Failed to create scope: {r.status_code}",
                status_code=r.status_code,
                detail=r.text,
            )
        return r.json()

    # --- Source operations ---

    async def capture_content_source(
        self, scope_id: str, source_id: str, content: str, metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Capture a content source. Returns 202 Accepted with source reference."""
        client = await self._get_client()
        body: Dict[str, Any] = {
            "scope_id": scope_id,
            "source_id": source_id,
            "content": content,
        }
        if metadata:
            body["metadata"] = metadata
        r = await client.post("/v1/sources/content", json=body)
        # M0 probe: returns 202 Accepted (async)
        if r.status_code not in (200, 201, 202):
            raise PowerContextError(
                f"Failed to capture source: {r.status_code}",
                status_code=r.status_code,
                detail=r.text,
            )
        return r.json() if r.content else {}

    # --- Atomic Memory operations ---

    async def create_atomic_memory(
        self, scope_id: str, kind: str, text: str
    ) -> Dict[str, Any]:
        """Create an atomic memory artifact.

        Returns {family, artifact_id, revision, etag}.
        """
        client = await self._get_client()
        body = {
            "family": "atomic-memory",
            "content": {
                "schema": "powercontext.atomic-memory.v1",
                "kind": kind,
                "text": text,
            },
        }
        r = await client.post(f"/v1/scopes/{scope_id}/artifacts", json=body)
        if r.status_code not in (200, 201):
            raise PowerContextError(
                f"Failed to create atomic memory: {r.status_code}",
                status_code=r.status_code,
                detail=r.text,
            )
        result = r.json()
        # Capture ETag from response header
        etag = r.headers.get("etag") or r.headers.get("ETag")
        if etag:
            result["etag"] = etag
        return result

    async def read_artifact(
        self, scope_id: str, artifact_id: str
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """Read current artifact content. Returns (record, etag)."""
        client = await self._get_client()
        r = await client.get(
            f"/v1/scopes/{scope_id}/artifacts/atomic-memory/{artifact_id}"
        )
        if r.status_code == 404:
            raise PowerContextError(
                f"Artifact not found: {artifact_id}", status_code=404
            )
        if r.status_code != 200:
            raise PowerContextError(
                f"Failed to read artifact: {r.status_code}",
                status_code=r.status_code,
                detail=r.text,
            )
        etag = r.headers.get("etag") or r.headers.get("ETag")
        return r.json(), etag

    async def replace_artifact(
        self,
        scope_id: str,
        artifact_id: str,
        kind: str,
        text: str,
        if_match: str,
    ) -> Dict[str, Any]:
        """Replace artifact content with If-Match. Returns updated record + etag."""
        client = await self._get_client()
        body = {
            "content": {
                "schema": "powercontext.atomic-memory.v1",
                "kind": kind,
                "text": text,
            }
        }
        headers = {"If-Match": if_match}
        r = await client.put(
            f"/v1/scopes/{scope_id}/artifacts/atomic-memory/{artifact_id}",
            json=body,
            headers=headers,
        )
        if r.status_code == 412:
            raise PowerContextError(
                "Precondition failed: ETag expired. Please re-read and retry.",
                status_code=412,
                detail=r.text,
            )
        if r.status_code not in (200, 201):
            raise PowerContextError(
                f"Failed to replace artifact: {r.status_code}",
                status_code=r.status_code,
                detail=r.text,
            )
        result = r.json()
        etag = r.headers.get("etag") or r.headers.get("ETag")
        if etag:
            result["etag"] = etag
        return result

    async def list_atomic_memories(
        self,
        scope_id: str,
        states: Optional[List[str]] = None,
        kind: Optional[str] = None,
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List atomic memories with pagination. Returns {items, next_cursor}."""
        client = await self._get_client()
        body: Dict[str, Any] = {"scope_id": scope_id, "limit": limit}
        if states:
            body["states"] = states
        else:
            body["states"] = ["active"]
        if kind:
            body["kind"] = kind
        if cursor:
            body["cursor"] = cursor
        r = await client.post("/v1/atomic-memory/list", json=body)
        if r.status_code != 200:
            raise PowerContextError(
                f"Failed to list memories: {r.status_code}",
                status_code=r.status_code,
                detail=r.text,
            )
        return r.json()

    async def list_all_atomic_memories(
        self, scope_id: str, states: Optional[List[str]] = None, kind: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all atomic memories, handling pagination."""
        all_items = []
        cursor = None
        while True:
            result = await self.list_atomic_memories(
                scope_id, states=states, kind=kind, limit=100, cursor=cursor
            )
            items = result.get("items", [])
            all_items.extend(items)
            cursor = result.get("next_cursor")
            if not cursor:
                break
        return all_items

    async def search_atomic_memories(
        self,
        scope_id: str,
        query: str,
        mode: str = "text",
        kind: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Search atomic memories. Returns {items, next_cursor}."""
        client = await self._get_client()
        body: Dict[str, Any] = {
            "scope_id": scope_id,
            "query": query,
            "mode": mode,
            "limit": limit,
        }
        if kind:
            body["kind"] = kind
        r = await client.post("/v1/atomic-memory/search", json=body)
        if r.status_code != 200:
            raise PowerContextError(
                f"Failed to search memories: {r.status_code}",
                status_code=r.status_code,
                detail=r.text,
            )
        return r.json()

    async def get_artifact_state(
        self, scope_id: str, artifact_id: str
    ) -> Dict[str, Any]:
        """Get artifact lifecycle state. Returns {state, state_version}."""
        client = await self._get_client()
        r = await client.get(
            f"/v1/scopes/{scope_id}/artifacts/atomic-memory/{artifact_id}/state"
        )
        if r.status_code == 404:
            raise PowerContextError(
                f"Artifact state not found: {artifact_id}", status_code=404
            )
        if r.status_code != 200:
            raise PowerContextError(
                f"Failed to get artifact state: {r.status_code}",
                status_code=r.status_code,
                detail=r.text,
            )
        return r.json()

    async def forget_artifact(
        self, scope_id: str, artifact_id: str, revision: int, state_version: int
    ) -> Dict[str, Any]:
        """Forget an artifact (lifecycle → forgotten)."""
        client = await self._get_client()
        body = {
            "scope_id": scope_id,
            "target": {
                "artifact": {
                    "family": "atomic-memory",
                    "artifact_id": artifact_id,
                    "revision": revision,
                },
                "state_version": state_version,
            },
            "state": "forgotten",
        }
        r = await client.post("/v1/atomic-memory/lifecycle", json=body)
        if r.status_code != 200:
            raise PowerContextError(
                f"Failed to forget artifact: {r.status_code}",
                status_code=r.status_code,
                detail=r.text,
            )
        return r.json()

    async def list_revisions(
        self, scope_id: str, artifact_id: str
    ) -> List[Dict[str, Any]]:
        """List all revisions of an artifact."""
        client = await self._get_client()
        r = await client.get(
            f"/v1/scopes/{scope_id}/artifacts/atomic-memory/{artifact_id}/revisions"
        )
        if r.status_code != 200:
            raise PowerContextError(
                f"Failed to list revisions: {r.status_code}",
                status_code=r.status_code,
                detail=r.text,
            )
        return r.json()

    async def read_revision(
        self, scope_id: str, artifact_id: str, revision: int
    ) -> Dict[str, Any]:
        """Read a specific revision of an artifact."""
        client = await self._get_client()
        r = await client.get(
            f"/v1/scopes/{scope_id}/artifacts/atomic-memory/{artifact_id}/revisions/{revision}"
        )
        if r.status_code == 404:
            raise PowerContextError(
                f"Revision not found: {artifact_id} r{revision}", status_code=404
            )
        if r.status_code != 200:
            raise PowerContextError(
                f"Failed to read revision: {r.status_code}",
                status_code=r.status_code,
                detail=r.text,
            )
        return r.json()


# Singleton instance
_client: Optional[PowerContextClient] = None


def get_powercontext_client() -> PowerContextClient:
    """Get or create the singleton PowerContext client."""
    global _client
    if _client is None:
        _client = PowerContextClient()
    return _client
