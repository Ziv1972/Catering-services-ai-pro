'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DollarSign, FolderKanban, Wrench, CalendarDays,
  ListTodo, ArrowRight, MessageSquare, Send,
  AlertCircle, CheckCircle2, Clock,
  ChevronRight, ChevronDown, ArrowLeft, X,
} from 'lucide-react';
import { dashboardAPI, chatAPI, drillDownAPI } from '@/lib/api';
import { format } from 'date-fns';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid, Legend,
} from 'recharts';

export default function Dashboard() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<Array<{ role: string; text: string }>>([]);
  const [chatLoading, setChatLoading] = useState(false);

  // Drill-down state
  const [drillDown, setDrillDown] = useState<{
    type: string;
    level: number;
    context: any;
    data: any;
    loading: boolean;
  } | null>(null);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const result = await dashboardAPI.get();
      setData(result);
    } catch {
      // Sections will show empty states
    } finally {
      setLoading(false);
    }
  };

  const handleChat = async () => {
    if (!chatInput.trim()) return;
    const userMsg = chatInput;
    setChatMessages((prev) => [...prev, { role: 'user', text: userMsg }]);
    setChatInput('');
    setChatLoading(true);
    try {
      const result = await chatAPI.send(userMsg);
      setChatMessages((prev) => [...prev, { role: 'ai', text: result.response }]);
    } catch {
      setChatMessages((prev) => [...prev, { role: 'ai', text: 'Sorry, could not process your request.' }]);
    } finally {
      setChatLoading(false);
    }
  };

  const quickChat = async (prompt: string) => {
    setChatMessages((prev) => [...prev, { role: 'user', text: prompt }]);
    setChatLoading(true);
    try {
      const result = await chatAPI.send(prompt);
      setChatMessages((prev) => [...prev, { role: 'ai', text: result.response }]);
    } catch {
      setChatMessages((prev) => [...prev, { role: 'ai', text: 'Sorry, could not process your request.' }]);
    } finally {
      setChatLoading(false);
    }
  };

  // Drill-down handlers
  const openBudgetDrillDown = async (supplier_id?: number, site_id?: number, label?: string) => {
    setDrillDown({ type: 'budget', level: 1, context: { supplier_id, site_id, label }, data: null, loading: true });
    try {
      const result = await drillDownAPI.budget({ supplier_id, site_id });
      setDrillDown((prev) => prev ? { ...prev, data: result, loading: false } : null);
    } catch {
      setDrillDown((prev) => prev ? { ...prev, data: { items: [] }, loading: false } : null);
    }
  };

  const drillIntoProducts = async (month: number, monthName: string) => {
    if (!drillDown) return;
    const ctx = drillDown.context;
    setDrillDown((prev) => prev ? {
      ...prev,
      level: 2,
      context: { ...ctx, month, monthName },
      data: null,
      loading: true,
    } : null);
    try {
      const result = await drillDownAPI.products({
        supplier_id: ctx.supplier_id,
        site_id: ctx.site_id,
        month,
      });
      setDrillDown((prev) => prev ? { ...prev, data: result, loading: false } : null);
    } catch {
      setDrillDown((prev) => prev ? { ...prev, data: { items: [] }, loading: false } : null);
    }
  };

  const goBackDrillDown = () => {
    if (drillDown && drillDown.level > 1) {
      openBudgetDrillDown(drillDown.context.supplier_id, drillDown.context.site_id, drillDown.context.label);
    } else {
      setDrillDown(null);
    }
  };

  const openProjectDrillDown = async (projectId: number, projectName: string) => {
    setDrillDown({ type: 'project', level: 1, context: { label: projectName }, data: null, loading: true });
    try {
      const result = await drillDownAPI.project(projectId);
      setDrillDown((prev) => prev ? { ...prev, data: result, loading: false } : null);
    } catch {
      setDrillDown((prev) => prev ? { ...prev, data: null, loading: false } : null);
    }
  };

  const openMaintenanceDrillDown = async (siteId: number, siteName: string) => {
    setDrillDown({ type: 'maintenance', level: 1, context: { label: siteName }, data: null, loading: true });
    try {
      const result = await drillDownAPI.maintenance({ site_id: siteId });
      setDrillDown((prev) => prev ? { ...prev, data: result, loading: false } : null);
    } catch {
      setDrillDown((prev) => prev ? { ...prev, data: null, loading: false } : null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4" />
          <p className="text-gray-500">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  const budgetSummary = data?.budget_summary || [];
  const projects = data?.projects || [];
  const maintenance = data?.maintenance || [];
  const meetings = data?.meetings || [];
  const todos = data?.todos || { mine: [], delegated: [], overdue_count: 0 };
  const proformaCosts = data?.proforma_costs || [];
  const displayYear = data?.budget_year || new Date().getFullYear();
  const displayMonth = data?.display_month;

  const chartData = budgetSummary.map((b: any) => ({
    name: `${b.supplier_name}${b.shift && b.shift !== 'all' ? ` [${b.shift}]` : ''}\n(${b.site_name})`,
    budget: b.monthly_budget,
    actual: b.monthly_actual,
  }));

  const formatCurrency = (val: number) =>
    val.toLocaleString('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 });

  const getPriorityColor = (p: string) => {
    const colors: Record<string, string> = {
      urgent: 'bg-red-100 text-red-800',
      high: 'bg-orange-100 text-orange-800',
      medium: 'bg-blue-100 text-blue-800',
      low: 'bg-gray-100 text-gray-700',
    };
    return colors[p] || colors.medium;
  };

  const getStatusColor = (s: string) => {
    const colors: Record<string, string> = {
      planning: 'bg-purple-100 text-purple-800',
      active: 'bg-green-100 text-green-800',
      on_hold: 'bg-yellow-100 text-yellow-800',
      completed: 'bg-blue-100 text-blue-800',
    };
    return colors[s] || 'bg-gray-100 text-gray-700';
  };

  return (
    <main className="max-w-7xl mx-auto px-4 py-6">
      {/* Drill-down overlay */}
      {drillDown && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <Card className="w-full max-w-sm md:max-w-2xl lg:max-w-3xl max-h-[80vh] overflow-auto">
            <CardHeader className="pb-2 sticky top-0 bg-white z-10 border-b">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {drillDown.level > 1 && (
                    <Button variant="ghost" size="sm" onClick={goBackDrillDown}>
                      <ArrowLeft className="w-4 h-4" />
                    </Button>
                  )}
                  <div>
                    <CardTitle className="text-lg">
                      {drillDown.type === 'budget' && drillDown.level === 1
                        ? `Monthly Spending ${drillDown.context.label ? `- ${drillDown.context.label}` : ''}`
                        : drillDown.type === 'budget' && drillDown.level === 2
                        ? `Products - ${drillDown.context.monthName}`
                        : drillDown.type === 'project'
                        ? `Project: ${drillDown.context.label}`
                        : drillDown.type === 'maintenance'
                        ? `Maintenance: ${drillDown.context.label}`
                        : 'Details'}
                    </CardTitle>
                    <p className="text-sm text-gray-500">
                      {drillDown.type === 'budget' && drillDown.level === 1 ? 'Click a month to see product breakdown'
                        : drillDown.type === 'budget' ? 'Product-level spending detail'
                        : drillDown.type === 'project' ? 'Tasks and progress'
                        : drillDown.type === 'maintenance' ? 'Expense breakdown'
                        : ''}
                    </p>
                  </div>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setDrillDown(null)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="pt-4">
              {drillDown.loading ? (
                <div className="text-center py-12 text-gray-400">Loading...</div>
              ) : drillDown.type === 'budget' && drillDown.level === 1 ? (
                <>
                  {/* Monthly spending chart */}
                  <div className="h-64 mb-4">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={drillDown.data?.items || []}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="month_name" tick={{ fontSize: 12 }} />
                        <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`} />
                        <Tooltip formatter={(val: any) => formatCurrency(Number(val))} />
                        <Bar dataKey="total" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Spending" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  {/* Monthly table */}
                  <div className="space-y-1">
                    {(drillDown.data?.items || []).map((item: any) => (
                      <div
                        key={item.month}
                        onClick={() => drillIntoProducts(item.month, item.month_name)}
                        className="flex items-center justify-between p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-blue-50 transition-colors"
                      >
                        <div>
                          <span className="font-medium">{item.month_name}</span>
                          <span className="text-xs text-gray-500 ml-2">{item.invoice_count} invoices</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="font-semibold">{formatCurrency(item.total)}</span>
                          <ChevronRight className="w-4 h-4 text-gray-400" />
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              ) : drillDown.type === 'budget' && drillDown.level === 2 ? (
                /* Product breakdown */
                <div className="space-y-1">
                  {(drillDown.data?.items || []).length === 0 ? (
                    <p className="text-center py-8 text-gray-400">No product data for this month</p>
                  ) : (
                    <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-left text-gray-500">
                          <th className="pb-2 font-medium">Product</th>
                          <th className="pb-2 font-medium text-right">Quantity</th>
                          <th className="pb-2 font-medium text-right">Total</th>
                          <th className="pb-2 font-medium text-right">Orders</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(drillDown.data?.items || []).slice(0, 50).map((item: any, i: number) => (
                          <tr key={i} className="border-b last:border-0">
                            <td className="py-2 font-medium">{item.product_name}</td>
                            <td className="py-2 text-right text-gray-600">{item.total_quantity?.toLocaleString()}</td>
                            <td className="py-2 text-right font-mono">{formatCurrency(item.total_spent)}</td>
                            <td className="py-2 text-right text-gray-500">{item.order_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    </div>
                  )}
                </div>
              ) : drillDown.type === 'project' ? (
                /* Project drill-down */
                <div>
                  {!drillDown.data ? (
                    <p className="text-center py-8 text-gray-400">No project data available</p>
                  ) : (
                    <>
                      {drillDown.data.description && (
                        <p className="text-sm text-gray-600 mb-4">{drillDown.data.description}</p>
                      )}
                      <div className="flex items-center gap-3 mb-4">
                        <Badge className={getStatusColor(drillDown.data.status)}>{drillDown.data.status}</Badge>
                        {drillDown.data.site_name && <Badge variant="outline">{drillDown.data.site_name}</Badge>}
                        <span className="text-sm text-gray-500">
                          {drillDown.data.done_count}/{drillDown.data.task_count} tasks done
                        </span>
                      </div>
                      <div className="h-2 bg-gray-200 rounded-full mb-4">
                        <div
                          className="h-2 bg-purple-500 rounded-full"
                          style={{ width: `${drillDown.data.task_count > 0 ? Math.round(drillDown.data.done_count / drillDown.data.task_count * 100) : 0}%` }}
                        />
                      </div>
                      <div className="space-y-2">
                        {(drillDown.data.tasks || []).map((t: any) => (
                          <div key={t.id} className={`flex items-center gap-3 p-3 rounded-lg ${t.status === 'done' ? 'bg-gray-50 opacity-60' : 'bg-gray-50'}`}>
                            {t.status === 'done' ? (
                              <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />
                            ) : t.status === 'in_progress' ? (
                              <Clock className="w-4 h-4 text-blue-500 shrink-0" />
                            ) : (
                              <div className="w-4 h-4 rounded-full border-2 border-gray-300 shrink-0" />
                            )}
                            <div className="flex-1">
                              <span className={`text-sm font-medium ${t.status === 'done' ? 'line-through text-gray-400' : ''}`}>
                                {t.title}
                              </span>
                              {t.assigned_to && (
                                <span className="text-xs text-gray-500 ml-2">({t.assigned_to})</span>
                              )}
                            </div>
                            <Badge variant="outline" className="text-xs">{t.status}</Badge>
                          </div>
                        ))}
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-4"
                        onClick={() => { setDrillDown(null); router.push(`/projects/${drillDown.data.id}`); }}
                      >
                        Open Full Project <ArrowRight className="w-3 h-3 ml-1" />
                      </Button>
                    </>
                  )}
                </div>
              ) : drillDown.type === 'maintenance' ? (
                /* Maintenance drill-down */
                <div>
                  {!drillDown.data || (drillDown.data.expenses || []).length === 0 ? (
                    <p className="text-center py-8 text-gray-400">No maintenance expenses recorded</p>
                  ) : (
                    <>
                      {drillDown.data.budget_amount > 0 && (
                        <div className="mb-4 p-3 bg-amber-50 rounded-lg">
                          <div className="flex justify-between text-sm mb-1">
                            <span>Budget: {formatCurrency(drillDown.data.budget_amount)}</span>
                            <span>Spent: {formatCurrency(drillDown.data.total_spent)}</span>
                          </div>
                          <div className="h-2 bg-gray-200 rounded-full">
                            <div
                              className={`h-2 rounded-full ${
                                drillDown.data.total_spent / drillDown.data.budget_amount > 0.9 ? 'bg-red-500' :
                                drillDown.data.total_spent / drillDown.data.budget_amount > 0.7 ? 'bg-amber-500' : 'bg-green-500'
                              }`}
                              style={{ width: `${Math.min((drillDown.data.total_spent / drillDown.data.budget_amount) * 100, 100)}%` }}
                            />
                          </div>
                        </div>
                      )}
                      <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b text-left text-gray-500">
                            <th className="pb-2 font-medium">Date</th>
                            <th className="pb-2 font-medium">Description</th>
                            <th className="pb-2 font-medium">Category</th>
                            <th className="pb-2 font-medium text-right">Amount</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(drillDown.data.expenses || []).map((exp: any) => (
                            <tr key={exp.id} className="border-b last:border-0">
                              <td className="py-2 text-gray-500">{exp.date}</td>
                              <td className="py-2 font-medium">{exp.description}</td>
                              <td className="py-2">
                                <Badge variant="secondary" className="text-xs">{exp.category}</Badge>
                              </td>
                              <td className="py-2 text-right font-mono">{formatCurrency(exp.amount)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-4"
                        onClick={() => { setDrillDown(null); router.push('/maintenance'); }}
                      >
                        Open Maintenance <ArrowRight className="w-3 h-3 ml-1" />
                      </Button>
                    </>
                  )}
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ═══════ ROW 1: Budget vs Actual ═══════ */}
      <Card className="mb-6 border-l-4 border-l-blue-500">
        <CardHeader className="pb-2">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-50 rounded-lg">
                <DollarSign className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <CardTitle className="text-lg">Budget vs Actual ({displayYear})</CardTitle>
                <p className="text-sm text-gray-500">
                  Supplier spending &middot; click a row to drill down
                </p>
              </div>
            </div>
            <Button variant="ghost" size="sm" onClick={() => router.push('/budget')}>
              View All <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {budgetSummary.length === 0 && proformaCosts.length === 0 ? (
            <p className="text-gray-400 text-center py-6">
              No budget data configured. <span className="underline cursor-pointer" onClick={() => router.push('/budget')}>Set up budgets</span>
            </p>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="space-y-3">
                {budgetSummary.map((b: any, i: number) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-blue-50 cursor-pointer transition-colors"
                    onClick={(e) => {
                      e.stopPropagation();
                      openBudgetDrillDown(b.supplier_id, b.site_id, `${b.supplier_name} (${b.site_name})`);
                    }}
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-1.5">
                        <p className="font-medium text-sm">{b.supplier_name}</p>
                        {b.shift && b.shift !== 'all' && (
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${b.shift === 'night' ? 'bg-indigo-100 text-indigo-700' : 'bg-yellow-100 text-yellow-700'}`}>
                            {b.shift === 'night' ? 'Night' : 'Day'}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500">{b.site_name}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-semibold">
                        {formatCurrency(b.monthly_actual)} / {formatCurrency(b.monthly_budget)}
                      </p>
                      <div className="w-20 sm:w-24 md:w-32 h-2 bg-gray-200 rounded-full mt-1">
                        <div
                          className={`h-2 rounded-full ${
                            b.monthly_percent > 90 ? 'bg-red-500' :
                            b.monthly_percent > 70 ? 'bg-yellow-500' : 'bg-green-500'
                          }`}
                          style={{ width: `${Math.min(b.monthly_percent, 100)}%` }}
                        />
                      </div>
                      <p className="text-xs text-gray-500 mt-0.5">{b.monthly_percent}%</p>
                    </div>
                  </div>
                ))}

                {/* Proforma actual costs from FoodHouse */}
                {proformaCosts.length > 0 && budgetSummary.length === 0 && (
                  <div className="p-3 bg-amber-50 rounded-lg border border-amber-200">
                    <p className="text-sm font-medium text-amber-800 mb-2">FoodHouse Actual Costs ({displayYear})</p>
                    {proformaCosts.map((pc: any, i: number) => (
                      <div key={i} className="flex justify-between text-sm">
                        <span>Site {pc.site_id} ({pc.count} invoices)</span>
                        <span className="font-mono font-medium">{formatCurrency(pc.total)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {chartData.length > 0 && (
                <div className="h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData}>
                      <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`} />
                      <Tooltip formatter={(val: any) => formatCurrency(Number(val))} />
                      <Bar dataKey="budget" fill="#93c5fd" name="Budget" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="actual" fill="#3b82f6" name="Actual" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ═══════ ROW 2: Projects + Maintenance ═══════ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <Card
          className="hover:shadow-lg transition-shadow cursor-pointer border-l-4 border-l-purple-500"
          onClick={() => router.push('/projects')}
        >
          <CardHeader className="pb-2">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-50 rounded-lg">
                  <FolderKanban className="w-5 h-5 text-purple-600" />
                </div>
                <div>
                  <CardTitle className="text-lg">Active Projects</CardTitle>
                  <p className="text-sm text-gray-500">{projects.length} ongoing</p>
                </div>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-400" />
            </div>
          </CardHeader>
          <CardContent>
            {projects.length === 0 ? (
              <p className="text-gray-400 text-center py-6">No active projects. Click to create one.</p>
            ) : (
              <div className="space-y-3">
                {projects.map((p: any) => (
                  <div
                    key={p.id}
                    className="p-3 bg-gray-50 rounded-lg hover:bg-purple-50 cursor-pointer transition-colors"
                    onClick={(e) => { e.stopPropagation(); openProjectDrillDown(p.id, p.name); }}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium text-sm">{p.name}</span>
                      <Badge className={getStatusColor(p.status)}>{p.status}</Badge>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="flex-1 h-2 bg-gray-200 rounded-full">
                        <div
                          className="h-2 bg-purple-500 rounded-full transition-all"
                          style={{ width: `${p.progress}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500 whitespace-nowrap">
                        {p.done_count}/{p.task_count} tasks
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card
          className="hover:shadow-lg transition-shadow cursor-pointer border-l-4 border-l-amber-500"
          onClick={() => router.push('/maintenance')}
        >
          <CardHeader className="pb-2">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-amber-50 rounded-lg">
                  <Wrench className="w-5 h-5 text-amber-600" />
                </div>
                <div>
                  <CardTitle className="text-lg">Maintenance Budget</CardTitle>
                  <p className="text-sm text-gray-500">Q{data?.current_quarter} {data?.current_year}</p>
                </div>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-400" />
            </div>
          </CardHeader>
          <CardContent>
            {maintenance.length === 0 ? (
              <p className="text-gray-400 text-center py-6">No quarterly budgets set. Click to configure.</p>
            ) : (
              <div className="space-y-3">
                {maintenance.map((m: any, i: number) => (
                  <div
                    key={i}
                    className="p-3 bg-gray-50 rounded-lg hover:bg-amber-50 cursor-pointer transition-colors"
                    onClick={(e) => { e.stopPropagation(); openMaintenanceDrillDown(m.id, m.site_name); }}
                  >
                    <div className="flex justify-between items-center mb-2">
                      <span className="font-medium text-sm">{m.site_name}</span>
                      <span className="text-sm">{formatCurrency(m.actual)} / {formatCurrency(m.budget)}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="flex-1 h-3 bg-gray-200 rounded-full">
                        <div
                          className={`h-3 rounded-full transition-all ${
                            m.percent_used > 90 ? 'bg-red-500' :
                            m.percent_used > 70 ? 'bg-amber-500' : 'bg-green-500'
                          }`}
                          style={{ width: `${Math.min(m.percent_used, 100)}%` }}
                        />
                      </div>
                      <span className="text-sm font-medium w-12 text-right">{m.percent_used}%</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">Remaining: {formatCurrency(m.remaining)}</p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ═══════ ROW 3: Meetings + Todos ═══════ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <Card
          className="hover:shadow-lg transition-shadow cursor-pointer border-l-4 border-l-sky-500"
          onClick={() => router.push('/meetings')}
        >
          <CardHeader className="pb-2">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-sky-50 rounded-lg">
                  <CalendarDays className="w-5 h-5 text-sky-600" />
                </div>
                <div>
                  <CardTitle className="text-lg">Upcoming Meetings</CardTitle>
                  <p className="text-sm text-gray-500">{meetings.length} scheduled</p>
                </div>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-400" />
            </div>
          </CardHeader>
          <CardContent>
            {meetings.length === 0 ? (
              <p className="text-gray-400 text-center py-6">No upcoming meetings</p>
            ) : (
              <div className="space-y-2">
                {meetings.slice(0, 5).map((m: any) => (
                  <div key={m.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <CalendarDays className="w-4 h-4 text-sky-500" />
                      <div>
                        <p className="font-medium text-sm">{m.title}</p>
                        <p className="text-xs text-gray-500">
                          {m.scheduled_at ? format(new Date(m.scheduled_at), 'EEE, MMM d · h:mm a') : 'TBD'}
                        </p>
                      </div>
                    </div>
                    {m.has_brief ? (
                      <Badge className="bg-green-100 text-green-800">
                        <CheckCircle2 className="w-3 h-3 mr-1" /> Brief
                      </Badge>
                    ) : (
                      <Badge variant="outline"><Clock className="w-3 h-3 mr-1" /> Pending</Badge>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card
          className="hover:shadow-lg transition-shadow cursor-pointer border-l-4 border-l-emerald-500"
          onClick={() => router.push('/todos')}
        >
          <CardHeader className="pb-2">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-emerald-50 rounded-lg">
                  <ListTodo className="w-5 h-5 text-emerald-600" />
                </div>
                <div>
                  <CardTitle className="text-lg">Tasks & Follow-ups</CardTitle>
                  <p className="text-sm text-gray-500">
                    {todos.mine.length + todos.delegated.length} open
                    {todos.overdue_count > 0 && (
                      <span className="text-red-600 ml-2">&middot; {todos.overdue_count} overdue</span>
                    )}
                  </p>
                </div>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-400" />
            </div>
          </CardHeader>
          <CardContent>
            {todos.mine.length === 0 && todos.delegated.length === 0 ? (
              <p className="text-gray-400 text-center py-6">No open tasks. Click to add one.</p>
            ) : (
              <div className="space-y-4">
                {todos.mine.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase mb-2">My Tasks ({todos.mine.length})</p>
                    <div className="space-y-1.5">
                      {todos.mine.slice(0, 3).map((t: any) => (
                        <div key={t.id} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                          <div className="flex items-center gap-2">
                            {t.is_overdue && <AlertCircle className="w-3.5 h-3.5 text-red-500" />}
                            <span className={`text-sm ${t.is_overdue ? 'text-red-700' : ''}`}>{t.title}</span>
                          </div>
                          <Badge className={`text-xs ${getPriorityColor(t.priority)}`}>{t.priority}</Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {todos.delegated.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase mb-2">
                      Delegated ({todos.delegated.length})
                    </p>
                    <div className="space-y-1.5">
                      {todos.delegated.slice(0, 3).map((t: any) => (
                        <div key={t.id} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                          <div className="flex items-center gap-2">
                            {t.is_overdue && <AlertCircle className="w-3.5 h-3.5 text-red-500" />}
                            <span className={`text-sm ${t.is_overdue ? 'text-red-700' : ''}`}>
                              <span className="font-medium">{t.assigned_to}:</span> {t.title}
                            </span>
                          </div>
                          <Badge className={`text-xs ${getPriorityColor(t.priority)}`}>{t.priority}</Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ═══════ ROW 4: AI Chat ═══════ */}
      <Card className="border-l-4 border-l-indigo-500">
        <CardHeader className="pb-2">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-50 rounded-lg">
              <MessageSquare className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <CardTitle className="text-lg">AI Assistant</CardTitle>
              <p className="text-sm text-gray-500">Ask anything about your operations</p>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* Chat messages */}
          {chatMessages.length > 0 && (
            <div className="mb-4 max-h-64 overflow-y-auto space-y-3">
              {chatMessages.map((msg, i) => (
                <div
                  key={i}
                  className={`p-3 rounded-lg text-sm ${
                    msg.role === 'user'
                      ? 'bg-gray-100 text-gray-800 ml-4 md:ml-8'
                      : 'bg-indigo-50 text-gray-800 mr-4 md:mr-8'
                  } whitespace-pre-wrap`}
                >
                  {msg.text}
                </div>
              ))}
              {chatLoading && (
                <div className="p-3 bg-indigo-50 rounded-lg mr-4 md:mr-8">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" />
                    <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                    <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="flex gap-2">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleChat()}
              placeholder="Ask about budget, complaints, meetings..."
              className="flex-1 px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
              disabled={chatLoading}
            />
            <Button
              onClick={handleChat}
              disabled={chatLoading || !chatInput.trim()}
              className="bg-indigo-600 hover:bg-indigo-700"
            >
              {chatLoading ? (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>

          <div className="flex gap-2 mt-3 flex-wrap">
            {['Budget status this month', 'Upcoming meetings summary', 'Recent complaints'].map((q) => (
              <button
                key={q}
                onClick={() => quickChat(q)}
                className="text-xs px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-full text-gray-600 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
