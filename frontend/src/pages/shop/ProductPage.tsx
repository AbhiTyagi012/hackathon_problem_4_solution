import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../../api/client";
import type { Decision, Product } from "../../api/types";
import { useProfile } from "../../context/ProfileContext";
import { ProductCard } from "../../components/ProductCard";
import { DecisionBanner } from "../../components/DecisionBanner";
import { logger } from "../../lib/logger";

export function ProductPage() {
  const { id } = useParams<{ id: string }>();
  const { profile } = useProfile();
  const [product, setProduct] = useState<Product | null>(null);
  const [bought, setBought] = useState(false);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    api.getProduct(id).then(setProduct).catch((e) => setError(e.message));
    setBought(false);
    setDecision(null);
  }, [id]);

  const handleBuy = async () => {
    if (!id) return;
    setLoading(true);
    setError("");
    logger.info("purchase requested", { productId: id });
    try {
      const rec = await api.recommendPurchase(profile, id);
      setDecision(rec);
      setBought(true);
    } catch (e) {
      logger.error("purchase recommendation failed", e);
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  if (!product) return <div style={{ padding: 24 }}>{error || "Loading…"}</div>;

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: "24px 16px" }}>
      <div style={{ border: "1px solid var(--border)", borderRadius: 12, padding: 24, background: "var(--surface)" }}>
        <div style={{ fontSize: 13, color: "var(--fg-muted)" }}>{product.category} · {product.brand}</div>
        <h2 style={{ margin: "6px 0" }}>{product.name}</h2>
        <p style={{ color: "var(--fg-muted)" }}>{product.description}</p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 12 }}>
          {product.tags.map((t) => (
            <span key={t} style={{ fontSize: 12, background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 999, padding: "2px 8px" }}>
              {t}
            </span>
          ))}
        </div>
        <div style={{ fontSize: 24, fontWeight: 800, marginBottom: 16 }}>${product.price.toFixed(2)}</div>
        <button
          onClick={handleBuy}
          disabled={loading || bought}
          style={{
            background: bought ? "#16a34a" : "var(--accent)",
            color: "#fff",
            border: "none",
            borderRadius: 10,
            padding: "12px 24px",
            fontWeight: 700,
            cursor: bought ? "default" : "pointer",
            fontSize: 15,
          }}
        >
          {bought ? "✓ Purchased" : loading ? "Processing…" : "Buy now"}
        </button>
      </div>

      {error && <p style={{ color: "crimson" }}>{error}</p>}

      {decision && (
        <div style={{ marginTop: 28 }}>
          <h3>Customers who bought this also liked</h3>
          <DecisionBanner decision={decision} />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 16, marginTop: 16 }}>
            {decision.recommendations.map((item) => (
              <ProductCard key={item.product.id} item={item} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
