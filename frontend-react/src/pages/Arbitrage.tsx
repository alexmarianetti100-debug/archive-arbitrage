import { useArbitrage } from '../hooks/useApi';
import { ArbitrageCard } from '../components/ArbitrageCard';
import { EmptyArbitrage } from '../components/EmptyState';

export function Arbitrage() {
  const { data: opportunities, isLoading } = useArbitrage();

  const highConf = opportunities?.filter(o => o.confidence === 'high') || [];
  const mediumConf = opportunities?.filter(o => o.confidence === 'medium') || [];
  const lowConf = opportunities?.filter(o => o.confidence === 'low') || [];
  const total = (opportunities?.length) || 0;

  return (
    <div className="p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div>
        <h1 className="font-serif text-headline text-text-primary italic">Arbitrage</h1>
        <p className="font-mono text-[11px] text-text-muted mt-1 tracking-wide">
          CROSS-PLATFORM PRICE GAPS
        </p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-3">
        <div className="surface-terminal rounded-lg p-3.5 relative">
          <div className="relative z-10">
            <div className="data-value text-xl text-signal-green">{highConf.length}</div>
            <div className="font-mono text-[10px] text-text-muted mt-1 uppercase tracking-wider">High Conf.</div>
          </div>
        </div>
        <div className="surface-terminal rounded-lg p-3.5 relative">
          <div className="relative z-10">
            <div className="data-value text-xl text-signal-amber">{mediumConf.length}</div>
            <div className="font-mono text-[10px] text-text-muted mt-1 uppercase tracking-wider">Medium</div>
          </div>
        </div>
        <div className="surface-terminal rounded-lg p-3.5 relative">
          <div className="relative z-10">
            <div className="data-value text-xl text-text-secondary">{lowConf.length}</div>
            <div className="font-mono text-[10px] text-text-muted mt-1 uppercase tracking-wider">Low</div>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-28 bg-surface rounded-lg border border-border animate-skeleton" />
          ))}
        </div>
      ) : total === 0 ? (
        <EmptyArbitrage />
      ) : (
        <div className="space-y-6">
          {/* High Confidence */}
          {highConf.length > 0 && (
            <section>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-1.5 h-1.5 rounded-full bg-signal-green" />
                <h3 className="font-mono text-xs text-text-secondary uppercase tracking-wider">High Confidence</h3>
                <span className="font-mono text-[10px] text-text-muted">{highConf.length}</span>
              </div>
              <div className="space-y-2">
                {highConf.map((opp, i) => (
                  <ArbitrageCard key={i} opportunity={opp} />
                ))}
              </div>
            </section>
          )}

          {/* Medium Confidence */}
          {mediumConf.length > 0 && (
            <section>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-1.5 h-1.5 rounded-full bg-signal-amber" />
                <h3 className="font-mono text-xs text-text-secondary uppercase tracking-wider">Medium Confidence</h3>
                <span className="font-mono text-[10px] text-text-muted">{mediumConf.length}</span>
              </div>
              <div className="space-y-2">
                {mediumConf.map((opp, i) => (
                  <ArbitrageCard key={i} opportunity={opp} />
                ))}
              </div>
            </section>
          )}

          {/* Low Confidence */}
          {lowConf.length > 0 && (
            <section>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-1.5 h-1.5 rounded-full bg-text-muted" />
                <h3 className="font-mono text-xs text-text-secondary uppercase tracking-wider">Low Confidence</h3>
                <span className="font-mono text-[10px] text-text-muted">{lowConf.length}</span>
              </div>
              <div className="space-y-2">
                {lowConf.map((opp, i) => (
                  <ArbitrageCard key={i} opportunity={opp} />
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
