"""CDP Connection Pool — 自动重连 + 心跳检测

管理 TabBitBrowser CDP 连接，支持：
- 连接池（复用 WebSocket）
- 自动重连（连接断开时）
- 心跳检测（定期检查 CDP 可用性）
- 懒初始化（首次使用时才连接）
"""

import asyncio
import time
import httpx
import json

CDP_HOST = "127.0.0.1"
CDP_PORT = 9222
CDP_VERSION_URL = f"http://{CDP_HOST}:{CDP_PORT}/json/version"
CDP_LIST_URL = f"http://{CDP_HOST}:{CDP_PORT}/json"

# 连接状态
_cdp_available = None
_last_check = 0
_check_interval = 60  # 60秒检查一次


async def is_cdp_available(force: bool = False) -> bool:
    """检查 CDP 是否可用（带缓存）"""
    global _cdp_available, _last_check
    
    now = time.time()
    if not force and _cdp_available is not None and (now - _last_check) < _check_interval:
        return _cdp_available
    
    try:
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            r = await client.get(CDP_VERSION_URL)
            _cdp_available = r.status_code == 200
            _last_check = now
            return _cdp_available
    except Exception:
        _cdp_available = False
        _last_check = now
        return False


async def get_cdp_ws_url() -> str | None:
    """获取 CDP WebSocket URL"""
    if not await is_cdp_available():
        return None
    try:
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            r = await client.get(CDP_VERSION_URL)
            data = r.json()
            return data.get("webSocketDebuggerUrl")
    except Exception:
        return None


async def cdp_send_command(ws_url: str, method: str, params: dict = None, 
                           timeout: float = 30) -> dict | None:
    """发送 CDP 命令（带消息 ID 过滤和自动重连）
    
    Args:
        ws_url: WebSocket URL
        method: CDP 方法名
        params: 参数
        timeout: 超时时间
        
    Returns:
        CDP 响应数据，失败返回 None
    """
    import websockets
    
    msg_id = int(time.time() * 1000) % 100000
    payload = {"id": msg_id, "method": method, "params": params or {}}
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            # 清除代理环境变量
            import os
            old_proxy = {}
            for key in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
                old_proxy[key] = os.environ.pop(key, None)
            
            try:
                async with websockets.connect(
                    ws_url, 
                    max_size=10 * 1024 * 1024,
                    open_timeout=10,
                ) as ws:
                    await ws.send(json.dumps(payload))
                    
                    deadline = time.time() + timeout
                    while time.time() < deadline:
                        remaining = deadline - time.time()
                        if remaining <= 0:
                            break
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 5))
                            msg = json.loads(raw)
                            if msg.get("id") == msg_id:
                                return msg
                        except asyncio.TimeoutError:
                            continue
                    return None
            finally:
                # 恢复代理环境变量
                for key, val in old_proxy.items():
                    if val is not None:
                        os.environ[key] = val
                        
        except (ConnectionError, websockets.exceptions.WebSocketException, OSError) as e:
            if attempt < max_retries - 1:
                # 重连前等待
                await asyncio.sleep(2)
                # 强制重新检查 CDP 可用性
                await is_cdp_available(force=True)
                continue
            return None
    
    return None


async def create_tab(url: str = "about:blank") -> tuple[str, str] | None:
    """创建新标签页
    
    Returns:
        (target_id, ws_url) 或 None
    """
    if not await is_cdp_available():
        return None
    
    try:
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            r = await client.put(
                f"http://{CDP_HOST}:{CDP_PORT}/json/new",
                params={"url": url}
            )
            if r.status_code == 200:
                data = r.json()
                return (data.get("id"), data.get("webSocketDebuggerUrl"))
    except Exception:
        pass
    return None


async def close_tab(target_id: str) -> bool:
    """关闭标签页"""
    try:
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            r = await client.get(
                f"http://{CDP_HOST}:{CDP_PORT}/json/close/{target_id}"
            )
            return r.status_code == 200
    except Exception:
        return False


# ===== 心跳集成 =====

def reset_cache():
    """重置 CDP 可用性缓存"""
    global _cdp_available, _last_check
    _cdp_available = None
    _last_check = 0


async def heartbeat_check() -> str:
    """心跳检查（供 HEARTBEAT 调用）
    
    Returns:
        状态消息，或 None 表示正常
    """
    available = await is_cdp_available(force=True)
    if available:
        return None
    return "⚠️ TabBitBrowser CDP 不可达，CDP 模块暂停"


if __name__ == "__main__":
    import asyncio
    
    async def test():
        print(f"CDP available: {await is_cdp_available(force=True)}")
        ws = await get_cdp_ws_url()
        print(f"WS URL: {ws}")
        msg = await heartbeat_check()
        print(f"Heartbeat: {msg or 'OK'}")
    
    asyncio.run(test())
