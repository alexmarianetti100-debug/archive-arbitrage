import { motion } from 'framer-motion';
import { ExternalLink, TrendingUp, Clock, Package, ArrowUpRight } from 'lucide-react';
import type { Item, ViewMode } from '../types';

interface DealCardProps {
  item: Item;
  view: ViewMode;
  onClick?: (item: Item) => void;
}

const gradeClass: Record<string, string> = {
  A: 'grade-a',
  B: 'grade-b',
  C: 'grade-c',
  D: 'grade-d',
};

export function DealCard({ item, view, onClick }: DealCardProps) {
  const buyPrice = item.original_price || 0;
  const sellPrice = item.price || item.market_price || 0;
  const profit = item.exact_profit || (sellPrice - buyPrice);
  // exact_margin is a decimal (e.g., 0.35), margin_percent may be either
  // decimal or already a percentage — normalize to 0-1 range
  const rawMargin = item.exact_margin ?? item.margin_percent ?? 0;
  const margin = rawMargin > 1 ? rawMargin / 100 : rawMargin;
  const grade = item.deal_grade || 'D';
  const gc = gradeClass[grade] || gradeClass.D;
  const hasPricing = buyPrice > 0 && sellPrice > 0 && profit > 0;

  // List view
  if (view === 'list') {
    return (
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        onClick={() => onClick?.(item)}
        className="group bg-surface rounded-lg border border-border hover:border-border-strong transition-all p-3 cursor-pointer"
      >
        <div className="flex items-center gap-3">
          {/* Image */}
          <div className="w-12 h-12 rounded bg-void flex-shrink-0 overflow-hidden">
            {item.images?.[0] ? (
              <img src={item.images[0]} alt="" className="w-full h-full object-cover" loading="lazy" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <Package className="w-4 h-4 text-text-muted" />
              </div>
            )}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              {item.deal_grade && (
                <span className={`grade-badge rounded ${gc}`}>{grade}</span>
              )}
              <span className="font-mono text-[10px] text-text-muted uppercase tracking-wider">
                {item.brand || item.source}
              </span>
            </div>
            <h4 className="text-xs text-text-primary truncate">{item.title}</h4>
          </div>

          {/* Prices */}
          <div className="text-right hidden sm:block">
            <span className="font-mono text-xs text-text-muted">${buyPrice.toFixed(0)}</span>
            {hasPricing && (
              <>
                <span className="font-mono text-xs text-text-secondary mx-1.5">&rarr;</span>
                <span className="font-mono text-xs text-text-primary">${sellPrice.toFixed(0)}</span>
              </>
            )}
          </div>

          {/* Profit */}
          {hasPricing && (
            <div className="text-right min-w-[70px]">
              <div className="flex items-center gap-1 text-signal-green data-value text-sm">
                <TrendingUp className="w-3 h-3" />
                +${profit.toFixed(0)}
              </div>
              <span className="font-mono text-[10px] text-text-muted">
                {(margin * 100).toFixed(0)}%
              </span>
            </div>
          )}

          {/* Action */}
          <a
            href={item.source_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="p-1.5 text-text-muted hover:text-accent rounded transition-colors"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </motion.div>
    );
  }

  // Grid view
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      onClick={() => onClick?.(item)}
      className="group bg-surface rounded-lg border border-border hover:border-border-strong transition-all overflow-hidden cursor-pointer"
    >
      {/* Image */}
      <div className="relative aspect-[4/3] bg-void overflow-hidden">
        {item.images?.[0] ? (
          <img
            src={item.images[0]}
            alt={item.title}
            className="w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-500"
            loading="lazy"
            onError={(e) => { e.currentTarget.style.display = 'none'; }}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Package className="w-10 h-10 text-text-muted" />
          </div>
        )}

        {/* Gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

        {/* Grade Badge */}
        {item.deal_grade && (
          <div className="absolute top-2.5 left-2.5">
            <span className={`grade-badge rounded ${gc}`}>{grade}</span>
          </div>
        )}

        {/* Source */}
        <div className="absolute top-2.5 right-2.5">
          <span className="platform-badge rounded">{item.source}</span>
        </div>

        {/* Needs Review Badge */}
        {item.needs_review && (
          <span className={`absolute left-2 px-1.5 py-0.5 bg-signal-amber/90 text-void rounded font-mono text-[9px] font-medium uppercase z-10 ${item.deal_grade ? 'top-10' : 'top-2'}`}>
            Review
          </span>
        )}

        {/* Quick action */}
        <a
          href={item.source_url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="absolute bottom-2.5 right-2.5 p-1.5 bg-accent text-void rounded opacity-0 group-hover:opacity-100 translate-y-1 group-hover:translate-y-0 transition-all duration-200 hover:bg-accent-hover"
        >
          <ArrowUpRight className="w-3.5 h-3.5" />
        </a>
      </div>

      {/* Content */}
      <div className="p-3.5">
        {/* Brand */}
        <p className="font-mono text-[10px] text-accent uppercase tracking-[0.1em] mb-1">
          {item.brand || item.source}
        </p>

        {/* Title */}
        <h3 className="text-xs text-text-primary line-clamp-2 mb-3 h-8 leading-relaxed">
          {item.title}
        </h3>

        {/* Price Row */}
        <div className="flex items-baseline gap-2 mb-2">
          <span className="data-value text-lg text-text-primary">
            ${buyPrice.toFixed(0)}
          </span>
          {hasPricing && (
            <span className="font-mono text-[10px] text-text-muted">
              &rarr; ${sellPrice.toFixed(0)}
            </span>
          )}
        </div>

        {/* Profit Row */}
        {hasPricing && (
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-1.5 text-signal-green">
              <TrendingUp className="w-3.5 h-3.5" />
              <span className="data-value text-sm">+${profit.toFixed(0)}</span>
            </div>
            <span className="font-mono text-[10px] text-text-muted">
              {(margin * 100).toFixed(0)}% margin
            </span>
          </div>
        )}

        {/* Meta */}
        <div className="flex items-center gap-3 font-mono text-[10px] text-text-muted pt-2.5 border-t border-border">
          {item.est_days_to_sell && item.est_days_to_sell < 365 ? (
            <div className="flex items-center gap-1">
              <Clock className="w-2.5 h-2.5" />
              <span>~{item.est_days_to_sell.toFixed(0)}d</span>
            </div>
          ) : null}
          {item.comp_count ? (
            <span>{item.comp_count} comps</span>
          ) : null}
          {item.sold_count ? (
            <span>{item.sold_count} sold</span>
          ) : null}
          {item.size && (
            <span>sz {item.size}</span>
          )}
        </div>

        {/* CTA */}
        <a
          href={item.source_url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="mt-3 w-full py-2 bg-accent/5 hover:bg-accent text-accent hover:text-void border border-accent/15 hover:border-accent font-mono text-[11px] uppercase tracking-wider rounded flex items-center justify-center gap-2 transition-all duration-200"
        >
          View Deal
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </motion.div>
  );
}
