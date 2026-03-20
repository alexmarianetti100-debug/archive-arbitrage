import type { ArbitrageOpportunity } from '../types';
import { ArrowRight } from 'lucide-react';

interface ArbitrageCardProps {
  opportunity: ArbitrageOpportunity;
}

const platformColor: Record<string, string> = {
  grailed: '#ff4444',
  poshmark: '#cf3476',
  ebay: '#00d4ff',
  depop: '#ff2300',
  mercari: '#4dc1e8',
  therealreal: '#000',
  vinted: '#09b1ba',
};

export function ArbitrageCard({ opportunity }: ArbitrageCardProps) {
  const buyColor = platformColor[opportunity.buy_platform.toLowerCase()] || '#6b6b6b';
  const sellColor = platformColor[opportunity.sell_platform.toLowerCase()] || '#6b6b6b';

  return (
    <div className="surface-terminal rounded-lg p-4 hover:border-border-strong transition-colors relative">
      <div className="flex items-start justify-between gap-4 relative z-10">
        {/* Left: Product Info */}
        <div className="flex-1 min-w-0">
          <h4 className="text-sm text-text-primary mb-1 font-medium">{opportunity.canonical_name}</h4>
          <p className="font-mono text-[11px] text-text-muted line-clamp-1">{opportunity.reasoning}</p>
        </div>

        {/* Right: Profit */}
        <div className="text-right flex-shrink-0">
          <div className="data-value text-xl text-signal-green">+${opportunity.net_profit.toFixed(0)}</div>
          <span className="font-mono text-[10px] text-text-muted">{opportunity.net_margin.toFixed(0)}% net</span>
        </div>
      </div>

      {/* Trade Flow */}
      <div className="mt-3 flex items-center gap-2 relative z-10">
        {/* Buy Side */}
        <div className="flex-1 surface-inset rounded p-2.5">
          <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-text-muted mb-1">Buy</div>
          <div className="flex items-center justify-between">
            <span
              className="font-mono text-[11px] font-medium"
              style={{ color: buyColor }}
            >
              {opportunity.buy_platform}
            </span>
            <span className="data-value text-sm text-text-primary">${opportunity.buy_price.toFixed(0)}</span>
          </div>
        </div>

        {/* Arrow */}
        <ArrowRight className="w-3.5 h-3.5 text-text-muted flex-shrink-0" />

        {/* Sell Side */}
        <div className="flex-1 surface-inset rounded p-2.5">
          <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-text-muted mb-1">Sell</div>
          <div className="flex items-center justify-between">
            <span
              className="font-mono text-[11px] font-medium"
              style={{ color: sellColor }}
            >
              {opportunity.sell_platform}
            </span>
            <span className="data-value text-sm text-text-primary">${opportunity.sell_reference_price.toFixed(0)}</span>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="mt-2.5 flex items-center justify-between font-mono text-[10px] text-text-muted relative z-10">
        <span>
          Fees: {opportunity.platform_fees > 0 ? `${(opportunity.platform_fees * 100).toFixed(0)}%` : 'N/A'}
        </span>
        <span className={`uppercase tracking-wider ${
          opportunity.confidence === 'high' ? 'text-signal-green' :
          opportunity.confidence === 'medium' ? 'text-signal-amber' :
          'text-text-muted'
        }`}>
          {opportunity.confidence} conf.
        </span>
      </div>
    </div>
  );
}
