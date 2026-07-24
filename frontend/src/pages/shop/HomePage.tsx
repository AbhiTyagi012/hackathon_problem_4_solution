import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import type { Decision, Product } from "../../api/types";
import { useProfile } from "../../context/ProfileContext";
import { ProductCard } from "../../components/ProductCard";
import { DecisionBanner } from "../../components/DecisionBanner";
import { logger } from "../../lib/logger";

export function HomePage() {
  const { profile } = useProfile();
  const [decision, setDecision] = useState<Decision | null>(null);
  const [allProducts, setAllProducts] = useState<Product[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    logger.info("fetching home recommendations", { interests: profile.interests });
    Promise.all([api.recommendHome(profile), api.listProducts()])
      .then(([rec, products]) => {
        setDecision(rec);
        setAllProducts(products);
      })
      .catch((e) => {
        logger.error("failed to load home page", e);
        setError(e.message);
      })
      .finally(() => setLoading(false));
  }, [profile]);

  const hasProfile = profile.interests.length > 0 || profile.budget_band || profile.max_budget;
  const recommendedIds = new Set(decision?.recommendations.map((r) => r.product.id) ?? []);
  const otherProducts = allProducts.filter((p) => !recommendedIds.has(p.id));

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto", padding: "24px 16px" }}>
      <h2>Recommended for you</h2>
      {!hasProfile && (
        <p style={{ color: "var(--fg-muted)" }}>
          Tip: set up your <Link to="/profile">profile</Link> for more targeted recommendations. Showing
          a cold-start view for now.
        </p>
      )}
      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {loading && <p>Loading…</p>}
      {decision && (
        <>
          <DecisionBanner decision={decision} />
          {decision.recommendations.length > 0 ? (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
                gap: 16,
                marginTop: 16,
              }}
            >
              {decision.recommendations.map((item) => (
                <ProductCard key={item.product.id} item={item} />
              ))}
            </div>
          ) : (
            <p style={{ color: "var(--fg-muted)", marginTop: 12 }}>
              No rules matched your profile yet — browse all products below.
            </p>
          )}
        </>
      )}

      {!loading && otherProducts.length > 0 && (
        <>
          <h2 style={{ marginTop: 36 }}>All products</h2>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
              gap: 16,
              marginTop: 16,
            }}
          >
            {otherProducts.map((product) => (
              <Link key={product.id} to={`/product/${product.id}`} style={{ textDecoration: "none", color: "var(--fg)" }}>
                <div style={{ border: "1px solid var(--border)", borderRadius: 12, padding: 16, background: "var(--surface)" }}>
                  <div style={{ fontWeight: 700 }}>{product.name}</div>
                  <div style={{ fontSize: 13, color: "var(--fg-muted)" }}>{product.category} · {product.brand}</div>
                  <div style={{ fontWeight: 700, marginTop: 6 }}>${product.price.toFixed(2)}</div>
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
