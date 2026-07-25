import type { SimilarProduct } from "../api/types";
import { CatalogProductCard } from "./CatalogProductCard";

export function SimilarProductCard({ item }: { item: SimilarProduct }) {
  return (
    <div className="similar-card">
      <CatalogProductCard product={item.product} compact />
      <div className="similar-card-reason">{item.reason}</div>
      <div className="similar-card-score">Match {Math.round(item.score * 100)}%</div>
    </div>
  );
}
