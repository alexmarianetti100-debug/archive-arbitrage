// Types for Archive Arbitrage Frontend
// Field names match the actual API response from /api/items

export interface Item {
  id: number;
  source: string;
  source_url: string;
  title: string;
  brand: string | null;
  category: string | null;
  size: string | null;
  condition: string | null;
  // Pricing — API returns these names
  price: number;
  original_price: number;
  market_price: number | null;
  margin_percent: number | null;
  images: string[];
  is_auction: boolean;
  status: string;
  // Qualification fields
  deal_grade?: string | null;
  deal_grade_reasoning?: string | null;
  comp_count?: number | null;
  high_quality_comps?: number | null;
  demand_score?: number | null;
  demand_level?: string | null;
  sold_count?: number | null;
  active_count?: number | null;
  exact_sell_price?: number | null;
  exact_profit?: number | null;
  exact_margin?: number | null;
  sell_through_rate?: number | null;
  est_days_to_sell?: number | null;
  qualified_at?: string | null;
  // Volume/velocity
  weighted_volume?: number | null;
  sales_per_day?: number | null;
  volume_trend?: string | null;
  same_size_sold?: number | null;
  price_trend_percent?: number | null;
  // Season
  exact_season?: string | null;
  exact_year?: number | null;
  season_confidence?: number | null;
  // Image hashing
  image_hash?: string | null;
  image_phash?: string | null;
  needs_review?: boolean;
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
  grade_a_count?: number;
  grade_b_count?: number;
  grade_c_count?: number;
  grade_d_count?: number;
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

export interface ItemComp {
  item_comp_id: number;
  rank: number;
  similarity_score: number;
  feedback_status: 'pending' | 'accepted' | 'rejected';
  rejection_reason?: string | null;
  title: string;
  sold_price: number;
  sold_date: string | null;
  sold_url: string | null;
  source: string | null;
  condition: string | null;
}

export interface ItemCompsResponse {
  comps: ItemComp[];
  total: number;
  accepted: number;
  rejected: number;
  pending: number;
}

export interface RegradeResult {
  triggered: boolean;
  comps_remaining: number;
  grade_before?: string;
  grade_after?: string;
  price_before?: number;
  price_after?: number;
  margin_before?: number;
  margin_after?: number;
  reason?: string;
  flagged_for_review?: boolean;
}

export interface CompFeedbackResponse {
  updated: boolean;
  regrade: RegradeResult;
}

export type RejectionReason = 'wrong_model' | 'wrong_condition' | 'wrong_brand' | 'outlier' | 'other';

export type Grade = 'A' | 'B' | 'C' | 'D' | null;
export type ViewMode = 'grid' | 'list';
export type SortField = 'newest' | 'profit' | 'margin' | 'grade' | 'velocity';
