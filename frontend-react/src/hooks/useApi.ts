import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchItems, fetchItem, fetchItemPriceHistory, fetchItemMarketData, fetchStats, fetchArbitrage, fetchProducts, fetchVolumeStats, fetchVolumeTimeseries, fetchStatsComparison, fetchScrapeStatus, fetchScrapeHistory, fetchQueries, fetchTierSummary, fetchJapanTargets, fetchTelemetry, fetchJapanTelemetry, fetchItemComps, submitCompFeedback } from '../utils/api';

export const useItems = (params: Parameters<typeof fetchItems>[0] = {}) => {
  return useQuery({
    queryKey: ['items', params],
    queryFn: () => fetchItems(params),
    staleTime: 5 * 60 * 1000,
  });
};

export const useStats = (params: { created_after?: string } = {}) => {
  return useQuery({
    queryKey: ['stats', params],
    queryFn: () => fetchStats(params),
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
};

export const useItem = (id: number | null) => {
  return useQuery({
    queryKey: ['item', id],
    queryFn: () => fetchItem(id!),
    enabled: id !== null,
    staleTime: 5 * 60 * 1000,
  });
};

export const useItemPriceHistory = (id: number | null) => {
  return useQuery({
    queryKey: ['item-price-history', id],
    queryFn: () => fetchItemPriceHistory(id!),
    enabled: id !== null,
    staleTime: 5 * 60 * 1000,
  });
};

export const useItemMarketData = (id: number | null) => {
  return useQuery({
    queryKey: ['item-market-data', id],
    queryFn: () => fetchItemMarketData(id!),
    enabled: id !== null,
    staleTime: 10 * 60 * 1000,
  });
};

export const useStatsComparison = () => {
  return useQuery({
    queryKey: ['stats-comparison'],
    queryFn: fetchStatsComparison,
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
};

export const useArbitrage = () => {
  return useQuery({
    queryKey: ['arbitrage'],
    queryFn: fetchArbitrage,
    staleTime: 5 * 60 * 1000,
  });
};

export const useProducts = () => {
  return useQuery({
    queryKey: ['products'],
    queryFn: fetchProducts,
    staleTime: 5 * 60 * 1000,
  });
};

export const useVolumeStats = () => {
  return useQuery({
    queryKey: ['volume-stats'],
    queryFn: fetchVolumeStats,
    staleTime: 5 * 60 * 1000,
  });
};

export const useVolumeTimeseries = (days: number = 14) => {
  return useQuery({
    queryKey: ['volume-timeseries', days],
    queryFn: () => fetchVolumeTimeseries(days),
    staleTime: 5 * 60 * 1000,
  });
};

export const useQueries = (tier?: string) => {
  return useQuery({
    queryKey: ['queries', tier],
    queryFn: () => fetchQueries(tier),
    staleTime: 30 * 1000,
  });
};

export const useTierSummary = () => {
  return useQuery({
    queryKey: ['tier-summary'],
    queryFn: fetchTierSummary,
    staleTime: 30 * 1000,
  });
};

export const useJapanTargets = () => {
  return useQuery({
    queryKey: ['japan-targets'],
    queryFn: fetchJapanTargets,
    staleTime: 60 * 1000,
  });
};

export const useTelemetry = (params: Parameters<typeof fetchTelemetry>[0] = {}) => {
  return useQuery({
    queryKey: ['telemetry', params],
    queryFn: () => fetchTelemetry(params),
    staleTime: 30 * 1000,
  });
};

export const useJapanTelemetry = () => {
  return useQuery({
    queryKey: ['japan-telemetry'],
    queryFn: fetchJapanTelemetry,
    staleTime: 60 * 1000,
  });
};

export const useScrapeStatus = () => {
  return useQuery({
    queryKey: ['scrape-status'],
    queryFn: fetchScrapeStatus,
    staleTime: 3 * 1000,
    refetchInterval: 5 * 1000,
  });
};

export const useScrapeHistory = () => {
  return useQuery({
    queryKey: ['scrape-history'],
    queryFn: fetchScrapeHistory,
    staleTime: 10 * 1000,
  });
};

export const useItemComps = (itemId: number | null) => {
  return useQuery({
    queryKey: ['item-comps', itemId],
    queryFn: () => fetchItemComps(itemId!),
    enabled: itemId !== null,
    staleTime: 5 * 60 * 1000,
  });
};

export const useCompFeedback = (itemId: number) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemCompId, status, reason }: {
      itemCompId: number;
      status: 'accepted' | 'rejected';
      reason?: string;
    }) => submitCompFeedback(itemId, itemCompId, status, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['item-comps', itemId] });
      queryClient.invalidateQueries({ queryKey: ['item', itemId] });
      queryClient.invalidateQueries({ queryKey: ['items'] });
    },
  });
};
