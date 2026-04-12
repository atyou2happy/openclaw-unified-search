"""Unified data models for search requests and responses."""

from datetime import datetime
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """统一搜索请求"""
    query: str = Field(..., min_length=1, description="搜索关键词/问题")
    sources: list[str] = Field(default_factory=list, description="指定数据源，空=全部可用")
    max_results: int = Field(default=10, ge=1, le=50, description="每个源最大结果数")
    timeout: int = Field(default=30, ge=5, le=120, description="超时秒数")
    depth: str = Field(default="normal", pattern="^(quick|normal|deep)$", description="搜索深度")
    language: str = Field(default="auto", description="语言: auto|zh|en")


class SearchResult(BaseModel):
    """单条搜索结果"""
    title: str = Field(default="", description="标题")
    url: str = Field(default="", description="来源URL")
    snippet: str = Field(default="", description="摘要")
    source: str = Field(..., description="来源模块名")
    content: str | None = Field(default=None, description="完整内容（按需）")
    relevance: float = Field(default=0.0, ge=0.0, le=1.0, description="相关度评分")
    timestamp: datetime | None = Field(default=None, description="发布时间")
    metadata: dict = Field(default_factory=dict, description="额外元数据")


class SearchResponse(BaseModel):
    """统一搜索响应"""
    query: str
    results: list[SearchResult] = Field(default_factory=list)
    total: int = 0
    elapsed: float = Field(default=0.0, description="耗时秒")
    sources_used: list[str] = Field(default_factory=list, description="实际使用的数据源")
    cached: bool = False
    errors: dict[str, str] = Field(default_factory=dict, description="模块错误信息")


class ModuleStatus(BaseModel):
    """模块状态"""
    name: str
    description: str
    available: bool
    last_error: str | None = None
