from app.history.repository import FilePurchaseHistoryRepository


def test_get_unknown_shopper_returns_empty_list(tmp_path):
    repo = FilePurchaseHistoryRepository(str(tmp_path / "history.json"))
    assert repo.get("nobody") == []


def test_record_purchase_persists_across_instances(tmp_path):
    path = str(tmp_path / "history.json")
    repo = FilePurchaseHistoryRepository(path)
    repo.record_purchase("shopper-a", "p001")
    repo.record_purchase("shopper-a", "p002")

    reloaded = FilePurchaseHistoryRepository(path)
    assert reloaded.get("shopper-a") == ["p001", "p002"]


def test_record_purchase_keeps_shoppers_independent(tmp_path):
    repo = FilePurchaseHistoryRepository(str(tmp_path / "history.json"))
    repo.record_purchase("shopper-a", "p001")
    repo.record_purchase("shopper-b", "p099")
    assert repo.get("shopper-a") == ["p001"]
    assert repo.get("shopper-b") == ["p099"]
