import { useQuery } from '@tanstack/react-query';
import { fetchItems, fetchStats, fetchArbitrage } from '../utils/api';

export const useItems = (params: Parameters<typeof fetchItems>[0] = {}) => {
  return useQuery({
    queryKey: ['items', params],
    queryFn: () => fetchItems(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

export const useStats = () => {
  return useQuery({
    queryKey: ['stats'],
    queryFn: fetchStats,
    staleTime: 60 * 1000, // 1 minute
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
