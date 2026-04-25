"""Configuration management — env vars override defaults."""

import os
from pathlib import Path


def _env(key: str, default: str | None = None) -> str | None:
    """Read env var, stripping whitespace."""
    val = os.environ.get(key)
    return val.strip() if val else default


def _env_int(key: str, default: int) -> int:
    """Read env var as int."""
    val = _env(key)
    return int(val) if val else default


def _env_bool(key: str, default: bool) -> bool:
    """Read env var as bool (1/true/yes = True)."""
    val = _env(key)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes")


class Config:
    """Application configuration — env vars override class defaults."""

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8900
    DEBUG: bool = False

    # Cache
    CACHE_MAX_SIZE: int = 1000
    CACHE_TTL_SECONDS: int = 3600  # 1 hour

    # Search engine
    DEFAULT_TIMEOUT: int = 30
    DEFAULT_MAX_RESULTS: int = 10
    MAX_CONCURRENT_MODULES: int = 10

    # Proxy (for WSL / restricted networks)
    PROXY_URL: str | None = "http://127.0.0.1:21882"

    # TabBitBrowser
    TABBIT_CDP_PORT: int = 9222
    TABBIT_TIMEOUT: int = 120
    TABBIT_SCRIPT_PATH: str = str(
        Path(__file__).parent.parent.parent.parent
        / "claw-mem" / "tools" / "tabbit_cdp_search.py"
    )

    # GitHub
    GITHUB_TOKEN: str | None = None

    # PDF
    PDF_MAX_SIZE_MB: int = 50
    PDF_MAX_PAGES: int = 100

    # DuckDuckGo
    DDG_REGION: str = "cn-zh"

    # Academic
    SEMANTIC_SCHOLAR_API_KEY: str | None = None

    @classmethod
    def get_proxy(cls) -> str | None:
        """Get proxy URL — env vars take precedence over class default."""
        return (
            _env("HTTPS_PROXY")
            or _env("HTTP_PROXY")
            or _env("https_proxy")
            or _env("http_proxy")
            or cls.PROXY_URL
        )
