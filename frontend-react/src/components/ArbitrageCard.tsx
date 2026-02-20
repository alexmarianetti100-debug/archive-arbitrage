import type { ArbitrageOpportunity } from '../types';
import { ArrowRight, ExternalLink } from 'lucide-react';

interface ArbitrageCardProps {
  opportunity: ArbitrageOpportunity;
}

export function ArbitrageCard({ opportunity }: ArbitrageCardProps) {
  const platformColors: Record<string, string> = {
    grailed: 'text-red-400',
    poshmark: 'text-pink-400',
    ebay: 'text-blue-400',
    depop: 'text-green-400',
  };

  return (
    <div className="bg-gray-900 rounded-xl p-5 border border-gray-800 hover:border-gray-700 transition-colors">
      <div className="flex items-start justify-between gap-4">
        {/* Left: Product Info */}
        <div className="flex-1 min-w-0">
          <h4 className="font-semibold text-white mb-1">{opportunity.canonical_name}</h4>
          <p className="text-sm text-gray-400 line-clamp-2">{opportunity.reasoning}</p>
        </div>
        
        {/* Right: Profit */}
        <div className="text-right">
          <div className="text-2xl font-bold text-green-400">+${opportunity.net_profit.toFixed(0)}</div>
          <div className="text-sm text-gray-400">{opportunity.net_margin.toFixed(0)}% net</div>
        </div>
      </div>
      
      {/* Trade Flow */}
      <div className="mt-4 flex items-center gap-4">
        {/* Buy Side */}
        <div className="flex-1 bg-gray-800 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">BUY</div>
          <div className="flex items-center gap-2">
            <span className={`font-semibold ${platformColors[opportunity.buy_platform] || 'text-gray-400'}`}>
              {opportunity.buy_platform}
            </span>
            <span className="text-white font-bold">${opportunity.buy_price.toFixed(0)}</span>
          </div>
        </div>
        
        {/* Arrow */}
        <ArrowRight className="w-5 h-5 text-gray-500" />
        
        {/* Sell Side */}
        <div className="flex-1 bg-gray-800 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">SELL</div>
          <div className="flex items-center gap-2">
            <span className={`font-semibold ${platformColors[opportunity.sell_platform] || 'text-gray-400'}`}>
              {opportunity.sell_platform}
            </span>
            <span className="text-white font-bold">${opportunity.sell_reference_price.toFixed(0)}</span>
          </div>
        </div>
      </div>
      
      {/* Footer */}
      <div className="mt-4 flex items-center justify-between text-xs">
        <div className="text-gray-500">
          After {opportunity.platform_fees > 0 ? `${(opportunity.platform_fees * 100).toFixed(0)}%` : ''} fees
        </div>
        <button className="text-purple-400 hover:text-purple-300 flex items-center gap-1 transition-colors">
          View Details
          <ExternalLink className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}
