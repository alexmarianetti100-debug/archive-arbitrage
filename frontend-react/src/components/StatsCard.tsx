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
    <div className={`relative rounded-lg p-4 border transition-colors ${
      highlight
        ? 'bg-accent/[0.03] border-accent/10 glow-accent'
        : 'bg-surface border-border hover:border-border-strong'
    }`}>
      {/* Label */}
      <div className="flex items-center justify-between mb-3">
        <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted">
          {title}
        </span>
        <div className={`flex items-center gap-1 font-mono text-[10px] ${
          trendUp ? 'text-signal-green' : 'text-signal-red'
        }`}>
          {trendUp ? <TrendingUp className="w-2.5 h-2.5" /> : <TrendingDown className="w-2.5 h-2.5" />}
          <span>{trend}</span>
        </div>
      </div>

      {/* Value */}
      <div className="data-value text-2xl text-text-primary mb-1">
        {value}
      </div>

      {/* Subtitle */}
      <span className="font-mono text-[10px] text-text-muted">{subtitle}</span>
    </div>
  );
}
