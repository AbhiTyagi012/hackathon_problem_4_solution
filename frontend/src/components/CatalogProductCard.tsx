import { Link } from "react-router-dom";
import type { Product } from "../api/types";
import { categoryAccent, formatSubcategoryLabel, getBroadCategory } from "../lib/catalog";

interface CatalogProductCardProps {
  product: Product;
  compact?: boolean;
}

export function CatalogProductCard({ product, compact = false }: CatalogProductCardProps) {
  const accent = categoryAccent(getBroadCategory(product));

  return (
    <Link to={`/product/${product.id}`} className={`catalog-card${compact ? " catalog-card-compact" : ""}`}>
      <div className="catalog-card-media" style={{ background: `linear-gradient(135deg, ${accent}22, ${accent}44)` }}>
        <span className="catalog-card-badge">{formatSubcategoryLabel(product.category)}</span>
        <span className="catalog-card-initial">{product.name.charAt(0)}</span>
      </div>
      <div className="catalog-card-body">
        <div className="catalog-card-brand">{product.brand || "ShopSense"}</div>
        <div className="catalog-card-name">{product.name}</div>
        <div className="catalog-card-meta">
          {formatSubcategoryLabel(product.category)} · {product.tags.slice(0, 2).join(" · ")}
        </div>
        <div className="catalog-card-price">${product.price.toFixed(2)}</div>
      </div>
    </Link>
  );
}
