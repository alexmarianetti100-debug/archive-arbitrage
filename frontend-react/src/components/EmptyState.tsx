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
    message: 'Try adjusting your filters to see more results',
  },
  no_data: {
    icon: Package,
    title: 'No items yet',
    message: 'Start by running a scrape to find deals',
  },
  error: {
    icon: AlertCircle,
    title: 'Something went wrong',
    message: 'Failed to load data. Please try again.',
  },
  search: {
    icon: Search,
    title: 'No matches found',
    message: 'Try different search terms or filters',
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
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col items-center justify-center py-16 px-4 text-center"
    >
      {/* Icon */}
      <div className="w-20 h-20 rounded-2xl bg-surface border border-border flex items-center justify-center mb-6">
        {customIcon || <Icon className="w-10 h-10 text-text-muted" />}
      </div>

      {/* Title */}
      <h3 className="text-xl font-semibold text-text-primary mb-2">
        {title}
      </h3>

      {/* Message */}
      <p className="text-sm text-text-secondary max-w-sm mb-6">
        {message}
      </p>

      {/* Action */}
      {action && (
        <button
          onClick={action.onClick}
          className="flex items-center gap-2 px-5 py-2.5 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-lg transition-colors"
        >
          {type === 'error' && <RefreshCw className="w-4 h-4" />}
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
      action={{
        label: 'Clear filters',
        onClick: onClearFilters,
      }}
    />
  );
}

export function EmptyArbitrage() {
  return (
    <EmptyState
      type="no_data"
      title="No arbitrage opportunities"
      message="No cross-platform price gaps found right now. Check back after the next scrape."
    />
  );
}

export function EmptyProducts() {
  return (
    <EmptyState
      type="no_data"
      title="No products catalogued"
      message="Products are extracted from sold comps during qualification. Run a qualification pass to build the catalog."
    />
  );
}

export function LoadingError({ onRetry }: { onRetry: () => void }) {
  return (
    <EmptyState
      type="error"
      action={{
        label: 'Try again',
        onClick: onRetry,
      }}
    />
  );
}
