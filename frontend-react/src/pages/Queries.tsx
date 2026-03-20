import { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Search, ArrowUpDown, ChevronUp, ChevronDown, Ban } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { useQueries, useTierSummary, useJapanTargets } from '../hooks/useApi';
import { updateQueryTier } from '../utils/api';

// ── Tier Badge ──────────────────────────────────────────────────────────

function TierBadge({ tier }: { tier: string }) {
  const styles: Record<string, string> = {
    A: 'grade-a',
    B: 'grade-b',
    trap: 'grade-d',
  };
  return <span className={`grade-badge rounded ${styles[tier] || styles.B}`}>{tier === 'trap' ? 'T' : tier}</span>;
}

// ── Tabs ─────────────────────────────────────────────────────────────────

type Tab = 'english' | 'japan' | 'performance';

function TabBar({ value, onChange }: { value: Tab; onChange: (t: Tab) => void }) {
  const tabs: { value: Tab; label: string }[] = [
    { value: 'english', label: 'English Queries' },
    { value: 'japan', label: 'Japanese Targets' },
    { value: 'performance', label: 'Performance' },
  ];

  return (
    <div className="flex items-center gap-0.5 bg-surface rounded-lg p-0.5 border border-border">
      {tabs.map((tab) => {
        const isActive = value === tab.value;
        return (
          <button
            key={tab.value}
            onClick={() => onChange(tab.value)}
            className={`relative px-3 py-1.5 font-mono text-[11px] rounded transition-all ${
              isActive ? 'text-void' : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {isActive && (
              <motion.div
                layoutId="queryTabActive"
                className="absolute inset-0 bg-accent rounded"
                transition={{ type: 'spring', bounce: 0.15, duration: 0.5 }}
              />
            )}
            <span className="relative z-10">{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}

// ── Summary Bar ──────────────────────────────────────────────────────────

function SummaryBar() {
  const { data } = useTierSummary();
  if (!data) return null;

  return (
    <div className="flex flex-wrap items-center gap-3 font-mono text-[10px]">
      <div className="flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-grade-a" />
        <span className="text-grade-a">{data.a_count} A-tier</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-grade-b" />
        <span className="text-grade-b">{data.b_count} B-tier</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-grade-d" />
        <span className="text-text-muted">{data.trap_count} traps</span>
      </div>
      <span className="text-border">|</span>
      <span className="text-text-muted">{data.total_queries} tracked</span>
      <span className="text-text-muted">{data.promoted_count} promoted</span>
      <span className="text-text-muted">{data.demoted_count} demoted</span>
    </div>
  );
}

// ── English Queries Table ────────────────────────────────────────────────

type SortKey = 'query' | 'tier' | 'total_runs' | 'total_deals' | 'deal_rate' | 'best_gap' | 'junk_ratio';

function EnglishQueriesTab() {
  const { data, isLoading } = useQueries();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('deal_rate');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [tierFilter, setTierFilter] = useState<string>('');

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  const handleTierAction = async (query: string, action: 'promote' | 'demote') => {
    await updateQueryTier(query, action);
    queryClient.invalidateQueries({ queryKey: ['queries'] });
    queryClient.invalidateQueries({ queryKey: ['tier-summary'] });
  };

  const filtered = useMemo(() => {
    if (!data?.queries) return [];
    let result = [...data.queries];

    if (search) {
      const q = search.toLowerCase();
      result = result.filter((r) => r.query.toLowerCase().includes(q));
    }
    if (tierFilter) {
      result = result.filter((r) => r.tier === tierFilter);
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
  }, [data, search, tierFilter, sortKey, sortDir]);

  const SortHeader = ({ label, colKey, align = 'left' }: { label: string; colKey: SortKey; align?: string }) => (
    <th
      className={`cursor-pointer hover:text-text-secondary transition-colors ${align === 'right' ? 'text-right' : ''}`}
      onClick={() => handleSort(colKey)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {sortKey === colKey && <ArrowUpDown className="w-2.5 h-2.5 text-accent" />}
      </span>
    </th>
  );

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="h-10 bg-surface rounded border border-border animate-skeleton" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
          <input
            type="text"
            placeholder="Search queries..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 bg-surface border border-border rounded font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/40"
          />
        </div>

        <div className="flex gap-1">
          {['', 'A', 'B', 'trap'].map((t) => (
            <button
              key={t}
              onClick={() => setTierFilter(t)}
              className={`px-2.5 py-1 rounded font-mono text-[11px] border transition-all ${
                tierFilter === t
                  ? 'bg-accent/10 border-accent/30 text-accent'
                  : 'bg-surface border-border text-text-muted hover:border-border-strong'
              }`}
            >
              {t || 'All'}
            </button>
          ))}
        </div>

        <span className="font-mono text-[10px] text-text-muted ml-auto">{filtered.length} queries</span>
      </div>

      {/* Table */}
      <div className="surface-terminal rounded-lg overflow-hidden relative">
        <div className="overflow-x-auto relative z-10">
          <table className="table-terminal">
            <thead>
              <tr>
                <SortHeader label="Query" colKey="query" />
                <th>Tier</th>
                <SortHeader label="Runs" colKey="total_runs" align="right" />
                <SortHeader label="Deals" colKey="total_deals" align="right" />
                <SortHeader label="Rate" colKey="deal_rate" align="right" />
                <SortHeader label="Gap" colKey="best_gap" align="right" />
                <SortHeader label="Junk" colKey="junk_ratio" align="right" />
                <th>Status</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((q) => (
                <tr key={q.query}>
                  <td>
                    <span className="text-text-primary text-xs">{q.query}</span>
                  </td>
                  <td><TierBadge tier={q.tier} /></td>
                  <td className="text-right">{q.total_runs}</td>
                  <td className="text-right">
                    <span className={q.total_deals > 0 ? 'text-signal-green' : 'text-text-muted'}>
                      {q.total_deals}
                    </span>
                  </td>
                  <td className="text-right">
                    <span className={
                      q.deal_rate >= 0.30 ? 'text-signal-green' :
                      q.deal_rate > 0 ? 'text-text-primary' : 'text-text-muted'
                    }>
                      {(q.deal_rate * 100).toFixed(0)}%
                    </span>
                  </td>
                  <td className="text-right">
                    <span className={q.best_gap >= 0.50 ? 'text-signal-green' : 'text-text-muted'}>
                      {q.best_gap > 0 ? `${(q.best_gap * 100).toFixed(0)}%` : '—'}
                    </span>
                  </td>
                  <td className="text-right">
                    <span className={
                      q.junk_ratio >= 0.80 ? 'text-signal-red' :
                      q.junk_ratio >= 0.50 ? 'text-signal-amber' : 'text-text-muted'
                    }>
                      {q.junk_ratio > 0 ? `${(q.junk_ratio * 100).toFixed(0)}%` : '—'}
                    </span>
                  </td>
                  <td>
                    <div className="flex items-center gap-1">
                      {q.promoted && <span className="font-mono text-[9px] text-signal-green uppercase">PRO</span>}
                      {q.demoted && <span className="font-mono text-[9px] text-signal-red uppercase">DEM</span>}
                    </div>
                  </td>
                  <td className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      {q.tier !== 'A' && (
                        <button
                          onClick={() => handleTierAction(q.query, 'promote')}
                          className="p-1 rounded hover:bg-signal-green/10 text-text-muted hover:text-signal-green transition-colors"
                          title="Promote to A-tier"
                        >
                          <ChevronUp className="w-3.5 h-3.5" />
                        </button>
                      )}
                      {q.tier !== 'trap' && (
                        <button
                          onClick={() => handleTierAction(q.query, 'demote')}
                          className="p-1 rounded hover:bg-signal-red/10 text-text-muted hover:text-signal-red transition-colors"
                          title="Demote to trap"
                        >
                          <ChevronDown className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ── Japan Targets Tab ─────────────────────────────────────────────────────

function JapanTargetsTab() {
  const { data, isLoading } = useJapanTargets();
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    if (!data?.targets) return [];
    if (!search) return data.targets;
    const q = search.toLowerCase();
    return data.targets.filter(
      (t) => t.jp.includes(q) || t.en.toLowerCase().includes(q) || t.brand.toLowerCase().includes(q)
    );
  }, [data, search]);

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-10 bg-surface rounded border border-border animate-skeleton" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
          <input
            type="text"
            placeholder="Search JP or EN..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 bg-surface border border-border rounded font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/40"
          />
        </div>
        <span className="font-mono text-[10px] text-text-muted ml-auto">{filtered.length} targets</span>
      </div>

      <div className="surface-terminal rounded-lg overflow-hidden relative">
        <div className="overflow-x-auto relative z-10">
          <table className="table-terminal">
            <thead>
              <tr>
                <th>Japanese Query</th>
                <th>English Mapping</th>
                <th>Brand</th>
                <th>Category</th>
                <th>EN Tier</th>
                <th className="text-right">JP Runs</th>
                <th className="text-right">JP Deals</th>
                <th className="text-right">Weight</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => (
                <tr key={`${t.jp}-${t.en}`}>
                  <td>
                    <span className="text-text-primary text-xs">{t.jp}</span>
                  </td>
                  <td>
                    <span className="text-text-secondary text-xs">{t.en}</span>
                  </td>
                  <td>
                    <span className="text-accent text-[10px] uppercase tracking-wider">{t.brand}</span>
                  </td>
                  <td>
                    <span className="text-text-muted text-[10px]">{t.category}</span>
                  </td>
                  <td><TierBadge tier={t.en_tier} /></td>
                  <td className="text-right">{t.jp_total_runs || '—'}</td>
                  <td className="text-right">
                    <span className={t.jp_total_deals > 0 ? 'text-signal-green' : 'text-text-muted'}>
                      {t.jp_total_deals || '—'}
                    </span>
                  </td>
                  <td className="text-right">
                    <span className="text-text-secondary">{t.weight}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ── Performance Tab ──────────────────────────────────────────────────────

function PerformanceTab() {
  const { data, isLoading } = useQueries();
  const [search, setSearch] = useState('');
  const [showUnderperforming, setShowUnderperforming] = useState(false);

  const filtered = useMemo(() => {
    if (!data?.queries) return [];
    let result = [...data.queries];

    if (search) {
      const q = search.toLowerCase();
      result = result.filter((r) => r.query.toLowerCase().includes(q));
    }

    if (showUnderperforming) {
      result = result.filter((r) => r.total_runs >= 5 && r.deal_rate < 0.05);
    }

    // Sort by runs desc for performance view
    result.sort((a, b) => b.total_runs - a.total_runs);

    return result;
  }, [data, search, showUnderperforming]);

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="h-10 bg-surface rounded border border-border animate-skeleton" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
          <input
            type="text"
            placeholder="Search queries..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 bg-surface border border-border rounded font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/40"
          />
        </div>

        <button
          onClick={() => setShowUnderperforming(!showUnderperforming)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded border font-mono text-[11px] transition-all ${
            showUnderperforming
              ? 'bg-signal-red/10 border-signal-red/30 text-signal-red'
              : 'bg-surface border-border text-text-muted hover:border-border-strong'
          }`}
        >
          <Ban className="w-3 h-3" />
          Underperforming
        </button>

        <span className="font-mono text-[10px] text-text-muted ml-auto">{filtered.length} queries</span>
      </div>

      <div className="surface-terminal rounded-lg overflow-hidden relative">
        <div className="overflow-x-auto relative z-10">
          <table className="table-terminal">
            <thead>
              <tr>
                <th>Query</th>
                <th>Tier</th>
                <th className="text-right">Runs</th>
                <th className="text-right">Deals</th>
                <th className="text-right">Rate</th>
                <th className="text-right">Gap</th>
                <th className="text-right">Junk</th>
                <th className="text-right">Raw Found</th>
                <th className="text-right">Post-Filter</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((q) => (
                <tr key={q.query}>
                  <td><span className="text-text-primary text-xs">{q.query}</span></td>
                  <td><TierBadge tier={q.tier} /></td>
                  <td className="text-right">{q.total_runs}</td>
                  <td className="text-right">
                    <span className={q.total_deals > 0 ? 'text-signal-green' : 'text-text-muted'}>
                      {q.total_deals}
                    </span>
                  </td>
                  <td className="text-right">
                    <span className={
                      q.deal_rate >= 0.30 ? 'text-signal-green' :
                      q.deal_rate > 0 ? 'text-text-primary' : 'text-text-muted'
                    }>
                      {(q.deal_rate * 100).toFixed(1)}%
                    </span>
                  </td>
                  <td className="text-right">
                    {q.best_gap > 0 ? `${(q.best_gap * 100).toFixed(0)}%` : '—'}
                  </td>
                  <td className="text-right">
                    <span className={
                      q.junk_ratio >= 0.80 ? 'text-signal-red' :
                      q.junk_ratio >= 0.50 ? 'text-signal-amber' : 'text-text-muted'
                    }>
                      {q.junk_ratio > 0 ? `${(q.junk_ratio * 100).toFixed(0)}%` : '—'}
                    </span>
                  </td>
                  <td className="text-right text-text-muted">{q.raw_items_found || '—'}</td>
                  <td className="text-right text-text-muted">{q.post_filter_candidates || '—'}</td>
                  <td>
                    <span className="font-mono text-[10px] text-text-muted">{q.reason}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────

export function Queries() {
  const [activeTab, setActiveTab] = useState<Tab>('english');

  return (
    <div className="p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="font-serif text-headline text-text-primary italic">Queries</h1>
          <p className="font-mono text-[11px] text-text-muted mt-1 tracking-wide">
            MANAGE ENGLISH &amp; JAPANESE SEARCH TARGETS
          </p>
        </div>
        <TabBar value={activeTab} onChange={setActiveTab} />
      </div>

      {/* Summary */}
      <SummaryBar />

      {/* Tab content */}
      {activeTab === 'english' && <EnglishQueriesTab />}
      {activeTab === 'japan' && <JapanTargetsTab />}
      {activeTab === 'performance' && <PerformanceTab />}
    </div>
  );
}
