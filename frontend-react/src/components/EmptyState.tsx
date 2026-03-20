import { motion } from 'framer-motion';
import { Package, Search, Filter, AlertCircle, RefreshCw } from 'lucide-react';

interface EmptyStateProps {
  type?: 'no_results' | 'no_data' | 'error' | 'search';
  title?: string;
  message?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  icon?: React.ReactNode;
}

const defaultConfigs = {
  no_results: {
    icon: Filter,
    title: 'No deals found',
    message: 'Adjust filters to surface more results',
  },
  no_data: {
    icon: Package,
    title: 'No items yet',
    message: 'Run a scrape cycle to populate the pipeline',
  },
  error: {
    icon: AlertCircle,
    title: 'Connection error',
    message: 'Failed to reach the API. Check backend status.',
  },
  search: {
    icon: Search,
    title: 'No matches',
    message: 'Try different search terms or broaden filters',
  },
};

export function EmptyState({
  type = 'no_results',
  title: customTitle,
  message: customMessage,
  action,
  icon: customIcon,
}: EmptyStateProps) {
  const config = defaultConfigs[type];
  const Icon = config.icon;
  const title = customTitle || config.title;
  const message = customMessage || config.message;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col items-center justify-center py-16 px-4 text-center"
    >
      <div className="w-14 h-14 rounded-lg bg-surface border border-border flex items-center justify-center mb-5">
        {customIcon || <Icon className="w-6 h-6 text-text-muted" />}
      </div>

      <h3 className="text-sm font-medium text-text-primary mb-1.5">{title}</h3>
      <p className="font-mono text-[11px] text-text-muted max-w-xs mb-5">{message}</p>

      {action && (
        <button
          onClick={action.onClick}
          className="flex items-center gap-1.5 px-4 py-2 bg-accent hover:bg-accent-hover text-void font-mono text-[11px] uppercase tracking-wider rounded transition-colors"
        >
          {type === 'error' && <RefreshCw className="w-3 h-3" />}
          {action.label}
        </button>
      )}
    </motion.div>
  );
}

export function EmptyDeals({ onClearFilters }: { onClearFilters: () => void }) {
  return (
    <EmptyState
      type="no_results"
      action={{ label: 'Clear filters', onClick: onClearFilters }}
    />
  );
}

export function EmptyArbitrage() {
  return (
    <EmptyState
      type="no_data"
      title="No arbitrage opportunities"
      message="No cross-platform gaps detected. Check back after the next scrape cycle."
    />
  );
}

export function EmptyProducts() {
  return (
    <EmptyState
      type="no_data"
      title="No products catalogued"
      message="Products are built from sold comps during qualification. Run a qualification pass."
    />
  );
}

export function LoadingError({ onRetry }: { onRetry: () => void }) {
  return (
    <EmptyState
      type="error"
      action={{ label: 'Retry', onClick: onRetry }}
    />
  );
}
