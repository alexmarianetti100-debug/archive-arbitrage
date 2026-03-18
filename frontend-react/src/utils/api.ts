import axios from 'axios';
import type { Item, Product, Stats, ArbitrageOpportunity, ItemCompsResponse, CompFeedbackResponse } from '../types';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const fetchItems = async (params: {
  brand?: string;
  grade?: string;
  category?: string;
  min_price?: number;
  max_price?: number;
  season?: string;
  year?: number;
  year_min?: number;
  year_max?: number;
  sort?: string;
  page_size?: number;
  page?: number;
  created_after?: string;
}): Promise<Item[]> => {
  const apiParams: any = { ...params };
  const { data } = await api.get('/items', { params: apiParams });
  return data.items || data;
};

export const fetchItem = async (id: number): Promise<Item> => {
  const { data } = await api.get(`/items/${id}`);
  return data;
};

export const fetchItemPriceHistory = async (id: number): Promise<{
  current: { source_price: number; our_price: number; recorded_at: string };
  history: { price: number; recorded_at: string }[];
}> => {
  const { data } = await api.get(`/items/${id}/price-history`);
  return data;
};

export const fetchItemMarketData = async (id: number): Promise<{
  search_key: string;
  listings: { title: string; price: number; image_url: string | null; url: string }[];
  stats: { count: number; avg_price: number; min_price: number; max_price: number } | null;
  demand_level: string;
}> => {
  const { data } = await api.get(`/items/${id}/market-data`);
  return data;
};

export const fetchStats = async (params: { created_after?: string } = {}): Promise<Stats> => {
  const { data } = await api.get('/stats', { params });
  return data;
};

export const fetchBrands = async (): Promise<string[]> => {
  const { data } = await api.get('/brands');
  return data.brands || data;
};

export const fetchProducts = async (): Promise<Product[]> => {
  const { data } = await api.get('/products');
  return data.products || data;
};

export const fetchArbitrage = async (): Promise<ArbitrageOpportunity[]> => {
  const { data } = await api.get('/arbitrage');
  return data.opportunities || data;
};

export const fetchVolumeStats = async (): Promise<any> => {
  const { data } = await api.get('/volume-stats');
  return data;
};

export const fetchVolumeTimeseries = async (days: number = 14): Promise<{ daily_volumes: { date: string; volume: number }[] }> => {
  const { data } = await api.get('/volume-timeseries', { params: { days } });
  return data;
};

// Scrape control
export interface ScrapeStartConfig {
  mode: 'gap_hunter' | 'full_scrape';
  platforms?: string[];
  query_source?: string;
  custom_queries?: string[];
  max_results_per_query?: number;
  min_margin?: number;
  min_profit?: number;
  skip_auth?: boolean;
  dry_run?: boolean;
  skip_japan?: boolean;
  max_targets?: number;
}

export interface ScrapeRunSummary {
  run_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  mode: string;
  config: Record<string, unknown>;
  started_at: string;
  completed_at: string | null;
  stats: Record<string, number>;
  error: string | null;
}

export const startScrape = async (config: ScrapeStartConfig): Promise<{ run_id: string; status: string }> => {
  const { data } = await api.post('/scrape/start', config);
  return data;
};

export const fetchScrapeStatus = async (): Promise<{ running: boolean; run: ScrapeRunSummary | null }> => {
  const { data } = await api.get('/scrape/status');
  return data;
};

export const fetchScrapeHistory = async (): Promise<{ runs: ScrapeRunSummary[] }> => {
  const { data } = await api.get('/scrape/history');
  return data;
};

export const stopScrape = async (): Promise<{ cancelled: boolean; run_id: string }> => {
  const { data } = await api.post('/scrape/stop');
  return data;
};

// Query management
export interface QueryEntry {
  query: string;
  tier: 'A' | 'B' | 'trap';
  reason: string;
  total_runs: number;
  total_deals: number;
  deal_rate: number;
  best_gap: number;
  weight_multiplier: number;
  promoted: boolean;
  demoted: boolean;
  junk_ratio: number;
  last_run: string | null;
  raw_items_found: number;
  post_filter_candidates: number;
}

export interface TierSummary {
  a_count: number;
  b_count: number;
  trap_count: number;
  total_queries: number;
  promoted_count: number;
  demoted_count: number;
  top_a: string[];
  worst_traps: string[];
}

export interface JapanTarget {
  jp: string;
  en: string;
  category: string;
  brand: string;
  weight: number;
  en_tier: string;
  en_deal_rate: number;
  jp_total_runs: number;
  jp_total_deals: number;
  jp_last_run: string | null;
}

export const fetchQueries = async (tier?: string): Promise<{ queries: QueryEntry[]; total: number }> => {
  const { data } = await api.get('/queries', { params: tier ? { tier } : {} });
  return data;
};

export const fetchTierSummary = async (): Promise<TierSummary> => {
  const { data } = await api.get('/queries/tier-summary');
  return data;
};

export const updateQueryTier = async (query: string, action: 'promote' | 'demote'): Promise<any> => {
  const { data } = await api.put(`/queries/${encodeURIComponent(query)}/tier`, null, { params: { action } });
  return data;
};

export const fetchJapanTargets = async (): Promise<{ targets: JapanTarget[]; total: number }> => {
  const { data } = await api.get('/queries/japan');
  return data;
};

// Telemetry
export interface TelemetryAggregates {
  total_runs: number;
  total_deals: number;
  avg_deal_rate: number;
  avg_junk_ratio: number;
  skip_reasons: Record<string, number>;
}

export interface TelemetryResponse {
  queries: QueryEntry[];
  total: number;
  aggregates: TelemetryAggregates;
}

export interface JapanTelemetryEntry {
  query: string;
  total_runs: number;
  total_deals: number;
  deal_rate: number;
  best_gap: number;
  last_run: string | null;
}

export interface JapanTelemetryResponse {
  queries: JapanTelemetryEntry[];
  total: number;
  aggregates: {
    total_runs: number;
    total_deals: number;
    avg_deal_rate: number;
  };
}

export const fetchTelemetry = async (params: {
  min_runs?: number;
  sort_by?: string;
  order?: string;
} = {}): Promise<TelemetryResponse> => {
  const { data } = await api.get('/telemetry/query-performance', { params });
  return data;
};

export const fetchJapanTelemetry = async (): Promise<JapanTelemetryResponse> => {
  const { data } = await api.get('/telemetry/japan-performance');
  return data;
};

export const fetchStatsComparison = async (): Promise<{
  current: Stats;
  trends: { active_items: number; grade_a_count: number; avg_margin: number; unique_brands: number };
}> => {
  const { data } = await api.get('/stats/compare');
  return data;
};

export const fetchItemComps = async (itemId: number): Promise<ItemCompsResponse> => {
  const { data } = await api.get(`/items/${itemId}/comps`);
  return data;
};

export const submitCompFeedback = async (
  itemId: number,
  itemCompId: number,
  status: 'accepted' | 'rejected',
  reason?: string,
): Promise<CompFeedbackResponse> => {
  const { data } = await api.post(`/items/${itemId}/comps/${itemCompId}/feedback`, {
    status,
    reason: reason || undefined,
  });
  return data;
};
