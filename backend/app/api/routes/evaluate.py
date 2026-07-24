from fastapi import APIRouter, Depends

from app.api.deps import get_audit_store, get_recommendation_service
from app.models.schemas import Decision, EvaluationRequest
from app.services.audit_store import AuditStore
from app.services.recommendation_service import RecommendationService

router = APIRouter(tags=["evaluate"])


@router.post("/evaluate", response_model=Decision)
def evaluate(req: EvaluationRequest, svc: RecommendationService = Depends(get_recommendation_service)):
    """Raw engine access: pass any facts dict, get back a full decision + explanation."""
    facts = dict(req.facts)
    facts["context_type"] = req.context_type
    return svc.evaluate(facts)


@router.get("/decisions", response_model=list[Decision])
def list_decisions(limit: int = 50, store: AuditStore = Depends(get_audit_store)):
    return store.list_recent(limit)


@router.get("/decisions/{decision_id}", response_model=Decision)
def get_decision(decision_id: str, store: AuditStore = Depends(get_audit_store)):
    return store.get(decision_id)
