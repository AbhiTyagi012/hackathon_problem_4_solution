from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Condition tree
# --------------------------------------------------------------------------- #
class Condition(BaseModel):
    """A recursive condition node.

    Exactly one shape must be used per node:
      - group:  {"all": [...]}  |  {"any": [...]}  |  {"not": {...}}
      - leaf:   {"field": "...", "operator": "...", "value": ...}
    """

    all: Optional[list["Condition"]] = None
    any: Optional[list["Condition"]] = None
    not_: Optional["Condition"] = Field(default=None, alias="not")

    field: Optional[str] = None
    operator: Optional[str] = None
    value: Any = None

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _check_exactly_one_shape(self) -> "Condition":
        is_leaf = self.field is not None and self.operator is not None
        group_count = sum(x is not None for x in (self.all, self.any, self.not_))
        if is_leaf and group_count == 0:
            return self
        if not is_leaf and group_count == 1:
            return self
        raise ValueError(
            "condition must be exactly one of: a leaf (field+operator[+value]) "
            "or a single group (all|any|not)"
        )

    def summarize(self) -> str:
        if self.all is not None:
            return "(" + " AND ".join(c.summarize() for c in self.all) + ")"
        if self.any is not None:
            return "(" + " OR ".join(c.summarize() for c in self.any) + ")"
        if self.not_ is not None:
            return f"NOT {self.not_.summarize()}"
        return f"{self.field} {self.operator} {self.value!r}"


Condition.model_rebuild()


# --------------------------------------------------------------------------- #
# Rules
# --------------------------------------------------------------------------- #
class RecommendAction(BaseModel):
    products: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    score: float = 1.0


class Rule(BaseModel):
    id: str
    name: str
    description: str = ""
    enabled: bool = True
    priority: int = 100  # higher = evaluated first / stronger
    condition: Condition
    recommend: RecommendAction = Field(default_factory=RecommendAction)
    version: int = 1
    updated_at: datetime = Field(default_factory=utcnow)


class RuleCreate(BaseModel):
    name: str
    description: str = ""
    enabled: bool = True
    priority: int = 100
    condition: Condition
    recommend: RecommendAction = Field(default_factory=RecommendAction)


class RuleReorder(BaseModel):
    ordered_ids: list[str]


# --------------------------------------------------------------------------- #
# Catalog / profile
# --------------------------------------------------------------------------- #
class Product(BaseModel):
    id: str
    name: str
    category: str
    price: float
    brand: str = ""
    tags: list[str] = Field(default_factory=list)
    image: str = ""
    description: str = ""


class Profile(BaseModel):
    age: Optional[int] = None
    gender: Optional[str] = None
    interests: list[str] = Field(default_factory=list)
    budget_band: Optional[str] = None  # low | medium | high
    max_budget: Optional[float] = None
    location: Optional[str] = None
    past_purchase_categories: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Evaluation / explanation
# --------------------------------------------------------------------------- #
class RuleTrace(BaseModel):
    rule_id: str
    rule_name: str
    priority: int
    matched: bool
    reason: str
    recommend: RecommendAction = Field(default_factory=RecommendAction)


class RecommendedProduct(BaseModel):
    product: Product
    score: float
    matched_rule_ids: list[str] = Field(default_factory=list)
    reason: str = ""
    source: str = "rules"  # "rules" | "ai_fallback"


class Decision(BaseModel):
    decision_id: str
    context_type: str  # home | search | purchase | evaluate | bulk
    context: dict[str, Any]
    recommendations: list[RecommendedProduct] = Field(default_factory=list)
    rules_evaluated: int = 0
    rules_matched: list[RuleTrace] = Field(default_factory=list)
    rules_rejected: list[RuleTrace] = Field(default_factory=list)
    explanation: str = ""
    used_ai_fallback: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class EvaluationRequest(BaseModel):
    context_type: str = "evaluate"
    facts: dict[str, Any]


# --------------------------------------------------------------------------- #
# Recommendation request payloads
# --------------------------------------------------------------------------- #
class HomeRequest(BaseModel):
    profile: Profile


class SearchRequest(BaseModel):
    profile: Profile
    search_query: str = ""
    search_category: Optional[str] = None


class PurchaseRequest(BaseModel):
    profile: Profile
    purchased_product_id: str


class BulkRequest(BaseModel):
    profiles: list[Profile]


# --------------------------------------------------------------------------- #
# LLM payloads
# --------------------------------------------------------------------------- #
class NlRuleRequest(BaseModel):
    text: str


class NlRuleResponse(BaseModel):
    rule: RuleCreate
    source: str = "grok"  # "grok" | "fallback"
    notes: str = ""


class RulePreviewRequest(BaseModel):
    profile: Optional[Profile] = None


class RulePreviewResponse(BaseModel):
    rule_id: str
    matched: bool
    matched_products: list[Product] = Field(default_factory=list)
    feedback: str = ""
    needs_product: bool = False
    suggested_product: Optional[dict[str, Any]] = None


class RuleReviewResponse(BaseModel):
    review: str
    source: str = "grok"
