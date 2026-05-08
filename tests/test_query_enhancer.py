"""Tests for QueryEnhancer — v2.0 query enhancement engine."""

import pytest
from app.engine.query_enhancer import QueryEnhancer
from app.models import QueryAnalysis


class TestQueryEnhancerBasic:
    """Basic enhancement tests."""

    def test_empty_query(self):
        analysis = QueryEnhancer.enhance("")
        assert analysis.original_query == ""
        assert analysis.language == "unknown"
        assert analysis.confidence == 0.0

    def test_simple_english_query(self):
        analysis = QueryEnhancer.enhance("python async await")
        assert analysis.original_query == "python async await"
        assert "code" in analysis.primary_type or "code" in analysis.secondary_types
        assert analysis.language == "en"

    def test_simple_chinese_query(self):
        analysis = QueryEnhancer.enhance("Python异步编程")
        assert analysis.original_query == "Python异步编程"
        assert analysis.language in ("zh", "mixed")

    def test_mixed_language_query(self):
        analysis = QueryEnhancer.enhance("Python asyncio异步编程")
        assert analysis.language == "mixed"


class TestSpellCorrection:
    """Spell correction tests."""

    def test_common_typo_correction(self):
        analysis = QueryEnhancer.enhance("pythn async await")
        assert analysis.spell_corrected is True
        assert "python" in analysis.enhanced_query.lower()

    def test_javascript_typo(self):
        analysis = QueryEnhancer.enhance("javscript tutorial")
        assert analysis.spell_corrected is True
        assert "javascript" in analysis.enhanced_query.lower()

    def test_no_false_positive_correction(self):
        analysis = QueryEnhancer.enhance("python tutorial")
        assert analysis.spell_corrected is False


class TestIntentClassification:
    """Enhanced intent classification tests."""

    def test_code_intent_strong(self):
        analysis = QueryEnhancer.enhance("python fastapi docker deployment")
        assert analysis.primary_type == "code"
        assert analysis.confidence > 0.3

    def test_academic_intent(self):
        analysis = QueryEnhancer.enhance("transformer attention mechanism paper")
        assert analysis.primary_type == "academic" or "academic" in analysis.secondary_types

    def test_news_intent(self):
        analysis = QueryEnhancer.enhance("2026年AI最新进展")
        assert "news" in (analysis.primary_type,) + tuple(analysis.secondary_types)

    def test_tutorial_intent(self):
        analysis = QueryEnhancer.enhance("how to deploy fastapi tutorial")
        assert "tutorial" in (analysis.primary_type,) + tuple(analysis.secondary_types)

    def test_knowledge_intent(self):
        analysis = QueryEnhancer.enhance("什么是RAG")
        assert "knowledge" in (analysis.primary_type,) + tuple(analysis.secondary_types)

    def test_general_fallback(self):
        analysis = QueryEnhancer.enhance("test")
        assert analysis.primary_type == "general"


class TestQuestionDetection:
    """Question detection tests."""

    def test_english_question(self):
        analysis = QueryEnhancer.enhance("how to implement RAG?")
        assert analysis.is_question is True

    def test_chinese_question(self):
        analysis = QueryEnhancer.enhance("什么是向量数据库")
        assert analysis.is_question is True

    def test_non_question(self):
        analysis = QueryEnhancer.enhance("python async await")
        assert analysis.is_question is False


class TestSynonymExpansion:
    """Synonym expansion tests."""

    def test_k8s_expansion(self):
        analysis = QueryEnhancer.enhance("k8s deployment")
        assert any("kubernetes" in t.lower() for t in analysis.expanded_terms)

    def test_llm_expansion(self):
        analysis = QueryEnhancer.enhance("LLM fine-tuning")
        assert len(analysis.expanded_terms) > 0


class TestCrossLanguageRewrite:
    """Cross-language query rewrite tests."""

    def test_chinese_to_english_rewrite(self):
        analysis = QueryEnhancer.enhance("机器学习算法")
        assert len(analysis.rewritten_queries) > 0

    def test_english_to_chinese_rewrite(self):
        analysis = QueryEnhancer.enhance("machine learning algorithm")
        assert len(analysis.rewritten_queries) > 0


class TestQueryAnalysisModel:
    """Pydantic model validation tests."""

    def test_model_defaults(self):
        qa = QueryAnalysis(original_query="test")
        assert qa.enhanced_query == ""
        assert qa.rewritten_queries == []
        assert qa.confidence == 0.5
        assert qa.spell_corrected is False

    def test_model_confidence_range(self):
        with pytest.raises(Exception):
            QueryAnalysis(original_query="test", confidence=1.5)
