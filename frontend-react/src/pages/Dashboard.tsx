import { useStatsComparison } from '../hooks/useApi';
import { StatsCard } from '../components/StatsCard';
import { GradeDistribution } from '../components/GradeDistribution';
import { VelocityChart } from '../components/VelocityChart';
import { RecentDeals } from '../components/RecentDeals';

function formatTrend(value: number): string {
  if (value === 0) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value}%`;
}

export function Dashboard() {
  const { data, isLoading } = useStatsComparison();

  if (isLoading) {
    return (
      <div className="p-6 lg:p-8">
        <div className="space-y-6">
          <div className="h-6 w-48 bg-surface rounded animate-skeleton" />
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-28 bg-surface rounded-lg border border-border animate-skeleton" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  const stats = data?.current;
  const trends = data?.trends;

  return (
    <div className="p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="font-serif text-headline text-text-primary italic">Overview</h1>
          <p className="font-mono text-[11px] text-text-muted mt-1 tracking-wide">
            REAL-TIME ARBITRAGE INTELLIGENCE
          </p>
        </div>
        <div className="hidden sm:flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-signal-green animate-pulse-slow" />
          <span className="font-mono text-[10px] text-text-muted">
            LIVE — {new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatsCard
          title="Active Items"
          value={stats?.active_items?.toLocaleString() || '0'}
          subtitle="In pipeline"
          trend={formatTrend(trends?.active_items ?? 0)}
          trendUp={(trends?.active_items ?? 0) >= 0}
        />
        <StatsCard
          title="A-Grade"
          value={stats?.grade_a_count || 0}
          subtitle="Guaranteed flips"
          trend={formatTrend(trends?.grade_a_count ?? 0)}
          trendUp={(trends?.grade_a_count ?? 0) >= 0}
          highlight
        />
        <StatsCard
          title="Avg Margin"
          value={`${stats?.avg_margin || 0}%`}
          subtitle="Across portfolio"
          trend={trends?.avg_margin ? `${trends.avg_margin > 0 ? '+' : ''}${trends.avg_margin}pp` : '—'}
          trendUp={(trends?.avg_margin ?? 0) >= 0}
        />
        <StatsCard
          title="Brands"
          value={stats?.unique_brands || 0}
          subtitle="Tracked"
          trend={formatTrend(trends?.unique_brands ?? 0)}
          trendUp={(trends?.unique_brands ?? 0) >= 0}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div className="surface-terminal rounded-lg p-5 relative">
          <div className="flex items-center justify-between mb-4 relative z-10">
            <h3 className="font-mono text-xs text-text-secondary uppercase tracking-wider">Grade Distribution</h3>
          </div>
          <div className="relative z-10">
            <GradeDistribution />
          </div>
        </div>

        <div className="surface-terminal rounded-lg p-5 relative">
          <div className="flex items-center justify-between mb-4 relative z-10">
            <h3 className="font-mono text-xs text-text-secondary uppercase tracking-wider">Pipeline Volume</h3>
            <span className="font-mono text-[10px] text-text-muted">14D</span>
          </div>
          <div className="relative z-10">
            <VelocityChart />
          </div>
        </div>
      </div>

      {/* Recent Deals */}
      <div className="surface-terminal rounded-lg p-5 relative">
        <div className="flex items-center justify-between mb-4 relative z-10">
          <h3 className="font-mono text-xs text-text-secondary uppercase tracking-wider">Recent A-Grade Deals</h3>
          <span className="font-mono text-[10px] text-signal-green">
            {stats?.grade_a_count || 0} active
          </span>
        </div>
        <div className="relative z-10">
          <RecentDeals />
        </div>
      </div>
    </div>
  );
}
