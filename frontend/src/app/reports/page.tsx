'use client';

import { useEffect, useMemo, useState, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  FileBarChart, Download, Save, Trash2, Play, Table2, BarChart3,
  Loader2, Bookmark, Plus,
} from 'lucide-react';
import {
  reportsAPI, suppliersAPI,
  type ReportConfig, type ReportResponse, type SourceMetadata, type SavedReport,
} from '@/lib/api';
import { ReportChart } from '@/components/reports/ReportChart';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const PRETTY: Record<string, string> = {
  qty: 'Quantity', total: 'Total', unit_price: 'Unit Price',
  budget: 'Budget', actual: 'Actual', variance: 'Variance',
  supplier: 'Supplier', site: 'Site', category: 'Category',
  product: 'Product', month: 'Month', shift: 'Shift',
  meal_type: 'Meal Type', family: 'Family', severity: 'Severity',
};
const label = (k: string) => PRETTY[k] || k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

const fmtCell = (v: any) =>
  typeof v === 'number'
    ? v.toLocaleString('en-US', { maximumFractionDigits: 2 })
    : String(v ?? '');

const SITES = [
  { id: 0, name: 'All sites' },
  { id: 1, name: 'Nes Ziona' },
  { id: 2, name: 'Kiryat Gat' },
];

export default function ReportsPage() {
  const currentYear = new Date().getFullYear();
  const [sources, setSources] = useState<SourceMetadata[]>([]);
  const [activeSourceKey, setActiveSourceKey] = useState<string>('vending');
  const [config, setConfig] = useState<ReportConfig>({
    data_source: 'vending',
    filters: { year: currentYear, from_month: 1, to_month: 12 },
    group_by: ['product'],
    metrics: [{ name: 'qty', agg: 'sum' }, { name: 'total', agg: 'sum' }],
    chart_type: 'bar',
    limit: 500,
  });
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewMode, setPreviewMode] = useState<'table' | 'chart'>('table');

  const [suppliers, setSuppliers] = useState<{ id: number; name: string }[]>([]);
  const [savedReports, setSavedReports] = useState<SavedReport[]>([]);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [saveName, setSaveName] = useState('');

  const activeSource = useMemo(
    () => sources.find((s) => s.key === activeSourceKey),
    [sources, activeSourceKey]
  );

  // Initial load
  useEffect(() => {
    (async () => {
      try {
        const [{ sources: srcs }, supList, saved] = await Promise.all([
          reportsAPI.getSources(),
          suppliersAPI.list(true).catch(() => []),
          reportsAPI.listSaved().catch(() => []),
        ]);
        setSources(srcs);
        setSuppliers(supList);
        setSavedReports(saved);
      } catch (e: any) {
        setError(e?.response?.data?.detail || e?.message || 'Failed to load metadata');
      }
    })();
  }, []);

  // When data source changes, reset group_by/metrics to defaults for that source
  const switchSource = (newKey: string) => {
    const src = sources.find((s) => s.key === newKey);
    if (!src) return;
    setActiveSourceKey(newKey);
    setReport(null);
    setConfig((c) => ({
      ...c,
      data_source: newKey,
      group_by: src.group_by_options[0] ? [src.group_by_options[0].key] : [],
      metrics: src.metric_options.slice(0, 2).map((m) => ({ name: m.name, agg: m.default_agg })),
      chart_type: (src.default_chart as ReportConfig['chart_type']) || 'bar',
      filters: { ...c.filters },
    }));
  };

  const runReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await reportsAPI.run(config);
      setReport(result);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Report failed');
      setReport(null);
    } finally {
      setLoading(false);
    }
  }, [config]);

  const exportReport = async () => {
    setLoading(true);
    setError(null);
    try {
      await reportsAPI.exportXlsx(config);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Export failed');
    } finally {
      setLoading(false);
    }
  };

  const saveReport = async () => {
    if (!saveName.trim()) return;
    try {
      const created = await reportsAPI.createSaved({ name: saveName.trim(), config });
      setSavedReports((s) => [created, ...s]);
      setShowSaveModal(false);
      setSaveName('');
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Save failed');
    }
  };

  const loadSaved = async (s: SavedReport) => {
    setActiveSourceKey(s.config.data_source);
    setConfig(s.config);
    setReport(null);
    setError(null);
  };

  const deleteSaved = async (id: number) => {
    if (!confirm('Delete this saved report?')) return;
    try {
      await reportsAPI.deleteSaved(id);
      setSavedReports((s) => s.filter((r) => r.id !== id));
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Delete failed');
    }
  };

  // ─── Chip toggle helpers ─────────────────────────────────
  const toggleGroupBy = (key: string) =>
    setConfig((c) => ({
      ...c,
      group_by: c.group_by.includes(key)
        ? c.group_by.filter((g) => g !== key)
        : [...c.group_by, key],
    }));

  const toggleMetric = (m: { name: string; default_agg: string }) =>
    setConfig((c) => {
      const exists = c.metrics.find((x) => x.name === m.name);
      return {
        ...c,
        metrics: exists
          ? c.metrics.filter((x) => x.name !== m.name)
          : [...c.metrics, { name: m.name, agg: m.default_agg }],
      };
    });

  const setMetricAgg = (name: string, agg: string) =>
    setConfig((c) => ({
      ...c,
      metrics: c.metrics.map((m) => (m.name === name ? { ...m, agg } : m)),
    }));

  return (
    <div className="max-w-7xl mx-auto p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FileBarChart className="w-7 h-7 text-indigo-600" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Report Generator</h1>
            <p className="text-xs text-gray-500">
              Build custom reports from any data source. Export to Excel.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={runReport} disabled={loading} className="gap-2">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            Run
          </Button>
          <Button onClick={exportReport} disabled={loading || !report} variant="outline" className="gap-2">
            <Download className="w-4 h-4" />
            Export Excel
          </Button>
          <Button onClick={() => setShowSaveModal(true)} disabled={!report} variant="outline" className="gap-2">
            <Save className="w-4 h-4" />
            Save
          </Button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md p-3">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left: config */}
        <div className="lg:col-span-4 space-y-4">
          {/* Data source */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold">Data Source</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1">
              {sources.map((s) => (
                <button
                  key={s.key}
                  onClick={() => switchSource(s.key)}
                  className={`w-full text-left px-3 py-2 rounded-md text-sm border transition ${
                    activeSourceKey === s.key
                      ? 'bg-indigo-50 border-indigo-200 text-indigo-900'
                      : 'bg-white border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <div className="font-medium">{s.label}</div>
                  <div className="text-xs text-gray-500">{s.label_he}</div>
                </button>
              ))}
            </CardContent>
          </Card>

          {/* Filters */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold">Filters</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Year</label>
                  <select
                    value={config.filters.year || ''}
                    onChange={(e) =>
                      setConfig((c) => ({
                        ...c,
                        filters: { ...c.filters, year: e.target.value ? Number(e.target.value) : undefined },
                      }))
                    }
                    className="w-full border rounded px-2 py-1 text-sm"
                  >
                    <option value="">All</option>
                    {[currentYear - 2, currentYear - 1, currentYear, currentYear + 1].map((y) => (
                      <option key={y} value={y}>{y}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">From</label>
                  <select
                    value={config.filters.from_month || 1}
                    onChange={(e) =>
                      setConfig((c) => ({ ...c, filters: { ...c.filters, from_month: Number(e.target.value) } }))
                    }
                    className="w-full border rounded px-2 py-1 text-sm"
                  >
                    {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">To</label>
                  <select
                    value={config.filters.to_month || 12}
                    onChange={(e) =>
                      setConfig((c) => ({ ...c, filters: { ...c.filters, to_month: Number(e.target.value) } }))
                    }
                    className="w-full border rounded px-2 py-1 text-sm"
                  >
                    {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs text-gray-500 mb-1">Site</label>
                <select
                  value={config.filters.site_id ?? 0}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    setConfig((c) => ({ ...c, filters: { ...c.filters, site_id: v === 0 ? undefined : v } }));
                  }}
                  className="w-full border rounded px-2 py-1 text-sm"
                >
                  {SITES.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>

              {(activeSourceKey === 'proforma_items' || activeSourceKey === 'budgets') && (
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Supplier</label>
                  <select
                    value={config.filters.supplier_id ?? 0}
                    onChange={(e) => {
                      const v = Number(e.target.value);
                      setConfig((c) => ({ ...c, filters: { ...c.filters, supplier_id: v === 0 ? undefined : v } }));
                    }}
                    className="w-full border rounded px-2 py-1 text-sm"
                  >
                    <option value={0}>All suppliers</option>
                    {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </div>
              )}

              {activeSourceKey === 'vending' && (
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Shift</label>
                  <select
                    value={config.filters.shift || 'all'}
                    onChange={(e) =>
                      setConfig((c) => ({ ...c, filters: { ...c.filters, shift: e.target.value } }))
                    }
                    className="w-full border rounded px-2 py-1 text-sm"
                  >
                    <option value="all">All shifts</option>
                    <option value="day">Day</option>
                    <option value="evening">Evening</option>
                  </select>
                </div>
              )}

              <div>
                <label className="block text-xs text-gray-500 mb-1">Product search</label>
                <input
                  type="text"
                  value={config.filters.product_name_like || ''}
                  onChange={(e) =>
                    setConfig((c) => ({
                      ...c,
                      filters: { ...c.filters, product_name_like: e.target.value || undefined },
                    }))
                  }
                  placeholder="Substring match…"
                  className="w-full border rounded px-2 py-1 text-sm"
                />
              </div>
            </CardContent>
          </Card>

          {/* Group by */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold">Group By</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {activeSource?.group_by_options.map((g) => {
                const active = config.group_by.includes(g.key);
                return (
                  <button
                    key={g.key}
                    onClick={() => toggleGroupBy(g.key)}
                    className={`px-3 py-1 rounded-full text-xs border transition ${
                      active
                        ? 'bg-indigo-600 text-white border-indigo-600'
                        : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    {g.label}
                  </button>
                );
              })}
            </CardContent>
          </Card>

          {/* Metrics */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold">Metrics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {activeSource?.metric_options.map((m) => {
                const selected = config.metrics.find((x) => x.name === m.name);
                return (
                  <div key={m.name} className="flex items-center gap-2">
                    <button
                      onClick={() => toggleMetric(m)}
                      className={`flex-1 text-left px-3 py-1.5 rounded text-xs border transition ${
                        selected
                          ? 'bg-emerald-50 border-emerald-300 text-emerald-900'
                          : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      {m.label}
                    </button>
                    {selected && (
                      <select
                        value={selected.agg}
                        onChange={(e) => setMetricAgg(m.name, e.target.value)}
                        className="border rounded px-2 py-1 text-xs"
                      >
                        <option value="sum">Sum</option>
                        <option value="avg">Avg</option>
                        <option value="min">Min</option>
                        <option value="max">Max</option>
                        <option value="count">Count</option>
                      </select>
                    )}
                  </div>
                );
              })}
            </CardContent>
          </Card>

          {/* Saved reports */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Bookmark className="w-4 h-4" />
                Saved Reports
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1">
              {savedReports.length === 0 ? (
                <p className="text-xs text-gray-400">No saved reports yet. Run a report and click Save.</p>
              ) : (
                savedReports.map((s) => (
                  <div
                    key={s.id}
                    className="flex items-center justify-between gap-2 px-2 py-1.5 rounded hover:bg-gray-50"
                  >
                    <button
                      onClick={() => loadSaved(s)}
                      className="flex-1 text-left text-sm text-gray-700 truncate"
                      title={s.description || s.name}
                    >
                      <div className="font-medium truncate">{s.name}</div>
                      <div className="text-xs text-gray-400">{s.data_source}</div>
                    </button>
                    <button
                      onClick={() => reportsAPI.exportSaved(s.id, s.name)}
                      className="p-1 rounded hover:bg-gray-200 text-gray-600"
                      title="Export Excel"
                    >
                      <Download className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => deleteSaved(s.id)}
                      className="p-1 rounded hover:bg-red-100 text-red-600"
                      title="Delete"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right: preview */}
        <div className="lg:col-span-8 space-y-4">
          <Card>
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
              <CardTitle className="text-sm font-semibold">Preview</CardTitle>
              <div className="flex items-center gap-2">
                <div className="flex border rounded overflow-hidden">
                  <button
                    onClick={() => setPreviewMode('table')}
                    className={`px-3 py-1 text-xs flex items-center gap-1 ${
                      previewMode === 'table' ? 'bg-indigo-600 text-white' : 'bg-white text-gray-700'
                    }`}
                  >
                    <Table2 className="w-3.5 h-3.5" />
                    Table
                  </button>
                  <button
                    onClick={() => setPreviewMode('chart')}
                    className={`px-3 py-1 text-xs flex items-center gap-1 ${
                      previewMode === 'chart' ? 'bg-indigo-600 text-white' : 'bg-white text-gray-700'
                    }`}
                  >
                    <BarChart3 className="w-3.5 h-3.5" />
                    Chart
                  </button>
                </div>
                {previewMode === 'chart' && (
                  <select
                    value={config.chart_type}
                    onChange={(e) =>
                      setConfig((c) => ({ ...c, chart_type: e.target.value as ReportConfig['chart_type'] }))
                    }
                    className="border rounded px-2 py-1 text-xs"
                  >
                    <option value="bar">Bar</option>
                    <option value="stacked_bar">Stacked Bar</option>
                    <option value="line">Line</option>
                    <option value="pie">Pie</option>
                  </select>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {!report ? (
                <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
                  Configure a report and click <span className="font-medium mx-1">Run</span> to preview.
                </div>
              ) : previewMode === 'table' ? (
                <div className="overflow-auto max-h-[560px] border rounded">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 sticky top-0">
                      <tr>
                        {report.columns.map((c) => (
                          <th key={c} className="text-left px-3 py-2 font-medium text-gray-700 border-b whitespace-nowrap">
                            {label(c)}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {report.rows.map((row, i) => (
                        <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                          {report.columns.map((c) => (
                            <td
                              key={c}
                              className={`px-3 py-1.5 border-b whitespace-nowrap ${
                                typeof row[c] === 'number' ? 'text-right tabular-nums' : ''
                              }`}
                            >
                              {fmtCell(row[c])}
                            </td>
                          ))}
                        </tr>
                      ))}
                      {/* Totals footer */}
                      {Object.keys(report.totals).length > 0 && (() => {
                        const firstMetricIdx = report.columns.findIndex((c) => c in report.totals);
                        return (
                          <tr className="bg-indigo-50 font-semibold sticky bottom-0">
                            {report.columns.map((c, i) => {
                              const isMetric = c in report.totals;
                              const showLabel = !isMetric && i === Math.max(firstMetricIdx - 1, 0);
                              return (
                                <td
                                  key={c}
                                  className={`px-3 py-2 border-t-2 border-indigo-200 whitespace-nowrap ${
                                    isMetric ? 'text-right tabular-nums' : ''
                                  }`}
                                >
                                  {isMetric ? fmtCell(report.totals[c]) : showLabel ? 'Total' : ''}
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })()}
                    </tbody>
                  </table>
                </div>
              ) : (
                <ReportChart report={report} chartType={config.chart_type} />
              )}
              {report && (
                <div className="text-xs text-gray-500 mt-2">
                  {report.row_count} row{report.row_count === 1 ? '' : 's'}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Save modal */}
      {showSaveModal && (
        <div
          className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
          onClick={() => setShowSaveModal(false)}
        >
          <div
            className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
              <Save className="w-5 h-5 text-indigo-600" />
              Save Report
            </h3>
            <input
              type="text"
              value={saveName}
              onChange={(e) => setSaveName(e.target.value)}
              placeholder='e.g. "מ.א 2025 by product"'
              className="w-full border rounded px-3 py-2 text-sm mb-3"
              autoFocus
            />
            <p className="text-xs text-gray-500 mb-4">
              The current data source, filters, group-by and metrics will be saved.
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowSaveModal(false)}>Cancel</Button>
              <Button onClick={saveReport} disabled={!saveName.trim()} className="gap-2">
                <Plus className="w-4 h-4" />
                Save
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

