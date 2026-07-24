from fastapi import APIRouter, Depends

from app.api.deps import get_product_repository
from app.catalog.repository import ProductRepository
from app.models.schemas import Product

router = APIRouter(prefix="/products", tags=["catalog"])


@router.get("", response_model=list[Product])
def list_products(
    category: str | None = None,
    repo: ProductRepository = Depends(get_product_repository),
):
    if category:
        return repo.by_category(category)
    return repo.list_products()


@router.get("/{product_id}", response_model=Product)
def get_product(product_id: str, repo: ProductRepository = Depends(get_product_repository)):
    return repo.get(product_id)
