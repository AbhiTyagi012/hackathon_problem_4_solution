import type { Product } from "../api/types";
import { groupProductsByCategory, formatCategoryLabel, categoryAccent } from "../lib/catalog";
import { CatalogProductCard } from "./CatalogProductCard";
import { ProductRail } from "./ProductCarousel";

interface CategoryCatalogProps {
  products: Product[];
  excludeIds?: Set<string>;
}

export function CategoryCatalog({ products, excludeIds }: CategoryCatalogProps) {
  const filtered = excludeIds ? products.filter((p) => !excludeIds.has(p.id)) : products;
  const groups = groupProductsByCategory(filtered).filter((g) => g.products.length > 0);

  if (groups.length === 0) return null;

  return (
    <>
      {groups.map(({ category, products: categoryProducts }) => (
        <section key={category} className="shop-section category-department">
          <div
            className="category-department-header"
            style={{
              borderColor: categoryAccent(category),
              background: `linear-gradient(90deg, ${categoryAccent(category)}18, transparent)`,
            }}
          >
            <div>
              <h2>{formatCategoryLabel(category)}</h2>
              <p className="section-subtitle">{categoryProducts.length} products in this department</p>
            </div>
          </div>
          <ProductRail>
            {categoryProducts.map((product) => (
              <CatalogProductCard key={product.id} product={product} />
            ))}
          </ProductRail>
        </section>
      ))}
    </>
  );
}
