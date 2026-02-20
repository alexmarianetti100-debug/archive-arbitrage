// Types for Archive Arbitrage Frontend

export interface Item {
  id: number;
  source: string;
  source_id: string;
  source_url: string;
  title: string;
  brand: string | null;
  category: string | null;
  size: string | null;
  condition: string | null;
  source_price: number;
  source_shipping: number;
  market_price: number | null;
  our_price: number | null;
  margin_percent: number | null;
  images: string[];
  is_auction: boolean;
  status: string;
  created_at: string;
  updated_at: string;
  // Qualification fields
  deal_grade?: string;
  deal_grade_reasoning?: string;
  comp_count?: number;
  demand_level?: string;
  sold_count?: number;
  active_count?: number;
  exact_profit?: number;
  exact_margin?: number;
  sell_through_rate?: number;
  est_days_to_sell?: number;
  // Product matching
  product_id?: number;
  product_fingerprint?: string;
  product_match_confidence?: string;
  exact_product_comps?: number;
  price_confidence?: string;
  price_band_low?: number;
  price_band_high?: number;
}

export interface Product {
  id: number;
  fingerprint_hash: string;
  canonical_name: string;
  brand: string;
  sub_brand: string;
  model: string;
  item_type: string;
  material: string;
  total_sales: number;
  sales_30d: number;
  sales_90d: number;
  velocity_trend: string;
  is_high_velocity: boolean;
}

export interface Stats {
  total_items: number;
  active_items: number;
  unique_brands: number;
  avg_margin: number;
  a_grade_count?: number;
  b_grade_count?: number;
}

export interface ArbitrageOpportunity {
  fingerprint_hash: string;
  canonical_name: string;
  buy_platform: string;
  buy_price: number;
  sell_platform: string;
  sell_reference_price: number;
  platform_fees: number;
  net_profit: number;
  net_margin: number;
  confidence: string;
  reasoning: string;
}

export interface PricePoint {
  date: string;
  price: number;
  source: string;
}

export type Grade = 'A' | 'B' | 'C' | 'D' | null;
export type ViewMode = 'grid' | 'list';
export type SortField = 'newest' | 'profit' | 'margin' | 'grade' | 'velocity';
