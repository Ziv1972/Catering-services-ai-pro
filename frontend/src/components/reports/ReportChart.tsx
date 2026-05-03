'use client';

import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import type { ReportResponse } from '@/lib/api';

const PALETTE = ['#4F46E5', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#78716c', '#22c55e'];

const fmt = (v: any) =>
  typeof v === 'number' ? v.toLocaleString('en-US', { maximumFractionDigits: 2 }) : v;

export function ReportChart({
  report,
  chartType,
}: {
  report: ReportResponse;
  chartType: 'bar' | 'line' | 'pie' | 'stacked_bar';
}) {
  const { chart } = report;
  if (!chart.labels.length || !chart.series.length) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
        No chart data — add a Group By dimension to see a chart.
      </div>
    );
  }

  // Recharts expects an array of objects, one per label
  const data = chart.labels.map((label, i) => {
    const row: Record<string, any> = { label };
    chart.series.forEach((s) => {
      row[s.name] = s.data[i] ?? 0;
    });
    return row;
  });

  if (chartType === 'pie') {
    const seriesName = chart.series[0]?.name || 'value';
    const pieData = data.map((d) => ({ name: d.label, value: Number(d[seriesName] || 0) }));
    return (
      <ResponsiveContainer width="100%" height={360}>
        <PieChart>
          <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={130} label>
            {pieData.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
            ))}
          </Pie>
          <Tooltip formatter={fmt} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  if (chartType === 'line') {
    return (
      <ResponsiveContainer width="100%" height={360}>
        <LineChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} angle={-25} textAnchor="end" height={60} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={fmt} />
          <Tooltip formatter={fmt} />
          <Legend />
          {chart.series.map((s, i) => (
            <Line
              key={s.name}
              type="monotone"
              dataKey={s.name}
              stroke={PALETTE[i % PALETTE.length]}
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    );
  }

  // bar / stacked_bar
  const stackId = chartType === 'stacked_bar' ? 's1' : undefined;
  return (
    <ResponsiveContainer width="100%" height={360}>
      <BarChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="label" tick={{ fontSize: 11 }} angle={-25} textAnchor="end" height={60} />
        <YAxis tick={{ fontSize: 11 }} tickFormatter={fmt} />
        <Tooltip formatter={fmt} />
        <Legend />
        {chart.series.map((s, i) => (
          <Bar key={s.name} dataKey={s.name} stackId={stackId} fill={PALETTE[i % PALETTE.length]} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
