'use client';

import { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import {
  TrendingUp, Calendar, DollarSign, Utensils,
  AlertTriangle, FileText, BarChart3
} from 'lucide-react';
import { historicalAPI } from '@/lib/api';
import { X, ArrowLeft } from 'lucide-react';
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

function parseMonthLabel(label: string): { month: number; year: number } | null {
  const parts = label.split(' ');
  if (parts.length === 2) {
    const month = MONTH_MAP[parts[0]];
    const year = parseInt(parts[1]);
    if (month && year) return { month, year };
  }
  return null;
}

export default function AnalyticsPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Drill-down state
  const [drillDown, setDrillDown] = useState<{
    type: string;
    label: string;
    data: any;
    loading: boolean;
  } | null>(null);

  useEffect(() => {
    loadAnalytics();
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

    setDrillDown({ type: 'meals', label: monthLabel, data: null, loading: true });
    try {
      const result = await historicalAPI.drillDownMeals({ month: parsed.month, year: parsed.year });
      setDrillDown((prev) => prev ? { ...prev, data: result, loading: false } : null);
    } catch {
      setDrillDown((prev) => prev ? { ...prev, data: { items: [] }, loading: false } : null);
    }
  };

  const fmt = (v: number) => v.toLocaleString('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 });

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

  // Extract dynamic site keys from meal trends for the chart
  const siteKeys = data.mealTrends?.length > 0
    ? Object.keys(data.mealTrends[0]).filter((k: string) => k !== 'month')
    : [];

  // Extract dynamic vendor keys from vendor series
  const vendorKeys = data.vendorSeries?.length > 0
    ? Object.keys(data.vendorSeries[0]).filter(
        (k: string) => !['month', 'total', 'ma_3m'].includes(k)
      )
    : [];

  return (
    <div>
      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-gray-900">Analytics & Insights</h2>
          <p className="text-gray-500 text-sm">
            Real data from database across all sites
          </p>
        </div>

        {/* Key Metrics from DB counts */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
          <Card className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Records</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">
                  {totalRecords.toLocaleString()}
                </p>
              </div>
              <BarChart3 className="w-7 h-7 text-blue-500" />
            </div>
          </Card>

          <Card className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Meal Records</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">
                  {(counts.meals || 0).toLocaleString()}
                </p>
              </div>
              <Utensils className="w-7 h-7 text-green-500" />
            </div>
          </Card>

          <Card className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Menu Checks</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">
                  {counts.menu_checks || 0}
                </p>
              </div>
              <FileText className="w-7 h-7 text-purple-500" />
            </div>
          </Card>

          <Card className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Proformas</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">
                  {counts.proformas || 0}
                </p>
              </div>
              <DollarSign className="w-7 h-7 text-orange-500" />
            </div>
          </Card>

          <Card className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Complaints</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">
                  {counts.complaints || 0}
                </p>
              </div>
              <AlertTriangle className="w-7 h-7 text-red-500" />
            </div>
          </Card>
        </div>

        {/* Charts Row 1 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Meal Trends */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Utensils className="w-5 h-5 text-green-600" />
                Meal Count Trends by Site
              </CardTitle>
            </CardHeader>
            <CardContent>
              {data.mealTrends?.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={data.mealTrends} onClick={handleMealClick} style={{ cursor: 'pointer' }}>
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

          {/* Cost Trends */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <DollarSign className="w-5 h-5 text-purple-600" />
                Cost per Meal (Trend)
              </CardTitle>
            </CardHeader>
            <CardContent>
              {data.costTrends?.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <ComposedChart data={data.costTrends} onClick={handleCostClick} style={{ cursor: 'pointer' }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" fontSize={12} />
                    <YAxis fontSize={12} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="total_cost" fill="#8b5cf6" name="Total Cost" opacity={0.3} />
                    <Line
                      type="monotone"
                      dataKey="avg_cost"
                      stroke="#8b5cf6"
                      name="Avg Cost/Meal"
                      strokeWidth={2}
                      dot={{ r: 4 }}
                    />
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
          {/* Complaint Categories */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-orange-600" />
                Complaints by Category
              </CardTitle>
            </CardHeader>
            <CardContent>
              {data.complaintCategories?.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={data.complaintCategories}
                      cx="50%"
                      cy="50%"
                      labelLine={true}
                      label={(entry: any) => `${entry.name} (${entry.value})`}
                      outerRadius={100}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {data.complaintCategories.map((_: any, index: number) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-gray-500 text-center py-12">No complaint data available</p>
              )}
            </CardContent>
          </Card>

          {/* Menu Compliance Findings */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-blue-600" />
                Menu Compliance Findings
              </CardTitle>
            </CardHeader>
            <CardContent>
              {data.menuFindings?.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={data.menuFindings}>
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

        {/* Vendor Spending - Full Width */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-green-600" />
              Vendor Spending with 3-Month Moving Average
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.vendorSeries?.length > 0 ? (
              <ResponsiveContainer width="100%" height={400}>
                <ComposedChart data={data.vendorSeries}>
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
                    type="monotone"
                    dataKey="ma_3m"
                    stroke="#ef4444"
                    name="3M Moving Avg"
                    strokeWidth={3}
                    dot={{ r: 5, fill: '#ef4444' }}
                    strokeDasharray="5 5"
                  />
                </ComposedChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-gray-500 text-center py-12">No vendor spending data available</p>
            )}
          </CardContent>
        </Card>

        {/* Vendor Totals */}
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
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={data.vendorTotals}
                      cx="50%"
                      cy="50%"
                      labelLine={true}
                      label={(entry: any) => `${entry.name}`}
                      outerRadius={100}
                      fill="#8884d8"
                      dataKey="value"
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

          {/* Record Counts Summary */}
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
                    <span className="text-gray-700 capitalize">
                      {label.replace(/_/g, ' ')}
                    </span>
                    <span className="text-xl font-bold text-gray-900">
                      {(count || 0).toLocaleString()}
                    </span>
                  </div>
                ))}
                <div className="flex justify-between items-center pt-2 border-t-2">
                  <span className="font-semibold text-gray-900">Total</span>
                  <span className="text-2xl font-bold text-blue-600">
                    {totalRecords.toLocaleString()}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
        {/* Drill-down Modal */}
        {drillDown && (
          <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setDrillDown(null)}>
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-sm md:max-w-2xl max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
              <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between rounded-t-xl">
                <h3 className="text-lg font-semibold">
                  {drillDown.type === 'cost' ? 'Cost Breakdown' : 'Meal Details'} — {drillDown.label}
                </h3>
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
                              <td className="py-2 text-right">{item.total_quantity?.toLocaleString()}</td>
                              <td className="py-2 text-right font-medium">{fmt(item.total_spent)}</td>
                              <td className="py-2 text-right text-gray-500">{item.order_count}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      </div>
                    ) : (
                      <p className="text-center text-gray-500 py-8">No cost data for this month</p>
                    )}
                  </div>
                ) : (
                  <div>
                    {drillDown.data?.items?.length > 0 ? (
                      <>
                        <div className="grid grid-cols-2 gap-4 mb-4">
                          <div className="bg-blue-50 rounded-lg p-3 text-center">
                            <p className="text-2xl font-bold text-blue-700">{drillDown.data.total_meals?.toLocaleString()}</p>
                            <p className="text-xs text-blue-600">Total Meals</p>
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
                              <th className="pb-2 font-medium text-gray-600">Date</th>
                              <th className="pb-2 font-medium text-gray-600">Site</th>
                              <th className="pb-2 font-medium text-gray-600 text-right">Meals</th>
                              <th className="pb-2 font-medium text-gray-600 text-right">Cost</th>
                            </tr>
                          </thead>
                          <tbody>
                            {drillDown.data.items.map((item: any, idx: number) => (
                              <tr key={idx} className="border-b last:border-b-0">
                                <td className="py-2">{item.date}</td>
                                <td className="py-2">{item.site_name}</td>
                                <td className="py-2 text-right">{item.meal_count}</td>
                                <td className="py-2 text-right">{item.cost ? fmt(item.cost) : '-'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        </div>
                      </>
                    ) : (
                      <p className="text-center text-gray-500 py-8">No meal data for this month</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
