'use client';

import { useMemo } from 'react';
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';

const CHART_COLORS = ['#6366f1', '#8b5cf6', '#a855f7', '#d946ef', '#ec4899', '#f43f5e', '#f97316', '#eab308'];

interface ChartBlock {
  type: 'bar' | 'line' | 'pie';
  title?: string;
  data: Array<Record<string, any>>;
  xKey?: string;
  yKey?: string;
  yKeys?: string[];
}

interface ParsedBlock {
  kind: 'text' | 'chart';
  content?: string;
  chart?: ChartBlock;
}

function parseMessageBlocks(text: string): ParsedBlock[] {
  const blocks: ParsedBlock[] = [];
  const chartRegex = /```chart\n([\s\S]*?)```/g;
  let lastIndex = 0;
  let match;

  while ((match = chartRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      const before = text.slice(lastIndex, match.index).trim();
      if (before) blocks.push({ kind: 'text', content: before });
    }

    try {
      const chartData = JSON.parse(match[1].trim());
      blocks.push({ kind: 'chart', chart: chartData });
    } catch {
      blocks.push({ kind: 'text', content: match[1] });
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    const remaining = text.slice(lastIndex).trim();
    if (remaining) blocks.push({ kind: 'text', content: remaining });
  }

  if (blocks.length === 0) {
    blocks.push({ kind: 'text', content: text });
  }

  return blocks;
}

function ChartRenderer({ chart }: { chart: ChartBlock }) {
  const { type, title, data, xKey = 'name', yKey = 'value', yKeys } = chart;

  if (!data || data.length === 0) return null;

  const keys = yKeys || [yKey];

  return (
    <div className="my-3">
      {title && <p className="text-xs font-semibold text-gray-600 mb-2">{title}</p>}
      <div className="bg-white rounded-lg border p-2" style={{ height: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          {type === 'pie' ? (
            <PieChart>
              <Pie
                data={data}
                dataKey={yKey}
                nameKey={xKey}
                cx="50%"
                cy="50%"
                outerRadius={70}
                label={({ name, value }: any) => `${name}: ${value}`}
              >
                {data.map((_, i) => (
                  <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          ) : type === 'line' ? (
            <LineChart data={data}>
              <XAxis dataKey={xKey} tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              {keys.length > 1 && <Legend />}
              {keys.map((k, i) => (
                <Line
                  key={k}
                  type="monotone"
                  dataKey={k}
                  stroke={CHART_COLORS[i % CHART_COLORS.length]}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              ))}
            </LineChart>
          ) : (
            <BarChart data={data}>
              <XAxis dataKey={xKey} tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              {keys.length > 1 && <Legend />}
              {keys.map((k, i) => (
                <Bar
                  key={k}
                  dataKey={k}
                  fill={CHART_COLORS[i % CHART_COLORS.length]}
                  radius={[4, 4, 0, 0]}
                />
              ))}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function TextBlock({ text }: { text: string }) {
  const lines = text.split('\n');
  const tableRows: string[][] = [];
  const nonTableLines: string[] = [];
  let inTable = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      if (/^\|[\s-|]+\|$/.test(trimmed)) {
        inTable = true;
        continue;
      }
      inTable = true;
      const cells = trimmed.split('|').filter(Boolean).map(c => c.trim());
      tableRows.push(cells);
    } else {
      if (inTable && tableRows.length > 0) {
        inTable = false;
      }
      nonTableLines.push(line);
    }
  }

  if (tableRows.length > 0) {
    const headers = tableRows[0];
    const body = tableRows.slice(1);
    return (
      <div>
        {nonTableLines.length > 0 && (
          <div className="whitespace-pre-wrap mb-2">{nonTableLines.join('\n').trim()}</div>
        )}
        <div className="overflow-x-auto my-2">
          <table className="text-xs border-collapse w-full">
            <thead>
              <tr>
                {headers.map((h, i) => (
                  <th key={i} className="border border-gray-200 px-2 py-1 bg-gray-50 text-left font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {body.map((row, ri) => (
                <tr key={ri}>
                  {row.map((cell, ci) => (
                    <td key={ci} className="border border-gray-200 px-2 py-1">{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  return <div className="whitespace-pre-wrap">{text}</div>;
}

export default function ChatMessageRenderer({ text }: { text: string }) {
  const blocks = useMemo(() => parseMessageBlocks(text), [text]);

  return (
    <div>
      {blocks.map((block, i) => {
        if (block.kind === 'chart' && block.chart) {
          return <ChartRenderer key={i} chart={block.chart} />;
        }
        return <TextBlock key={i} text={block.content || ''} />;
      })}
    </div>
  );
}
