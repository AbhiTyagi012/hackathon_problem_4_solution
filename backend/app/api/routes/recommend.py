from fastapi import APIRouter, Depends

from app.api.deps import get_recommendation_service
from app.models.schemas import BulkRequest, Decision, HomeRequest, PurchaseRequest, SearchRequest
from app.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/recommend", tags=["recommend"])


@router.post("/home", response_model=Decision)
def recommend_home(req: HomeRequest, svc: RecommendationService = Depends(get_recommendation_service)):
    return svc.home(req.profile)


@router.post("/search", response_model=Decision)
def recommend_search(req: SearchRequest, svc: RecommendationService = Depends(get_recommendation_service)):
    return svc.search(req.profile, req.search_query, req.search_category)


@router.post("/purchase", response_model=Decision)
def recommend_purchase(req: PurchaseRequest, svc: RecommendationService = Depends(get_recommendation_service)):
    return svc.purchase(req.profile, req.purchased_product_id)


@router.post("/bulk", response_model=list[Decision])
def recommend_bulk(req: BulkRequest, svc: RecommendationService = Depends(get_recommendation_service)):
    return svc.bulk(req.profiles)
