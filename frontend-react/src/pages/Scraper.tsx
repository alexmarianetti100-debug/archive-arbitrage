import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Play, Square, Loader2, CheckCircle2, XCircle, AlertTriangle,
  Clock, Zap, ChevronDown, ChevronUp, Settings2,
} from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { useScrapeStatus, useScrapeHistory } from '../hooks/useApi';
import { useSSE, type SSEEvent } from '../hooks/useSSE';
import { startScrape, stopScrape, type ScrapeStartConfig, type ScrapeRunSummary } from '../utils/api';

// ── Scrape Config Form ──────────────────────────────────────────────────

interface ScrapeConfigProps {
  onStart: (config: ScrapeStartConfig) => void;
  disabled: boolean;
}

function ScrapeConfig({ onStart, disabled }: ScrapeConfigProps) {
  const [mode, setMode] = useState<'gap_hunter' | 'full_scrape'>('gap_hunter');
  const [querySource, setQuerySource] = useState('trend_engine');
  const [customQueries, setCustomQueries] = useState('');
  const [maxTargets, setMaxTargets] = useState(20);
  const [maxPerQuery, setMaxPerQuery] = useState(15);
  const [minMargin, setMinMargin] = useState(25);
  const [minProfit, setMinProfit] = useState(50);
  const [skipAuth, setSkipAuth] = useState(false);
  const [skipJapan, setSkipJapan] = useState(false);
  const [dryRun, setDryRun] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleSubmit = () => {
    const config: ScrapeStartConfig = {
      mode,
      query_source: querySource,
      max_results_per_query: maxPerQuery,
      min_margin: minMargin / 100,
      min_profit: minProfit,
      skip_auth: skipAuth,
      dry_run: dryRun,
      skip_japan: skipJapan,
      max_targets: maxTargets,
    };
    if (querySource === 'custom' && customQueries.trim()) {
      config.custom_queries = customQueries.split(',').map((q) => q.trim()).filter(Boolean);
    }
    onStart(config);
  };

  const inputClass = "w-full px-3 py-1.5 bg-void border border-border rounded font-mono text-xs text-text-primary focus:outline-none focus:border-accent/40";
  const labelClass = "font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted mb-1 block";

  return (
    <div className="surface-terminal rounded-lg relative">
      <div className="p-5 relative z-10 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-mono text-xs text-text-secondary uppercase tracking-wider">Run Configuration</h3>
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-1 font-mono text-[10px] text-text-muted hover:text-text-secondary transition-colors"
          >
            <Settings2 className="w-3 h-3" />
            {showAdvanced ? 'Less' : 'More'}
            {showAdvanced ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
        </div>

        {/* Row 1: Mode + Query Source */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Scrape Mode</label>
            <div className="flex gap-2">
              <button
                onClick={() => setMode('gap_hunter')}
                className={`flex-1 py-2 rounded font-mono text-[11px] border transition-all ${
                  mode === 'gap_hunter'
                    ? 'bg-accent/10 border-accent/30 text-accent'
                    : 'bg-surface border-border text-text-secondary hover:border-border-strong'
                }`}
              >
                Gap Hunter
              </button>
              <button
                onClick={() => setMode('full_scrape')}
                className={`flex-1 py-2 rounded font-mono text-[11px] border transition-all ${
                  mode === 'full_scrape'
                    ? 'bg-accent/10 border-accent/30 text-accent'
                    : 'bg-surface border-border text-text-secondary hover:border-border-strong'
                }`}
              >
                Full Scrape
              </button>
            </div>
          </div>

          <div>
            <label className={labelClass}>Query Source</label>
            <select
              value={querySource}
              onChange={(e) => setQuerySource(e.target.value)}
              className={inputClass}
            >
              <option value="trend_engine">TrendEngine (dynamic)</option>
              <option value="japan">Japanese Targets</option>
              <option value="custom">Custom Queries</option>
            </select>
          </div>
        </div>

        {/* Custom queries input */}
        {querySource === 'custom' && (
          <div>
            <label className={labelClass}>Custom Queries (comma-separated)</label>
            <input
              type="text"
              value={customQueries}
              onChange={(e) => setCustomQueries(e.target.value)}
              placeholder="rick owens geobasket, raf simons riot bomber, chrome hearts ring"
              className={inputClass}
            />
          </div>
        )}

        {/* Row 2: Targets + Per Query */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div>
            <label className={labelClass}>Max Targets</label>
            <input type="number" value={maxTargets} onChange={(e) => setMaxTargets(Number(e.target.value))} min={1} max={100} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Per Query</label>
            <input type="number" value={maxPerQuery} onChange={(e) => setMaxPerQuery(Number(e.target.value))} min={5} max={50} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Min Margin %</label>
            <input type="number" value={minMargin} onChange={(e) => setMinMargin(Number(e.target.value))} min={5} max={80} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Min Profit $</label>
            <input type="number" value={minProfit} onChange={(e) => setMinProfit(Number(e.target.value))} min={10} max={1000} className={inputClass} />
          </div>
        </div>

        {/* Advanced toggles */}
        <AnimatePresence>
          {showAdvanced && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="flex flex-wrap gap-4 pt-2">
                {[
                  { label: 'Skip Auth', value: skipAuth, set: setSkipAuth },
                  { label: 'Skip Japan', value: skipJapan, set: setSkipJapan },
                  { label: 'Dry Run', value: dryRun, set: setDryRun },
                ].map((toggle) => (
                  <button
                    key={toggle.label}
                    onClick={() => toggle.set(!toggle.value)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded border font-mono text-[11px] transition-all ${
                      toggle.value
                        ? 'bg-signal-amber/10 border-signal-amber/30 text-signal-amber'
                        : 'bg-surface border-border text-text-muted hover:border-border-strong'
                    }`}
                  >
                    <div className={`w-2 h-2 rounded-full transition-colors ${toggle.value ? 'bg-signal-amber' : 'bg-text-muted'}`} />
                    {toggle.label}
                  </button>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Run button */}
        <button
          onClick={handleSubmit}
          disabled={disabled}
          className="w-full py-3 bg-accent hover:bg-accent-hover disabled:bg-accent/20 disabled:cursor-not-allowed text-void font-mono text-xs uppercase tracking-wider rounded flex items-center justify-center gap-2 transition-colors"
        >
          {disabled ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Scrape Running...
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5" />
              Run Scrape
            </>
          )}
        </button>
      </div>
    </div>
  );
}

// ── Event Feed ──────────────────────────────────────────────────────────

function eventIcon(type: string) {
  switch (type) {
    case 'scrape:started': return <Play className="w-3 h-3 text-signal-blue" />;
    case 'scrape:progress': return <Loader2 className="w-3 h-3 text-signal-amber animate-spin" />;
    case 'scrape:deal_found': return <Zap className="w-3 h-3 text-signal-green" />;
    case 'scrape:complete': return <CheckCircle2 className="w-3 h-3 text-signal-green" />;
    case 'scrape:error': return <XCircle className="w-3 h-3 text-signal-red" />;
    case 'scrape:cancelled': return <AlertTriangle className="w-3 h-3 text-signal-amber" />;
    default: return <Clock className="w-3 h-3 text-text-muted" />;
  }
}

function eventMessage(event: SSEEvent): string {
  const d = event.data;
  switch (event.type) {
    case 'scrape:started': return `Scrape started — mode: ${d.mode || 'unknown'}`;
    case 'scrape:progress': return String(d.message || d.phase || 'Processing...');
    case 'scrape:deal_found': return `Deal #${d.deal_number}: ${d.brand} — ${d.title} ($${d.price})`;
    case 'scrape:complete': {
      const stats = d.stats as Record<string, number> | undefined;
      const dur = d.duration_seconds;
      return `Complete — ${stats?.deals_found ?? 0} deals found in ${dur ? `${dur}s` : '?'}`;
    }
    case 'scrape:error': return `Error: ${d.error || 'Unknown error'}`;
    case 'scrape:cancelled': return 'Scrape cancelled';
    default: return event.type;
  }
}

function EventFeed({ events, connected }: { events: SSEEvent[]; connected: boolean }) {
  if (events.length === 0 && !connected) return null;

  return (
    <div className="surface-terminal rounded-lg relative">
      <div className="p-4 relative z-10">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-mono text-xs text-text-secondary uppercase tracking-wider">Live Feed</h3>
          {connected && (
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-signal-green animate-pulse-slow" />
              <span className="font-mono text-[10px] text-signal-green">STREAMING</span>
            </div>
          )}
        </div>

        <div className="space-y-1.5 max-h-80 overflow-y-auto">
          {events.map((event, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              className={`flex items-start gap-2.5 py-1.5 px-2 rounded ${
                event.type === 'scrape:deal_found' ? 'bg-signal-green/5' :
                event.type === 'scrape:error' ? 'bg-signal-red/5' : ''
              }`}
            >
              <div className="mt-0.5 flex-shrink-0">{eventIcon(event.type)}</div>
              <span className="font-mono text-[11px] text-text-primary flex-1">
                {eventMessage(event)}
              </span>
              <span className="font-mono text-[9px] text-text-muted flex-shrink-0">
                {new Date(event.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Run History ──────────────────────────────────────────────────────────

function statusBadge(status: string) {
  switch (status) {
    case 'running': return <span className="font-mono text-[10px] text-signal-amber uppercase tracking-wider">Running</span>;
    case 'completed': return <span className="font-mono text-[10px] text-signal-green uppercase tracking-wider">Done</span>;
    case 'failed': return <span className="font-mono text-[10px] text-signal-red uppercase tracking-wider">Failed</span>;
    case 'cancelled': return <span className="font-mono text-[10px] text-text-muted uppercase tracking-wider">Stopped</span>;
    default: return <span className="font-mono text-[10px] text-text-muted uppercase tracking-wider">{status}</span>;
  }
}

function RunHistory({ runs }: { runs: ScrapeRunSummary[] }) {
  if (!runs.length) return null;

  return (
    <div className="surface-terminal rounded-lg relative">
      <div className="p-4 relative z-10">
        <h3 className="font-mono text-xs text-text-secondary uppercase tracking-wider mb-3">Recent Runs</h3>
        <div className="space-y-2">
          {runs.map((run) => (
            <div
              key={run.run_id}
              className="flex items-center gap-3 py-2 px-2.5 rounded bg-void/50 border border-border"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="font-mono text-[11px] text-text-primary">
                    {run.mode === 'gap_hunter' ? 'Gap Hunter' : 'Full Scrape'}
                  </span>
                  {statusBadge(run.status)}
                </div>
                <span className="font-mono text-[10px] text-text-muted">
                  {new Date(run.started_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                  {run.completed_at && ` — ${Math.round((new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000)}s`}
                </span>
              </div>

              {run.stats && Object.keys(run.stats).length > 0 && (
                <div className="text-right flex-shrink-0">
                  <span className="data-value text-sm text-signal-green">{run.stats.deals_found ?? run.stats.deals_sent ?? 0}</span>
                  <span className="font-mono text-[9px] text-text-muted block">deals</span>
                </div>
              )}

              {run.error && (
                <div className="text-right flex-shrink-0 max-w-[120px]">
                  <span className="font-mono text-[10px] text-signal-red truncate block">{run.error}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Main Page ───────────────────────────────────────────────────────────

export function Scraper() {
  const queryClient = useQueryClient();
  const { data: statusData } = useScrapeStatus();
  const { data: historyData } = useScrapeHistory();

  const isRunning = statusData?.running ?? false;
  const activeRunId = statusData?.run?.run_id ?? null;

  const [streamRunId, setStreamRunId] = useState<string | null>(null);
  const sseUrl = streamRunId ? `/api/scrape/stream/${streamRunId}` : null;

  const { events, connected, clearEvents } = useSSE({
    url: sseUrl,
    onEvent: (event) => {
      if (['scrape:complete', 'scrape:error', 'scrape:cancelled'].includes(event.type)) {
        // Refresh status and history after run ends
        queryClient.invalidateQueries({ queryKey: ['scrape-status'] });
        queryClient.invalidateQueries({ queryKey: ['scrape-history'] });
      }
    },
  });

  const dealsFound = useMemo(() => {
    return events.filter((e) => e.type === 'scrape:deal_found').length;
  }, [events]);

  const handleStart = async (config: ScrapeStartConfig) => {
    try {
      clearEvents();
      const result = await startScrape(config);
      setStreamRunId(result.run_id);
      queryClient.invalidateQueries({ queryKey: ['scrape-status'] });
    } catch (err: any) {
      console.error('Failed to start scrape:', err);
    }
  };

  const handleStop = async () => {
    try {
      await stopScrape();
      queryClient.invalidateQueries({ queryKey: ['scrape-status'] });
    } catch (err: any) {
      console.error('Failed to stop scrape:', err);
    }
  };

  return (
    <div className="p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-serif text-headline text-text-primary italic">Scraper</h1>
          <p className="font-mono text-[11px] text-text-muted mt-1 tracking-wide">
            LAUNCH &amp; MONITOR SCRAPE RUNS
          </p>
        </div>

        {isRunning && (
          <button
            onClick={handleStop}
            className="flex items-center gap-2 px-4 py-2 bg-signal-red/10 hover:bg-signal-red/20 border border-signal-red/30 rounded font-mono text-[11px] text-signal-red uppercase tracking-wider transition-colors"
          >
            <Square className="w-3 h-3" />
            Stop
          </button>
        )}
      </div>

      {/* Active run stats bar */}
      {(isRunning || connected) && (
        <div className="flex items-center gap-4 font-mono text-[10px]">
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-signal-green animate-pulse-slow" />
            <span className="text-signal-green">RUNNING</span>
          </div>
          <span className="text-text-muted">|</span>
          <span className="text-text-secondary">{events.length} events</span>
          <span className="text-text-muted">|</span>
          <span className="text-signal-green">{dealsFound} deals found</span>
          {activeRunId && (
            <>
              <span className="text-text-muted">|</span>
              <span className="text-text-muted">ID: {activeRunId}</span>
            </>
          )}
        </div>
      )}

      {/* Config */}
      <ScrapeConfig onStart={handleStart} disabled={isRunning} />

      {/* Live Feed */}
      <EventFeed events={events} connected={connected} />

      {/* History */}
      <RunHistory runs={historyData?.runs ?? []} />
    </div>
  );
}
