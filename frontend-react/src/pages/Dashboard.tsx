import { useStats } from '../hooks/useApi';
import { StatsCard } from '../components/StatsCard';
import { GradeDistribution } from '../components/GradeDistribution';
import { VelocityChart } from '../components/VelocityChart';
import { RecentDeals } from '../components/RecentDeals';

export function Dashboard() {
  const { data: stats, isLoading } = useStats();

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-800 rounded w-64"></div>
          <div className="grid grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-32 bg-gray-800 rounded-xl"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-3xl font-bold text-white">Dashboard</h2>
        <p className="text-gray-400 mt-1">Real-time arbitrage intelligence</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatsCard
          title="Active Items"
          value={stats?.active_items || 0}
          subtitle="In database"
          trend="+12%"
          trendUp={true}
        />
        <StatsCard
          title="A-Grade Deals"
          value={stats?.a_grade_count || 0}
          subtitle="Guaranteed flips"
          trend="Hot"
          trendUp={true}
          highlight
        />
        <StatsCard
          title="Avg Margin"
          value={`${stats?.avg_margin || 0}%`}
          subtitle="Across all items"
          trend="+5%"
          trendUp={true}
        />
        <StatsCard
          title="Brands"
          value={stats?.unique_brands || 0}
          subtitle="Tracked"
          trend="Stable"
          trendUp={true}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
          <h3 className="text-lg font-semibold mb-4">Deal Grade Distribution</h3>
          <GradeDistribution />
        </div>
        
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
          <h3 className="text-lg font-semibold mb-4">Sales Velocity (30d)</h3>
          <VelocityChart />
        </div>
      </div>

      {/* Recent Deals */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <h3 className="text-lg font-semibold mb-4">Recent A-Grade Deals</h3>
        <RecentDeals />
      </div>
    </div>
  );
}
