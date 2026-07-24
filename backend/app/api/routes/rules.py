from fastapi import APIRouter, Depends

from app.api.deps import get_rule_admin_service
from app.models.schemas import (
    NlRuleRequest,
    NlRuleResponse,
    Rule,
    RuleCreate,
    RulePreviewRequest,
    RulePreviewResponse,
    RuleReorder,
    RuleReviewResponse,
)
from app.services.rule_admin_service import RuleAdminService

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=list[Rule])
def list_rules(svc: RuleAdminService = Depends(get_rule_admin_service)):
    return svc.list_rules()


@router.get("/{rule_id}", response_model=Rule)
def get_rule(rule_id: str, svc: RuleAdminService = Depends(get_rule_admin_service)):
    return svc.get_rule(rule_id)


@router.post("", response_model=Rule)
def create_rule(payload: RuleCreate, svc: RuleAdminService = Depends(get_rule_admin_service)):
    return svc.create_rule(payload)


@router.put("/{rule_id}", response_model=Rule)
def update_rule(rule_id: str, payload: RuleCreate, svc: RuleAdminService = Depends(get_rule_admin_service)):
    return svc.update_rule(rule_id, payload)


@router.delete("/{rule_id}")
def delete_rule(rule_id: str, svc: RuleAdminService = Depends(get_rule_admin_service)):
    svc.delete_rule(rule_id)
    return {"status": "deleted", "rule_id": rule_id}


@router.patch("/reorder", response_model=list[Rule])
def reorder_rules(payload: RuleReorder, svc: RuleAdminService = Depends(get_rule_admin_service)):
    return svc.reorder(payload.ordered_ids)


@router.post("/from-text", response_model=NlRuleResponse)
def rule_from_text(payload: NlRuleRequest, svc: RuleAdminService = Depends(get_rule_admin_service)):
    return svc.nl_to_rule(payload.text)


@router.post("/{rule_id}/preview", response_model=RulePreviewResponse)
def preview_rule(
    rule_id: str, payload: RulePreviewRequest, svc: RuleAdminService = Depends(get_rule_admin_service)
):
    return svc.preview(rule_id, payload.profile)


@router.post("/review", response_model=RuleReviewResponse)
def review_rules(svc: RuleAdminService = Depends(get_rule_admin_service)):
    return svc.review()
