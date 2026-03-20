import { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { ArrowUpDown, TrendingUp, TrendingDown, Minus, Search } from 'lucide-react';
import { useProducts } from '../hooks/useApi';
import { EmptyProducts } from '../components/EmptyState';

type SortKey = 'total_sales' | 'sales_30d' | 'sales_90d' | 'canonical_name';
type SortDir = 'asc' | 'desc';

const velocityIcon = (trend: string) => {
  switch (trend?.toLowerCase()) {
    case 'accelerating':
    case 'rising':
    case 'up':
      return <TrendingUp className="w-3 h-3 text-signal-green" />;
    case 'declining':
    case 'falling':
    case 'down':
      return <TrendingDown className="w-3 h-3 text-signal-red" />;
    default:
      return <Minus className="w-3 h-3 text-text-muted" />;
  }
};

const velocityColor = (trend: string) => {
  switch (trend?.toLowerCase()) {
    case 'accelerating':
    case 'rising':
    case 'up':
      return 'text-signal-green';
    case 'declining':
    case 'falling':
    case 'down':
      return 'text-signal-red';
    default:
      return 'text-text-muted';
  }
};

export function Products() {
  const { data: products, isLoading } = useProducts();
  const [sortKey, setSortKey] = useState<SortKey>('sales_30d');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [searchQuery, setSearchQuery] = useState('');

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const filtered = useMemo(() => {
    if (!products) return [];
    let result = [...products];

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(p =>
        p.canonical_name?.toLowerCase().includes(q) ||
        p.brand?.toLowerCase().includes(q) ||
        p.model?.toLowerCase().includes(q)
      );
    }

    result.sort((a, b) => {
      const aVal = a[sortKey] ?? 0;
      const bVal = b[sortKey] ?? 0;
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortDir === 'asc' ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
    });

    return result;
  }, [products, sortKey, sortDir, searchQuery]);

  const SortHeader = ({ label, colKey, align = 'left' }: { label: string; colKey: SortKey; align?: string }) => (
    <th
      className={`cursor-pointer hover:text-text-secondary transition-colors ${align === 'right' ? 'text-right' : ''}`}
      onClick={() => handleSort(colKey)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {sortKey === colKey && (
          <ArrowUpDown className="w-2.5 h-2.5 text-accent" />
        )}
      </span>
    </th>
  );

  return (
    <div className="p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-serif text-headline text-text-primary italic">Products</h1>
          <p className="font-mono text-[11px] text-text-muted mt-1 tracking-wide">
            CATALOG &amp; VELOCITY DATA
          </p>
        </div>

        {/* Search */}
        <div className="relative w-64">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
          <input
            type="text"
            placeholder="Search products..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 bg-surface border border-border rounded font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/40"
          />
        </div>
      </div>

      {/* Stats bar */}
      {products && products.length > 0 && (
        <div className="flex items-center gap-4 font-mono text-[10px] text-text-muted">
          <span>{filtered.length} products</span>
          <span className="text-border">|</span>
          <span>{products.filter(p => p.is_high_velocity).length} high velocity</span>
          <span className="text-border">|</span>
          <span>{products.reduce((s, p) => s + (p.total_sales || 0), 0).toLocaleString()} total sales</span>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">
          {[...Array(10)].map((_, i) => (
            <div key={i} className="h-10 bg-surface rounded border border-border animate-skeleton" />
          ))}
        </div>
      ) : !filtered.length ? (
        <EmptyProducts />
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="surface-terminal rounded-lg overflow-hidden relative"
        >
          <div className="overflow-x-auto relative z-10">
            <table className="table-terminal">
              <thead>
                <tr>
                  <SortHeader label="Product" colKey="canonical_name" />
                  <th>Brand</th>
                  <th>Type</th>
                  <SortHeader label="30d Sales" colKey="sales_30d" align="right" />
                  <SortHeader label="90d Sales" colKey="sales_90d" align="right" />
                  <SortHeader label="Total" colKey="total_sales" align="right" />
                  <th className="text-right">Velocity</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((product, i) => (
                  <motion.tr
                    key={product.id || i}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: Math.min(i * 0.02, 0.5) }}
                  >
                    <td>
                      <div className="flex items-center gap-2 max-w-xs">
                        {product.is_high_velocity && (
                          <div className="w-1 h-1 rounded-full bg-signal-green flex-shrink-0" />
                        )}
                        <span className="truncate text-text-primary text-xs font-sans">
                          {product.canonical_name || product.model || '—'}
                        </span>
                      </div>
                    </td>
                    <td>
                      <span className="text-accent text-[10px] uppercase tracking-wider">
                        {product.brand || '—'}
                      </span>
                    </td>
                    <td>
                      <span className="text-text-muted">
                        {product.item_type || '—'}
                      </span>
                    </td>
                    <td className="text-right">
                      <span className={product.sales_30d > 0 ? 'text-text-primary' : 'text-text-muted'}>
                        {product.sales_30d ?? 0}
                      </span>
                    </td>
                    <td className="text-right">
                      <span className={product.sales_90d > 0 ? 'text-text-primary' : 'text-text-muted'}>
                        {product.sales_90d ?? 0}
                      </span>
                    </td>
                    <td className="text-right">
                      <span className="text-text-primary">
                        {product.total_sales?.toLocaleString() ?? 0}
                      </span>
                    </td>
                    <td className="text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {velocityIcon(product.velocity_trend)}
                        <span className={`text-[10px] uppercase tracking-wider ${velocityColor(product.velocity_trend)}`}>
                          {product.velocity_trend || 'stable'}
                        </span>
                      </div>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}
    </div>
  );
}
