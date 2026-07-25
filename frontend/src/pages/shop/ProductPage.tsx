import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../../api/client";
import type { Decision, Product } from "../../api/types";
import { useProfile } from "../../context/ProfileContext";
import { ProductCard } from "../../components/ProductCard";
import { DecisionBanner } from "../../components/DecisionBanner";
import { ProductRail } from "../../components/ProductCarousel";
import { categoryAccent, formatSubcategoryLabel, getBroadCategory } from "../../lib/catalog";
import { logger } from "../../lib/logger";

export function ProductPage() {
  const { id } = useParams<{ id: string }>();
  const { profile, shopperId } = useProfile();
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
      const rec = await api.recommendPurchase(profile, shopperId, id);
      setDecision(rec);
      setBought(true);
    } catch (e) {
      logger.error("purchase recommendation failed", e);
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  if (!product) return <div className="shop-page">{error || "Loading…"}</div>;

  const accent = categoryAccent(getBroadCategory(product));
  const hasRecommendations = (decision?.recommendations.length ?? 0) > 0;

  return (
    <div className="shop-page">
      <div className="product-detail">
        <div className="product-detail-media" style={{ background: `linear-gradient(135deg, ${accent}22, ${accent}55)` }}>
          <span className="catalog-card-initial">{product.name.charAt(0)}</span>
        </div>
        <div className="product-detail-body">
          <div className="catalog-card-brand">{product.brand || "ShopSense"}</div>
          <div className="section-subtitle">{formatSubcategoryLabel(product.category)}</div>
          <h2>{product.name}</h2>
          <p style={{ color: "var(--fg-muted)" }}>{product.description}</p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 16 }}>
            {product.tags.map((t) => (
              <span key={t} className="tag-chip">
                {t}
              </span>
            ))}
          </div>
          <div className="catalog-card-price" style={{ fontSize: "1.6rem", marginBottom: 16 }}>
            ${product.price.toFixed(2)}
          </div>
          <button
            type="button"
            onClick={handleBuy}
            disabled={loading || bought}
            className="btn-primary"
            style={{ background: bought ? "#16a34a" : undefined }}
          >
            {bought ? "✓ Purchased" : loading ? "Processing…" : "Buy now"}
          </button>
        </div>
      </div>

      {error && <p className="page-error">{error}</p>}

      {hasRecommendations && decision && (
        <section className="shop-section">
          <div className="section-heading">
            <h3>Customers who bought this also liked</h3>
          </div>
          <DecisionBanner decision={decision} />
          <ProductRail>
            {decision.recommendations.map((item) => (
              <ProductCard key={item.product.id} item={item} />
            ))}
          </ProductRail>
        </section>
      )}
    </div>
  );
}
