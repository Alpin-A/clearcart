const BASE = "/api";

export interface SearchResult {
  asin: string;
  title: string;
  brand: string;
  price: number | null;
  has_price: boolean;
  avg_rating: number | null;
  review_count: number;
  fit_score: number;
  evidence_score: number;
  complaint_rate: number;
  top_pros: string[];
  top_cons: string[];
  over_budget: boolean;
  matched_preferences: string[];
}

export interface ProductDetail extends SearchResult {
  description_text: string;
  features_text: string;
  price_fit: number | null;
  rating_confidence: number | null;
  main_category?: string;
}

export async function searchProducts(
  query: string,
  topK: number = 10
): Promise<SearchResult[]> {
  const params = new URLSearchParams({ q: query, top_k: String(topK) });
  const res = await fetch(`${BASE}/search?${params}`);
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}

export async function getProduct(asin: string): Promise<ProductDetail> {
  const res = await fetch(`${BASE}/product/${asin}`);
  if (!res.ok) throw new Error(`Product not found: ${asin}`);
  return res.json();
}
