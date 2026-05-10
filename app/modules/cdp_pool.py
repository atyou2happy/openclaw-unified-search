"""CDP Connection Pool — auto-reconnect + heartbeat (v1.0.0 class-based).

Manages TabBitBrowser CDP connections:
- Connection pool (WebSocket reuse)
- Auto-reconnect on disconnect
- Heartbeat check (periodic CDP availability)
- Lazy init (connect on first use)

v1.0.0: Global variables → CDPPool class for testability + thread safety.
"""

import asyncio
import json
import logging
import time

import httpx

logger = logging.getLogger(__name__)

CDP_HOST = "127.0.0.1"
CDP_PORT = 9222
CDP_VERSION_URL = f"http://{CDP_HOST}:{CDP_PORT}/json/version"
CDP_LIST_URL = f"http://{CDP_HOST}:{CDP_PORT}/json"


class CDPPool:
    """CDP connection pool — singleton class for WebSocket management."""

    def __init__(self, check_interval: int = 60):
        self._available: bool | None = None
        self._last_check: float = 0
        self._check_interval: int = check_interval
        self._check_lock: asyncio.Lock | None = None
        self._http_client: httpx.AsyncClient | None = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create httpx client for CDP HTTP requests."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=10, trust_env=False)
        return self._http_client

    async def close(self):
        """Close httpx client gracefully."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def is_available(self, force: bool = False) -> bool:
        """Check CDP availability (cached + locked).

        Args:
            force: Skip cache, check immediately
        """
        now = time.time()
        if not force and self._available is not None and (now - self._last_check) < self._check_interval:
            return self._available

        if self._check_lock is None:
            self._check_lock = asyncio.Lock()

        async with self._check_lock:
            # Double-check after acquiring lock
            if not force and self._available is not None and (now - self._last_check) < self._check_interval:
                return self._available

            try:
                client = await self._get_http_client()
                r = await client.get(CDP_VERSION_URL)
                self._available = r.status_code == 200
                self._last_check = now
                return self._available
            except Exception:
                self._available = False
                self._last_check = now
                return False

    async def get_ws_url(self) -> str | None:
        """Get CDP WebSocket URL."""
        if not await self.is_available():
            return None
        try:
            client = await self._get_http_client()
            r = await client.get(CDP_VERSION_URL)
            data = r.json()
            return data.get("webSocketDebuggerUrl")
        except Exception:
            return None

    async def send_command(
        self, ws_url: str, method: str, params: dict = None, timeout: float = 30
    ) -> dict | None:
        """Send CDP command (with message ID filtering and auto-reconnect).

        Args:
            ws_url: WebSocket URL
            method: CDP method name
            params: Parameters
            timeout: Timeout in seconds

        Returns:
            CDP response data, None on failure
        """
        import websockets

        msg_id = 1
        try:
            # Clear proxy env for localhost WebSocket
            import os
            saved_env = {}
            for key in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"):
                if key in os.environ:
                    saved_env[key] = os.environ.pop(key)

            try:
                async with websockets.connect(
                    ws_url, max_size=10 * 1024 * 1024, close_timeout=5
                ) as ws:
                    # Restore env after connect
                    os.environ.update(saved_env)
                    saved_env.clear()

                    cmd = {"id": msg_id, "method": method}
                    if params:
                        cmd["params"] = params
                    await ws.send(json.dumps(cmd))

                    # Wait for response with matching ID
                    deadline = time.time() + timeout
                    while time.time() < deadline:
                        remaining = deadline - time.time()
                        if remaining <= 0:
                            break
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 5))
                            data = json.loads(raw)

                            # Filter by message ID to avoid event notifications
                            if data.get("id") == msg_id:
                                return data.get("result")

                        except asyncio.TimeoutError:
                            continue
            finally:
                # Restore env if not already restored
                os.environ.update(saved_env)

        except (ConnectionError, websockets.exceptions.WebSocketException, OSError) as e:
            logger.warning(f"CDP command failed ({method}): {e}")
        except Exception as e:
            logger.warning(f"CDP unexpected error ({method}): {e}")

        return None

    async def create_tab(self, url: str = "about:blank") -> dict | None:
        """Create new browser tab via CDP."""
        ws_url = await self.get_ws_url()
        if not ws_url:
            return None
        result = await self.send_command(
            ws_url, "Target.createTarget", {"url": url}
        )
        return result

    async def close_tab(self, target_id: str) -> bool:
        """Close browser tab via CDP."""
        ws_url = await self.get_ws_url()
        if not ws_url:
            return False
        result = await self.send_command(
            ws_url, "Target.closeTarget", {"targetId": target_id}
        )
        return result is not None

    def reset_cache(self):
        """Reset availability cache (for hot-reload)."""
        self._available = None
        self._last_check = 0


# Global singleton instance
cdp_pool = CDPPool()


# Backward-compatible module-level API
async def is_cdp_available(force: bool = False) -> bool:
    """Check CDP availability (backward compat wrapper)."""
    return await cdp_pool.is_available(force=force)


async def get_cdp_ws_url() -> str | None:
    """Get CDP WebSocket URL (backward compat wrapper)."""
    return await cdp_pool.get_ws_url()


async def cdp_send_command(ws_url: str, method: str, params: dict = None,
                           timeout: float = 30) -> dict | None:
    """Send CDP command (backward compat wrapper)."""
    return await cdp_pool.send_command(ws_url, method, params, timeout)


async def cdp_create_tab(url: str = "about:blank") -> dict | None:
    """Create browser tab (backward compat wrapper)."""
    return await cdp_pool.create_tab(url)


async def cdp_close_tab(target_id: str) -> bool:
    """Close browser tab (backward compat wrapper)."""
    return await cdp_pool.close_tab(target_id)


# Aliases for direct import convenience (used by CDP AI modules)
create_tab = cdp_create_tab
close_tab = cdp_close_tab


def reset_cache():
    """Reset CDP availability cache (backward compat wrapper)."""
    cdp_pool.reset_cache()


# Standalone test
async def _test():
    """Quick CDP connectivity test."""
    available = await is_cdp_available(force=True)
    print(f"CDP available: {available}")
    if available:
        ws_url = await get_cdp_ws_url()
        print(f"WebSocket URL: {ws_url}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_test())
