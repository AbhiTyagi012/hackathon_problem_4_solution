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
    confirm_conflict: bool = False  # bypass the RAG conflict-check block; set after an explicit admin confirmation


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
    budget_band: Optional[str] = None  # low | medium | high
    max_budget: Optional[float] = None
    location: Optional[str] = None


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
    shopper_id: str


class SearchRequest(BaseModel):
    profile: Profile
    shopper_id: str
    search_query: str = ""
    search_category: Optional[str] = None


class PurchaseRequest(BaseModel):
    profile: Profile
    shopper_id: str
    purchased_product_id: str


class BulkRequest(BaseModel):
    profiles: list[Profile]


class SimilarRequest(BaseModel):
    shopper_id: str


# --------------------------------------------------------------------------- #
# Purchase-history similarity (embeddings) — a distinct mechanism from the
# rule engine, so it gets its own response shape rather than reusing Decision:
# there is no rule trace to report here, only a similarity score.
# --------------------------------------------------------------------------- #
class SimilarProduct(BaseModel):
    product: Product
    score: float
    similar_to_product_id: str
    reason: str = ""


class SimilarProductsResponse(BaseModel):
    items: list[SimilarProduct] = Field(default_factory=list)
    source: str = "gemini"  # "gemini" | "fallback"


# --------------------------------------------------------------------------- #
# LLM payloads
# --------------------------------------------------------------------------- #
class NlRuleRequest(BaseModel):
    text: str


class NlRuleResponse(BaseModel):
    rule: Optional[RuleCreate] = None  # None when the request is outside the supported scope
    source: str = "groq"  # "groq" | "fallback"
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
    source: str = "groq"


# --------------------------------------------------------------------------- #
# Rule authoring pipeline: Interpret -> Retrieve -> Conflict-check -> Validate
# -> Preview. Each step is inspectable via `PipelineStep`, and conflict-check
# is RAG (retrieval over the ruleset via RuleVectorIndex), not a whole-ruleset
# dump like RuleReviewResponse above.
# --------------------------------------------------------------------------- #
class RuleConflictCandidate(BaseModel):
    rule_id: str
    rule_name: str
    similarity: float
    note: str = ""


class ConflictCheckResult(BaseModel):
    verdict: str = "ok"  # "ok" | "overlap" | "duplicate"
    candidates: list[RuleConflictCandidate] = Field(default_factory=list)
    notes: str = ""
    source: str = "groq"  # "groq" | "fallback"


class PipelineStep(BaseModel):
    agent: str
    status: str  # "ok" | "repaired" | "unsupported" | "failed"
    detail: str = ""


class RuleDraftPipelineResponse(BaseModel):
    rule: Optional[RuleCreate] = None
    conflict_check: Optional[ConflictCheckResult] = None
    preview: Optional[RulePreviewResponse] = None
    steps: list[PipelineStep] = Field(default_factory=list)
    source: str = "groq"
    notes: str = ""
