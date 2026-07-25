from app.embeddings.rule_index import RuleVectorIndex
from app.models.schemas import Condition, RecommendAction, Rule


def test_search_excludes_requested_rule_id(rule_repo, embedding_service):
    index = RuleVectorIndex(embedding_service, rule_repo)
    query = index.embed_query("beauty skincare rule")
    results = index.search(query, k=5, exclude_rule_id="rule-beauty")
    assert "rule-beauty" not in {rid for rid, _ in results}


def test_invalidate_picks_up_a_newly_added_rule(rule_repo, embedding_service):
    index = RuleVectorIndex(embedding_service, rule_repo)
    query = index.embed_query("zzz-unique-new-rule-marker")
    before = {rid for rid, _ in index.search(query, k=50)}
    assert "brand-new-rule" not in before

    rule_repo.add(
        Rule(
            id="brand-new-rule",
            name="zzz-unique-new-rule-marker",
            priority=1,
            condition=Condition(field="budget_band", operator="equals_ci", value="low"),
            recommend=RecommendAction(tags=["zzz-unique-new-rule-marker"], score=1.0),
        )
    )
    index.invalidate()
    after = {rid for rid, _ in index.search(query, k=50)}
    assert "brand-new-rule" in after


def test_search_on_empty_ruleset_returns_nothing(tmp_path, embedding_service):
    from app.rules.repository import FileRuleRepository

    empty_repo = FileRuleRepository(str(tmp_path))
    index = RuleVectorIndex(embedding_service, empty_repo)
    assert index.search(index.embed_query("anything"), k=5) == []


def test_embed_query_follows_index_source_not_live_call_result(rule_repo, embedding_service):
    """Regression: a live per-query embed can independently succeed against
    Gemini even when the index itself was built on the offline fallback path
    (e.g. a transient rate limit at build time that's since cleared) — that
    used to return a real, differently-dimensioned vector and crash FAISS
    search. embed_query must follow the index's committed source instead."""
    index = RuleVectorIndex(embedding_service, rule_repo)
    index.embed_query("force build")  # embedding_service fixture forces offline fallback -> source="fallback"
    assert index.source == "fallback"

    class _AlwaysRealEmbeddingService:
        def is_enabled(self):
            return True

        def embed(self, text):
            return [0.1] * 999, "gemini"  # a different dimension than the fallback vector space

    index._embedding_service = _AlwaysRealEmbeddingService()
    query = index.embed_query("some text")
    assert len(query) != 999  # still followed the index's fallback source, not the live call


def test_search_returns_empty_on_dimension_mismatch_instead_of_crashing(rule_repo, embedding_service):
    """Defense in depth: even if a mismatched vector reaches search() directly,
    it must degrade to no-results, not raise (FAISS itself raises AssertionError
    on a dimension mismatch, which previously propagated as an unhandled 500)."""
    index = RuleVectorIndex(embedding_service, rule_repo)
    index.embed_query("force build")
    mismatched_vector = [0.1] * 999
    assert index.search(mismatched_vector, k=5) == []
