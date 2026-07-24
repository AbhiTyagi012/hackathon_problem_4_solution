import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import type { Decision, Product, SimilarProduct } from "../../api/types";
import { useProfile } from "../../context/ProfileContext";
import { ProductCard } from "../../components/ProductCard";
import { DecisionBanner } from "../../components/DecisionBanner";
import { CategoryCatalog } from "../../components/CategoryCatalog";
import { ProductRail } from "../../components/ProductCarousel";
import { SimilarProductCard } from "../../components/SimilarProductCard";
import { logger } from "../../lib/logger";

export function HomePage() {
  const { profile, shopperId } = useProfile();
  const [decision, setDecision] = useState<Decision | null>(null);
  const [allProducts, setAllProducts] = useState<Product[]>([]);
  const [similar, setSimilar] = useState<SimilarProduct[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    logger.info("fetching home recommendations", { shopperId });
    Promise.all([
      api.recommendHome(profile, shopperId),
      api.listProducts(),
      api.recommendSimilar(shopperId),
    ])
      .then(([rec, products, similarResp]) => {
        setDecision(rec);
        setAllProducts(products);
        setSimilar(similarResp.items);
      })
      .catch((e) => {
        logger.error("failed to load home page", e);
        setError(e.message);
      })
      .finally(() => setLoading(false));
  }, [profile, shopperId]);

  const hasProfile = Boolean(profile.budget_band || profile.max_budget || profile.age || profile.location);
  const recommendedIds = new Set(decision?.recommendations.map((r) => r.product.id) ?? []);
  const hasRecommendations = (decision?.recommendations.length ?? 0) > 0;
  const hasSimilar = similar.length > 0;

  return (
    <div className="shop-page">
      {loading && <p className="page-status">Loading your personalized storefront…</p>}
      {error && <p className="page-error">{error}</p>}

      {!loading && hasRecommendations && decision && (
        <section className="shop-section">
          <div className="section-heading">
            <h2>Recommended for you</h2>
            {!hasProfile && (
              <p className="section-subtitle">
                Tip: set up your <Link to="/profile">profile</Link> for more targeted recommendations.
              </p>
            )}
          </div>
          <DecisionBanner decision={decision} />
          <ProductRail>
            {decision.recommendations.map((item) => (
              <ProductCard key={item.product.id} item={item} />
            ))}
          </ProductRail>
        </section>
      )}

      {!loading && hasSimilar && (
        <section className="shop-section">
          <div className="section-heading">
            <h2>Based on your purchase history</h2>
            <p className="section-subtitle">Similar picks powered by embeddings, not rules</p>
          </div>
          <ProductRail>
            {similar.map((item) => (
              <SimilarProductCard key={item.product.id} item={item} />
            ))}
          </ProductRail>
        </section>
      )}

      {!loading && (
        <CategoryCatalog products={allProducts} excludeIds={recommendedIds} />
      )}
    </div>
  );
}
