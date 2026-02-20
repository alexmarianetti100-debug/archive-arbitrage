import { TrendingUp, TrendingDown } from 'lucide-react';

interface StatsCardProps {
  title: string;
  value: string | number;
  subtitle: string;
  trend: string;
  trendUp: boolean;
  highlight?: boolean;
}

export function StatsCard({ title, value, subtitle, trend, trendUp, highlight }: StatsCardProps) {
  return (
    <div className={`rounded-xl p-6 border ${
      highlight 
        ? 'bg-purple-600/10 border-purple-600/30' 
        : 'bg-gray-900 border-gray-800'
    }`}>
      <h3 className="text-sm font-medium text-gray-400">{title}</h3>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-3xl font-bold text-white">{value}</span>
      </div>
      <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
      <div className={`mt-3 flex items-center gap-1 text-xs ${
        trendUp ? 'text-green-400' : 'text-red-400'
      }`}>
        {trendUp ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
        <span>{trend}</span>
      </div>
    </div>
  );
}
