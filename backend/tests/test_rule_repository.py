import pytest

from app.core.exceptions import RuleNotFoundError
from app.models.schemas import Condition, RecommendAction, Rule
from app.rules.repository import FileRuleRepository


def _make_rule(rid="rule-test", priority=50):
    return Rule(
        id=rid,
        name="Test rule",
        priority=priority,
        condition=Condition(field="age", operator="gte", value=18),
        recommend=RecommendAction(tags=["budget"], score=1.0),
    )


def test_loads_seeded_rules_default_dir():
    from app.core.config import get_settings

    repo = FileRuleRepository(get_settings().rules_dir)
    rules = repo.list_rules()
    assert len(rules) >= 10
    # sorted by priority desc
    assert rules[0].priority >= rules[-1].priority


def test_add_get_update_delete_roundtrip(tmp_path):
    repo = FileRuleRepository(str(tmp_path))
    repo.add(_make_rule("rule-a", priority=10))
    assert repo.get("rule-a").name == "Test rule"

    # a fresh repo reading the same dir sees the persisted rule
    repo2 = FileRuleRepository(str(tmp_path))
    assert repo2.get("rule-a").id == "rule-a"

    updated = _make_rule("rule-a", priority=99)
    repo2.update(updated)
    reloaded = FileRuleRepository(str(tmp_path))
    assert reloaded.get("rule-a").priority == 99
    assert reloaded.get("rule-a").version == 2  # bumped on update

    reloaded.delete("rule-a")
    with pytest.raises(RuleNotFoundError):
        reloaded.get("rule-a")


def test_reorder_sets_descending_priorities(tmp_path):
    repo = FileRuleRepository(str(tmp_path))
    repo.add(_make_rule("r1", 10))
    repo.add(_make_rule("r2", 20))
    repo.add(_make_rule("r3", 30))
    ordered = repo.reorder(["r2", "r3", "r1"])
    assert [r.id for r in ordered] == ["r2", "r3", "r1"]
    assert ordered[0].priority > ordered[1].priority > ordered[2].priority


def test_reorder_unknown_id_raises(tmp_path):
    repo = FileRuleRepository(str(tmp_path))
    repo.add(_make_rule("r1", 10))
    with pytest.raises(RuleNotFoundError):
        repo.reorder(["r1", "ghost"])


def test_reorder_partial_list_raises(tmp_path):
    from app.core.exceptions import RuleValidationError

    repo = FileRuleRepository(str(tmp_path))
    repo.add(_make_rule("r1", 10))
    repo.add(_make_rule("r2", 20))
    with pytest.raises(RuleValidationError):
        repo.reorder(["r1"])  # missing r2
