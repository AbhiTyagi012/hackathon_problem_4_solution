import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { Decision, Product } from "../../api/types";
import { useProfile } from "../../context/ProfileContext";
import { ProductCard } from "../../components/ProductCard";
import { DecisionBanner } from "../../components/DecisionBanner";
import { Link } from "react-router-dom";
import { logger } from "../../lib/logger";

export function SearchPage() {
  const { profile, shopperId } = useProfile();
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<Product[]>([]);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [allProducts, setAllProducts] = useState<Product[]>([]);

  useEffect(() => {
    api.listProducts().then(setAllProducts).catch((e) => logger.error("failed to load products", e));
  }, []);

  const runSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    logger.info("search requested", { query });
    try {
      const [allProducts, rec] = await Promise.all([
        api.listProducts(),
        api.recommendSearch(profile, shopperId, query),
      ]);
      const lowered = query.toLowerCase();
      setMatches(
        allProducts.filter(
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

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto", padding: "24px 16px" }}>
      <h2>Search products</h2>
      <form onSubmit={runSearch} style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Try 'laptop', 'gaming', 'audio'…"
          style={{
            flex: 1,
            padding: "10px 14px",
            borderRadius: 8,
            border: "1px solid var(--border)",
            background: "var(--surface)",
            color: "var(--fg)",
          }}
        />
        <button
          type="submit"
          style={{ background: "var(--accent)", color: "#fff", border: "none", borderRadius: 8, padding: "10px 20px", fontWeight: 600, cursor: "pointer" }}
        >
          Search
        </button>
      </form>

      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {loading && <p>Searching…</p>}

      {matches.length > 0 && (
        <>
          <h3>Matching products</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 16 }}>
            {matches.map((p) => (
              <Link key={p.id} to={`/product/${p.id}`} style={{ textDecoration: "none", color: "var(--fg)" }}>
                <div style={{ border: "1px solid var(--border)", borderRadius: 12, padding: 16, background: "var(--surface)" }}>
                  <div style={{ fontWeight: 700 }}>{p.name}</div>
                  <div style={{ fontSize: 13, color: "var(--fg-muted)" }}>{p.category}</div>
                  <div style={{ fontWeight: 700, marginTop: 6 }}>${p.price.toFixed(2)}</div>
                </div>
              </Link>
            ))}
          </div>
        </>
      )}

      {decision && decision.recommendations.length > 0 && (
        <>
          <h3 style={{ marginTop: 28 }}>Recommended for you</h3>
          <DecisionBanner decision={decision} />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 16, marginTop: 16 }}>
            {decision.recommendations.map((item) => (
              <ProductCard key={item.product.id} item={item} />
            ))}
          </div>
        </>
      )}

      {allProducts.length > 0 && (
        <>
          <h3 style={{ marginTop: 28 }}>All products</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 16, marginTop: 16 }}>
            {allProducts.map((p) => (
              <Link key={p.id} to={`/product/${p.id}`} style={{ textDecoration: "none", color: "var(--fg)" }}>
                <div style={{ border: "1px solid var(--border)", borderRadius: 12, padding: 16, background: "var(--surface)" }}>
                  <div style={{ fontWeight: 700 }}>{p.name}</div>
                  <div style={{ fontSize: 13, color: "var(--fg-muted)" }}>{p.category}</div>
                  <div style={{ fontWeight: 700, marginTop: 6 }}>${p.price.toFixed(2)}</div>
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
