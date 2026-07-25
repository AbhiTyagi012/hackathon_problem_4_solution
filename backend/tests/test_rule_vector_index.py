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
