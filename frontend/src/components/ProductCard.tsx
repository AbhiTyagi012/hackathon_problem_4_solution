import { useState } from "react";
import { Link } from "react-router-dom";
import type { RecommendedProduct } from "../api/types";
import { categoryAccent, formatCategoryLabel, getBroadCategory } from "../lib/catalog";
import { RecommendationExplanation } from "./RecommendationExplanation";

export function ProductCard({ item }: { item: RecommendedProduct }) {
  const [open, setOpen] = useState(false);
  const { product } = item;
  const accent = categoryAccent(getBroadCategory(product));

  return (
    <div className="recommend-card">
      <Link to={`/product/${product.id}`} className="recommend-card-media" style={{ background: `linear-gradient(135deg, ${accent}22, ${accent}55)` }}>
        <span className="catalog-card-initial">{product.name.charAt(0)}</span>
      </Link>
      <div className="recommend-card-body">
        <div className="recommend-card-top">
          <Link to={`/product/${product.id}`} className="recommend-card-name">
            {product.name}
          </Link>
          {item.source === "ai_fallback" && <span className="badge-ai">AI suggestion</span>}
        </div>
        <div className="recommend-card-meta">
          {formatCategoryLabel(product.category)} · {product.brand}
        </div>
        <div className="recommend-card-price">${product.price.toFixed(2)}</div>
        <div className="recommend-card-score">Rule score {item.score.toFixed(1)}</div>
        <button type="button" onClick={() => setOpen((o) => !o)} className="link-button">
          {open ? "Hide" : "Why this?"}
        </button>
        {open && <RecommendationExplanation reason={item.reason} matchedRuleIds={item.matched_rule_ids} />}
      </div>
    </div>
  );
}
