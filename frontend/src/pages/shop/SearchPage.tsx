import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { Decision, Product } from "../../api/types";
import { useProfile } from "../../context/ProfileContext";
import { ProductCard } from "../../components/ProductCard";
import { DecisionBanner } from "../../components/DecisionBanner";
import { CategoryCatalog } from "../../components/CategoryCatalog";
import { CatalogProductCard } from "../../components/CatalogProductCard";
import { ProductRail } from "../../components/ProductCarousel";
import { logger } from "../../lib/logger";

export function SearchPage() {
  const { profile, shopperId } = useProfile();
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<Product[]>([]);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [allProducts, setAllProducts] = useState<Product[]>([]);
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    api.listProducts().then(setAllProducts).catch((e) => logger.error("failed to load products", e));
  }, []);

  const runSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    setSearched(true);
    logger.info("search requested", { query });
    try {
      const [products, rec] = await Promise.all([
        api.listProducts(),
        api.recommendSearch(profile, shopperId, query),
      ]);
      const lowered = query.toLowerCase();
      setMatches(
        products.filter(
          (p) =>
            p.name.toLowerCase().includes(lowered) ||
            p.category.toLowerCase().includes(lowered) ||
            p.tags.some((t) => t.toLowerCase().includes(lowered))
        )
      );
      setDecision(rec);
    } catch (err) {
      logger.error("search failed", err);
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const hasRecommendations = (decision?.recommendations.length ?? 0) > 0;

  return (
    <div className="shop-page">
      <section className="shop-section search-hero">
        <div className="section-heading">
          <h2>Search products</h2>
          <p className="section-subtitle">Find items by name, category, or tag</p>
        </div>
        <form onSubmit={runSearch} className="search-form">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Try 'laptop', 'gaming', 'audio'…"
            className="search-input"
          />
          <button type="submit" className="btn-primary">
            Search
          </button>
        </form>
      </section>

      {error && <p className="page-error">{error}</p>}
      {loading && <p className="page-status">Searching…</p>}

      {searched && matches.length > 0 && (
        <section className="shop-section">
          <div className="section-heading">
            <h3>Matching products</h3>
            <span className="category-count">{matches.length} results</span>
          </div>
          <ProductRail>
            {matches.map((p) => (
              <CatalogProductCard key={p.id} product={p} />
            ))}
          </ProductRail>
        </section>
      )}

      {searched && !loading && matches.length === 0 && (
        <p className="page-status">No products matched your search.</p>
      )}

      {hasRecommendations && decision && (
        <section className="shop-section">
          <div className="section-heading">
            <h3>Recommended for you</h3>
          </div>
          <DecisionBanner decision={decision} />
          <ProductRail>
            {decision.recommendations.map((item) => (
              <ProductCard key={item.product.id} item={item} />
            ))}
          </ProductRail>
        </section>
      )}

      <CategoryCatalog products={allProducts} />
    </div>
  );
}
