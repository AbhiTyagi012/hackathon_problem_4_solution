import type {
  Decision,
  NlRuleResponse,
  Product,
  Profile,
  Rule,
  RuleCreate,
  RulePreviewResponse,
  RuleReviewResponse,
  SimilarProductsResponse,
} from "./types";
import { logger } from "../lib/logger";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = options.method || "GET";
  const start = performance.now();
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (err) {
    logger.error(`${method} ${path} -> network error`, err);
    throw err;
  }
  const durationMs = Math.round(performance.now() - start);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    logger.error(`${method} ${path} -> ${res.status} (${durationMs}ms)`, body);
    throw new Error(body.message || `${res.status} ${res.statusText}`);
  }
  logger.info(`${method} ${path} -> ${res.status} (${durationMs}ms)`);
  return res.json();
}

export const api = {
  // catalog
  listProducts: (category?: string) =>
    request<Product[]>(`/products${category ? `?category=${encodeURIComponent(category)}` : ""}`),
  getProduct: (id: string) => request<Product>(`/products/${id}`),

  // rules
  listRules: () => request<Rule[]>("/rules"),
  getRule: (id: string) => request<Rule>(`/rules/${id}`),
  createRule: (payload: RuleCreate) =>
    request<Rule>("/rules", { method: "POST", body: JSON.stringify(payload) }),
  updateRule: (id: string, payload: RuleCreate) =>
    request<Rule>(`/rules/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteRule: (id: string) => request<{ status: string }>(`/rules/${id}`, { method: "DELETE" }),
  reorderRules: (orderedIds: string[]) =>
    request<Rule[]>("/rules/reorder", {
      method: "PATCH",
      body: JSON.stringify({ ordered_ids: orderedIds }),
    }),
  ruleFromText: (text: string) =>
    request<NlRuleResponse>("/rules/from-text", { method: "POST", body: JSON.stringify({ text }) }),
  previewRule: (id: string, profile?: Profile) =>
    request<RulePreviewResponse>(`/rules/${id}/preview`, {
      method: "POST",
      body: JSON.stringify({ profile: profile ?? null }),
    }),
  previewDraftRule: (payload: RuleCreate) =>
    request<RulePreviewResponse>("/rules/preview-draft", { method: "POST", body: JSON.stringify(payload) }),
  reviewRules: () => request<RuleReviewResponse>("/rules/review", { method: "POST" }),

  // recommendations
  recommendHome: (profile: Profile, shopper_id: string) =>
    request<Decision>("/recommend/home", { method: "POST", body: JSON.stringify({ profile, shopper_id }) }),
  recommendSearch: (
    profile: Profile,
    shopper_id: string,
    search_query: string,
    search_category?: string | null
  ) =>
    request<Decision>("/recommend/search", {
      method: "POST",
      body: JSON.stringify({ profile, shopper_id, search_query, search_category: search_category ?? null }),
    }),
  recommendPurchase: (profile: Profile, shopper_id: string, purchased_product_id: string) =>
    request<Decision>("/recommend/purchase", {
      method: "POST",
      body: JSON.stringify({ profile, shopper_id, purchased_product_id }),
    }),
  recommendSimilar: (shopper_id: string) =>
    request<SimilarProductsResponse>("/recommend/similar", {
      method: "POST",
      body: JSON.stringify({ shopper_id }),
    }),

  // audit
  listDecisions: (limit = 50) => request<Decision[]>(`/decisions?limit=${limit}`),
};
