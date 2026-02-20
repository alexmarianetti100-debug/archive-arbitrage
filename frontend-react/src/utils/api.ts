import axios from 'axios';
import type { Item, Product, Stats, ArbitrageOpportunity } from '../types';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const fetchItems = async (params: {
  status?: string;
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
  limit?: number;
  offset?: number;
}): Promise<Item[]> => {
  // Map frontend 'grade' to backend filter if needed
  const apiParams: any = { ...params };
  if (params.grade) {
    // Backend doesn't have grade filter directly, we'll filter client-side for now
    // or the backend accepts it as part of the query
  }
  const { data } = await api.get('/items', { params: apiParams });
  return data.items || data; // Handle both {items: []} and direct array responses
};

export const fetchItem = async (id: number): Promise<Item> => {
  const { data } = await api.get(`/items/${id}`);
  return data;
};

export const fetchItemPriceHistory = async (id: number): Promise<any[]> => {
  const { data } = await api.get(`/items/${id}/price-history`);
  return data;
};

export const fetchItemMarketData = async (id: number): Promise<any> => {
  const { data } = await api.get(`/items/${id}/market-data`);
  return data;
};

export const fetchStats = async (): Promise<Stats> => {
  const { data } = await api.get('/stats');
  return data;
};

export const fetchBrands = async (): Promise<string[]> => {
  const { data } = await api.get('/brands');
  return data.brands || data;
};

export const fetchProducts = async (): Promise<Product[]> => {
  const { data } = await api.get('/products');
  return data;
};

export const fetchArbitrage = async (): Promise<ArbitrageOpportunity[]> => {
  const { data } = await api.get('/arbitrage');
  return data;
};
