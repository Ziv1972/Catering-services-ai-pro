'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import {
  TrendingUp, Calendar, DollarSign, Utensils,
  AlertTriangle, FileText, BarChart3, X, ArrowLeft, ChevronRight, Check
} from 'lucide-react';
import { historicalAPI, categoryAnalysisAPI, suppliersAPI } from '@/lib/api';
import { Button } from '@/components/ui/button';
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  ComposedChart,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

const MONTH_MAP: Record<string, number> = {
  Jan: 1, Feb: 2, Mar: 3, Apr: 4, May: 5, Jun: 6,
  Jul: 7, Aug: 8, Sep: 9, Oct: 10, Nov: 11, Dec: 12,
};

const MONTH_NAMES_SHORT: Record<number, string> = {
  1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
  7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec',
};

function parseMonthLabel(label: string): { month: number; year: number } | null {
  const parts = label.split(' ');
  if (parts.length === 2) {
    const month = MONTH_MAP[parts[0]];
    const year = parseInt(parts[1]);
    if (month && year) return { month, year };
  }
  return null;
}

const CATEGORY_COLORS: Record<string, string> = {
  total_meals: '#3b82f6', extras_lunch: '#f59e0b', kitchenette_fruit: '#10b981',
  kitchenette_dry: '#8b5cf6', kitchenette_dairy: '#06b6d4', coffee_tea: '#78716c',
  cut_veg: '#22c55e', coffee_beans: '#a16207', uncategorized: '#d1d5db',
};

const PRODUCT_COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#78716c'];

// Format currency with 2 decimal places, safely handles undefined/null
const fmt = (v: number | null | undefined) =>
  `₪${(v ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

// Format integer quantity
const fmtQty = (v: number | null | undefined) =>
  (v ?? 0).toLocaleString();

// ─── Year/Period Picker Component ───
function PeriodPicker({
  selectedYear,
  fromMonth,
  toMonth,
  onYearChange,
  onFromMonthChange,
  onToMonthChange,
}: {
  selectedYear: number;
  fromMonth: number;
  toMonth: number;
  onYearChange: (y: number) => void;
  onFromMonthChange: (m: number) => void;
  onToMonthChange: (m: number) => void;
}) {
  const currentYear = new Date().getFullYear();
  const years = [currentYear - 2, currentYear - 1, currentYear];
  const months = Array.from({ length: 12 }, (_, i) => i + 1);

  return (
    <div className="flex flex-wrap items-center gap-3 mb-4 p-3 bg-gray-50 rounded-lg text-sm">
      <div className="flex items-center gap-1.5">
        <span className="text-gray-500 font-medium">Year:</span>
        <select
          value={selectedYear}
          onChange={(e) => onYearChange(Number(e.target.value))}
          className="border rounded px-2 py-1 text-sm bg-white"
        >
          {years.map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-gray-500 font-medium">From:</span>
        <select
          value={fromMonth}
          onChange={(e) => onFromMonthChange(Number(e.target.value))}
          className="border rounded px-2 py-1 text-sm bg-white"
        >
          {months.map((m) => (
            <option key={m} value={m}>{MONTH_NAMES_SHORT[m]}</option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-gray-500 font-medium">To:</span>
        <select
          value={toMonth}
          onChange={(e) => onToMonthChange(Number(e.target.value))}
          className="border rounded px-2 py-1 text-sm bg-white"
        >
          {months.map((m) => (
            <option key={m} value={m}>{MONTH_NAMES_SHORT[m]}</option>
          ))}
        </select>
      </div>
    </div>
  );
}

// ─── Drill-down state type ───
interface CatDrillState {
  level: number;
  context: {
    year: number;
    fromMonth: number;
    toMonth: number;
    month?: number;
    monthName?: string;
    site_id?: number;
    siteName?: string;
    categoryName?: string;
    categoryDisplayHe?: string;
    productNames?: string[];
    supplier_id?: number;
  };
  data: any;
  loading: boolean;
}

export default function AnalyticsPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // General drill-down state (cost/meals from charts)
  const [drillDown, setDrillDown] = useState<{
    type: string;
    label: string;
    data: any;
    loading: boolean;
    level?: number;
    context?: any;
  } | null>(null);

  // Category quantity drill-down (6 levels now)
  const [catDrill, setCatDrill] = useState<CatDrillState | null>(null);
  // History stack for back navigation without re-fetching
  const catHistoryRef = useRef<CatDrillState[]>([]);
  // Multi-product selection at Level 4
  const [selectedProducts, setSelectedProducts] = useState<string[]>([]);
  // Supplier filter
  const [suppliersList, setSuppliersList] = useState<any[]>([]);
  const [selectedSupplierId, setSelectedSupplierId] = useState<number | undefined>(undefined);

  const currentYear = new Date().getFullYear();

  useEffect(() => {
    loadAnalytics();
    suppliersAPI.list(true).then(setSuppliersList).catch(() => {});
  }, []);

  const loadAnalytics = async () => {
    try {
      const analyticsData = await historicalAPI.getAnalytics();
      setData(analyticsData);
    } catch (err) {
      setError('Failed to load analytics data. Make sure the backend is running.');
    } finally {
      setLoading(false);
    }
  };

  // ─── Chart click handlers ───
  const handleCostClick = async (chartData: any) => {
    if (!chartData?.activePayload?.[0]?.payload) return;
    const monthLabel = chartData.activePayload[0].payload.month;
    const parsed = parseMonthLabel(monthLabel);
    if (!parsed) return;

    setDrillDown({ type: 'cost', label: monthLabel, data: null, loading: true });
    try {
      const result = await historicalAPI.drillDownCost({ month: parsed.month, year: parsed.year });
      setDrillDown((prev) => prev ? { ...prev, data: result, loading: false } : null);
    } catch {
      setDrillDown((prev) => prev ? { ...prev, data: { items: [] }, loading: false } : null);
    }
  };

  const handleMealClick = async (chartData: any) => {
    if (!chartData?.activePayload?.[0]?.payload) return;
    const monthLabel = chartData.activePayload[0].payload.month;
    const parsed = parseMonthLabel(monthLabel);
    if (!parsed) return;

    setDrillDown({ type: 'meals', label: monthLabel, data: null, loading: true, level: 1, context: { month: parsed.month, year: parsed.year, monthLabel } });
    try {
      const result = await historicalAPI.drillDownMeals({ month: parsed.month, year: parsed.year });
      setDrillDown((prev) => prev ? { ...prev, data: result, loading: false } : null);
    } catch {
      setDrillDown((prev) => prev ? { ...prev, data: { items: [] }, loading: false } : null);
    }
  };

  const drillMealIntoCategories = async (siteId: number, siteName: string) => {
    if (!drillDown || drillDown.type !== 'meals') return;
    const ctx = drillDown.context;
    setDrillDown((prev) => prev ? {
      ...prev, level: 2, label: `${ctx.monthLabel} — ${siteName}`,
      context: { ...ctx, site_id: siteId, siteName },
      data: null, loading: true,
    } : null);
    try {
      const result = await historicalAPI.drillDownMealsCategories({
        month: ctx.month, year: ctx.year, site_id: siteId,
      });
      setDrillDown((prev) => prev ? { ...prev, data: result, loading: false } : null);
    } catch {
      setDrillDown((prev) => prev ? { ...prev, data: { items: [] }, loading: false } : null);
    }
  };

  const goBackMealDrill = () => {
    if (!drillDown || drillDown.type !== 'meals') return;
    if (drillDown.level === 2) {
      const ctx = drillDown.context;
      handleMealClick({ activePayload: [{ payload: { month: ctx.monthLabel } }] });
    } else {
      setDrillDown(null);
    }
  };

  // ─── Category Quantity Drill-Down (6 levels: months → sites → categories → category-monthly → products → product-monthly) ───

  // Deep copy to preserve history correctly
  const deepCopyCatDrill = (state: CatDrillState): CatDrillState => {
    return JSON.parse(JSON.stringify(state));
  };

  const pushHistory = useCallback(() => {
    if (catDrill) {
      catHistoryRef.current = [...catHistoryRef.current, deepCopyCatDrill(catDrill)];
    }
  }, [catDrill]);

  const openCategoryQtyDrillDown = async (year?: number) => {
    const y = year ?? currentYear;
    catHistoryRef.current = [];
    setSelectedProducts([]);
    setCatDrill({ level: 1, context: { year: y, fromMonth: 1, toMonth: 12, supplier_id: selectedSupplierId }, data: null, loading: true });
    try {
      const result = await categoryAnalysisAPI.quantityMonthly({ year: y, supplier_id: selectedSupplierId });
      setCatDrill((prev) => prev ? { ...prev, data: result, loading: false } : null);
    } catch {
      setCatDrill((prev) => prev ? { ...prev, data: { items: [] }, loading: false } : null);
    }
  };

  const refreshLevel1 = async (year: number, fromMonth: number, toMonth: number) => {
    catHistoryRef.current = [];
    setSelectedProducts([]);
    setCatDrill({ level: 1, context: { year, fromMonth, toMonth, supplier_id: selectedSupplierId }, data: null, loading: true });
    try {
      const result = await categoryAnalysisAPI.quantityMonthly({ year, supplier_id: selectedSupplierId });
      const filtered = {
        ...result,
        items: (result.items || []).filter((item: any) => item.month >= fromMonth && item.month <= toMonth),
      };
      setCatDrill((prev) => prev ? { ...prev, data: filtered, loading: false } : null);
    } catch {
      setCatDrill((prev) => prev ? { ...prev, data: { items: [] }, loading: false } : null);
    }
  };

  const drillIntoQtySites = async (month: number, monthName: string) => {
    if (!catDrill) return;
    pushHistory();
    const ctx = catDrill.context;
    setCatDrill((prev) => prev ? {
      ...prev, level: 2, context: { ...ctx, month, monthName },
      data: null, loading: true,
    } : null);
    try {
      const result = await categoryAnalysisAPI.quantityBySite({ year: ctx.year, month, supplier_id: ctx.supplier_id });
      setCatDrill((prev) => prev ? { ...prev, data: result, loading: false } : null);
    } catch {
      setCatDrill((prev) => prev ? { ...prev, data: { items: [] }, loading: false } : null);
    }
  };

  const drillIntoQtyCategories = async (siteId: number, siteName: string) => {
    if (!catDrill) return;
    pushHistory();
    const ctx = catDrill.context;
    setCatDrill((prev) => prev ? {
      ...prev, level: 3, context: { ...ctx, site_id: siteId, siteName },
      data: null, loading: true,
    } : null);
    try {
      const result = await categoryAnalysisAPI.quantityByCategory({ year: ctx.year, month: ctx.month!, site_id: siteId, supplier_id: ctx.supplier_id });
      setCatDrill((prev) => prev ? { ...prev, data: result, loading: false } : null);
    } catch {
      setCatDrill((prev) => prev ? { ...prev, data: { items: [] }, loading: false } : null);
    }
  };

  // Level 3.5 — Monthly breakdown for a specific category
  const drillIntoCategoryMonthly = async (categoryName: string, displayHe: string) => {
    if (!catDrill) return;
    pushHistory();
    const ctx = catDrill.context;
    setCatDrill((prev) => prev ? {
      ...prev, level: 3.5 as any, context: { ...ctx, categoryName, categoryDisplayHe: displayHe },
      data: null, loading: true,
    } : null);
    try {
      const result = await categoryAnalysisAPI.quantityCategoryMonthly({
        year: ctx.year, site_id: ctx.site_id!, category_name: categoryName, supplier_id: ctx.supplier_id,
      });
      const filtered = {
        ...result,
        items: (result.items || []).filter((item: any) =>
          item.month >= ctx.fromMonth && item.month <= ctx.toMonth
        ),
      };
      setCatDrill((prev) => prev ? { ...prev, data: filtered, loading: false } : null);
    } catch {
      setCatDrill((prev) => prev ? { ...prev, data: { items: [] }, loading: false } : null);
    }
  };

  const drillIntoQtyProducts = async (month: number, monthName: string) => {
    if (!catDrill) return;
    pushHistory();
    setSelectedProducts([]);
    const ctx = catDrill.context;
    setCatDrill((prev) => prev ? {
      ...prev, level: 4, context: { ...ctx, month, monthName },
      data: null, loading: true,
    } : null);
    try {
      const result = await categoryAnalysisAPI.quantityProducts({
        year: ctx.year, month, site_id: ctx.site_id!, category_name: ctx.categoryName!, supplier_id: ctx.supplier_id,
      });
      setCatDrill((prev) => prev ? { ...prev, data: result, loading: false } : null);
    } catch {
      setCatDrill((prev) => prev ? { ...prev, data: { items: [] }, loading: false } : null);
    }
  };

  // Level 5 — Multi-product monthly comparison
  const drillIntoProductMonthly = async (productNames: string[]) => {
    if (!catDrill || productNames.length === 0) return;
    pushHistory();
    const ctx = catDrill.context;
    setCatDrill((prev) => prev ? {
      ...prev, level: 5, context: { ...ctx, productNames },
      data: null, loading: true,
    } : null);
    try {
      const result = await categoryAnalysisAPI.quantityProductMonthly({
        year: ctx.year,
        site_id: ctx.site_id!,
        category_name: ctx.categoryName!,
        product_names: productNames.join(','),
        supplier_id: ctx.supplier_id,
      });
      setCatDrill((prev) => prev ? { ...prev, data: result, loading: false } : null);
    } catch {
      setCatDrill((prev) => prev ? { ...prev, data: { series: [] }, loading: false } : null);
    }
  };

  // Toggle product selection for multi-select
  const toggleProductSelection = (productName: string) => {
    setSelectedProducts((prev) =>
      prev.includes(productName)
        ? prev.filter((p) => p !== productName)
        : prev.length < 8
          ? [...prev, productName]
          : prev
    );
  };

  // Back navigation using history stack — no re-fetching
  const goBackCatDrill = () => {
    if (!catDrill) return;
    if (catDrill.level <= 1) {
      setCatDrill(null);
      catHistoryRef.current = [];
      setSelectedProducts([]);
      return;
    }
    const history = [...catHistoryRef.current];
    const prevState = history.pop();
    catHistoryRef.current = history;
    if (prevState) {
      setCatDrill(prevState);
      // Restore selected products only for Level 4
      if (prevState.level !== 4) {
        setSelectedProducts([]);
      }
    } else {
      setCatDrill(null);
      setSelectedProducts([]);
    }
  };

  const getCatDrillTitle = () => {
    if (!catDrill) return '';
    const ctx = catDrill.context;
    const levelNum = catDrill.level;
    if (levelNum === 1) return `Product Quantities by Month (${ctx.year})`;
    if (levelNum === 2) {
      const parts = [ctx.monthName, 'Quantities by Site'].filter(Boolean);
      return parts.join(' — ');
    }
    if (levelNum === 3) {
      const parts = [ctx.monthName, ctx.siteName, 'Categories'].filter(Boolean);
      return parts.join(' — ');
    }
    if (levelNum === 3.5) {
      const parts = [ctx.siteName, ctx.categoryDisplayHe, 'Monthly'].filter(Boolean);
      return parts.join(' — ');
    }
    if (levelNum === 4) {
      const parts = [ctx.siteName, ctx.categoryDisplayHe, ctx.monthName].filter(Boolean);
      return parts.join(' — ');
    }
    if (levelNum === 5) {
      const count = ctx.productNames?.length ?? 0;
      const parts = [ctx.siteName, ctx.categoryDisplayHe, `${count} product${count !== 1 ? 's' : ''}`].filter(Boolean);
      return parts.join(' — ');
    }
    return '';
  };

  const getCatDrillSubtitle = () => {
    if (!catDrill) return '';
    const levelNum = catDrill.level;
    if (levelNum === 1) return 'Click a month to drill down';
    if (levelNum === 2) return 'Click a site to see categories';
    if (levelNum === 3) return 'Click a category to see monthly breakdown';
    if (levelNum === 3.5) return 'Click a month to see products';
    if (levelNum === 4) return 'Select products to compare monthly trends';
    if (levelNum === 5) return 'Monthly comparison for selected products';
    return '';
  };

  // Period change handler — always resets to Level 1
  const handlePeriodChange = (field: 'year' | 'fromMonth' | 'toMonth', value: number) => {
    if (!catDrill) return;
    const ctx = catDrill.context;
    const newCtx = { ...ctx, [field]: value };
    refreshLevel1(newCtx.year, newCtx.fromMonth, newCtx.toMonth);
  };

  // Sort chart data chronologically by month label (e.g. "Jan 2025")
  const sortByMonth = (arr: any[] | undefined): any[] => {
    if (!arr?.length) return [];
    return [...arr].sort((a, b) => {
      const pa = parseMonthLabel(a.month);
      const pb = parseMonthLabel(b.month);
      if (!pa || !pb) return 0;
      return pa.year !== pb.year ? pa.year - pb.year : pa.month - pb.month;
    });
  };

  if (loading) {
    return <div className="flex items-center justify-center h-screen">Loading analytics...</div>;
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Card className="p-8 text-center max-w-md">
          <AlertTriangle className="w-12 h-12 text-orange-500 mx-auto mb-4" />
          <p className="text-gray-700 font-medium">{error || 'No data available'}</p>
          <p className="text-sm text-gray-500 mt-2">
            Ensure the backend API is running on port 8000.
          </p>
        </Card>
      </div>
    );
  }

  const counts = data.counts || {};
  const totalRecords = Object.values(counts).reduce((sum: number, c: any) => sum + (c || 0), 0);

  const sortedMealTrends = sortByMonth(data.mealTrends);
  const sortedCostTrends = sortByMonth(data.costTrends);
  const sortedVendorSeries = sortByMonth(data.vendorSeries);
  const sortedMenuFindings = sortByMonth(data.menuFindings);

  const siteKeys = sortedMealTrends.length > 0
    ? Object.keys(sortedMealTrends[0]).filter((k: string) => k !== 'month')
    : [];

  const vendorKeys = sortedVendorSeries.length > 0
    ? Object.keys(sortedVendorSeries[0]).filter(
        (k: string) => !['month', 'total', 'ma_3m'].includes(k)
      )
    : [];

  // Build Level 5 chart data — merge all products into unified month rows
  const buildProductComparisonData = () => {
    if (!catDrill || catDrill.level !== 5 || !catDrill.data?.series) return [];
    const monthMap: Record<number, any> = {};
    for (const product of catDrill.data.series) {
      for (const m of product.months) {
        if (!monthMap[m.month]) {
          monthMap[m.month] = { month: m.month, month_name: m.month_name };
        }
        monthMap[m.month][`qty_${product.product_name}`] = m.total_quantity;
        monthMap[m.month][`cost_${product.product_name}`] = m.total_cost;
      }
    }
    return Object.values(monthMap).sort((a: any, b: any) => a.month - b.month);
  };

  return (
    <div>
      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-gray-900">Analytics & Insights</h2>
          <p className="text-gray-500 text-sm">Real data from database across all sites</p>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
          <Card className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Records</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">{totalRecords.toLocaleString()}</p>
              </div>
              <BarChart3 className="w-7 h-7 text-blue-500" />
            </div>
          </Card>
          <Card className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Meal Records</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">{(counts.meals || 0).toLocaleString()}</p>
              </div>
              <Utensils className="w-7 h-7 text-green-500" />
            </div>
          </Card>
          <Card className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Menu Checks</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">{counts.menu_checks || 0}</p>
              </div>
              <FileText className="w-7 h-7 text-purple-500" />
            </div>
          </Card>
          <Card className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Proformas</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">{counts.proformas || 0}</p>
              </div>
              <DollarSign className="w-7 h-7 text-orange-500" />
            </div>
          </Card>
          <Card className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Violations</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">{counts.violations || 0}</p>
              </div>
              <AlertTriangle className="w-7 h-7 text-red-500" />
            </div>
          </Card>
        </div>

        {/* Charts Row 1 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Utensils className="w-5 h-5 text-green-600" />
                Meal Count Trends by Site
              </CardTitle>
            </CardHeader>
            <CardContent>
              {sortedMealTrends?.length > 0 ? (
                <ResponsiveContainer width="100%" height={300} minWidth={1}>
                  <LineChart data={sortedMealTrends} onClick={handleMealClick} style={{ cursor: 'pointer' }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" fontSize={12} />
                    <YAxis fontSize={12} />
                    <Tooltip />
                    <Legend />
                    {siteKeys.map((key: string, i: number) => (
                      <Line
                        key={key}
                        type="monotone"
                        dataKey={key}
                        stroke={COLORS[i % COLORS.length]}
                        name={key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                        strokeWidth={2}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-gray-500 text-center py-12">No meal data available</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <DollarSign className="w-5 h-5 text-purple-600" />
                Spending Trends
              </CardTitle>
            </CardHeader>
            <CardContent>
              {sortedCostTrends?.length > 0 ? (
                <ResponsiveContainer width="100%" height={300} minWidth={1}>
                  <ComposedChart data={sortedCostTrends} onClick={handleCostClick} style={{ cursor: 'pointer' }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" fontSize={12} />
                    <YAxis fontSize={12} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="total_cost" fill="#8b5cf6" name="Total Cost" opacity={0.3} />
                    <Line type="monotone" dataKey="avg_cost" stroke="#8b5cf6" name="Avg Cost/Meal" strokeWidth={2} dot={{ r: 4 }} />
                  </ComposedChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-gray-500 text-center py-12">No cost data available</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Charts Row 2 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-orange-600" />
                Violations by Category
              </CardTitle>
            </CardHeader>
            <CardContent>
              {data.violationCategories?.length > 0 ? (
                <ResponsiveContainer width="100%" height={300} minWidth={1}>
                  <PieChart>
                    <Pie
                      data={data.violationCategories}
                      cx="50%" cy="50%"
                      labelLine label={(entry: any) => `${entry.name} (${entry.value})`}
                      outerRadius={100} fill="#8884d8" dataKey="value"
                    >
                      {data.violationCategories.map((_: any, index: number) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-gray-500 text-center py-12">No violation data available</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-blue-600" />
                Menu Compliance Findings
              </CardTitle>
            </CardHeader>
            <CardContent>
              {sortedMenuFindings?.length > 0 ? (
                <ResponsiveContainer width="100%" height={300} minWidth={1}>
                  <BarChart data={sortedMenuFindings}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" fontSize={12} />
                    <YAxis fontSize={12} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="critical" fill="#ef4444" name="Critical" />
                    <Bar dataKey="warnings" fill="#f59e0b" name="Warnings" />
                    <Bar dataKey="passed" fill="#10b981" name="Passed" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-gray-500 text-center py-12">No menu check data available</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Vendor Spending */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-green-600" />
              Vendor Spending with 3-Month Moving Average
            </CardTitle>
          </CardHeader>
          <CardContent>
            {sortedVendorSeries?.length > 0 ? (
              <ResponsiveContainer width="100%" height={400} minWidth={1}>
                <ComposedChart data={sortedVendorSeries}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" fontSize={12} />
                  <YAxis fontSize={12} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                  <Tooltip />
                  <Legend />
                  {vendorKeys.map((key: string, i: number) => (
                    <Bar
                      key={key}
                      dataKey={key}
                      stackId="vendors"
                      fill={COLORS[i % COLORS.length]}
                      name={key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                    />
                  ))}
                  <Line
                    type="monotone" dataKey="ma_3m" stroke="#ef4444" name="3M Moving Avg"
                    strokeWidth={3} dot={{ r: 5, fill: '#ef4444' }} strokeDasharray="5 5"
                  />
                </ComposedChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-gray-500 text-center py-12">No vendor spending data available</p>
            )}
          </CardContent>
        </Card>

        {/* Vendor Totals + Records Summary */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <DollarSign className="w-5 h-5 text-orange-600" />
                Total Spending by Vendor
              </CardTitle>
            </CardHeader>
            <CardContent>
              {data.vendorTotals?.length > 0 ? (
                <ResponsiveContainer width="100%" height={300} minWidth={1}>
                  <PieChart>
                    <Pie
                      data={data.vendorTotals} cx="50%" cy="50%"
                      labelLine label={(entry: any) => `${entry.name}`}
                      outerRadius={100} fill="#8884d8" dataKey="value"
                    >
                      {data.vendorTotals.map((_: any, index: number) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-gray-500 text-center py-12">No vendor data available</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="w-5 h-5 text-blue-600" />
                Database Records Summary
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {Object.entries(counts).map(([label, count]: [string, any]) => (
                  <div key={label} className="flex justify-between items-center py-2 border-b last:border-b-0">
                    <span className="text-gray-700 capitalize">{label.replace(/_/g, ' ')}</span>
                    <span className="text-xl font-bold text-gray-900">{(count || 0).toLocaleString()}</span>
                  </div>
                ))}
                <div className="flex justify-between items-center pt-2 border-t-2">
                  <span className="font-semibold text-gray-900">Total</span>
                  <span className="text-2xl font-bold text-blue-600">{totalRecords.toLocaleString()}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* ═══════ Category Quantity Analysis Entry Card ═══════ */}
        <Card
          className="mt-6 mb-6 border-l-4 border-l-teal-500 hover:shadow-lg transition-shadow cursor-pointer"
          onClick={() => openCategoryQtyDrillDown()}
        >
          <CardHeader className="pb-2">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-teal-50 rounded-lg">
                  <BarChart3 className="w-5 h-5 text-teal-600" />
                </div>
                <div>
                  <CardTitle className="text-lg">Product Category Quantities ({currentYear})</CardTitle>
                  <p className="text-sm text-gray-500">
                    FoodHouse proforma quantities by product category &middot; 6-level drill-down
                  </p>
                </div>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-400" />
            </div>
          </CardHeader>
        </Card>

        {/* ═══════ Category Quantity Drill-Down Modal ═══════ */}
        {catDrill && (
          <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
            <Card className="w-full max-w-sm md:max-w-2xl lg:max-w-3xl max-h-[85vh] overflow-auto">
              <CardHeader className="pb-2 sticky top-0 bg-white z-10 border-b">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {catDrill.level > 1 && (
                      <Button variant="ghost" size="sm" onClick={goBackCatDrill}>
                        <ArrowLeft className="w-4 h-4" />
                      </Button>
                    )}
                    <div>
                      <CardTitle className="text-lg">{getCatDrillTitle()}</CardTitle>
                      <p className="text-sm text-gray-500">{getCatDrillSubtitle()}</p>
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => { setCatDrill(null); catHistoryRef.current = []; setSelectedProducts([]); }}>
                    <X className="w-4 h-4" />
                  </Button>
                </div>
                {/* Time Period Picker — shown at ALL levels, always resets to L1 */}
                <div className="flex flex-wrap items-center gap-3">
                  <PeriodPicker
                    selectedYear={catDrill.context.year}
                    fromMonth={catDrill.context.fromMonth}
                    toMonth={catDrill.context.toMonth}
                    onYearChange={(y) => handlePeriodChange('year', y)}
                    onFromMonthChange={(m) => handlePeriodChange('fromMonth', m)}
                    onToMonthChange={(m) => handlePeriodChange('toMonth', m)}
                  />
                  {suppliersList.length > 0 && (
                    <div className="flex items-center gap-1.5 p-3 bg-gray-50 rounded-lg text-sm">
                      <span className="text-gray-500 font-medium">Vendor:</span>
                      <select
                        value={selectedSupplierId ?? ''}
                        onChange={(e) => {
                          const val = e.target.value ? Number(e.target.value) : undefined;
                          setSelectedSupplierId(val);
                          refreshLevel1(catDrill.context.year, catDrill.context.fromMonth, catDrill.context.toMonth);
                        }}
                        className="border rounded px-2 py-1 bg-white"
                      >
                        <option value="">All Vendors</option>
                        {suppliersList.map((s: any) => (
                          <option key={s.id} value={s.id}>{s.name}</option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
              </CardHeader>
              <CardContent className="pt-4">
                {catDrill.loading ? (
                  <div className="text-center py-12 text-gray-400">Loading...</div>
                ) : catDrill.level === 1 ? (
                  /* ─── Level 1: Monthly quantity totals ─── */
                  <>
                    {(catDrill.data?.items || []).length === 0 ? (
                      <p className="text-center py-8 text-gray-400">No quantity data for {catDrill.context.year}</p>
                    ) : (
                      <>
                        <div className="h-56 mb-4">
                          <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                            <BarChart data={catDrill.data?.items || []}>
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis dataKey="month_name" tick={{ fontSize: 12 }} />
                              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)} />
                              <Tooltip formatter={(val: any) => fmtQty(Number(val))} />
                              <Bar dataKey="total_quantity" fill="#10b981" radius={[4, 4, 0, 0]} name="Quantity" />
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                        <div className="space-y-1">
                          {(catDrill.data?.items || []).map((item: any) => (
                            <div
                              key={item.month}
                              onClick={() => drillIntoQtySites(item.month, item.month_name)}
                              className="flex items-center justify-between p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-green-50 transition-colors"
                            >
                              <div>
                                <span className="font-medium">{item.month_name}</span>
                                <span className="text-xs text-gray-500 ml-2">{item.invoice_count ?? 0} invoices</span>
                              </div>
                              <div className="flex items-center gap-3">
                                <span className="tabular-nums text-gray-800">{fmtQty(item.total_quantity)}</span>
                                <ChevronRight className="w-4 h-4 text-gray-400" />
                              </div>
                            </div>
                          ))}
                        </div>
                      </>
                    )}
                  </>
                ) : catDrill.level === 2 ? (
                  /* ─── Level 2: Sites for a month ─── */
                  <>
                    {(catDrill.data?.items || []).length === 0 ? (
                      <p className="text-center py-8 text-gray-400">No site data for this month</p>
                    ) : (
                      <div className="space-y-1">
                        {(catDrill.data?.items || []).map((item: any) => (
                          <div
                            key={item.site_id}
                            onClick={() => drillIntoQtyCategories(item.site_id, item.site_name)}
                            className="flex items-center justify-between p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-green-50 transition-colors"
                          >
                            <div>
                              <span className="font-medium">{item.site_name}</span>
                              <span className="text-xs text-gray-500 ml-2">{item.invoice_count ?? 0} invoices</span>
                            </div>
                            <div className="flex items-center gap-3">
                              <span className="tabular-nums text-gray-800">{fmtQty(item.total_quantity)}</span>
                              <ChevronRight className="w-4 h-4 text-gray-400" />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                ) : catDrill.level === 3 ? (
                  /* ─── Level 3: Categories for a site ─── */
                  <>
                    {(catDrill.data?.items || []).length === 0 ? (
                      <p className="text-center py-8 text-gray-400">No category data for this site</p>
                    ) : (
                      <>
                        <div className="h-56 mb-4">
                          <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                            <BarChart data={catDrill.data?.items || []} layout="vertical">
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)} />
                              <YAxis type="category" dataKey="display_name_he" tick={{ fontSize: 12 }} width={100} />
                              <Tooltip formatter={(val: any) => fmtQty(Number(val))} />
                              <Bar dataKey="total_quantity" name="Quantity" radius={[0, 4, 4, 0]}>
                                {(catDrill.data?.items || []).map((item: any, idx: number) => (
                                  <Cell key={idx} fill={CATEGORY_COLORS[item.category_name] || '#94a3b8'} />
                                ))}
                              </Bar>
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                        <div className="space-y-1">
                          {(catDrill.data?.items || []).map((item: any) => (
                            <div
                              key={item.category_name}
                              onClick={() => drillIntoCategoryMonthly(item.category_name, item.display_name_he)}
                              className="flex items-center justify-between p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-green-50 transition-colors"
                            >
                              <div className="flex items-center gap-2">
                                <div
                                  className="w-3 h-3 rounded-full shrink-0"
                                  style={{ backgroundColor: CATEGORY_COLORS[item.category_name] || '#94a3b8' }}
                                />
                                <span className="font-medium">{item.display_name_he}</span>
                                <span className="text-xs text-gray-400">{item.item_count ?? 0} items</span>
                              </div>
                              <div className="flex items-center gap-3">
                                <span className="tabular-nums text-gray-800">{fmtQty(item.total_quantity)}</span>
                                <span className="text-xs text-gray-400">({fmt(item.total_cost)})</span>
                                <ChevronRight className="w-4 h-4 text-gray-400" />
                              </div>
                            </div>
                          ))}
                        </div>
                        {/* Total row */}
                        <div className="flex items-center justify-between p-3 mt-2 bg-teal-50 rounded-lg border border-teal-200">
                          <span className="text-sm text-teal-700">סה&quot;כ</span>
                          <div className="flex items-center gap-4">
                            <span className="text-sm text-teal-700 tabular-nums">
                              {fmtQty((catDrill.data?.items || []).reduce((s: number, i: any) => s + (i.total_quantity || 0), 0))}
                            </span>
                            <span className="text-xs text-teal-600">
                              ({fmt((catDrill.data?.items || []).reduce((s: number, i: any) => s + (i.total_cost || 0), 0))})
                            </span>
                          </div>
                        </div>
                      </>
                    )}
                  </>
                ) : catDrill.level === 3.5 ? (
                  /* ─── Level 3.5: Monthly breakdown of a category ─── */
                  <>
                    {(catDrill.data?.items || []).length === 0 ? (
                      <p className="text-center py-8 text-gray-400">No monthly data for this category</p>
                    ) : (
                      <>
                        <div className="h-56 mb-4">
                          <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                            <ComposedChart data={catDrill.data?.items || []}>
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis dataKey="month_name" tick={{ fontSize: 12 }} />
                              <YAxis yAxisId="qty" tick={{ fontSize: 11 }} tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)} />
                              <YAxis yAxisId="cost" orientation="right" tick={{ fontSize: 11 }} tickFormatter={(v: number) => `₪${v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v}`} />
                              <Tooltip
                                formatter={(val: any, name: any) =>
                                  name === 'Cost' ? fmt(Number(val)) : fmtQty(Number(val))
                                }
                              />
                              <Legend />
                              <Bar yAxisId="qty" dataKey="total_quantity" fill={CATEGORY_COLORS[catDrill.context.categoryName ?? ''] || '#10b981'} radius={[4, 4, 0, 0]} name="Quantity" />
                              <Line yAxisId="cost" type="monotone" dataKey="total_cost" stroke="#ef4444" strokeWidth={2} dot={{ r: 3 }} name="Cost" />
                            </ComposedChart>
                          </ResponsiveContainer>
                        </div>
                        <div className="space-y-1">
                          {(catDrill.data?.items || []).map((item: any) => (
                            <div
                              key={item.month}
                              onClick={() => drillIntoQtyProducts(item.month, item.month_name)}
                              className="flex items-center justify-between p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-green-50 transition-colors"
                            >
                              <div>
                                <span className="font-medium">{item.month_name}</span>
                                <span className="text-xs text-gray-500 ml-2">{item.product_count ?? 0} products</span>
                              </div>
                              <div className="flex items-center gap-4">
                                <span className="tabular-nums text-gray-800">{fmtQty(item.total_quantity)}</span>
                                <span className="text-xs text-gray-500">{fmt(item.total_cost)}</span>
                                <ChevronRight className="w-4 h-4 text-gray-400" />
                              </div>
                            </div>
                          ))}
                        </div>
                        {/* Total row */}
                        <div className="flex items-center justify-between p-3 mt-2 bg-teal-50 rounded-lg border border-teal-200">
                          <span className="text-sm text-teal-700">סה&quot;כ</span>
                          <div className="flex items-center gap-4">
                            <span className="text-sm text-teal-700 tabular-nums">
                              {fmtQty((catDrill.data?.items || []).reduce((s: number, i: any) => s + (i.total_quantity || 0), 0))}
                            </span>
                            <span className="text-xs text-teal-600">
                              ({fmt((catDrill.data?.items || []).reduce((s: number, i: any) => s + (i.total_cost || 0), 0))})
                            </span>
                          </div>
                        </div>
                      </>
                    )}
                  </>
                ) : catDrill.level === 4 ? (
                  /* ─── Level 4: Products in category — click to see monthly ─── */
                  <div>
                    {(catDrill.data?.items || []).length === 0 ? (
                      <p className="text-center py-8 text-gray-400">No products in this category</p>
                    ) : (
                      <>
                        {/* Multi-select compare bar */}
                        {selectedProducts.length > 1 && (
                          <div className="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-200 flex items-center justify-between">
                            <span className="text-sm text-blue-700">
                              {selectedProducts.length} products selected
                            </span>
                            <div className="flex gap-2">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setSelectedProducts([])}
                                className="text-xs text-blue-600"
                              >
                                Clear
                              </Button>
                              <Button
                                size="sm"
                                onClick={() => drillIntoProductMonthly(selectedProducts)}
                                className="bg-blue-600 text-white hover:bg-blue-700 text-xs"
                              >
                                Compare {selectedProducts.length} Products
                              </Button>
                            </div>
                          </div>
                        )}
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="border-b text-left text-gray-500">
                                <th className="pb-2 font-medium">Product</th>
                                <th className="pb-2 font-medium text-right">Qty</th>
                                <th className="pb-2 font-medium text-right">Avg Price</th>
                                <th className="pb-2 font-medium text-right">Total</th>
                                <th className="pb-2 w-8"></th>
                              </tr>
                            </thead>
                            <tbody>
                              {(catDrill.data?.items || []).map((item: any, i: number) => {
                                const isSelected = selectedProducts.includes(item.product_name);
                                return (
                                  <tr
                                    key={i}
                                    onClick={() => drillIntoProductMonthly([item.product_name])}
                                    className="border-b last:border-0 cursor-pointer hover:bg-green-50 transition-colors"
                                  >
                                    <td className="py-2 font-medium flex items-center gap-1">
                                      {item.product_name}
                                      <ChevronRight className="w-3 h-3 text-gray-300" />
                                    </td>
                                    <td className="py-2 text-right text-gray-600 tabular-nums">{fmtQty(item.total_quantity)}</td>
                                    <td className="py-2 text-right text-gray-600 tabular-nums">{fmt(item.avg_unit_price)}</td>
                                    <td className="py-2 text-right tabular-nums">{fmt(item.total_cost)}</td>
                                    <td className="py-2">
                                      <div
                                        onClick={(e) => { e.stopPropagation(); toggleProductSelection(item.product_name); }}
                                        className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${isSelected ? 'bg-blue-600 border-blue-600' : 'border-gray-300 hover:border-blue-400'}`}
                                      >
                                        {isSelected && <Check className="w-3 h-3 text-white" />}
                                      </div>
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                            <tfoot>
                              <tr className="border-t-2">
                                <td className="py-2" />
                                <td className="py-2 text-sm text-teal-700">סה&quot;כ</td>
                                <td className="py-2 text-right text-sm text-teal-700 tabular-nums">
                                  {fmtQty((catDrill.data?.items || []).reduce((s: number, i: any) => s + (i.total_quantity || 0), 0))}
                                </td>
                                <td className="py-2" />
                                <td className="py-2 text-right text-sm text-teal-700 tabular-nums">
                                  {fmt((catDrill.data?.items || []).reduce((s: number, i: any) => s + (i.total_cost || 0), 0))}
                                </td>
                              </tr>
                            </tfoot>
                          </table>
                        </div>
                        {selectedProducts.length === 0 && (
                          <p className="text-xs text-gray-400 mt-3 text-center">
                            Tap rows to select products, then compare their monthly trends
                          </p>
                        )}
                      </>
                    )}
                  </div>
                ) : catDrill.level === 5 ? (
                  /* ─── Level 5: Multi-product monthly comparison ─── */
                  <div>
                    {(catDrill.data?.series || []).length === 0 ? (
                      <p className="text-center py-8 text-gray-400">No monthly data for selected products</p>
                    ) : (
                      <>
                        {/* Multi-line chart */}
                        <div className="h-64 mb-4">
                          <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                            <LineChart data={buildProductComparisonData()}>
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis dataKey="month_name" tick={{ fontSize: 12 }} />
                              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)} />
                              <Tooltip formatter={(val: any) => fmtQty(Number(val))} />
                              <Legend />
                              {(catDrill.data?.series || []).map((product: any, idx: number) => (
                                <Line
                                  key={product.product_name}
                                  type="monotone"
                                  dataKey={`qty_${product.product_name}`}
                                  stroke={PRODUCT_COLORS[idx % PRODUCT_COLORS.length]}
                                  strokeWidth={2}
                                  dot={{ r: 4 }}
                                  name={product.product_name}
                                />
                              ))}
                            </LineChart>
                          </ResponsiveContainer>
                        </div>

                        {/* Per-product tables */}
                        {(catDrill.data?.series || []).map((product: any, pIdx: number) => (
                          <div key={product.product_name} className="mb-4">
                            <div className="flex items-center gap-2 mb-2">
                              <div
                                className="w-3 h-3 rounded-full"
                                style={{ backgroundColor: PRODUCT_COLORS[pIdx % PRODUCT_COLORS.length] }}
                              />
                              <span className="font-medium text-sm">{product.product_name}</span>
                            </div>
                            <div className="overflow-x-auto">
                              <table className="w-full text-sm">
                                <thead>
                                  <tr className="border-b text-left text-gray-500">
                                    <th className="pb-1 font-medium text-xs">Month</th>
                                    <th className="pb-1 font-medium text-xs text-right">Qty</th>
                                    <th className="pb-1 font-medium text-xs text-right">Avg Price</th>
                                    <th className="pb-1 font-medium text-xs text-right">Total</th>
                                    <th className="pb-1 font-medium text-xs text-right">Orders</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {product.months.map((m: any, i: number) => (
                                    <tr key={i} className="border-b last:border-0">
                                      <td className="py-1.5">{m.month_name}</td>
                                      <td className="py-1.5 text-right text-gray-600 tabular-nums">{fmtQty(m.total_quantity)}</td>
                                      <td className="py-1.5 text-right text-gray-600 tabular-nums">{fmt(m.avg_price)}</td>
                                      <td className="py-1.5 text-right tabular-nums">{fmt(m.total_cost)}</td>
                                      <td className="py-1.5 text-right text-gray-500">{m.order_count}</td>
                                    </tr>
                                  ))}
                                </tbody>
                                <tfoot>
                                  <tr className="border-t">
                                    <td className="py-1.5 text-sm text-teal-700">סה&quot;כ</td>
                                    <td className="py-1.5 text-right text-sm text-teal-700 tabular-nums">
                                      {fmtQty(product.months.reduce((s: number, m: any) => s + (m.total_quantity || 0), 0))}
                                    </td>
                                    <td className="py-1.5" />
                                    <td className="py-1.5 text-right text-sm text-teal-700 tabular-nums">
                                      {fmt(product.months.reduce((s: number, m: any) => s + (m.total_cost || 0), 0))}
                                    </td>
                                    <td className="py-1.5 text-right text-sm text-teal-700">
                                      {product.months.reduce((s: number, m: any) => s + (m.order_count || 0), 0)}
                                    </td>
                                  </tr>
                                </tfoot>
                              </table>
                            </div>
                          </div>
                        ))}
                      </>
                    )}
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </div>
        )}

        {/* ═══════ Chart Drill-down Modal (cost/meals) ═══════ */}
        {drillDown && (
          <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setDrillDown(null)}>
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-sm md:max-w-2xl max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
              <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between rounded-t-xl">
                <div className="flex items-center gap-2">
                  {drillDown.type === 'meals' && (drillDown.level || 1) > 1 && (
                    <button onClick={goBackMealDrill} className="p-1 hover:bg-gray-100 rounded">
                      <ArrowLeft className="w-5 h-5" />
                    </button>
                  )}
                  <div>
                    <h3 className="text-lg font-semibold">
                      {drillDown.type === 'cost' ? 'Cost Breakdown' : drillDown.level === 2 ? 'Categories' : 'Meals by Site'} — {drillDown.label}
                    </h3>
                    {drillDown.type === 'meals' && (drillDown.level || 1) === 1 && (
                      <p className="text-xs text-gray-500">Click a site to see category breakdown</p>
                    )}
                  </div>
                </div>
                <button onClick={() => setDrillDown(null)} className="p-1 hover:bg-gray-100 rounded">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="p-6">
                {drillDown.loading ? (
                  <p className="text-center text-gray-500 py-8">Loading...</p>
                ) : drillDown.type === 'cost' ? (
                  <div>
                    {drillDown.data?.items?.length > 0 ? (
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b text-left">
                              <th className="pb-2 font-medium text-gray-600">Product</th>
                              <th className="pb-2 font-medium text-gray-600 text-right">Qty</th>
                              <th className="pb-2 font-medium text-gray-600 text-right">Total Spent</th>
                              <th className="pb-2 font-medium text-gray-600 text-right">Orders</th>
                            </tr>
                          </thead>
                          <tbody>
                            {drillDown.data.items.map((item: any, idx: number) => (
                              <tr key={idx} className="border-b last:border-b-0">
                                <td className="py-2">{item.product_name}</td>
                                <td className="py-2 text-right tabular-nums">{fmtQty(item.total_quantity)}</td>
                                <td className="py-2 text-right font-medium tabular-nums">{fmt(item.total_spent)}</td>
                                <td className="py-2 text-right text-gray-500">{item.order_count ?? 0}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="text-center text-gray-500 py-8">No cost data for this month</p>
                    )}
                  </div>
                ) : (drillDown.level || 1) === 1 ? (
                  <div>
                    {drillDown.data?.items?.length > 0 ? (
                      <>
                        <div className="grid grid-cols-2 gap-4 mb-4">
                          <div className="bg-blue-50 rounded-lg p-3 text-center">
                            <p className="text-2xl font-bold text-blue-700">{fmtQty(drillDown.data.total_meals)}</p>
                            <p className="text-xs text-blue-600">Total Meals</p>
                          </div>
                          <div className="bg-purple-50 rounded-lg p-3 text-center">
                            <p className="text-2xl font-bold text-purple-700">{fmt(drillDown.data.total_cost)}</p>
                            <p className="text-xs text-purple-600">Total Cost</p>
                          </div>
                        </div>
                        <div className="space-y-2">
                          {drillDown.data.items.map((item: any, idx: number) => (
                            <button
                              key={idx}
                              onClick={() => drillMealIntoCategories(item.site_id, item.site_name)}
                              className="w-full flex items-center justify-between p-3 rounded-lg border hover:bg-blue-50 transition-colors text-left"
                            >
                              <div>
                                <p className="font-medium text-gray-900">{item.site_name}</p>
                                <p className="text-xs text-gray-500">{fmtQty(item.meal_count)} meals · {fmt(item.cost)}</p>
                              </div>
                              <ChevronRight className="w-4 h-4 text-gray-400" />
                            </button>
                          ))}
                        </div>
                      </>
                    ) : (
                      <p className="text-center text-gray-500 py-8">No meal data for this month</p>
                    )}
                  </div>
                ) : (
                  <div>
                    {drillDown.data?.items?.length > 0 ? (
                      <>
                        <div className="grid grid-cols-2 gap-4 mb-4">
                          <div className="bg-green-50 rounded-lg p-3 text-center">
                            <p className="text-2xl font-bold text-green-700">{fmtQty(drillDown.data.total_quantity)}</p>
                            <p className="text-xs text-green-600">Total Quantity</p>
                          </div>
                          <div className="bg-purple-50 rounded-lg p-3 text-center">
                            <p className="text-2xl font-bold text-purple-700">{fmt(drillDown.data.total_cost)}</p>
                            <p className="text-xs text-purple-600">Total Cost</p>
                          </div>
                        </div>
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="border-b text-left">
                                <th className="pb-2 font-medium text-gray-600">Category</th>
                                <th className="pb-2 font-medium text-gray-600 text-right">Qty</th>
                                <th className="pb-2 font-medium text-gray-600 text-right">Cost</th>
                                <th className="pb-2 font-medium text-gray-600 text-right">% of Total</th>
                              </tr>
                            </thead>
                            <tbody>
                              {drillDown.data.items.map((item: any, idx: number) => (
                                <tr key={idx} className="border-b last:border-b-0">
                                  <td className="py-2">
                                    <div className="flex items-center gap-2">
                                      <div
                                        className="w-3 h-3 rounded-full shrink-0"
                                        style={{ backgroundColor: CATEGORY_COLORS[item.category] || '#d1d5db' }}
                                      />
                                      <span>{item.display_he}</span>
                                    </div>
                                  </td>
                                  <td className="py-2 text-right tabular-nums">{fmtQty(item.quantity)}</td>
                                  <td className="py-2 text-right font-medium tabular-nums">{fmt(item.cost)}</td>
                                  <td className="py-2 text-right text-gray-500">
                                    {drillDown.data.total_cost > 0 ? Math.round((item.cost ?? 0) / drillDown.data.total_cost * 100) : 0}%
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </>
                    ) : (
                      <p className="text-center text-gray-500 py-8">No category data for this site</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── Vending Machines (מ.א אוטומטים) Section ── */}
        <VendingSection />
      </main>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// Vending Machines analytics panel (מ.א אוטומטים)
// ═══════════════════════════════════════════════════════════════════════

function VendingSection() {
  const [year, setYear] = useState<number>(new Date().getFullYear());
  const [month, setMonth] = useState<number | ''>('');
  const [siteId, setSiteId] = useState<number | ''>('');
  const [shift, setShift] = useState<string>('all');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [productDetail, setProductDetail] = useState<any>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set('year', String(year));
      if (month) params.set('month', String(month));
      if (siteId) params.set('site_id', String(siteId));
      if (shift && shift !== 'all') params.set('shift', shift);
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/vending/analytics?${params}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
      });
      setData(res.ok ? await res.json() : null);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [year, month, siteId, shift]);

  useEffect(() => { load(); }, [load]);

  const loadProductTrend = async (productName: string) => {
    const params = new URLSearchParams();
    params.set('product_name', productName);
    params.set('year', String(year));
    if (siteId) params.set('site_id', String(siteId));
    if (shift && shift !== 'all') params.set('shift', shift);
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/vending/product-trend?${params}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
    });
    setProductDetail(res.ok ? await res.json() : null);
  };

  return (
    <div className="mt-8">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <CardTitle className="text-xl">מ.א אוטומטים — Vending Machines</CardTitle>
              <p className="text-sm text-muted-foreground mt-1">Monthly consumption, top products, per-machine usage</p>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={async () => {
                  const params = new URLSearchParams({ year: String(year) });
                  if (siteId) params.set('site_id', String(siteId));
                  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/vending/reprice?${params}`, {
                    method: 'POST',
                    headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
                  });
                  const data = await res.json().catch(() => ({}));
                  alert(`Repriced ${data.updated || 0} of ${data.scanned || 0} transactions.`);
                  load();
                }}
              >Reprice</Button>
              <Button onClick={() => setShowUpload(true)} size="sm">Upload invoice + consumption</Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <label>Year:
              <select value={year} onChange={(e) => setYear(parseInt(e.target.value))} className="ml-1 border rounded px-2 py-1">
                {[2024, 2025, 2026, 2027].map((y) => <option key={y} value={y}>{y}</option>)}
              </select>
            </label>
            <label>Month:
              <select value={month} onChange={(e) => setMonth(e.target.value ? parseInt(e.target.value) : '')} className="ml-1 border rounded px-2 py-1">
                <option value="">All</option>
                {[1,2,3,4,5,6,7,8,9,10,11,12].map((m) => <option key={m} value={m}>{MONTH_NAMES_SHORT[m]}</option>)}
              </select>
            </label>
            <label>Site:
              <select value={siteId} onChange={(e) => setSiteId(e.target.value ? parseInt(e.target.value) : '')} className="ml-1 border rounded px-2 py-1">
                <option value="">All</option>
                <option value="1">Nes Ziona</option>
                <option value="2">Kiryat Gat</option>
              </select>
            </label>
            <label>Shift:
              <select value={shift} onChange={(e) => setShift(e.target.value)} className="ml-1 border rounded px-2 py-1">
                <option value="all">All</option>
                <option value="day">Day</option>
                <option value="evening">Evening</option>
              </select>
            </label>
          </div>

          {loading ? (
            <p className="text-center text-gray-400 py-8 text-sm">Loading…</p>
          ) : !data || (data.total_qty === 0 && data.top_products.length === 0) ? (
            <div className="text-center text-gray-500 py-10 space-y-2">
              <p>No vending data yet for this period.</p>
              <p className="text-xs">Upload an invoice PDF + consumption Excel to populate this section.</p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <div className="rounded-xl border p-4 bg-gradient-to-br from-indigo-50 to-white">
                  <p className="text-xs text-indigo-700 font-semibold">TOTAL QTY</p>
                  <p className="text-2xl font-bold tabular-nums mt-1">{fmtQty(data.total_qty)}</p>
                </div>
                <div className="rounded-xl border p-4 bg-gradient-to-br from-emerald-50 to-white">
                  <p className="text-xs text-emerald-700 font-semibold">TOTAL COST</p>
                  <p className="text-2xl font-bold tabular-nums mt-1">{fmt(data.total_cost)}</p>
                </div>
                <div className="rounded-xl border p-4 bg-gradient-to-br from-amber-50 to-white">
                  <p className="text-xs text-amber-700 font-semibold">PRODUCTS</p>
                  <p className="text-2xl font-bold tabular-nums mt-1">{(data.top_products || []).length}</p>
                </div>
              </div>

              {/* Monthly trend */}
              <div>
                <h4 className="text-sm font-semibold mb-2">Monthly trend</h4>
                <div className="h-60">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data.monthly}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                      <XAxis dataKey="month_name" tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} />
                      <Tooltip formatter={(v: any, n: any) => n === 'cost' ? fmt(Number(v)) : fmtQty(Number(v))} />
                      <Bar dataKey="qty" fill="#6366f1" name="Qty" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Top products */}
              <div>
                <h4 className="text-sm font-semibold mb-2">Top products (click for trend)</h4>
                <div className="space-y-1 max-h-80 overflow-auto">
                  {(data.top_products || []).map((p: any) => (
                    <button
                      key={p.product_name}
                      onClick={() => loadProductTrend(p.product_name)}
                      className="w-full text-left flex items-center justify-between p-2.5 rounded-lg border bg-gray-50/50 hover:bg-indigo-50 hover:border-indigo-300 transition"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate">{p.product_name}</p>
                        {p.category && <p className="text-xs text-gray-500 truncate">Category: {p.category}</p>}
                      </div>
                      <div className="text-right ml-3 flex-shrink-0">
                        <p className="text-sm font-bold tabular-nums">{fmtQty(p.qty)}</p>
                        <p className="text-xs text-gray-500 tabular-nums">{fmt(p.cost)}</p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Machines (only if data) */}
              {(data.machines || []).length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold mb-2">Per-machine usage</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                    {data.machines.map((m: any) => (
                      <div key={m.machine_id} className="rounded-lg border p-2.5 bg-gray-50/50">
                        <p className="text-xs text-gray-600">Machine {m.machine_id}</p>
                        <p className="text-sm font-bold tabular-nums">{fmtQty(m.qty)} units</p>
                        <p className="text-xs text-gray-500 tabular-nums">{fmt(m.cost)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {showUpload && <VendingUploadModal onClose={() => setShowUpload(false)} onUploaded={() => { setShowUpload(false); load(); }} />}
      {productDetail && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setProductDetail(null)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[85vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="border-b px-5 py-3 flex items-center justify-between sticky top-0 bg-white">
              <h3 className="font-semibold">{productDetail.product_name}</h3>
              <button onClick={() => setProductDetail(null)} className="text-gray-400 hover:text-gray-700 text-xl">×</button>
            </div>
            <div className="p-5">
              <div className="h-60">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={productDetail.monthly}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                    <XAxis dataKey="month_name" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v: any) => fmtQty(Number(v))} />
                    <Bar dataKey="qty" fill="#6366f1" name="Qty" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function VendingUploadModal({ onClose, onUploaded }: { onClose: () => void; onUploaded: () => void }) {
  const [siteId, setSiteId] = useState<number>(1);
  const [shift, setShift] = useState<string>('all');
  const [pdf, setPdf] = useState<File | null>(null);
  const [xlsx, setXlsx] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const upload = async () => {
    setUploading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.set('site_id', String(siteId));
      fd.set('shift', shift);
      if (pdf) fd.set('invoice_pdf', pdf);
      if (xlsx) fd.set('consumption_xlsx', xlsx);
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/vending/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
        body: fd,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      setResult(await res.json());
    } catch (e: any) {
      setError(e.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl max-w-xl w-full max-h-[90vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
        <div className="border-b px-5 py-3 flex items-center justify-between sticky top-0 bg-white">
          <h3 className="font-semibold">Upload Vending Invoice + Consumption</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-xl">×</button>
        </div>
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <label className="text-sm">
              <span className="block text-gray-600 mb-1">Site</span>
              <select value={siteId} onChange={(e) => setSiteId(parseInt(e.target.value))} className="w-full border rounded-lg px-3 py-2">
                <option value={1}>Nes Ziona</option>
                <option value={2}>Kiryat Gat</option>
              </select>
            </label>
            <label className="text-sm">
              <span className="block text-gray-600 mb-1">Shift</span>
              <select value={shift} onChange={(e) => setShift(e.target.value)} className="w-full border rounded-lg px-3 py-2">
                <option value="all">All (no split)</option>
                <option value="day">Day</option>
                <option value="evening">Evening</option>
              </select>
            </label>
          </div>
          <label className="text-sm block">
            <span className="block text-gray-600 mb-1">Invoice PDF (prices + totals)</span>
            <input type="file" accept=".pdf" onChange={(e) => setPdf(e.target.files?.[0] || null)} className="w-full text-sm" />
          </label>
          <label className="text-sm block">
            <span className="block text-gray-600 mb-1">Consumption Excel (DataSheet — date + product + qty)</span>
            <input type="file" accept=".xlsx,.xls" onChange={(e) => setXlsx(e.target.files?.[0] || null)} className="w-full text-sm" />
          </label>
          <div className="text-xs text-gray-500 bg-gray-50 border rounded-lg p-2.5 leading-relaxed">
            <p className="font-semibold mb-1">Upload guide</p>
            <ul className="space-y-0.5 pl-4 list-disc">
              <li><b>NZ:</b> one upload — PDF + Excel, shift = All</li>
              <li><b>KG day:</b> upload KG day PDF + Excel together, shift = Day</li>
              <li><b>KG evening:</b> upload evening PDF alone, shift = Evening</li>
              <li>If you upload Excel alone, existing invoices for the same month are used for pricing</li>
            </ul>
          </div>
          {error && <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-2">{error}</p>}
          {result && (
            <div className="text-sm bg-emerald-50 border border-emerald-200 rounded-lg p-3 space-y-1">
              <p className="font-medium text-emerald-900">Upload successful</p>
              <p>Invoice items: <b>{result.invoice_items}</b></p>
              <p>Transactions saved: <b>{result.transactions_saved}</b> (priced: <b>{result.transactions_priced}</b>)</p>
              <p>Total amount: <b>{fmt(result.total_amount)}</b></p>
            </div>
          )}
          <div className="flex justify-end gap-2 pt-2 border-t">
            <Button variant="outline" onClick={onClose}>Close</Button>
            <Button onClick={upload} disabled={uploading || (!pdf && !xlsx)}>
              {uploading ? 'Uploading…' : 'Upload'}
            </Button>
            {result && <Button onClick={onUploaded}>Done</Button>}
          </div>
        </div>
      </div>
    </div>
  );
}
