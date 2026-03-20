import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { useVolumeTimeseries } from '../hooks/useApi';

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="surface-glass rounded px-3 py-2">
      <span className="font-mono text-[10px] text-text-muted block mb-1">{label}</span>
      {payload.map((p: any) => (
        <div key={p.name} className="flex items-center gap-2">
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: p.color }}
          />
          <span className="font-mono text-xs text-text-primary">
            {p.value} items
          </span>
        </div>
      ))}
    </div>
  );
}

export function VelocityChart() {
  const { data: timeseries, isLoading } = useVolumeTimeseries(14);

  if (isLoading) {
    return (
      <div className="h-48 flex items-center justify-center">
        <span className="font-mono text-xs text-text-muted animate-pulse-slow">LOADING...</span>
      </div>
    );
  }

  const chartData = (timeseries?.daily_volumes || []).map((d) => ({
    date: new Date(d.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    volume: d.volume,
  }));

  if (!chartData.length) {
    return (
      <div className="h-48 flex items-center justify-center">
        <span className="font-mono text-xs text-text-muted">NO DATA — run a scrape to populate</span>
      </div>
    );
  }

  return (
    <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 8, right: 4, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="velGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#00ff87" stopOpacity={0.15} />
              <stop offset="100%" stopColor="#00ff87" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="date"
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 10, fill: '#3a3a3a', fontFamily: 'DM Mono' }}
            interval="preserveStartEnd"
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 10, fill: '#3a3a3a', fontFamily: 'DM Mono' }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey="volume"
            stroke="#00ff87"
            strokeWidth={1.5}
            fill="url(#velGradient)"
            dot={false}
            activeDot={{ r: 3, fill: '#00ff87', strokeWidth: 0 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
