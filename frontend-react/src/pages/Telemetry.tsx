import { useMemo } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis } from 'recharts';
import { useTelemetry, useTierSummary, useJapanTelemetry } from '../hooks/useApi';

// ── Colors ──────────────────────────────────────────────────────────────

const TIER_COLORS: Record<string, string> = { A: '#00ff87', B: '#00d4ff', trap: '#4a4a4a' };
const SKIP_COLORS: Record<string, string> = {
  brand_mismatch_skips: '#ff3b30',
  stale_skips: '#ffb700',
  rep_ceiling_skips: '#ff6b00',
  implausible_gap_skips: '#ff3b30',
  low_trust_skips: '#c8ff00',
  validation_failed: '#00d4ff',
  category_mismatch_skips: '#6b6b6b',
};

const SKIP_LABELS: Record<string, string> = {
  brand_mismatch_skips: 'Brand Mismatch',
  category_mismatch_skips: 'Category Mismatch',
  stale_skips: 'Stale Listings',
  rep_ceiling_skips: 'Rep Ceiling',
  implausible_gap_skips: 'Implausible Gap',
  low_trust_skips: 'Low Trust',
  validation_failed: 'Validation Failed',
};

// ── Tooltip ─────────────────────────────────────────────────────────────

function ChartTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="surface-glass rounded px-3 py-2">
      <span className="font-mono text-xs text-text-primary">{d.name}</span>
      <span className="font-mono text-xs text-text-secondary block">{d.value.toLocaleString()}</span>
    </div>
  );
}

// ── Tier Distribution Chart ──────────────────────────────────────────────

function TierDistribution() {
  const { data } = useTierSummary();

  const chartData = useMemo(() => {
    if (!data) return [];
    return [
      { name: 'A-tier', value: data.a_count, fill: TIER_COLORS.A },
      { name: 'B-tier', value: data.b_count, fill: TIER_COLORS.B },
      { name: 'Trap', value: data.trap_count, fill: TIER_COLORS.trap },
    ].filter(d => d.value > 0);
  }, [data]);

  const total = chartData.reduce((s, d) => s + d.value, 0);

  if (!total) {
    return (
      <div className="h-48 flex items-center justify-center">
        <span className="font-mono text-xs text-text-muted">NO TIER DATA</span>
      </div>
    );
  }

  return (
    <div className="h-48 relative">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={chartData} cx="50%" cy="50%" innerRadius={55} outerRadius={75} paddingAngle={3} dataKey="value" strokeWidth={0}>
            {chartData.map((entry) => (
              <Cell key={entry.name} fill={entry.fill} opacity={0.85} />
            ))}
          </Pie>
          <Tooltip content={<ChartTooltip />} />
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <span className="data-value text-xl text-text-primary">{total}</span>
        <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-text-muted">Queries</span>
      </div>
      <div className="absolute bottom-0 left-0 right-0 flex items-center justify-center gap-4">
        {chartData.map((entry) => (
          <div key={entry.name} className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: entry.fill }} />
            <span className="font-mono text-[10px] text-text-secondary">{entry.name}: {entry.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Skip Reasons Chart ───────────────────────────────────────────────────

function SkipReasonsChart({ skipReasons }: { skipReasons: Record<string, number> }) {
  const chartData = useMemo(() => {
    return Object.entries(skipReasons)
      .filter(([, v]) => v > 0)
      .map(([key, value]) => ({
        name: SKIP_LABELS[key] || key,
        value,
        fill: SKIP_COLORS[key] || '#6b6b6b',
      }))
      .sort((a, b) => b.value - a.value);
  }, [skipReasons]);

  if (!chartData.length) {
    return <span className="font-mono text-[11px] text-text-muted">No skip data</span>;
  }

  return (
    <div className="h-40">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 4, left: 0, bottom: 0 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="name"
            width={110}
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 10, fill: '#6b6b6b', fontFamily: 'DM Mono' }}
          />
          <Tooltip content={<ChartTooltip />} />
          <Bar dataKey="value" radius={[0, 2, 2, 0]}>
            {chartData.map((entry) => (
              <Cell key={entry.name} fill={entry.fill} opacity={0.7} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Worst Performers Table ───────────────────────────────────────────────

function WorstPerformers() {
  const { data } = useTelemetry({ min_runs: 5, sort_by: 'deal_rate', order: 'asc' });

  const worst = useMemo(() => {
    if (!data?.queries) return [];
    return data.queries.filter(q => q.total_runs >= 5 && q.deal_rate < 0.05).slice(0, 10);
  }, [data]);

  if (!worst.length) return null;

  return (
    <div className="surface-terminal rounded-lg p-4 relative">
      <div className="relative z-10">
        <h3 className="font-mono text-xs text-text-secondary uppercase tracking-wider mb-3">
          Worst Performing Queries
          <span className="text-text-muted ml-2">(5+ runs, &lt;5% deal rate)</span>
        </h3>
        <div className="space-y-1">
          {worst.map((q) => (
            <div key={q.query} className="flex items-center gap-3 py-1.5 px-2 rounded hover:bg-surface-hover transition-colors">
              <span className="font-mono text-[11px] text-text-primary flex-1 truncate">{q.query}</span>
              <span className="font-mono text-[10px] text-text-muted">{q.total_runs} runs</span>
              <span className="font-mono text-[10px] text-signal-red">{q.total_deals} deals</span>
              <span className={`font-mono text-[10px] ${
                q.junk_ratio >= 0.8 ? 'text-signal-red' :
                q.junk_ratio >= 0.5 ? 'text-signal-amber' : 'text-text-muted'
              }`}>
                {q.junk_ratio > 0 ? `${(q.junk_ratio * 100).toFixed(0)}% junk` : ''}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Pipeline Comparison ──────────────────────────────────────────────────

function PipelineComparison() {
  const { data: enData } = useTelemetry();
  const { data: jpData } = useJapanTelemetry();

  if (!enData || !jpData) return null;

  const en = enData.aggregates;
  const jp = jpData.aggregates;

  const metrics = [
    {
      label: 'Total Queries',
      en: enData.total,
      jp: jpData.total,
    },
    {
      label: 'Total Runs',
      en: en.total_runs,
      jp: jp.total_runs,
    },
    {
      label: 'Total Deals',
      en: en.total_deals,
      jp: jp.total_deals,
    },
    {
      label: 'Avg Deal Rate',
      en: `${(en.avg_deal_rate * 100).toFixed(1)}%`,
      jp: `${(jp.avg_deal_rate * 100).toFixed(1)}%`,
      enRaw: en.avg_deal_rate,
      jpRaw: jp.avg_deal_rate,
    },
  ];

  return (
    <div className="surface-terminal rounded-lg p-4 relative">
      <div className="relative z-10">
        <h3 className="font-mono text-xs text-text-secondary uppercase tracking-wider mb-4">
          Pipeline Comparison
        </h3>
        <div className="grid grid-cols-3 gap-3">
          {/* Header */}
          <div />
          <div className="text-center">
            <span className="font-mono text-[10px] text-signal-blue uppercase tracking-wider">English</span>
          </div>
          <div className="text-center">
            <span className="font-mono text-[10px] text-signal-amber uppercase tracking-wider">Japanese</span>
          </div>

          {/* Rows */}
          {metrics.map((m) => (
            <>
              <div key={`${m.label}-label`} className="font-mono text-[10px] text-text-muted uppercase tracking-wider flex items-center">
                {m.label}
              </div>
              <div key={`${m.label}-en`} className="text-center">
                <span className="data-value text-sm text-text-primary">
                  {typeof m.en === 'number' ? m.en.toLocaleString() : m.en}
                </span>
              </div>
              <div key={`${m.label}-jp`} className="text-center">
                <span className="data-value text-sm text-text-primary">
                  {typeof m.jp === 'number' ? m.jp.toLocaleString() : m.jp}
                </span>
              </div>
            </>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Top Performers ───────────────────────────────────────────────────────

function TopPerformers() {
  const { data } = useTelemetry({ min_runs: 3, sort_by: 'deal_rate', order: 'desc' });

  const top = useMemo(() => {
    if (!data?.queries) return [];
    return data.queries.filter(q => q.tier === 'A').slice(0, 10);
  }, [data]);

  if (!top.length) return null;

  return (
    <div className="surface-terminal rounded-lg p-4 relative">
      <div className="relative z-10">
        <h3 className="font-mono text-xs text-text-secondary uppercase tracking-wider mb-3">
          Top A-Tier Queries
        </h3>
        <div className="space-y-1">
          {top.map((q) => (
            <div key={q.query} className="flex items-center gap-3 py-1.5 px-2 rounded hover:bg-surface-hover transition-colors">
              <span className="grade-badge rounded grade-a">A</span>
              <span className="font-mono text-[11px] text-text-primary flex-1 truncate">{q.query}</span>
              <span className="font-mono text-[10px] text-signal-green">{(q.deal_rate * 100).toFixed(0)}%</span>
              <span className="font-mono text-[10px] text-text-muted">{q.total_deals} deals</span>
              <span className="font-mono text-[10px] text-text-muted">{q.total_runs} runs</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────

export function Telemetry() {
  const { data: telemetry, isLoading } = useTelemetry();

  if (isLoading) {
    return (
      <div className="p-6 lg:p-8">
        <div className="space-y-6">
          <div className="h-6 w-48 bg-surface rounded animate-skeleton" />
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 bg-surface rounded-lg border border-border animate-skeleton" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  const agg = telemetry?.aggregates;

  return (
    <div className="p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div>
        <h1 className="font-serif text-headline text-text-primary italic">Telemetry</h1>
        <p className="font-mono text-[11px] text-text-muted mt-1 tracking-wide">
          QUERY PERFORMANCE &amp; PIPELINE INTELLIGENCE
        </p>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-surface rounded-lg border border-border p-4">
          <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted block mb-2">Total Runs</span>
          <span className="data-value text-2xl text-text-primary">{agg?.total_runs?.toLocaleString() || 0}</span>
        </div>
        <div className="bg-surface rounded-lg border border-border p-4">
          <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted block mb-2">Total Deals</span>
          <span className="data-value text-2xl text-signal-green">{agg?.total_deals?.toLocaleString() || 0}</span>
        </div>
        <div className="bg-surface rounded-lg border border-border p-4">
          <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted block mb-2">Avg Deal Rate</span>
          <span className="data-value text-2xl text-text-primary">{agg ? `${(agg.avg_deal_rate * 100).toFixed(1)}%` : '—'}</span>
        </div>
        <div className="bg-surface rounded-lg border border-border p-4">
          <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted block mb-2">Avg Junk Ratio</span>
          <span className={`data-value text-2xl ${
            (agg?.avg_junk_ratio || 0) >= 0.5 ? 'text-signal-red' :
            (agg?.avg_junk_ratio || 0) >= 0.3 ? 'text-signal-amber' : 'text-text-primary'
          }`}>
            {agg ? `${(agg.avg_junk_ratio * 100).toFixed(1)}%` : '—'}
          </span>
        </div>
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div className="surface-terminal rounded-lg p-5 relative">
          <h3 className="font-mono text-xs text-text-secondary uppercase tracking-wider mb-4 relative z-10">
            Tier Distribution
          </h3>
          <div className="relative z-10">
            <TierDistribution />
          </div>
        </div>

        <div className="surface-terminal rounded-lg p-5 relative">
          <h3 className="font-mono text-xs text-text-secondary uppercase tracking-wider mb-4 relative z-10">
            Skip Reasons (All Time)
          </h3>
          <div className="relative z-10">
            {agg?.skip_reasons ? (
              <SkipReasonsChart skipReasons={agg.skip_reasons} />
            ) : (
              <span className="font-mono text-[11px] text-text-muted">No skip data</span>
            )}
          </div>
        </div>
      </div>

      {/* Top & worst performers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <TopPerformers />
        <WorstPerformers />
      </div>

      {/* Pipeline comparison */}
      <PipelineComparison />
    </div>
  );
}
