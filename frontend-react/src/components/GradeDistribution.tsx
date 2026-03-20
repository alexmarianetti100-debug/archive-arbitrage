import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { useStats } from '../hooks/useApi';

const GRADE_COLORS: Record<string, string> = {
  A: '#00ff87',
  B: '#00d4ff',
  C: '#ffb700',
  D: '#4a4a4a',
};

interface GradeData {
  name: string;
  value: number;
  fill: string;
}

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const data = payload[0].payload;
  return (
    <div className="surface-glass rounded px-3 py-2">
      <div className="flex items-center gap-2">
        <span
          className="w-2 h-2 rounded-full"
          style={{ background: data.fill }}
        />
        <span className="font-mono text-xs text-text-primary">
          Grade {data.name}
        </span>
      </div>
      <span className="font-mono text-xs text-text-secondary">
        {data.value} items
      </span>
    </div>
  );
}

export function GradeDistribution() {
  const { data: stats } = useStats();

  const gradeData: GradeData[] = [
    { name: 'A', value: stats?.grade_a_count || 0, fill: GRADE_COLORS.A },
    { name: 'B', value: stats?.grade_b_count || 0, fill: GRADE_COLORS.B },
    { name: 'C', value: stats?.grade_c_count || 0, fill: GRADE_COLORS.C },
    { name: 'D', value: stats?.grade_d_count || 0, fill: GRADE_COLORS.D },
  ].filter(d => d.value > 0);

  const total = gradeData.reduce((s, d) => s + d.value, 0);

  if (total === 0) {
    return (
      <div className="h-48 flex items-center justify-center">
        <span className="font-mono text-xs text-text-muted">NO DATA</span>
      </div>
    );
  }

  return (
    <div className="h-48 relative">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={gradeData}
            cx="50%"
            cy="50%"
            innerRadius={55}
            outerRadius={75}
            paddingAngle={3}
            dataKey="value"
            strokeWidth={0}
          >
            {gradeData.map((entry) => (
              <Cell key={entry.name} fill={entry.fill} opacity={0.85} />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
        </PieChart>
      </ResponsiveContainer>

      {/* Center label */}
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <span className="data-value text-xl text-text-primary">{total}</span>
        <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-text-muted">Total</span>
      </div>

      {/* Legend */}
      <div className="absolute bottom-0 left-0 right-0 flex items-center justify-center gap-4">
        {gradeData.map((entry) => (
          <div key={entry.name} className="flex items-center gap-1.5">
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: entry.fill }}
            />
            <span className="font-mono text-[10px] text-text-secondary">
              {entry.name}: {Math.round(entry.value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
