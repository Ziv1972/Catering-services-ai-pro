'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DollarSign, FolderKanban, Wrench, CalendarDays,
  ListTodo, ArrowRight, MessageSquare, Send,
  AlertCircle, AlertTriangle, CheckCircle2, Clock,
  ChevronRight, ChevronDown, ArrowLeft, X,
  UtensilsCrossed, Upload, Loader2,
} from 'lucide-react';
import { dashboardAPI, chatAPI, drillDownAPI, categoryAnalysisAPI, dailyMealsAPI } from '@/lib/api';
import ChatMessageRenderer from '@/components/chat/ChatMessageRenderer';
import { format } from 'date-fns';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid, Legend, Cell,
  AreaChart, Area,
} from 'recharts';

export default function Dashboard() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<Array<{ role: string; text: string }>>(() => {
    if (typeof window !== 'undefined') {
      try {
        const saved = sessionStorage.getItem('chat_history');
        return saved ? JSON.parse(saved) : [];
      } catch { return []; }
    }
    return [];
  });
  const [chatLoading, setChatLoading] = useState(false);
  const chatAbortRef = useRef<AbortController | null>(null);

  // Drill-down state
  const [drillDown, setDrillDown] = useState<{
    type: string;
    level: number;
    context: any;
    data: any;
    loading: boolean;
  } | null>(null);

  // Working days state (for budget drill-down month detail)
  const [workingDays, setWorkingDays] = useState<number | null>(null);
  const [workingDaysInput, setWorkingDaysInput] = useState('');
  const [workingDaysSaving, setWorkingDaysSaving] = useState(false);

  // Budget drill-down controls
  const [budgetRange, setBudgetRange] = useState<number>(12);
  const [drillDownYear, setDrillDownYear] = useState<number>(new Date().getFullYear());

  // Supplier monthly spending chart
  const [supplierMonthly, setSupplierMonthly] = useState<any>(null);
  const [supplierMonthlyLoading, setSupplierMonthlyLoading] = useState(false);
  const [smYear, setSmYear] = useState<number>(new Date().getFullYear());
  const [smFromMonth, setSmFromMonth] = useState<number>(1);
  const [smToMonth, setSmToMonth] = useState<number>(12);
  const [smSiteId, setSmSiteId] = useState<number | undefined>(undefined);
  const [hiddenSuppliers, setHiddenSuppliers] = useState<Set<string>>(new Set());

  // Meals monthly chart (below supplier spending)
  const [mealsMonthly, setMealsMonthly] = useState<any>(null);
  const [mealsMonthlyLoading, setMealsMonthlyLoading] = useState(false);

  // Meals drill-down (meal types breakdown)
  const [mealsDrill, setMealsDrill] = useState<any>(null);
  const [mealsDrillLoading, setMealsDrillLoading] = useState(false);

  // Budget vs actual meals spending
  const [mealsBudget, setMealsBudget] = useState<any>(null);
  const [mealsBudgetLoading, setMealsBudgetLoading] = useState(false);

  // Kitchenette/BTB data
  const [kitchenette, setKitchenette] = useState<any>(null);
  const [kitchenetteLoading, setKitchenetteLoading] = useState(false);

  // Kitchenette drill-down modal state
  const [kitDrillFamily, setKitDrillFamily] = useState<{ family_key: string; family_name: string } | null>(null);
  const [kitDrillData, setKitDrillData] = useState<any>(null);
  const [kitDrillLoading, setKitDrillLoading] = useState(false);
  const [kitDrillSite, setKitDrillSite] = useState<number | undefined>(undefined);
  const [kitDrillMonth, setKitDrillMonth] = useState<number | undefined>(undefined);

  // Drill-down panel state for Budget vs Actual section
  const [bvaPanel, setBvaPanel] = useState<'overview' | 'meals' | 'budget' | 'kitchenette'>('overview');

  // Daily meals (from email/CSV)
  const [dailyMeals, setDailyMeals] = useState<any>(null);
  const [dailyMealsLoading, setDailyMealsLoading] = useState(false);
  const [dailyMealsDays, setDailyMealsDays] = useState(30);
  const [dailyMealsSiteId, setDailyMealsSiteId] = useState<number | undefined>(undefined);
  const [csvUploading, setCsvUploading] = useState(false);
  const [csvResult, setCsvResult] = useState<any>(null);
  const csvInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadDashboard();
  }, []);

  // Persist chat messages to sessionStorage
  useEffect(() => {
    try {
      sessionStorage.setItem('chat_history', JSON.stringify(chatMessages));
    } catch { /* sessionStorage full or unavailable */ }
  }, [chatMessages]);

  const loadDashboard = async () => {
    try {
      const result = await dashboardAPI.get();
      setData(result);
      if (result?.proforma_year) {
        setDrillDownYear(result.proforma_year);
      }
    } catch {
      // Sections will show empty states
    } finally {
      setLoading(false);
    }
  };

  const loadSupplierMonthly = async (year?: number, fromMonth?: number, toMonth?: number, siteId?: number) => {
    setSupplierMonthlyLoading(true);
    try {
      const result = await dashboardAPI.supplierMonthly({
        year: year ?? smYear,
        from_month: fromMonth ?? smFromMonth,
        to_month: toMonth ?? smToMonth,
        site_id: siteId,
      });
      setSupplierMonthly(result);
      if (result?.year) setSmYear(result.year);
    } catch {
      setSupplierMonthly(null);
    } finally {
      setSupplierMonthlyLoading(false);
    }
  };

  const loadMealsMonthly = async (year?: number, fromMonth?: number, toMonth?: number, siteId?: number) => {
    setMealsMonthlyLoading(true);
    try {
      const result = await dashboardAPI.mealsMonthly({
        year: year ?? smYear,
        from_month: fromMonth ?? smFromMonth,
        to_month: toMonth ?? smToMonth,
        site_id: siteId,
      });
      setMealsMonthly(result);
    } catch {
      setMealsMonthly(null);
    } finally {
      setMealsMonthlyLoading(false);
    }
  };

  const loadMealsDetail = async (year?: number, fromMonth?: number, toMonth?: number, siteId?: number) => {
    setMealsDrillLoading(true);
    try {
      const result = await dashboardAPI.mealsDetail({
        year: year ?? smYear,
        from_month: fromMonth ?? smFromMonth,
        to_month: toMonth ?? smToMonth,
        site_id: siteId,
      });
      setMealsDrill(result);
    } catch {
      setMealsDrill(null);
    } finally {
      setMealsDrillLoading(false);
    }
  };

  const loadMealsBudget = async (year?: number, siteId?: number) => {
    setMealsBudgetLoading(true);
    try {
      const result = await dashboardAPI.mealsBudget({ year: year ?? smYear, site_id: siteId });
      setMealsBudget(result);
    } catch {
      setMealsBudget(null);
    } finally {
      setMealsBudgetLoading(false);
    }
  };

  const loadKitchenette = async (year?: number, _siteId?: number) => {
    // Top kitchenette view always shows combined sites — site filter only applies in drill-down.
    setKitchenetteLoading(true);
    try {
      const result = await dashboardAPI.kitchenetteMonthly({ year: year ?? smYear });
      setKitchenette(result);
    } catch {
      setKitchenette(null);
    } finally {
      setKitchenetteLoading(false);
    }
  };

  const loadKitchenetteDrill = async (
    family_key: string,
    family_name: string,
    siteId?: number,
    month?: number,
  ) => {
    setKitDrillFamily({ family_key, family_name });
    setKitDrillLoading(true);
    try {
      const result = await dashboardAPI.kitchenetteDrilldown({
        family_key,
        year: smYear,
        site_id: siteId,
        month,
      });
      setKitDrillData(result);
    } catch {
      setKitDrillData(null);
    } finally {
      setKitDrillLoading(false);
    }
  };

  const closeKitDrill = () => {
    setKitDrillFamily(null);
    setKitDrillData(null);
    setKitDrillSite(undefined);
    setKitDrillMonth(undefined);
  };

  const loadDailyMeals = async (days?: number, siteId?: number) => {
    setDailyMealsLoading(true);
    try {
      const result = await dashboardAPI.dailyMeals({
        days: days ?? dailyMealsDays,
        site_id: siteId,
      });
      setDailyMeals(result);
    } catch {
      setDailyMeals(null);
    } finally {
      setDailyMealsLoading(false);
    }
  };

  const handleCsvUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setCsvUploading(true);
    setCsvResult(null);
    try {
      const result = await dailyMealsAPI.upload(file);
      setCsvResult(result);
      await loadDailyMeals();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Upload failed';
      setCsvResult({ status: 'error', message: msg });
    } finally {
      setCsvUploading(false);
      if (csvInputRef.current) csvInputRef.current.value = '';
    }
  };

  const toggleSupplier = (key: string) => {
    setHiddenSuppliers((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  // Load supplier monthly + meals monthly + daily meals + budget + kitchenette on mount
  useEffect(() => {
    loadSupplierMonthly();
    loadMealsMonthly();
    loadDailyMeals();
    loadMealsBudget();
    loadKitchenette();
  }, []);

  const SUPPLIER_COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#78716c'];

  // Gradient colors for meal types and kitchenette families
  const MEAL_COLORS = ['#6366f1', '#3b82f6', '#0ea5e9', '#14b8a6', '#22c55e', '#eab308', '#f97316', '#ef4444', '#ec4899'];
  const KITCHEN_COLORS = ['#8b5cf6', '#6366f1', '#3b82f6', '#0ea5e9', '#14b8a6', '#f59e0b', '#78716c'];

  const getChatErrorMessage = (error: unknown): string => {
    if (error instanceof DOMException && error.name === 'AbortError') {
      return 'Request timed out. The AI service is taking too long to respond. Please try again.';
    }
    const axiosError = error as any;
    const status = axiosError?.response?.status;
    const detail = axiosError?.response?.data?.detail;
    if (status === 503) {
      return detail || 'The AI service is temporarily unavailable. Please try again later.';
    }
    if (status === 401) {
      return 'Your session has expired. Please refresh the page and log in again.';
    }
    if (status === 500) {
      return 'The AI service encountered an internal error. Please try again later.';
    }
    if (!axiosError?.response) {
      return 'Network error — could not reach the server. Check your connection and try again.';
    }
    return 'An unexpected error occurred. Please try again.';
  };

  const sendChatMessage = useCallback(async (message: string) => {
    if (chatAbortRef.current) chatAbortRef.current.abort();
    const controller = new AbortController();
    chatAbortRef.current = controller;
    setChatLoading(true);
    try {
      const result = await chatAPI.send(message, controller.signal);
      setChatMessages((prev) => [...prev, { role: 'ai', text: result.response }]);
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return;
      setChatMessages((prev) => [
        ...prev,
        { role: 'ai', text: getChatErrorMessage(error) },
      ]);
    } finally {
      setChatLoading(false);
      chatAbortRef.current = null;
    }
  }, []);

  const handleChat = async () => {
    if (!chatInput.trim() || chatLoading) return;
    const userMsg = chatInput.trim();
    setChatMessages((prev) => [...prev, { role: 'user', text: userMsg }]);
    setChatInput('');
    await sendChatMessage(userMsg);
  };

  const quickChat = async (prompt: string) => {
    if (chatLoading) return;
    setChatMessages((prev) => [...prev, { role: 'user', text: prompt }]);
    await sendChatMessage(prompt);
  };

  // Drill-down handlers
  // Level 1: Monthly overview (budget vs actual)
  const openBudgetDrillDown = async (supplier_id?: number, site_id?: number, label?: string, yearOverride?: number) => {
    const year = yearOverride || drillDownYear;
    setDrillDown({ type: 'budget', level: 1, context: { supplier_id, site_id, label }, data: null, loading: true });
    try {
      const result = await drillDownAPI.budget({
        supplier_id,
        site_id,
        year,
      });
      // Use the resolved proforma_year from backend for subsequent calls
      if (result?.year) setDrillDownYear(result.year);
      setDrillDown((prev) => prev ? { ...prev, data: result, loading: false } : null);
    } catch (err: any) {
      const errMsg = err?.response?.data?.detail || err?.message || 'Unknown error';
      setDrillDown((prev) => prev ? { ...prev, data: { items: [], error: errMsg }, loading: false } : null);
    }
  };

  const changeDrillDownYear = (newYear: number) => {
    setDrillDownYear(newYear);
    if (drillDown && drillDown.type === 'budget' && drillDown.level === 1) {
      openBudgetDrillDown(drillDown.context.supplier_id, drillDown.context.site_id, drillDown.context.label, newYear);
    }
  };

  // Level 2: Month → Category breakdown
  const drillIntoMonthCategories = async (month: number, monthName: string) => {
    if (!drillDown) return;
    const ctx = drillDown.context;
    // Preserve Level 1 data: reuse cached version on back-nav, deep-copy on first entry
    const level1Data = ctx.level1Data
      ? ctx.level1Data
      : (drillDown.data ? JSON.parse(JSON.stringify(drillDown.data)) : null);
    setDrillDown((prev) => prev ? {
      ...prev,
      level: 2,
      context: { ...ctx, month, monthName, level1Data },
      data: null,
      loading: true,
    } : null);
    setWorkingDays(null);
    setWorkingDaysInput('');
    try {
      const [catResult, wdResult] = await Promise.all([
        categoryAnalysisAPI.costByCategory({
          year: drillDownYear,
          month,
          site_id: ctx.site_id,
          supplier_id: ctx.supplier_id,
        }),
        categoryAnalysisAPI.getWorkingDays({ site_id: ctx.site_id, year: drillDownYear }),
      ]);
      const wdEntry = (wdResult?.items || []).find((e: any) => e.month === month);
      if (wdEntry) {
        setWorkingDays(wdEntry.working_days);
        setWorkingDaysInput(String(wdEntry.working_days));
      }
      setDrillDown((prev) => prev ? { ...prev, data: catResult, loading: false } : null);
    } catch {
      setDrillDown((prev) => prev ? { ...prev, data: { items: [] }, loading: false } : null);
    }
  };

  // Level 3: Category → Products
  const drillIntoCategoryProducts = async (categoryName: string, displayHe: string, month?: number) => {
    if (!drillDown) return;
    const ctx = drillDown.context;
    const m = month ?? ctx.month;
    setDrillDown((prev) => prev ? {
      ...prev,
      level: 3,
      context: { ...ctx, categoryName, categoryDisplayHe: displayHe },
      data: null,
      loading: true,
    } : null);
    try {
      const result = await categoryAnalysisAPI.costProducts({
        year: drillDownYear,
        month: m,
        site_id: ctx.site_id,
        supplier_id: ctx.supplier_id,
        category_name: categoryName,
      });
      setDrillDown((prev) => prev ? { ...prev, data: result, loading: false } : null);
    } catch {
      setDrillDown((prev) => prev ? { ...prev, data: { items: [] }, loading: false } : null);
    }
  };

  // Level 4: Product → Monthly breakdown
  const drillIntoProductDetail = async (productName: string) => {
    if (!drillDown) return;
    const ctx = drillDown.context;
    setDrillDown((prev) => prev ? {
      ...prev,
      level: 4,
      context: { ...ctx, productName },
      data: null,
      loading: true,
    } : null);
    try {
      const result = await drillDownAPI.productHistory({
        product_name: productName,
        supplier_id: ctx.supplier_id,
        site_id: ctx.site_id,
        year: drillDownYear,
      });
      setDrillDown((prev) => prev ? { ...prev, data: result, loading: false } : null);
    } catch {
      setDrillDown((prev) => prev ? { ...prev, data: { monthly: [] }, loading: false } : null);
    }
  };

  const saveWorkingDays = async () => {
    if (!drillDown || !workingDaysInput.trim()) return;
    const ctx = drillDown.context;
    const days = parseInt(workingDaysInput);
    if (isNaN(days) || days < 0 || days > 31) return;
    setWorkingDaysSaving(true);
    try {
      await categoryAnalysisAPI.setWorkingDays({
        site_id: ctx.site_id, year: drillDownYear, month: ctx.month, working_days: days,
      });
      setWorkingDays(days);
    } catch {
      // silent
    } finally {
      setWorkingDaysSaving(false);
    }
  };

  const goBackDrillDown = () => {
    if (!drillDown || drillDown.level <= 1) {
      setDrillDown(null);
      return;
    }
    const ctx = drillDown.context;
    if (drillDown.level === 4) {
      // Level 4 → Level 3
      drillIntoCategoryProducts(ctx.categoryName, ctx.categoryDisplayHe, ctx.month);
    } else if (drillDown.level === 3) {
      // Level 3 → Level 2
      drillIntoMonthCategories(ctx.month, ctx.monthName);
    } else if (drillDown.level === 2) {
      // Level 2 → Level 1 (restore cached data)
      if (ctx.level1Data) {
        setDrillDown({
          type: 'budget', level: 1,
          context: { supplier_id: ctx.supplier_id, site_id: ctx.site_id, label: ctx.label },
          data: ctx.level1Data, loading: false,
        });
      } else {
        openBudgetDrillDown(ctx.supplier_id, ctx.site_id, ctx.label);
      }
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

  const CATEGORY_COLORS: Record<string, string> = {
    total_meals: '#3b82f6', extras_lunch: '#f59e0b', kitchenette_fruit: '#10b981',
    kitchenette_dry: '#8b5cf6', kitchenette_dairy: '#06b6d4', coffee_tea: '#78716c',
    cut_veg: '#22c55e', coffee_beans: '#a16207', uncategorized: '#d1d5db',
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-[hsl(var(--background))]">
        <div className="text-center">
          <div className="relative w-10 h-10 mx-auto mb-4">
            <div className="absolute inset-0 rounded-full border-2 border-gray-200" />
            <div className="absolute inset-0 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          </div>
          <p className="text-sm text-muted-foreground">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  const budgetSummaryAll = data?.budget_summary || [];
  const budgetSummary = budgetSummaryAll.filter((b: any) => b.monthly_budget > 0);
  const unbudgetedSuppliers = budgetSummaryAll.filter((b: any) => !b.monthly_budget || b.monthly_budget <= 0);
  const projects = data?.projects || [];
  const maintenance = data?.maintenance || [];
  const meetings = data?.meetings || [];
  const todos = data?.todos || { mine: [], delegated: [], overdue_count: 0 };
  const proformaCosts = data?.proforma_costs || [];
  const displayYear = data?.budget_year || new Date().getFullYear();
  const proformaYear = data?.proforma_year || displayYear;
  const displayMonth = data?.display_month;

  const chartData = budgetSummary.map((b: any) => ({
    name: `${b.supplier_name}${b.shift && b.shift !== 'all' ? ` [${b.shift}]` : ''}\n(${b.site_name})`,
    budget: b.monthly_budget,
    actual: b.monthly_actual,
  }));

  const formatCurrency = (val: number) =>
    `₪${val.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;

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
    <main className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* ═══════ KPI STAT CARDS ═══════ */}
      <div className="stagger-children grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="group relative overflow-hidden rounded-xl border bg-card p-5 card-hover">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Budget Use</span>
            <div className="p-1.5 rounded-lg bg-blue-50 text-blue-600">
              <DollarSign className="w-4 h-4" />
            </div>
          </div>
          <p className="text-2xl font-bold tracking-tight">
            {budgetSummary.length > 0
              ? `${Math.round(budgetSummary.reduce((s: number, b: any) => s + (b.monthly_percent || 0), 0) / budgetSummary.length)}%`
              : '—'}
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            {budgetSummary.length} supplier{budgetSummary.length !== 1 ? 's' : ''} tracked
          </p>
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 to-blue-400 opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>

        {(() => {
          const totalOverdue = projects.reduce((s: number, p: any) => s + (p.overdue_count || 0), 0);
          const hasOverdue = totalOverdue > 0;
          return (
            <div className={`group relative overflow-hidden rounded-xl border p-5 card-hover ${hasOverdue ? 'bg-red-50 border-red-200' : 'bg-card'}`}>
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Projects</span>
                <div className={`p-1.5 rounded-lg ${hasOverdue ? 'bg-red-100 text-red-600' : 'bg-purple-50 text-purple-600'}`}>
                  {hasOverdue ? <AlertTriangle className="w-4 h-4" /> : <FolderKanban className="w-4 h-4" />}
                </div>
              </div>
              <p className="text-2xl font-bold tracking-tight">{projects.length}</p>
              <p className="text-xs text-muted-foreground mt-1">
                {projects.reduce((s: number, p: any) => s + (p.done_count || 0), 0)} / {projects.reduce((s: number, p: any) => s + (p.task_count || 0), 0)} tasks done
              </p>
              {hasOverdue && (
                <p className="text-xs font-semibold text-red-600 mt-1 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" />
                  {totalOverdue} overdue task{totalOverdue !== 1 ? 's' : ''}
                </p>
              )}
              <div className={`absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r ${hasOverdue ? 'from-red-500 to-red-400 opacity-100' : 'from-purple-500 to-purple-400 opacity-0 group-hover:opacity-100'} transition-opacity`} />
            </div>
          );
        })()}

        <div className="group relative overflow-hidden rounded-xl border bg-card p-5 card-hover">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Meetings</span>
            <div className="p-1.5 rounded-lg bg-sky-50 text-sky-600">
              <CalendarDays className="w-4 h-4" />
            </div>
          </div>
          <p className="text-2xl font-bold tracking-tight">{meetings.length}</p>
          <p className="text-xs text-muted-foreground mt-1">upcoming scheduled</p>
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-sky-500 to-sky-400 opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>

        <div className="group relative overflow-hidden rounded-xl border bg-card p-5 card-hover">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Tasks</span>
            <div className="p-1.5 rounded-lg bg-emerald-50 text-emerald-600">
              <ListTodo className="w-4 h-4" />
            </div>
          </div>
          <p className="text-2xl font-bold tracking-tight">{todos.mine.length + todos.delegated.length}</p>
          <p className="text-xs mt-1">
            {todos.overdue_count > 0 ? (
              <span className="text-red-600 font-medium">{todos.overdue_count} overdue</span>
            ) : (
              <span className="text-muted-foreground">all on track</span>
            )}
          </p>
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-emerald-500 to-emerald-400 opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </div>

      {/* Drill-down overlay */}
      {drillDown && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <Card className="w-full max-w-sm md:max-w-2xl lg:max-w-3xl max-h-[80vh] overflow-auto shadow-2xl border-0 ring-1 ring-black/5">
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
                        ? `Budget vs Actual ${drillDown.context.label ? `— ${drillDown.context.label}` : ''}`
                        : drillDown.type === 'budget' && drillDown.level === 2
                        ? [drillDown.context.monthName, 'Categories'].filter(Boolean).join(' — ')
                        : drillDown.type === 'budget' && drillDown.level === 3
                        ? [drillDown.context.monthName, drillDown.context.categoryDisplayHe].filter(Boolean).join(' — ')
                        : drillDown.type === 'budget' && drillDown.level === 4
                        ? drillDown.context.productName || 'Product Details'
                        : drillDown.type === 'project'
                        ? `Project: ${drillDown.context.label || ''}`
                        : drillDown.type === 'maintenance'
                        ? `Maintenance: ${drillDown.context.label || ''}`
                        : 'Details'}
                    </CardTitle>
                    <p className="text-sm text-gray-500">
                      {drillDown.type === 'budget' && drillDown.level === 1 ? 'Click a month or category to drill down'
                        : drillDown.type === 'budget' && drillDown.level === 2 ? 'Click a category to see products'
                        : drillDown.type === 'budget' && drillDown.level === 3 ? 'Click a product for monthly breakdown'
                        : drillDown.type === 'budget' && drillDown.level === 4 ? 'Monthly price & quantity history'
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
                (() => {
                  const allItems = drillDown.data?.items || [];
                  const catNames: string[] = drillDown.data?.category_names || [];
                  const visibleItems = allItems.filter((i: any) => i.budget > 0 || i.actual > 0).slice(-budgetRange);
                  const totalBudget = visibleItems.reduce((s: number, i: any) => s + (i.budget || 0), 0);
                  const totalActual = visibleItems.reduce((s: number, i: any) => s + (i.actual || 0), 0);
                  const isEmpty = totalBudget === 0 && totalActual === 0;
                  const budgetYearLabel = drillDown.data?.budget_year;
                  const proformaYearLabel = drillDown.data?.year;
                  return (
                    <>
                      {isEmpty && (
                        <div className="text-center py-8 mb-4 bg-gray-50 rounded-lg">
                          {drillDown.data?.error ? (
                            <>
                              <p className="text-red-400 text-sm">Error loading data</p>
                              <p className="text-red-300 text-xs mt-1 font-mono">{drillDown.data.error}</p>
                            </>
                          ) : (
                            <>
                              <p className="text-gray-400 text-sm">No budget or proforma data found for this supplier/site.</p>
                              <p className="text-gray-400 text-xs mt-1">
                                Budget year: {budgetYearLabel || 'N/A'} · Proforma year: {proformaYearLabel || 'N/A'}
                              </p>
                              <p className="text-gray-400 text-xs mt-1">Try selecting a different year from the dropdown.</p>
                            </>
                          )}
                        </div>
                      )}
                      {/* Year + Range selector */}
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                          <select
                            value={drillDownYear}
                            onChange={(e) => changeDrillDownYear(Number(e.target.value))}
                            className="px-2 py-1 text-xs border rounded-md bg-white focus:ring-2 focus:ring-blue-400"
                          >
                            {(() => {
                              const currentY = new Date().getFullYear();
                              const years = new Set([currentY, currentY - 1, currentY - 2, currentY - 3]);
                              if (drillDownYear) years.add(drillDownYear);
                              return Array.from(years).sort((a, b) => b - a).map((y) => (
                                <option key={y} value={y}>{y}</option>
                              ));
                            })()}
                          </select>
                          <div className="flex gap-1">
                            {[3, 6, 12].map((r) => (
                              <button
                                key={r}
                                onClick={() => setBudgetRange(r)}
                                className={`px-3 py-1 text-xs rounded-full font-medium transition-colors ${
                                  budgetRange === r ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                                }`}
                              >
                                {r}M
                              </button>
                            ))}
                          </div>
                        </div>
                        <div className="text-xs text-gray-500">
                          Budget: {formatCurrency(totalBudget)} · Actual: {formatCurrency(totalActual)}
                          {totalBudget > 0 && <span className={`ml-1 font-semibold ${totalActual / totalBudget > 0.9 ? 'text-red-600' : 'text-green-600'}`}>
                            ({Math.round(totalActual / totalBudget * 100)}%)
                          </span>}
                        </div>
                      </div>

                      {/* Budget vs Actual grouped bar chart */}
                      <div className="h-56 mb-4">
                        <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                          <BarChart data={visibleItems}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="month_name" tick={{ fontSize: 12 }} />
                            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`} />
                            <Tooltip formatter={(val: any) => formatCurrency(Number(val))} />
                            <Legend />
                            <Bar dataKey="budget" fill="#93c5fd" name="Budget" radius={[4, 4, 0, 0]} />
                            <Bar dataKey="actual" fill="#3b82f6" name="Actual" radius={[4, 4, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>

                      {/* Stacked category chart per month */}
                      {catNames.length > 0 && (
                        <div className="mb-4">
                          <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Cost by Category per Month</p>
                          <div className="h-48">
                            <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                              <BarChart data={visibleItems}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="month_name" tick={{ fontSize: 11 }} />
                                <YAxis tick={{ fontSize: 10 }} tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`} />
                                <Tooltip formatter={(val: any) => formatCurrency(Number(val))} />
                                <Legend wrapperStyle={{ fontSize: 10 }} />
                                {catNames.map((cn: string) => (
                                  <Bar
                                    key={cn}
                                    dataKey={`categories.${cn}`}
                                    stackId="cats"
                                    fill={CATEGORY_COLORS[cn] || '#94a3b8'}
                                    name={
                                      (drillDown.data?.categories || []).find((c: any) => c.category_name === cn)?.display_name_he || cn
                                    }
                                  />
                                ))}
                              </BarChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                      )}

                      {/* Category totals — clickable for product drill-down */}
                      {(drillDown.data?.categories || []).length > 0 && (
                        <div className="mb-4">
                          <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Category Totals &middot; click for products</p>
                          <div className="space-y-1">
                            {(drillDown.data?.categories || []).map((cat: any) => (
                              <div
                                key={cat.category_name}
                                onClick={() => drillIntoCategoryProducts(cat.category_name, cat.display_name_he)}
                                className="flex items-center justify-between p-2 bg-gray-50 rounded cursor-pointer hover:bg-blue-50 transition-colors"
                              >
                                <div className="flex items-center gap-2">
                                  <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: CATEGORY_COLORS[cat.category_name] || '#94a3b8' }} />
                                  <span className="text-sm">{cat.display_name_he}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <span className="text-sm font-semibold">{formatCurrency(cat.total_cost)}</span>
                                  <ChevronRight className="w-3 h-3 text-gray-400" />
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Monthly rows - clickable */}
                      <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Monthly Detail</p>
                      <div className="space-y-1">
                        {visibleItems.filter((i: any) => i.actual > 0).map((item: any) => (
                          <div
                            key={item.month}
                            onClick={() => drillIntoMonthCategories(item.month, item.month_name)}
                            className="flex items-center justify-between p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-blue-50 transition-colors"
                          >
                            <div>
                              <span className="font-medium">{item.month_name}</span>
                              <span className="text-xs text-gray-500 ml-2">{item.invoice_count} inv</span>
                            </div>
                            <div className="flex items-center gap-3">
                              <div className="text-right text-sm">
                                <span className="text-gray-500">{formatCurrency(item.budget)}</span>
                                <span className="mx-1">/</span>
                                <span className={`font-semibold ${item.budget > 0 && item.actual / item.budget > 0.9 ? 'text-red-600' : ''}`}>
                                  {formatCurrency(item.actual)}
                                </span>
                              </div>
                              <ChevronRight className="w-4 h-4 text-gray-400" />
                            </div>
                          </div>
                        ))}
                      </div>
                    </>
                  );
                })()
              ) : drillDown.type === 'budget' && drillDown.level === 2 ? (
                /* Level 2: Category breakdown for a month */
                <div>
                  {(drillDown.data?.items || []).length === 0 ? (
                    <p className="text-center py-8 text-gray-400">No data for this month</p>
                  ) : (
                    <>
                      {/* Working days + cost per day */}
                      {drillDown.context.site_id && (
                        <div className="p-3 bg-gray-50 rounded-lg border border-gray-200 mb-4">
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex items-center gap-2">
                              <CalendarDays className="w-4 h-4 text-gray-500" />
                              <span className="text-sm font-medium text-gray-700">Working Days</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <input
                                type="number"
                                min="0"
                                max="31"
                                value={workingDaysInput}
                                onChange={(e) => setWorkingDaysInput(e.target.value)}
                                placeholder="--"
                                className="w-16 px-2 py-1 text-center text-sm border rounded focus:ring-2 focus:ring-blue-400 focus:border-blue-400"
                              />
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={workingDaysSaving || !workingDaysInput.trim()}
                                onClick={saveWorkingDays}
                                className="text-xs"
                              >
                                {workingDaysSaving ? '...' : 'Save'}
                              </Button>
                            </div>
                          </div>
                          {workingDays && workingDays > 0 && (() => {
                            const totalCost = (drillDown.data?.items || []).reduce((s: number, i: any) => s + (i.total_cost || 0), 0);
                            return (
                              <div className="mt-2 text-sm text-gray-600 flex justify-between">
                                <span>Cost per working day:</span>
                                <span className="font-semibold">{formatCurrency(totalCost / workingDays)}</span>
                              </div>
                            );
                          })()}
                        </div>
                      )}

                      {/* Category cards */}
                      <div className="space-y-2">
                        {(drillDown.data?.items || []).map((cat: any, idx: number) => {
                          const totalCost = (drillDown.data?.items || []).reduce((s: number, c: any) => s + (c.total_cost || 0), 0);
                          const pct = totalCost > 0 ? Math.round((cat.total_cost / totalCost) * 100) : 0;
                          return (
                            <button
                              key={idx}
                              onClick={() => drillIntoCategoryProducts(cat.category_name, cat.display_name_he, drillDown.context.month)}
                              className="w-full flex items-center justify-between p-3 rounded-lg border hover:bg-blue-50 transition-colors text-left"
                            >
                              <div className="flex items-center gap-3">
                                <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: CATEGORY_COLORS[cat.category_name] || '#94a3b8' }} />
                                <div>
                                  <p className="font-medium text-gray-900">{cat.display_name_he}</p>
                                  <p className="text-xs text-gray-500">
                                    {cat.total_qty?.toLocaleString()} items · {cat.item_count} orders
                                  </p>
                                </div>
                              </div>
                              <div className="flex items-center gap-3">
                                <div className="text-right">
                                  <p className="font-semibold">{formatCurrency(cat.total_cost)}</p>
                                  <p className="text-xs text-gray-500">{pct}%</p>
                                </div>
                                <ChevronRight className="w-4 h-4 text-gray-400" />
                              </div>
                            </button>
                          );
                        })}
                      </div>

                      {/* Total */}
                      <div className="mt-3 pt-3 border-t flex justify-between text-sm font-semibold">
                        <span>Total</span>
                        <span>{formatCurrency((drillDown.data?.items || []).reduce((s: number, c: any) => s + (c.total_cost || 0), 0))}</span>
                      </div>
                    </>
                  )}
                </div>
              ) : drillDown.type === 'budget' && drillDown.level === 3 ? (
                /* Level 3: Products in category */
                <div>
                  {(drillDown.data?.items || []).length === 0 ? (
                    <p className="text-center py-8 text-gray-400">No products in this category</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b text-left text-gray-500">
                            <th className="pb-2 font-medium">Product</th>
                            <th className="pb-2 font-medium text-right">Qty</th>
                            <th className="pb-2 font-medium text-right">Avg Price</th>
                            <th className="pb-2 font-medium text-right">Total</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(drillDown.data?.items || []).map((item: any, i: number) => (
                            <tr
                              key={i}
                              onClick={() => drillIntoProductDetail(item.product_name)}
                              className="border-b last:border-0 cursor-pointer hover:bg-blue-50 transition-colors"
                            >
                              <td className="py-2 font-medium flex items-center gap-1">
                                {item.product_name}
                                <ChevronRight className="w-3 h-3 text-gray-300" />
                              </td>
                              <td className="py-2 text-right text-gray-600">{item.total_quantity?.toLocaleString()}</td>
                              <td className="py-2 text-right text-gray-600">{formatCurrency(item.avg_unit_price)}</td>
                              <td className="py-2 text-right font-mono">{formatCurrency(item.total_cost)}</td>
                            </tr>
                          ))}
                        </tbody>
                        <tfoot>
                          <tr className="border-t-2 bg-teal-50">
                            <td className="py-2 text-sm text-teal-700">סה&quot;כ</td>
                            <td className="py-2 text-right text-sm text-teal-700 tabular-nums">{(drillDown.data?.items || []).reduce((s: number, i: any) => s + (i.total_quantity || 0), 0).toLocaleString()}</td>
                            <td className="py-2" />
                            <td className="py-2 text-right text-sm text-teal-700 tabular-nums">{formatCurrency((drillDown.data?.items || []).reduce((s: number, i: any) => s + (i.total_cost || 0), 0))}</td>
                          </tr>
                        </tfoot>
                      </table>
                    </div>
                  )}
                </div>
              ) : drillDown.type === 'budget' && drillDown.level === 4 ? (
                /* Level 4: Product monthly breakdown */
                <div>
                  {/* Year selector for product history */}
                  <div className="flex items-center gap-3 mb-4 p-3 bg-gray-50 rounded-lg">
                    <span className="text-sm text-gray-500 font-medium">Year:</span>
                    <select
                      value={drillDownYear}
                      onChange={(e) => {
                        const newYear = Number(e.target.value);
                        setDrillDownYear(newYear);
                        if (drillDown.context.productName) {
                          drillIntoProductDetail(drillDown.context.productName);
                        }
                      }}
                      className="border rounded px-2 py-1 text-sm bg-white"
                    >
                      {(() => {
                        const cy = new Date().getFullYear();
                        const years = new Set([cy, cy - 1, cy - 2, cy - 3]);
                        if (drillDownYear) years.add(drillDownYear);
                        return Array.from(years).sort((a, b) => b - a).map((y) => (
                          <option key={y} value={y}>{y}</option>
                        ));
                      })()}
                    </select>
                  </div>
                  {(drillDown.data?.monthly || []).length === 0 ? (
                    <p className="text-center py-8 text-gray-400">No monthly data for this product</p>
                  ) : (
                    <>
                      {/* Price trend chart */}
                      <div className="h-48 mb-4">
                        <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                          <BarChart data={drillDown.data.monthly}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="month_name" tick={{ fontSize: 11 }} />
                            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `₪${v}`} />
                            <Tooltip formatter={(val: any) => formatCurrency(Number(val))} />
                            <Legend />
                            <Bar dataKey="total" fill="#3b82f6" name="Total Cost" radius={[4, 4, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>

                      {/* Monthly table */}
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b text-left text-gray-500">
                              <th className="pb-2 font-medium">Month</th>
                              <th className="pb-2 font-medium text-right">Qty</th>
                              <th className="pb-2 font-medium text-right">Avg Price</th>
                              <th className="pb-2 font-medium text-right">Total</th>
                              <th className="pb-2 font-medium text-right">Orders</th>
                            </tr>
                          </thead>
                          <tbody>
                            {drillDown.data.monthly.map((m: any, i: number) => (
                              <tr key={i} className="border-b last:border-0">
                                <td className="py-2">{m.month_name}</td>
                                <td className="py-2 text-right text-gray-600 tabular-nums">{m.quantity?.toLocaleString()}</td>
                                <td className="py-2 text-right text-gray-600 tabular-nums">₪{m.avg_price?.toFixed(2)}</td>
                                <td className="py-2 text-right tabular-nums">{formatCurrency(m.total)}</td>
                                <td className="py-2 text-right text-gray-500">{m.orders}</td>
                              </tr>
                            ))}
                          </tbody>
                          <tfoot>
                            <tr className="border-t-2 bg-teal-50">
                              <td className="py-2 text-sm text-teal-700">סה&quot;כ</td>
                              <td className="py-2 text-right text-sm text-teal-700 tabular-nums">{drillDown.data.monthly.reduce((s: number, m: any) => s + (m.quantity || 0), 0).toLocaleString()}</td>
                              <td className="py-2" />
                              <td className="py-2 text-right text-sm text-teal-700 tabular-nums">{formatCurrency(drillDown.data.monthly.reduce((s: number, m: any) => s + (m.total || 0), 0))}</td>
                              <td className="py-2 text-right text-sm text-teal-700">{drillDown.data.monthly.reduce((s: number, m: any) => s + (m.orders || 0), 0)}</td>
                            </tr>
                          </tfoot>
                        </table>
                      </div>
                    </>
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

      {/* ═══════ BUDGET VS ACTUAL ═══════ */}
      <div className="space-y-4">
        {/* Top Level: Trend + Progress */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Monthly Trend Chart — Meals Quantity + Spending */}
          <div className="lg:col-span-2 rounded-2xl border bg-gradient-to-br from-white to-slate-50/80 shadow-sm overflow-hidden">
            <div className="p-5 pb-3">
              <div className="flex items-center justify-between mb-1">
                <div>
                  <h3 className="text-base font-semibold text-gray-900">Meals Trend</h3>
                  <p className="text-xs text-gray-500">Monthly quantity &amp; spending &middot; {smYear}</p>
                </div>
                <div className="flex items-center gap-2">
                  {/* Year + Site filters */}
                  <select
                    value={smYear}
                    onChange={(e) => { const y = Number(e.target.value); setSmYear(y); loadSupplierMonthly(y, smFromMonth, smToMonth, smSiteId); loadMealsMonthly(y, smFromMonth, smToMonth, smSiteId); loadMealsBudget(y, smSiteId); loadKitchenette(y, smSiteId); }}
                    className="border rounded-lg px-2 py-1 bg-white text-xs"
                  >
                    {[new Date().getFullYear(), new Date().getFullYear() - 1, new Date().getFullYear() - 2].map((y) => (
                      <option key={y} value={y}>{y}</option>
                    ))}
                  </select>
                  {mealsMonthly?.sites?.length > 0 && (
                    <select
                      value={smSiteId ?? ''}
                      onChange={(e) => { const v = e.target.value ? Number(e.target.value) : undefined; setSmSiteId(v); loadSupplierMonthly(smYear, smFromMonth, smToMonth, v); loadMealsMonthly(smYear, smFromMonth, smToMonth, v); loadMealsBudget(smYear, v); loadKitchenette(smYear, v); }}
                      className="border rounded-lg px-2 py-1 bg-white text-xs"
                    >
                      <option value="">All Sites</option>
                      {mealsMonthly.sites.map((s: any) => (
                        <option key={s.id} value={s.id}>{s.name}</option>
                      ))}
                    </select>
                  )}
                </div>
              </div>

              {/* KPI Summary Row */}
              {mealsMonthly?.chart_data && (() => {
                const totalMeals = mealsMonthly.chart_data.reduce((s: number, r: any) => s + (r.total || 0), 0);
                const totalSupplement = mealsMonthly.chart_data.reduce((s: number, r: any) => s + (r.total_supplement || 0), 0);
                const totalCost = mealsMonthly.chart_data.reduce((s: number, r: any) => s + (r.total_cost || 0), 0);
                return (
                  <div className="flex gap-4 mb-3">
                    <div className="flex-1 rounded-xl bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-100 p-3">
                      <p className="text-[10px] uppercase tracking-wider text-blue-600 font-medium">Total Meals</p>
                      <p className="text-xl font-bold text-blue-900 tabular-nums">{totalMeals.toLocaleString()}</p>
                    </div>
                    <div className="flex-1 rounded-xl bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-100 p-3">
                      <p className="text-[10px] uppercase tracking-wider text-amber-600 font-medium">Supplement</p>
                      <p className="text-xl font-bold text-amber-900 tabular-nums">{totalSupplement.toLocaleString()}</p>
                    </div>
                    <div className="flex-1 rounded-xl bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-100 p-3">
                      <p className="text-[10px] uppercase tracking-wider text-emerald-600 font-medium">Total Cost</p>
                      <p className="text-xl font-bold text-emerald-900 tabular-nums">{formatCurrency(totalCost)}</p>
                    </div>
                  </div>
                );
              })()}
            </div>

            {/* Chart */}
            <div className="px-5 pb-5">
              {mealsMonthlyLoading ? (
                <div className="h-56 flex items-center justify-center text-gray-400 text-sm">
                  <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading...
                </div>
              ) : mealsMonthly?.chart_data?.length > 0 ? (
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                    <BarChart data={mealsMonthly.chart_data} barGap={2}>
                      <defs>
                        <linearGradient id="gradNZ" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#6366f1" stopOpacity={0.9} />
                          <stop offset="100%" stopColor="#6366f1" stopOpacity={0.5} />
                        </linearGradient>
                        <linearGradient id="gradKG" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#0ea5e9" stopOpacity={0.9} />
                          <stop offset="100%" stopColor="#0ea5e9" stopOpacity={0.5} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                      <XAxis dataKey="month_name" tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} />
                      <Tooltip
                        contentStyle={{ borderRadius: '12px', border: '1px solid #e5e7eb', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' }}
                        formatter={(val: any, name: any) => [Number(val).toLocaleString(), String(name)]}
                      />
                      {(mealsMonthly.site_keys || []).length > 1 ? (
                        (mealsMonthly.site_keys || []).map((sk: string, i: number) => (
                          <Bar key={sk} dataKey={sk} fill={i === 0 ? 'url(#gradNZ)' : 'url(#gradKG)'} name={sk} radius={[4, 4, 0, 0]} />
                        ))
                      ) : (
                        <Bar dataKey="total" fill="url(#gradNZ)" name="Meals" radius={[4, 4, 0, 0]} />
                      )}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="h-56 flex items-center justify-center text-gray-400 text-sm">No meal data for this period</div>
              )}
            </div>
          </div>

          {/* Budget Progress Per Site */}
          <div className="rounded-2xl border bg-gradient-to-br from-white to-slate-50/80 shadow-sm p-5">
            <h3 className="text-base font-semibold text-gray-900 mb-1">Budget Progress</h3>
            <p className="text-xs text-gray-500 mb-4">Actual vs budget per site</p>

            {mealsBudgetLoading ? (
              <div className="flex items-center justify-center py-12 text-gray-400 text-sm">
                <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading...
              </div>
            ) : (budgetSummary.length > 0 || (mealsBudget?.sites?.length > 0)) ? (
              <div className="space-y-2">
                {budgetSummary.map((b: any, i: number) => (
                  <div
                    key={i}
                    className="group flex items-center justify-between p-3.5 rounded-lg border border-transparent hover:border-blue-200 hover:bg-blue-50/50 cursor-pointer transition-all"
                    onClick={() => openBudgetDrillDown(b.supplier_id, b.site_id, `${b.supplier_name} (${b.site_name})`, data?.proforma_year)}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm truncate">{b.supplier_name}</p>
                      <p className="text-xs text-muted-foreground">{b.site_name}</p>
                    </div>
                    <div className="text-right ml-4">
                      <p className="text-sm tabular-nums">
                        <span className="font-semibold">{formatCurrency(b.monthly_actual)}</span>
                        <span className="text-muted-foreground"> / {formatCurrency(b.monthly_budget)}</span>
                      </p>
                      <div className="w-24 md:w-32 h-1.5 bg-gray-100 rounded-full mt-1.5">
                        <div
                          className={`h-1.5 rounded-full transition-all duration-700 ease-out ${
                            b.monthly_percent > 90 ? 'bg-red-500' :
                            b.monthly_percent > 70 ? 'bg-amber-500' : 'bg-emerald-500'
                          }`}
                          style={{ width: `${Math.min(b.monthly_percent, 100)}%` }}
                        />
                      </div>
                      <p className={`text-xs mt-0.5 font-medium ${
                        b.monthly_percent > 90 ? 'text-red-600' :
                        b.monthly_percent > 70 ? 'text-amber-600' : 'text-emerald-600'
                      }`}>{b.monthly_percent}%</p>
                    </div>
                  </div>
                ))}

                {/* Unbudgeted Suppliers */}
                {unbudgetedSuppliers.length > 0 && (
                  <div className="mt-2 p-3 bg-amber-50/50 rounded-lg border border-amber-200/60">
                    <p className="text-[10px] font-medium text-amber-700 mb-2 uppercase tracking-wider">Unbudgeted</p>
                    {unbudgetedSuppliers.map((b: any, idx: number) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between py-1.5 cursor-pointer hover:bg-amber-100/50 rounded px-2 -mx-2 transition-colors"
                        onClick={() => openBudgetDrillDown(b.supplier_id, b.site_id, `${b.supplier_name} (${b.site_name})`, data?.proforma_year)}
                      >
                        <div>
                          <p className="text-sm font-medium">{b.supplier_name}</p>
                          <p className="text-xs text-muted-foreground">{b.site_name}</p>
                        </div>
                        <p className="text-sm font-semibold tabular-nums">{formatCurrency(b.monthly_actual)}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center justify-center py-12 text-gray-400 text-sm">
                No budget data. <button onClick={() => router.push('/budget')} className="ml-1 text-blue-500 underline">Set up</button>
              </div>
            )}

          </div>
        </div>

        {/* Drill-Down Panel Tabs */}
        <div className="rounded-2xl border bg-gradient-to-br from-white to-slate-50/80 shadow-sm overflow-hidden">
          {/* Tab Navigation */}
          <div className="flex items-center gap-1 p-2 bg-gray-50/80 border-b">
            {([
              { key: 'meals', label: 'Meal Categories', icon: UtensilsCrossed },
              { key: 'budget', label: 'Budget vs Actual', icon: DollarSign },
              { key: 'kitchenette', label: 'Kitchenette', icon: UtensilsCrossed },
            ] as const).map(({ key, label }) => (
              <button
                key={key}
                onClick={() => {
                  setBvaPanel(key);
                  if (key === 'meals' && !mealsDrill) loadMealsDetail();
                  if (key === 'kitchenette' && !kitchenette) loadKitchenette();
                }}
                className={`px-4 py-2 rounded-xl text-xs font-medium transition-all ${
                  bvaPanel === key
                    ? 'bg-white shadow-sm text-gray-900 border'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-white/60'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="p-5">
            {/* ── Meal Categories Panel ── */}
            {bvaPanel === 'meals' && (
              mealsDrillLoading ? (
                <div className="h-64 flex items-center justify-center text-gray-400 text-sm">
                  <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading meal types...
                </div>
              ) : mealsDrill?.chart_data?.length > 0 ? (
                <div>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                      <BarChart data={mealsDrill.chart_data} barGap={1}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                        <XAxis dataKey="month_name" tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} />
                        <Tooltip
                          contentStyle={{ borderRadius: '12px', border: '1px solid #e5e7eb', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' }}
                          formatter={(val: any, name: any) => [Number(val).toLocaleString(), String(name)]}
                        />
                        {(mealsDrill.product_keys || []).map((pk: string, i: number) => (
                          <Bar key={pk} dataKey={pk} stackId="types" fill={MEAL_COLORS[i % MEAL_COLORS.length]} name={pk} radius={i === (mealsDrill.product_keys || []).length - 1 ? [3, 3, 0, 0] : [0, 0, 0, 0]} />
                        ))}
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  {/* Legend table */}
                  <div className="mt-4 grid grid-cols-2 md:grid-cols-3 gap-2">
                    {(mealsDrill.series || []).map((s: any, i: number) => (
                      <div key={s.product_name} className="flex items-center gap-2 p-2 rounded-lg bg-gray-50/80 border text-xs">
                        <div className="w-3 h-3 rounded flex-shrink-0" style={{ backgroundColor: MEAL_COLORS[i % MEAL_COLORS.length] }} />
                        <div className="min-w-0 flex-1">
                          <p className="text-gray-700 truncate font-medium">{s.product_name}</p>
                          <p className="text-gray-500 tabular-nums">{s.total_qty.toLocaleString()} meals &middot; {formatCurrency(s.total_cost)}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="h-64 flex items-center justify-center text-gray-400 text-sm">No meal type data</div>
              )
            )}

            {/* ── Budget vs Actual Panel ── */}
            {bvaPanel === 'budget' && (
              mealsBudgetLoading ? (
                <div className="h-64 flex items-center justify-center text-gray-400 text-sm">
                  <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading budget data...
                </div>
              ) : mealsBudget?.sites?.length > 0 ? (
                <div className="space-y-6">
                  {mealsBudget.sites.map((site: any) => (
                    <div key={site.site_id}>
                      <p className="text-sm font-semibold text-gray-800 mb-2">{site.site_name}</p>
                      <div className="h-48">
                        <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                          <BarChart data={site.monthly} barGap={4}>
                            <defs>
                              <linearGradient id={`gradBudget${site.site_id}`} x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#94a3b8" stopOpacity={0.6} />
                                <stop offset="100%" stopColor="#94a3b8" stopOpacity={0.2} />
                              </linearGradient>
                              <linearGradient id={`gradActual${site.site_id}`} x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#6366f1" stopOpacity={0.9} />
                                <stop offset="100%" stopColor="#6366f1" stopOpacity={0.5} />
                              </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                            <XAxis dataKey="month_name" tick={{ fontSize: 10, fill: '#6b7280' }} axisLine={false} tickLine={false} />
                            <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} axisLine={false} tickLine={false} tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`} />
                            <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #e5e7eb' }} formatter={(val: any, name: any) => [formatCurrency(Number(val)), String(name)]} />
                            <Bar dataKey="budget" fill={`url(#gradBudget${site.site_id})`} name="Budget" radius={[3, 3, 0, 0]} />
                            <Bar dataKey="actual" fill={`url(#gradActual${site.site_id})`} name="Actual" radius={[3, 3, 0, 0]} />
                            <Legend wrapperStyle={{ fontSize: '11px' }} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="h-64 flex items-center justify-center text-gray-400 text-sm">No budget data available</div>
              )
            )}

            {/* ── Kitchenette Panel ── */}
            {bvaPanel === 'kitchenette' && (
              kitchenetteLoading ? (
                <div className="h-64 flex items-center justify-center text-gray-400 text-sm">
                  <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading kitchenette data...
                </div>
              ) : kitchenette?.families?.length > 0 ? (
                <div>
                  <p className="text-xs text-gray-500 mb-2">Combined view (NZ + KG). Click a category for site/period drill-down.</p>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                      <BarChart data={kitchenette.chart_data} barGap={1}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                        <XAxis dataKey="month_name" tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`} />
                        <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #e5e7eb' }} formatter={(val: any, name: any) => [formatCurrency(Number(val)), String(name)]} />
                        {(kitchenette.families || []).map((f: any, i: number) => (
                          <Bar
                            key={f.family_key}
                            dataKey={`${f.family_name}_cost`}
                            stackId="kit"
                            fill={KITCHEN_COLORS[i % KITCHEN_COLORS.length]}
                            name={f.family_name}
                            radius={i === (kitchenette.families || []).length - 1 ? [3, 3, 0, 0] : [0, 0, 0, 0]}
                          />
                        ))}
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  {/* Clickable family summary cards → drill-down */}
                  <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-2">
                    {(kitchenette.families || []).map((f: any, i: number) => (
                      <button
                        key={f.family_key}
                        onClick={() => loadKitchenetteDrill(f.family_key, f.family_name)}
                        className="text-left rounded-xl bg-gray-50/80 border p-3 hover:bg-indigo-50 hover:border-indigo-300 hover:shadow-sm transition cursor-pointer"
                      >
                        <div className="flex items-center gap-1.5 mb-1">
                          <div className="w-2.5 h-2.5 rounded" style={{ backgroundColor: KITCHEN_COLORS[i % KITCHEN_COLORS.length] }} />
                          <p className="text-xs font-medium text-gray-700 truncate">{f.family_name}</p>
                        </div>
                        <p className="text-sm font-bold tabular-nums text-gray-900">{formatCurrency(f.total_cost)}</p>
                        <p className="text-[10px] text-gray-500 tabular-nums">{f.total_qty.toLocaleString()} units</p>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="h-64 flex flex-col items-center justify-center text-gray-400 text-sm gap-3">
                  <span>No kitchenette data for this year.</span>
                  <button
                    onClick={async () => {
                      setKitchenetteLoading(true);
                      try {
                        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/proformas/reextract-kitchenette?year=${smYear}`, {
                          method: 'POST',
                          headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
                        });
                        const data = await res.json();
                        alert(`Re-extracted ${data.total_items_saved || 0} kitchenette items from ${data.processed || 0} proformas.${data.message ? `\n\n${data.message}` : ''}`);
                        await loadKitchenette();
                      } catch (e) {
                        alert('Re-extract failed: ' + (e as Error).message);
                        setKitchenetteLoading(false);
                      }
                    }}
                    className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs hover:bg-indigo-700"
                  >
                    Re-extract from stored proformas
                  </button>
                  <span className="text-xs">Or upload proformas with a מטבחונים tab.</span>
                </div>
              )
            )}
          </div>
        </div>
      </div>

      {/* ═══════ DAILY MEALS ═══════ */}
      <Card className="overflow-hidden rounded-xl border bg-card shadow-sm">
        <CardHeader className="pb-3">
          <div className="flex justify-between items-center">
            <div>
              <CardTitle className="text-base font-semibold">Daily Meals</CardTitle>
              <p className="text-xs text-muted-foreground mt-0.5">
                FoodHouse daily meal counts from email reports
              </p>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="file"
                accept=".csv"
                ref={csvInputRef}
                onChange={handleCsvUpload}
                className="hidden"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => csvInputRef.current?.click()}
                disabled={csvUploading}
                className="border-orange-300 text-orange-700 hover:bg-orange-50"
              >
                {csvUploading ? (
                  <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                ) : (
                  <Upload className="w-4 h-4 mr-1" />
                )}
                {csvUploading ? 'Uploading...' : 'Upload CSV'}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* Upload result message */}
          {csvResult && (
            <div className={`mb-4 p-3 rounded-lg text-sm ${
              csvResult.status === 'error'
                ? 'bg-red-50 text-red-700 border border-red-200'
                : 'bg-green-50 text-green-700 border border-green-200'
            }`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {csvResult.status === 'error' ? (
                    <AlertCircle className="w-4 h-4" />
                  ) : (
                    <CheckCircle2 className="w-4 h-4" />
                  )}
                  <span>
                    {csvResult.status === 'error'
                      ? csvResult.message
                      : `${csvResult.items_processed} records imported for ${csvResult.date} (${csvResult.created} new, ${csvResult.updated} updated)`}
                  </span>
                </div>
                <button onClick={() => setCsvResult(null)} className="text-gray-400 hover:text-gray-600 ml-2">
                  <X className="w-3 h-3" />
                </button>
              </div>
            </div>
          )}

          {/* Controls */}
          <div className="flex flex-wrap items-center gap-2 mb-3 text-xs">
            <div className="flex gap-1">
              {[7, 14, 30].map((d) => (
                <button
                  key={d}
                  onClick={() => { setDailyMealsDays(d); loadDailyMeals(d, dailyMealsSiteId); }}
                  className={`px-3 py-1 rounded-full font-medium transition-colors ${
                    dailyMealsDays === d ? 'bg-orange-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {d}d
                </button>
              ))}
            </div>
            {dailyMeals?.sites?.length > 0 && (
              <select
                value={dailyMealsSiteId ?? ''}
                onChange={(e) => {
                  const v = e.target.value ? Number(e.target.value) : undefined;
                  setDailyMealsSiteId(v);
                  loadDailyMeals(dailyMealsDays, v);
                }}
                className="border rounded px-2 py-1 bg-white text-xs"
              >
                <option value="">All Sites</option>
                {dailyMeals.sites.map((s: any) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            )}
            {dailyMeals?.summary && (
              <span className="text-gray-500 ml-auto">
                {dailyMeals.summary.days_with_data} days &middot;
                avg {dailyMeals.summary.avg_daily}/day &middot;
                total {dailyMeals.summary.total_meals.toLocaleString()}
              </span>
            )}
          </div>

          {dailyMealsLoading ? (
            <div className="text-center py-8 text-gray-400 text-sm">Loading daily meals...</div>
          ) : !dailyMeals?.chart_data?.length ? (
            <div className="text-center py-8">
              <UtensilsCrossed className="w-10 h-10 mx-auto mb-3 text-gray-300" />
              <p className="text-gray-400 mb-2">No daily meal data yet</p>
              <p className="text-xs text-gray-400">Upload a CSV or set up Power Automate to push daily reports</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Daily bars chart — grouped by site, stacked by meal type */}
              <div className="lg:col-span-2">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-medium text-gray-500">Daily Meal Count by Type</p>
                  {!dailyMealsSiteId && (
                    <div className="flex items-center gap-3 text-[10px]">
                      <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-sm bg-gray-300" /> Left = NZ</span>
                      <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-sm bg-gray-500" /> Right = KG</span>
                      <span className="mx-1 text-gray-300">|</span>
                      <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-sm" style={{ background: '#ef4444' }} /> Meat</span>
                      <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-sm" style={{ background: '#3b82f6' }} /> Dairy</span>
                      <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-sm" style={{ background: '#f59e0b' }} /> Main Only</span>
                    </div>
                  )}
                </div>
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                    <BarChart data={dailyMeals.chart_data} barGap={0} barCategoryGap="20%">
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="date"
                        tick={{ fontSize: 10 }}
                        tickFormatter={(v: string) => {
                          const d = new Date(v);
                          return `${d.getDate()}/${d.getMonth() + 1}`;
                        }}
                      />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip
                        labelFormatter={(v: any) => {
                          const d = new Date(String(v));
                          return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
                        }}
                        formatter={(val: any, name: any) => [Number(val).toLocaleString(), String(name)]}
                      />
                      {dailyMealsSiteId ? (
                        /* Single site — simple stacked bars */
                        (dailyMeals.meal_type_keys || []).map((key: string, i: number) => (
                          <Bar
                            key={key}
                            dataKey={key}
                            stackId="meals"
                            fill={
                              key.includes('Meat') ? '#ef4444' :
                              key.includes('Dairy') ? '#3b82f6' :
                              key.includes('Main') ? '#f59e0b' :
                              SUPPLIER_COLORS[i % SUPPLIER_COLORS.length]
                            }
                            name={key}
                          />
                        ))
                      ) : (
                        /* All sites — grouped stacked: NZ stack + KG stack side by side */
                        (dailyMeals.meal_type_keys || []).map((key: string, i: number) => {
                          const siteMatch = key.match(/\(([^)]+)\)/);
                          const siteName = siteMatch ? siteMatch[1] : 'default';
                          const mealType = key.replace(/\s*\([^)]+\)/, '').trim();
                          const opacity = siteName.includes('Kiryat') ? 0.75 : 1;
                          const fill =
                            mealType.includes('Meat') ? '#ef4444' :
                            mealType.includes('Dairy') ? '#3b82f6' :
                            mealType.includes('Main') ? '#f59e0b' :
                            SUPPLIER_COLORS[i % SUPPLIER_COLORS.length];
                          return (
                            <Bar
                              key={key}
                              dataKey={key}
                              stackId={siteName}
                              fill={fill}
                              fillOpacity={opacity}
                              name={key}
                              legendType="none"
                            />
                          );
                        })
                      )}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Per-site comparison sidebar */}
              <div>
                <p className="text-xs font-medium text-gray-500 mb-3">
                  {dailyMeals.budget_comparison?.[0]?.month_name || 'Monthly'} — By Site
                </p>
                {dailyMeals.budget_comparison?.length > 0 ? (
                  <div className="space-y-3">
                    {dailyMeals.budget_comparison.map((bc: any) => {
                      const mealsPct = bc.avg_meals_6m > 0 ? Math.round(bc.meals / bc.avg_meals_6m * 100) : 0;
                      const costPct = bc.budget > 0 ? Math.round(bc.cost / bc.budget * 100) : 0;
                      const mealsDiff = bc.avg_meals_6m > 0 ? bc.meals - bc.avg_meals_6m : 0;
                      return (
                        <div key={bc.site_id} className="p-2.5 bg-gray-50 rounded-lg">
                          <p className="text-xs font-semibold text-gray-700 mb-2">{bc.site_name}</p>

                          {/* Meals vs 6-month avg */}
                          <div className="mb-2">
                            <div className="flex justify-between text-xs mb-0.5">
                              <span className="text-gray-500">Meals</span>
                              <span className={`font-medium ${mealsDiff > 0 ? 'text-green-600' : mealsDiff < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                                {bc.meals.toLocaleString()}
                                {bc.avg_meals_6m > 0 && (
                                  <span className="text-gray-400 font-normal"> / {bc.avg_meals_6m.toLocaleString()} avg</span>
                                )}
                              </span>
                            </div>
                            {bc.avg_meals_6m > 0 && (
                              <div className="h-1.5 bg-gray-200 rounded-full">
                                <div
                                  className={`h-1.5 rounded-full ${
                                    mealsPct > 110 ? 'bg-green-500' : mealsPct < 80 ? 'bg-red-500' : 'bg-blue-500'
                                  }`}
                                  style={{ width: `${Math.min(mealsPct, 100)}%` }}
                                />
                              </div>
                            )}
                          </div>

                          {/* Cost vs budget */}
                          <div>
                            <div className="flex justify-between text-xs mb-0.5">
                              <span className="text-gray-500">Cost</span>
                              <span className="font-medium text-gray-600">
                                ₪{(bc.cost || 0).toLocaleString()}
                                {bc.budget > 0 && (
                                  <span className="text-gray-400 font-normal"> / ₪{bc.budget.toLocaleString()}</span>
                                )}
                              </span>
                            </div>
                            {bc.budget > 0 && (
                              <div className="h-1.5 bg-gray-200 rounded-full">
                                <div
                                  className={`h-1.5 rounded-full ${
                                    costPct > 90 ? 'bg-red-500' : costPct > 70 ? 'bg-amber-500' : 'bg-green-500'
                                  }`}
                                  style={{ width: `${Math.min(costPct, 100)}%` }}
                                />
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-center py-6 text-xs text-gray-400">
                    No meal data for this month
                  </div>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ═══════ PROJECTS + MAINTENANCE ═══════ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card
          className="group overflow-hidden rounded-xl border bg-card shadow-sm card-hover cursor-pointer"
          onClick={() => router.push('/projects')}
        >
          <CardHeader className="pb-3">
            <div className="flex justify-between items-center">
              <div>
                <CardTitle className="text-base font-semibold">Active Projects</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">{projects.length} ongoing</p>
              </div>
              <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-foreground group-hover:translate-x-0.5 transition-all" />
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
          className="group overflow-hidden rounded-xl border bg-card shadow-sm card-hover cursor-pointer"
          onClick={() => router.push('/maintenance')}
        >
          <CardHeader className="pb-3">
            <div className="flex justify-between items-center">
              <div>
                <CardTitle className="text-base font-semibold">Maintenance Budget</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">Q{data?.current_quarter} {data?.current_year}</p>
              </div>
              <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-foreground group-hover:translate-x-0.5 transition-all" />
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

      {/* ═══════ MEETINGS + TODOS ═══════ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card
          className="group overflow-hidden rounded-xl border bg-card shadow-sm card-hover cursor-pointer"
          onClick={() => router.push('/meetings')}
        >
          <CardHeader className="pb-3">
            <div className="flex justify-between items-center">
              <div>
                <CardTitle className="text-base font-semibold">Upcoming Meetings</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">{meetings.length} scheduled</p>
              </div>
              <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-foreground group-hover:translate-x-0.5 transition-all" />
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
          className="group overflow-hidden rounded-xl border bg-card shadow-sm card-hover cursor-pointer"
          onClick={() => router.push('/todos')}
        >
          <CardHeader className="pb-3">
            <div className="flex justify-between items-center">
              <div>
                <CardTitle className="text-base font-semibold">Tasks & Follow-ups</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {todos.mine.length + todos.delegated.length} open
                  {todos.overdue_count > 0 && (
                    <span className="text-red-600 font-medium ml-1">&middot; {todos.overdue_count} overdue</span>
                  )}
                </p>
              </div>
              <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-foreground group-hover:translate-x-0.5 transition-all" />
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

      {/* ═══════ AI CHAT ═══════ */}
      <Card className="overflow-hidden rounded-xl border bg-card shadow-sm">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 text-white">
              <MessageSquare className="w-4 h-4" />
            </div>
            <div>
              <CardTitle className="text-base font-semibold">AI Assistant</CardTitle>
              <p className="text-xs text-muted-foreground mt-0.5">Ask anything about your operations</p>
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
                      ? 'bg-gray-100 text-gray-800 ml-4 md:ml-8 whitespace-pre-wrap'
                      : 'bg-indigo-50 text-gray-800 mr-4 md:mr-8'
                  }`}
                >
                  {msg.role === 'ai' ? <ChatMessageRenderer text={msg.text} /> : msg.text}
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
              placeholder="Ask about budget, violations, meetings..."
              className="flex-1 px-4 py-2.5 border rounded-lg bg-muted/30 focus:bg-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm transition-colors"
              disabled={chatLoading}
            />
            <Button
              onClick={handleChat}
              disabled={chatLoading || !chatInput.trim()}
              className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white shadow-sm"
              aria-label="Send message"
            >
              {chatLoading ? (
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>

          <div className="flex gap-2 mt-3 flex-wrap">
            {['Budget status this month', 'Upcoming meetings summary', 'Recent violations'].map((q) => (
              <button
                key={q}
                onClick={() => quickChat(q)}
                className="text-xs px-3 py-1.5 rounded-full border border-gray-200 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* ── Kitchenette Drill-down Modal ── */}
      {kitDrillFamily && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={closeKitDrill}>
          <div className="w-full max-w-3xl max-h-[85vh] overflow-auto bg-white rounded-2xl shadow-2xl ring-1 ring-black/5" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 bg-white z-10 border-b px-5 py-3 flex items-center justify-between">
              <div className="flex items-center gap-3">
                {kitDrillMonth && (
                  <button
                    onClick={() => { setKitDrillMonth(undefined); loadKitchenetteDrill(kitDrillFamily.family_key, kitDrillFamily.family_name, kitDrillSite, undefined); }}
                    className="text-sm text-indigo-600 hover:underline"
                  >← Back</button>
                )}
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">
                    {kitDrillFamily.family_name}
                    {kitDrillMonth && kitDrillData?.month_name && <span className="text-gray-500 font-normal"> · {kitDrillData.month_name} {kitDrillData.year}</span>}
                  </h3>
                  <p className="text-xs text-gray-500">
                    {kitDrillMonth ? 'Product breakdown' : 'Monthly trend — click a month to see products'}
                  </p>
                </div>
              </div>
              <button onClick={closeKitDrill} className="text-gray-400 hover:text-gray-700 text-xl leading-none">×</button>
            </div>

            {/* Filters */}
            <div className="px-5 py-3 border-b flex items-center gap-3 flex-wrap">
              <label className="text-xs text-gray-600">Site:</label>
              <select
                value={kitDrillSite ?? ''}
                onChange={(e) => {
                  const v = e.target.value ? parseInt(e.target.value) : undefined;
                  setKitDrillSite(v);
                  loadKitchenetteDrill(kitDrillFamily.family_key, kitDrillFamily.family_name, v, kitDrillMonth);
                }}
                className="text-sm border rounded-lg px-2 py-1"
              >
                <option value="">All Sites</option>
                <option value="1">Nes Ziona</option>
                <option value="2">Kiryat Gat</option>
              </select>
              {!kitDrillMonth && (
                <span className="text-xs text-gray-500 ml-auto">Total: <span className="font-bold text-gray-900">{formatCurrency(kitDrillData?.total_cost || 0)}</span></span>
              )}
              {kitDrillMonth && (
                <span className="text-xs text-gray-500 ml-auto">Month total: <span className="font-bold text-gray-900">{formatCurrency(kitDrillData?.total_cost || 0)}</span></span>
              )}
            </div>

            <div className="p-5">
              {kitDrillLoading ? (
                <div className="h-64 flex items-center justify-center text-gray-400">
                  <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading…
                </div>
              ) : !kitDrillData ? (
                <div className="h-32 flex items-center justify-center text-gray-400 text-sm">No data</div>
              ) : kitDrillData.level === 'monthly' ? (
                <>
                  <div className="h-72">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={kitDrillData.chart_data}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                        <XAxis dataKey="month_name" tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`} />
                        <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #e5e7eb' }} formatter={(val: any, name: any) => [formatCurrency(Number(val)), String(name)]} />
                        {(kitDrillData.sites || []).map((s: any, i: number) => (
                          <Bar
                            key={s.name}
                            dataKey={s.name}
                            stackId="kd"
                            fill={KITCHEN_COLORS[i % KITCHEN_COLORS.length]}
                            name={s.name}
                            radius={i === (kitDrillData.sites || []).length - 1 ? [3, 3, 0, 0] : [0, 0, 0, 0]}
                            onClick={(data: any) => {
                              if (data?.payload?.month) {
                                setKitDrillMonth(data.payload.month);
                                loadKitchenetteDrill(kitDrillFamily.family_key, kitDrillFamily.family_name, kitDrillSite, data.payload.month);
                              }
                            }}
                            cursor="pointer"
                          />
                        ))}
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="mt-4 grid grid-cols-2 md:grid-cols-3 gap-2">
                    {(kitDrillData.chart_data || []).filter((m: any) => m.total > 0).map((m: any) => (
                      <button
                        key={m.month}
                        onClick={() => { setKitDrillMonth(m.month); loadKitchenetteDrill(kitDrillFamily.family_key, kitDrillFamily.family_name, kitDrillSite, m.month); }}
                        className="text-left p-3 rounded-xl border bg-gray-50/80 hover:bg-indigo-50 hover:border-indigo-300 transition"
                      >
                        <p className="text-xs text-gray-600">{m.month_name}</p>
                        <p className="text-sm font-bold tabular-nums text-gray-900">{formatCurrency(m.total)}</p>
                      </button>
                    ))}
                  </div>
                </>
              ) : kitDrillData.level === 'products' ? (
                <div className="space-y-1">
                  {(kitDrillData.products || []).length === 0 ? (
                    <p className="text-sm text-gray-400 text-center py-8">No products in this period</p>
                  ) : (
                    (kitDrillData.products || []).map((p: any) => (
                      <div key={p.product_name} className="flex items-center justify-between p-3 rounded-lg border bg-gray-50/50 hover:bg-gray-100 transition">
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-gray-900 truncate">{p.product_name}</p>
                          <p className="text-xs text-gray-500 tabular-nums">
                            {p.qty.toLocaleString()} {p.unit}
                            {Object.keys(p.by_site || {}).length > 0 && (
                              <span className="ml-2 text-gray-400">
                                · {Object.entries(p.by_site).map(([s, v]: any) => `${s}: ${formatCurrency(Number(v))}`).join(' · ')}
                              </span>
                            )}
                          </p>
                        </div>
                        <p className="text-sm font-bold tabular-nums text-gray-900 ml-3">{formatCurrency(p.cost)}</p>
                      </div>
                    ))
                  )}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
