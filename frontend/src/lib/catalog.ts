import type { Product } from "../api/types";

/** Broad storefront departments — maps granular catalog categories into shopper-facing groups. */
const CATEGORY_TO_BROAD: Record<string, string> = {
  laptops: "electronics",
  phones: "electronics",
  audio: "electronics",
  accessories: "electronics",
  gaming: "electronics",
  electronics: "electronics",
  tv: "electronics",
  cameras: "electronics",
  watches: "electronics",

  beauty: "beauty",
  health: "beauty",

  fitness: "fitness",
  outdoor: "fitness",

  fashion: "fashion",
  footwear: "fashion",
  jewelry: "fashion",
  bags: "fashion",

  home: "home",
  kitchen: "home",
  furniture: "home",
  garden: "home",

  books: "books",
  toys: "toys",
  travel: "travel",
  "art-supplies": "arts",
  "musical-instruments": "arts",
  office: "office",
  automotive: "automotive",
  tools: "automotive",
  pet: "pet",
  baby: "baby",
  groceries: "groceries",
};

const BROAD_CATEGORY_ORDER = [
  "electronics",
  "beauty",
  "fitness",
  "fashion",
  "home",
  "books",
  "toys",
  "travel",
  "arts",
  "office",
  "automotive",
  "pet",
  "baby",
  "groceries",
  "other",
];

const BROAD_CATEGORY_LABELS: Record<string, string> = {
  electronics: "Electronics",
  beauty: "Beauty & Health",
  fitness: "Fitness & Sports",
  fashion: "Fashion",
  home: "Home & Living",
  books: "Books",
  toys: "Toys",
  travel: "Travel",
  arts: "Arts & Music",
  office: "Office",
  automotive: "Automotive & Tools",
  pet: "Pet Supplies",
  baby: "Baby",
  groceries: "Groceries",
  other: "More Products",
};

export function getBroadCategory(product: Product): string {
  return CATEGORY_TO_BROAD[product.category] ?? "other";
}

export function formatCategoryLabel(category: string): string {
  return (
    BROAD_CATEGORY_LABELS[category] ??
    category
      .split(/[-_]/)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ")
  );
}

export function formatSubcategoryLabel(category: string): string {
  return category
    .split(/[-_]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function groupProductsByCategory(products: Product[]): Array<{ category: string; products: Product[] }> {
  const buckets = new Map<string, Product[]>();
  for (const product of products) {
    const broad = getBroadCategory(product);
    const list = buckets.get(broad) ?? [];
    list.push(product);
    buckets.set(broad, list);
  }

  for (const [, list] of buckets) {
    list.sort((a, b) => a.name.localeCompare(b.name));
  }

  const categories = [...buckets.keys()];
  categories.sort((a, b) => {
    const ai = BROAD_CATEGORY_ORDER.indexOf(a);
    const bi = BROAD_CATEGORY_ORDER.indexOf(b);
    if (ai === -1 && bi === -1) return a.localeCompare(b);
    if (ai === -1) return 1;
    if (bi === -1) return -1;
    return ai - bi;
  });

  return categories.map((category) => ({
    category,
    products: buckets.get(category) ?? [],
  }));
}

export function categoryAccent(category: string): string {
  const accents: Record<string, string> = {
    electronics: "#2563eb",
    beauty: "#e11d48",
    fitness: "#16a34a",
    fashion: "#db2777",
    home: "#0d9488",
    books: "#4f46e5",
    toys: "#f59e0b",
    travel: "#0284c7",
    arts: "#9333ea",
    office: "#64748b",
    automotive: "#475569",
    pet: "#ea580c",
    baby: "#f472b6",
    groceries: "#84cc16",
    other: "#6d28d9",
  };
  return accents[category] ?? "var(--accent)";
}
