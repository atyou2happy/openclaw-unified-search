"""Configuration management."""

from pathlib import Path


class Config:
    """Application configuration with sensible defaults."""

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
    # Set HTTP_PROXY / HTTPS_PROXY env vars, or configure here
    PROXY_URL: str | None = "http://127.0.0.1:21882"  # WestWorld proxy for external access

    # TabBitBrowser
    TABBIT_CDP_PORT: int = 9222
    TABBIT_TIMEOUT: int = 120
    TABBIT_SCRIPT_PATH: str = str(
        Path(__file__).parent.parent.parent.parent /
        "claw-mem" / "tools" / "tabbit_cdp_search.py"
    )

    # GitHub
    GITHUB_TOKEN: str | None = None  # From env var GITHUB_TOKEN

    # PDF
    PDF_MAX_SIZE_MB: int = 50
    PDF_MAX_PAGES: int = 100

    # DuckDuckGo
    DDG_REGION: str = "cn-zh"

    # Academic
    SEMANTIC_SCHOLAR_API_KEY: str | None = None

    @classmethod
    def get_proxy(cls) -> str | None:
        """Get proxy URL from config or env"""
        import os
        return (
            cls.PROXY_URL
            or os.environ.get("HTTPS_PROXY")
            or os.environ.get("HTTP_PROXY")
            or os.environ.get("https_proxy")
            or os.environ.get("http_proxy")
        )
