import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, ExternalLink, Clock, Package,
  ChevronLeft, ChevronRight, Loader2,
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import type { Item } from '../types';
import { useItemMarketData } from '../hooks/useApi';
import { CompTable } from './CompTable';

interface ItemDetailPanelProps {
  item: Item | null;
  onClose: () => void;
}

const gradeClass: Record<string, string> = {
  A: 'grade-a',
  B: 'grade-b',
  C: 'grade-c',
  D: 'grade-d',
};

function CompTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="surface-glass rounded px-3 py-2">
      <span className="font-mono text-xs text-text-primary">${d.price}</span>
      <span className="font-mono text-[10px] text-text-muted block truncate max-w-[180px]">{d.title}</span>
    </div>
  );
}

export function ItemDetailPanel({ item, onClose }: ItemDetailPanelProps) {
  const [imageIndex, setImageIndex] = useState(0);
  const { data: marketData, isLoading: loadingMarket } = useItemMarketData(item?.id ?? null);

  // Reset image index when switching items
  useEffect(() => {
    setImageIndex(0);
  }, [item?.id]);

  // Close on Escape key
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') onClose();
  }, [onClose]);

  useEffect(() => {
    if (!item) return;
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [item, handleKeyDown]);

  if (!item) return null;

  const buyPrice = item.original_price || 0;
  const sellPrice = item.price || item.market_price || 0;
  const profit = item.exact_profit || (sellPrice - buyPrice);
  const rawMargin = item.exact_margin ?? item.margin_percent ?? 0;
  const margin = rawMargin > 1 ? rawMargin / 100 : rawMargin;
  const grade = item.deal_grade || 'D';
  const gc = gradeClass[grade] || gradeClass.D;
  const images = item.images || [];

  const prevImage = () => setImageIndex((i) => (i > 0 ? i - 1 : images.length - 1));
  const nextImage = () => setImageIndex((i) => (i < images.length - 1 ? i + 1 : 0));

  // Market data comps for chart
  const compChartData = (marketData?.listings || []).map((l) => ({
    title: l.title,
    price: l.price,
  }));

  return (
    <AnimatePresence>
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50"
      />

      {/* Panel */}
      <motion.div
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ type: 'spring', damping: 30, stiffness: 300 }}
        className="fixed right-0 top-0 h-full w-full max-w-lg bg-surface border-l border-border z-50 flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border flex-shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            {item.deal_grade && (
              <span className={`grade-badge rounded ${gc}`}>{grade}</span>
            )}
            <span className="font-mono text-[10px] text-accent uppercase tracking-wider truncate">
              {item.brand || item.source}
            </span>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <a
              href={item.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 hover:bg-surface-hover rounded transition-colors text-text-muted hover:text-accent"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
            <button
              onClick={onClose}
              className="p-1.5 hover:bg-surface-hover rounded transition-colors"
            >
              <X className="w-4 h-4 text-text-muted" />
            </button>
          </div>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto">
          {/* Image gallery */}
          {images.length > 0 ? (
            <div className="relative bg-void">
              <img
                src={images[imageIndex]}
                alt={item.title}
                className="w-full aspect-[4/3] object-contain"
              />
              {images.length > 1 && (
                <>
                  <button
                    onClick={prevImage}
                    className="absolute left-2 top-1/2 -translate-y-1/2 p-1.5 bg-black/50 hover:bg-black/70 rounded-full transition-colors"
                  >
                    <ChevronLeft className="w-4 h-4 text-white" />
                  </button>
                  <button
                    onClick={nextImage}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 bg-black/50 hover:bg-black/70 rounded-full transition-colors"
                  >
                    <ChevronRight className="w-4 h-4 text-white" />
                  </button>
                  <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1">
                    {images.map((_, i) => (
                      <button
                        key={i}
                        onClick={() => setImageIndex(i)}
                        className={`w-1.5 h-1.5 rounded-full transition-colors ${
                          i === imageIndex ? 'bg-white' : 'bg-white/30'
                        }`}
                      />
                    ))}
                  </div>
                </>
              )}
            </div>
          ) : (
            <div className="aspect-[4/3] bg-void flex items-center justify-center">
              <Package className="w-12 h-12 text-text-muted" />
            </div>
          )}

          <div className="p-4 space-y-5">
            {/* Title */}
            <div>
              <h2 className="text-sm text-text-primary leading-relaxed">{item.title}</h2>
              <div className="flex items-center gap-3 mt-2 font-mono text-[10px] text-text-muted">
                <span>{item.source}</span>
                {item.size && <span>Size {item.size}</span>}
                {item.condition && <span>{item.condition}</span>}
                {item.exact_season && item.exact_year && (
                  <span>{item.exact_season}{item.exact_year}</span>
                )}
              </div>
            </div>

            {/* Pricing */}
            <div className="surface-inset rounded-lg p-3.5">
              <div className="grid grid-cols-3 gap-3 text-center">
                <div>
                  <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-text-muted mb-1">Buy</div>
                  <div className="data-value text-lg text-text-primary">${buyPrice.toFixed(0)}</div>
                </div>
                <div>
                  <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-text-muted mb-1">Sell</div>
                  <div className="data-value text-lg text-text-primary">${sellPrice.toFixed(0)}</div>
                </div>
                <div>
                  <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-text-muted mb-1">Profit</div>
                  <div className={`data-value text-lg ${profit > 0 ? 'text-signal-green' : 'text-signal-red'}`}>
                    {profit > 0 ? '+' : ''}${profit.toFixed(0)}
                  </div>
                </div>
              </div>
              <div className="flex items-center justify-center gap-4 mt-2 pt-2 border-t border-border font-mono text-[10px] text-text-muted">
                <span>{(margin * 100).toFixed(0)}% margin</span>
                {item.est_days_to_sell && (
                  <span className="flex items-center gap-1">
                    <Clock className="w-2.5 h-2.5" />
                    ~{item.est_days_to_sell.toFixed(0)} days
                  </span>
                )}
                {item.sell_through_rate != null && (
                  <span>{(item.sell_through_rate * 100).toFixed(0)}% sell-through</span>
                )}
              </div>
            </div>

            {/* Grade reasoning */}
            {item.deal_grade_reasoning && (
              <div>
                <h4 className="font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted mb-2">Grade Reasoning</h4>
                <p className="font-mono text-[11px] text-text-secondary leading-relaxed">
                  {item.deal_grade_reasoning}
                </p>
              </div>
            )}

            {/* Comp & demand stats */}
            <div className="grid grid-cols-2 gap-2">
              {item.comp_count != null && (
                <div className="bg-void rounded p-2.5 border border-border">
                  <div className="font-mono text-[9px] uppercase tracking-wider text-text-muted">Comps</div>
                  <div className="data-value text-sm text-text-primary mt-0.5">
                    {item.comp_count}
                    {item.high_quality_comps != null && (
                      <span className="text-text-muted text-[10px] font-normal ml-1">({item.high_quality_comps} HQ)</span>
                    )}
                  </div>
                </div>
              )}
              {item.sold_count != null && (
                <div className="bg-void rounded p-2.5 border border-border">
                  <div className="font-mono text-[9px] uppercase tracking-wider text-text-muted">Sold</div>
                  <div className="data-value text-sm text-text-primary mt-0.5">
                    {item.sold_count}
                    {item.active_count != null && (
                      <span className="text-text-muted text-[10px] font-normal ml-1">/ {item.active_count} active</span>
                    )}
                  </div>
                </div>
              )}
              {item.demand_level && (
                <div className="bg-void rounded p-2.5 border border-border">
                  <div className="font-mono text-[9px] uppercase tracking-wider text-text-muted">Demand</div>
                  <div className={`data-value text-sm mt-0.5 ${
                    item.demand_level === 'high' ? 'text-signal-green' :
                    item.demand_level === 'medium' ? 'text-signal-amber' : 'text-text-muted'
                  }`}>
                    {item.demand_level}
                    {item.demand_score != null && (
                      <span className="text-text-muted text-[10px] font-normal ml-1">({item.demand_score.toFixed(2)})</span>
                    )}
                  </div>
                </div>
              )}
              {item.weighted_volume != null && item.weighted_volume > 0 && (
                <div className="bg-void rounded p-2.5 border border-border">
                  <div className="font-mono text-[9px] uppercase tracking-wider text-text-muted">Volume</div>
                  <div className="data-value text-sm text-text-primary mt-0.5">
                    {item.weighted_volume.toFixed(0)}
                    {item.volume_trend && (
                      <span className={`text-[10px] font-normal ml-1 ${
                        item.volume_trend === 'accelerating' ? 'text-signal-green' :
                        item.volume_trend === 'decelerating' ? 'text-signal-red' : 'text-text-muted'
                      }`}>
                        {item.volume_trend}
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Sold Comps — Feedback */}
            {item.id && (
              <div className="surface-inset rounded-lg p-4">
                <h4 className="font-mono text-[10px] text-text-muted uppercase tracking-wider mb-3">
                  Sold Comps
                </h4>
                <CompTable itemId={item.id} />
              </div>
            )}

            {/* Market data — active listings */}
            <div>
              <h4 className="font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted mb-2">
                Market Comps
              </h4>
              {loadingMarket ? (
                <div className="flex items-center gap-2 py-4 justify-center">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-text-muted" />
                  <span className="font-mono text-[11px] text-text-muted">Fetching live comps...</span>
                </div>
              ) : marketData?.stats ? (
                <div className="space-y-3">
                  {/* Stats row */}
                  <div className="flex items-center gap-4 font-mono text-[10px]">
                    <span className="text-text-secondary">{marketData.stats.count} active</span>
                    <span className="text-text-muted">|</span>
                    <span className="text-text-secondary">Avg ${marketData.stats.avg_price.toFixed(0)}</span>
                    <span className="text-text-muted">|</span>
                    <span className="text-text-secondary">${marketData.stats.min_price.toFixed(0)}–${marketData.stats.max_price.toFixed(0)}</span>
                    <span className={`ml-auto uppercase tracking-wider ${
                      marketData.demand_level === 'high' ? 'text-signal-green' :
                      marketData.demand_level === 'medium' ? 'text-signal-amber' : 'text-text-muted'
                    }`}>
                      {marketData.demand_level}
                    </span>
                  </div>

                  {/* Comp price chart */}
                  {compChartData.length > 0 && (
                    <div className="h-28">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={compChartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                          <XAxis dataKey="title" hide />
                          <YAxis
                            axisLine={false}
                            tickLine={false}
                            tick={{ fontSize: 10, fill: '#3a3a3a', fontFamily: 'DM Mono' }}
                          />
                          <Tooltip content={<CompTooltip />} />
                          <Bar dataKey="price" fill="#00d4ff" radius={[2, 2, 0, 0]} opacity={0.7} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>
              ) : (
                <span className="font-mono text-[11px] text-text-muted">No market data available</span>
              )}
            </div>

            {/* CTA */}
            <a
              href={item.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full py-3 bg-accent hover:bg-accent-hover text-void font-mono text-xs uppercase tracking-wider rounded text-center transition-colors"
            >
              View on {item.source}
              <ExternalLink className="w-3 h-3 inline ml-2" />
            </a>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
