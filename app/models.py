"""Unified data models for search requests and responses."""

from datetime import datetime
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """统一搜索请求"""
    query: str = Field(..., min_length=1, description="搜索关键词/问题")
    sources: list[str] = Field(default_factory=list, description="指定数据源，空=全部可用")
    max_results: int = Field(default=10, ge=1, le=50, description="每个源最大结果数")
    limit: int = Field(default=10, ge=1, le=50, description="结果数量限制")
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
    metadata: dict = Field(default_factory=dict, description="引擎元数据（意图识别等）")


class ModuleStatus(BaseModel):
    """模块状态"""
    name: str
    description: str
    available: bool
    last_error: str | None = None


class QueryAnalysis(BaseModel):
    """Enhanced query analysis result — v2.0 查询增强分析"""
    original_query: str = Field(..., description="原始查询")
    enhanced_query: str = Field(default="", description="增强后的查询")
    rewritten_queries: list[str] = Field(default_factory=list, description="改写变体列表")
    language: str = Field(default="auto", description="检测到的语言: zh|en|mixed")
    is_question: bool = Field(default=False, description="是否为问句")
    primary_type: str = Field(default="general", description="主意图类型")
    secondary_types: list[str] = Field(default_factory=list, description="次意图类型")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="意图置信度")
    spell_corrected: bool = Field(default=False, description="是否做了拼写纠错")
    expanded_terms: list[str] = Field(default_factory=list, description="扩展的同义词/相关词")


class ModulePerformance(BaseModel):
    """Module performance metrics — v2.0 模块性能追踪"""
    name: str
    total_requests: int = 0
    successful_requests: int = 0
    avg_response_time: float = 0.0
    avg_result_count: float = 0.0
    avg_quality_score: float = 0.0
    consecutive_failures: int = 0
    last_success_time: float = 0.0
    last_failure_time: float = 0.0
    success_rate_7d: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.5  # unknown -> neutral
        return self.successful_requests / self.total_requests

    @property
    def is_healthy(self) -> bool:
        """Module is healthy if success rate > 50% and < 5 consecutive failures"""
        return self.consecutive_failures < 5 and self.success_rate >= 0.5


class SearchResultV2(BaseModel):
    """Enhanced search result with quality scores — v2.0"""
    title: str = Field(default="", description="标题")
    url: str = Field(default="", description="来源URL")
    snippet: str = Field(default="", description="摘要")
    source: str = Field(..., description="来源模块名")
    content: str | None = Field(default=None, description="完整内容")
    relevance: float = Field(default=0.0, ge=0.0, le=1.0, description="综合相关度")
    timestamp: datetime | None = Field(default=None, description="发布时间")
    metadata: dict = Field(default_factory=dict, description="额外元数据")
    # v2.0 quality breakdown
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0, description="质量总分")
    quality_breakdown: dict = Field(default_factory=dict, description="质量分项: {relevance,authority,freshness,completeness}")
    category: str = Field(default="general", description="结果类别: web|academic|code|social|video|news|knowledge")
