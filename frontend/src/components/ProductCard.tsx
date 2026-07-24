import { useState } from "react";
import { Link } from "react-router-dom";
import type { RecommendedProduct } from "../api/types";
import { RecommendationExplanation } from "./RecommendationExplanation";

export function ProductCard({ item }: { item: RecommendedProduct }) {
  const [open, setOpen] = useState(false);
  const { product } = item;

  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: 12,
        padding: 16,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        background: "var(--surface)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <Link to={`/product/${product.id}`} style={{ fontWeight: 700, textDecoration: "none", color: "var(--fg)" }}>
          {product.name}
        </Link>
        {item.source === "ai_fallback" && <span style={badgeStyle}>AI suggestion</span>}
      </div>
      <div style={{ fontSize: 13, color: "var(--fg-muted)" }}>{product.category} · {product.brand}</div>
      <div style={{ fontWeight: 700 }}>${product.price.toFixed(2)}</div>
      <div style={{ fontSize: 12, color: "var(--fg-muted)" }}>score {item.score.toFixed(1)}</div>
      <button onClick={() => setOpen((o) => !o)} style={linkButton}>
        {open ? "Hide" : "Why this?"}
      </button>
      {open && <RecommendationExplanation reason={item.reason} matchedRuleIds={item.matched_rule_ids} />}
    </div>
  );
}

const badgeStyle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 700,
  color: "#7c3aed",
  background: "#ede9fe",
  borderRadius: 999,
  padding: "2px 8px",
  whiteSpace: "nowrap",
};

const linkButton: React.CSSProperties = {
  border: "none",
  background: "none",
  color: "var(--accent)",
  cursor: "pointer",
  padding: 0,
  fontSize: 13,
  textAlign: "left",
};
