import { motion } from 'framer-motion';
import { ExternalLink, TrendingUp, Clock, Package, ArrowUpRight } from 'lucide-react';
import type { Item, ViewMode } from '../types';

interface DealCardProps {
  item: Item;
  view: ViewMode;
}

const gradeStyles = {
  A: 'bg-grade-a/10 text-grade-a border-grade-a/30',
  B: 'bg-grade-b/10 text-grade-b border-grade-b/30',
  C: 'bg-grade-c/10 text-grade-c border-grade-c/30',
  D: 'bg-grade-d/10 text-grade-d border-grade-d/30',
};

export function DealCard({ item, view }: DealCardProps) {
  const profit = item.exact_profit || (item.our_price || 0) - item.source_price - (item.source_shipping || 0);
  const margin = item.exact_margin || item.margin_percent || 0;
  const grade = item.deal_grade || 'D';
  const gradeStyle = gradeStyles[grade as keyof typeof gradeStyles] || gradeStyles.D;

  // List view
  if (view === 'list') {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        whileHover={{ y: -2 }}
        className="bg-surface rounded-xl border border-border hover:border-accent/30 transition-all duration-200 p-4"
      >
        <div className="flex items-center gap-4">
          {/* Image */}
          <div className="w-16 h-16 rounded-lg bg-background flex-shrink-0 overflow-hidden">
            {item.images?.[0] ? (
              <img 
                src={item.images[0]} 
                alt=""
                className="w-full h-full object-cover"
                loading="lazy"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-text-muted">
                <Package className="w-6 h-6" />
              </div>
            )}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-xs font-bold px-2 py-0.5 rounded border ${gradeStyle}`}>
                {grade}
              </span>
              <span className="text-xs text-text-secondary uppercase tracking-wide">
                {item.brand}
              </span>
            </div>
            <h4 className="text-sm font-medium text-text-primary truncate">
              {item.title}
            </h4>
          </div>

          {/* Prices */}
          <div className="text-right hidden sm:block">
            <div className="text-sm text-text-secondary">
              ${item.source_price.toFixed(0)}
            </div>
            <div className="text-sm font-medium text-text-primary">
              → ${item.our_price?.toFixed(0)}
            </div>
          </div>

          {/* Profit */}
          <div className="text-right min-w-[80px]">
            <div className="flex items-center gap-1 text-grade-a font-semibold">
              <TrendingUp className="w-3.5 h-3.5" />
              +${profit.toFixed(0)}
            </div>
            <div className="text-xs text-text-secondary">
              {(margin * 100).toFixed(0)}% margin
            </div>
          </div>

          {/* Action */}
          <a
            href={item.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 text-text-secondary hover:text-accent hover:bg-accent/10 rounded-lg transition-colors"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
      </motion.div>
    );
  }

  // Grid view
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4 }}
      className="group bg-surface rounded-xl border border-border hover:border-accent/30 hover:shadow-lg hover:shadow-accent/5 transition-all duration-200 overflow-hidden"
    >
      {/* Image */}
      <div className="relative aspect-[4/3] bg-background overflow-hidden">
        {item.images?.[0] ? (
          <img
            src={item.images[0]}
            alt={item.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-text-muted">
            <Package className="w-12 h-12" />
          </div>
        )}

        {/* Overlays */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
        
        {/* Grade Badge */}
        <div className="absolute top-3 left-3">
          <span className={`text-xs font-bold px-2 py-1 rounded border ${gradeStyle}`}>
            Grade {grade}
          </span>
        </div>

        {/* Source Badge */}
        <div className="absolute top-3 right-3">
          <span className="text-xs bg-black/60 backdrop-blur text-white px-2 py-1 rounded">
            {item.source}
          </span>
        </div>

        {/* Quick Action on Hover */}
        <a
          href={item.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="absolute bottom-3 right-3 p-2 bg-accent text-white rounded-lg opacity-0 group-hover:opacity-100 translate-y-2 group-hover:translate-y-0 transition-all duration-200 hover:bg-accent-hover"
        >
          <ArrowUpRight className="w-4 h-4" />
        </a>
      </div>

      {/* Content */}
      <div className="p-4">
        {/* Brand */}
        <p className="text-xs text-accent uppercase tracking-wide font-medium mb-1">
          {item.brand}
        </p>

        {/* Title */}
        <h3 className="font-medium text-text-primary line-clamp-2 mb-3 h-10 text-sm">
          {item.title}
        </h3>

        {/* Price Row */}
        <div className="flex items-baseline gap-2 mb-2">
          <span className="text-xl font-bold text-text-primary">
            ${item.source_price.toFixed(0)}
          </span>
          <span className="text-sm text-text-secondary">
            → ${item.our_price?.toFixed(0)}
          </span>
        </div>

        {/* Profit Row */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-1.5 text-grade-a">
            <TrendingUp className="w-4 h-4" />
            <span className="font-semibold">+${profit.toFixed(0)}</span>
          </div>
          <span className="text-xs text-text-secondary">
            {(margin * 100).toFixed(0)}% margin
          </span>
        </div>

        {/* Meta */}
        <div className="flex items-center gap-3 text-xs text-text-secondary pt-3 border-t border-border">
          {item.est_days_to_sell ? (
            <div className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              <span>~{item.est_days_to_sell.toFixed(0)}d to sell</span>
            </div>
          ) : null}
          {item.exact_product_comps ? (
            <div>{item.exact_product_comps} comps</div>
          ) : null}
        </div>

        {/* CTA */}
        <a
          href={item.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 w-full py-2.5 bg-accent/10 hover:bg-accent text-accent hover:text-white border border-accent/30 hover:border-accent font-medium rounded-lg flex items-center justify-center gap-2 transition-all duration-200 text-sm"
        >
          View Deal
          <ExternalLink className="w-3.5 h-3.5" />
        </a>
      </div>
    </motion.div>
  );
}
