import type {
  Decision,
  LogEntry,
  NlRuleResponse,
  Product,
  Profile,
  Rule,
  RuleCreate,
  RuleDraftPipelineResponse,
  RulePreviewResponse,
  RuleReviewResponse,
  SimilarProductsResponse,
} from "./types";
import { logger } from "../lib/logger";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Thrown on any non-2xx response. `status`/`error` mirror the backend's
// {"error", "message", "detail"} shape; `detail` carries structured extra data
// (e.g. a ConflictCheckResult on 409) so callers can act on it instead of just
// showing the message string.
export class ApiError extends Error {
  status: number;
  error: string;
  detail?: unknown;

  constructor(status: number, error: string, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.error = error;
    this.detail = detail;
  }
}

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
    throw new ApiError(
      res.status,
      body.error || "Error",
      body.message || `${res.status} ${res.statusText}`,
      body.detail
    );
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
  draftRuleWithReview: (text: string) =>
    request<RuleDraftPipelineResponse>("/rules/draft-with-review", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
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

  // live logging
  recentLogs: (limit = 200) => request<LogEntry[]>(`/logs/recent?limit=${limit}`),
  // EventSource is a native browser API (not fetch-based), so the stream itself isn't
  // wrapped through request() — this just centralizes the URL construction.
  logsStreamUrl: (since = 0) => `${BASE_URL}/logs/stream?since=${since}`,
};
