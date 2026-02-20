import { useArbitrage } from '../hooks/useApi';
import { ArbitrageCard } from '../components/ArbitrageCard';

export function Arbitrage() {
  const { data: opportunities, isLoading } = useArbitrage();

  // Group by confidence
  const highConf = opportunities?.filter(o => o.confidence === 'high') || [];
  const mediumConf = opportunities?.filter(o => o.confidence === 'medium') || [];
  const lowConf = opportunities?.filter(o => o.confidence === 'low') || [];

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-3xl font-bold text-white">Cross-Platform Arbitrage</h2>
        <p className="text-gray-400 mt-1">Buy low on one platform, sell high on another</p>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
          <div className="text-2xl font-bold text-green-400">{highConf.length}</div>
          <div className="text-sm text-gray-400">High Confidence</div>
        </div>
        <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
          <div className="text-2xl font-bold text-yellow-400">{mediumConf.length}</div>
          <div className="text-sm text-gray-400">Medium Confidence</div>
        </div>
        <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
          <div className="text-2xl font-bold text-gray-400">{lowConf.length}</div>
          <div className="text-sm text-gray-400">Low Confidence</div>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-32 bg-gray-800 rounded-xl animate-pulse"></div>
          ))}
        </div>
      ) : (
        <div className="space-y-8">
          {/* High Confidence */}
          {highConf.length > 0 && (
            <section>
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <span className="w-2 h-2 bg-green-400 rounded-full"></span>
                High Confidence Opportunities
              </h3>
              <div className="space-y-3">
                {highConf.map((opp, i) => (
                  <ArbitrageCard key={i} opportunity={opp} />
                ))}
              </div>
            </section>
          )}

          {/* Medium Confidence */}
          {mediumConf.length > 0 && (
            <section>
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <span className="w-2 h-2 bg-yellow-400 rounded-full"></span>
                Medium Confidence Opportunities
              </h3>
              <div className="space-y-3">
                {mediumConf.map((opp, i) => (
                  <ArbitrageCard key={i} opportunity={opp} />
                ))}
              </div>
            </section>
          )}

          {/* Low Confidence */}
          {lowConf.length > 0 && (
            <section>
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <span className="w-2 h-2 bg-gray-400 rounded-full"></span>
                Low Confidence Opportunities
              </h3>
              <div className="space-y-3">
                {lowConf.map((opp, i) => (
                  <ArbitrageCard key={i} opportunity={opp} />
                ))}
              </div>
            </section>
          )}

          {opportunities?.length === 0 && (
            <div className="text-center py-20 text-gray-500">
              No arbitrage opportunities found. Run the detector to find deals.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
