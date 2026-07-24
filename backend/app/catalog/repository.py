"""Product catalog loaded from a seeded JSON file."""
from __future__ import annotations

import json
from pathlib import Path

from app.core.exceptions import ProductNotFoundError
from app.core.logging import get_logger
from app.models.schemas import Product

logger = get_logger(__name__)


class ProductRepository:
    def __init__(self, catalog_path: str):
        self._path = Path(catalog_path)
        data = json.loads(self._path.read_text(encoding="utf-8"))
        self._products: dict[str, Product] = {}
        for item in data.get("products", []):
            product = Product.model_validate(item)
            self._products[product.id] = product
        logger.info("loaded %d products from %s", len(self._products), self._path)

    def list_products(self) -> list[Product]:
        return list(self._products.values())

    def get(self, product_id: str) -> Product:
        if product_id not in self._products:
            raise ProductNotFoundError(f"product '{product_id}' not found")
        return self._products[product_id]

    def exists(self, product_id: str) -> bool:
        return product_id in self._products

    def by_category(self, category: str) -> list[Product]:
        c = category.lower()
        return [p for p in self._products.values() if p.category.lower() == c]

    def by_tag(self, tag: str) -> list[Product]:
        t = tag.lower()
        return [p for p in self._products.values() if t in [x.lower() for x in p.tags]]

    def categories(self) -> list[str]:
        return sorted({p.category for p in self._products.values()})

    def tags(self) -> list[str]:
        return sorted({t for p in self._products.values() for t in p.tags})
