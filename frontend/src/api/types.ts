export type ConditionGroup = {
  all?: Condition[];
  any?: Condition[];
  not?: Condition;
  field?: string;
  operator?: string;
  value?: unknown;
};
export type Condition = ConditionGroup;

export interface RecommendAction {
  products: string[];
  categories: string[];
  tags: string[];
  score: number;
}

export interface Rule {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  priority: number;
  condition: Condition;
  recommend: RecommendAction;
  version: number;
  updated_at: string;
}

export interface RuleCreate {
  name: string;
  description: string;
  enabled: boolean;
  priority: number;
  condition: Condition;
  recommend: RecommendAction;
}

export interface Product {
  id: string;
  name: string;
  category: string;
  price: number;
  brand: string;
  tags: string[];
  image: string;
  description: string;
}

export interface Profile {
  age?: number | null;
  gender?: string | null;
  interests: string[];
  budget_band?: string | null;
  max_budget?: number | null;
  location?: string | null;
  past_purchase_categories: string[];
}

export interface RuleTrace {
  rule_id: string;
  rule_name: string;
  priority: number;
  matched: boolean;
  reason: string;
  recommend: RecommendAction;
}

export interface RecommendedProduct {
  product: Product;
  score: number;
  matched_rule_ids: string[];
  reason: string;
  source: "rules" | "ai_fallback";
}

export interface Decision {
  decision_id: string;
  context_type: string;
  context: Record<string, unknown>;
  recommendations: RecommendedProduct[];
  rules_evaluated: number;
  rules_matched: RuleTrace[];
  rules_rejected: RuleTrace[];
  explanation: string;
  used_ai_fallback: boolean;
  created_at: string;
}

export interface NlRuleResponse {
  rule: RuleCreate;
  source: string;
  notes: string;
}

export interface RulePreviewResponse {
  rule_id: string;
  matched: boolean;
  matched_products: Product[];
  feedback: string;
  needs_product: boolean;
  suggested_product?: Record<string, unknown>;
}

export interface RuleReviewResponse {
  review: string;
  source: string;
}
