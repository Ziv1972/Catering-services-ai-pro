'use client';

import { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DollarSign, Plus, Pencil, X, Package } from 'lucide-react';
import { supplierBudgetsAPI, suppliersAPI } from '@/lib/api';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend
} from 'recharts';

const MONTHS = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'];
const MONTH_LABELS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

export default function BudgetPage() {
  const [budgets, setBudgets] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [vsActual, setVsActual] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    supplier_id: '', site_id: '1', year: new Date().getFullYear().toString(),
    yearly_amount: '', jan: '', feb: '', mar: '', apr: '', may: '', jun: '',
    jul: '', aug: '', sep: '', oct: '', nov: '', dec: '',
  });

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    try {
      const [budgetList, supplierList, vsData] = await Promise.allSettled([
        supplierBudgetsAPI.list({ year: new Date().getFullYear() }),
        suppliersAPI.list(true),
        supplierBudgetsAPI.vsActual({ year: new Date().getFullYear() }),
      ]);
      if (budgetList.status === 'fulfilled') setBudgets(budgetList.value);
      if (supplierList.status === 'fulfilled') setSuppliers(supplierList.value);
      if (vsData.status === 'fulfilled') setVsActual(vsData.value);
    } finally { setLoading(false); }
  };

  const handleDistributeEvenly = () => {
    const yearly = parseFloat(form.yearly_amount) || 0;
    const monthly = Math.round(yearly / 12);
    const update: any = {};
    MONTHS.forEach(m => { update[m] = monthly.toString(); });
    setForm(prev => ({ ...prev, ...update }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload: any = {
        supplier_id: parseInt(form.supplier_id),
        site_id: parseInt(form.site_id),
        year: parseInt(form.year),
        yearly_amount: parseFloat(form.yearly_amount) || 0,
      };
      MONTHS.forEach(m => { payload[m] = parseFloat((form as any)[m]) || 0; });

      if (editId) {
        await supplierBudgetsAPI.update(editId, payload);
      } else {
        await supplierBudgetsAPI.create(payload);
      }
      setShowForm(false);
      setEditId(null);
      await loadData();
    } finally { setSaving(false); }
  };

  const startEdit = (b: any) => {
    setForm({
      supplier_id: b.supplier_id.toString(),
      site_id: b.site_id.toString(),
      year: b.year.toString(),
      yearly_amount: b.yearly_amount.toString(),
      jan: (b.jan || 0).toString(), feb: (b.feb || 0).toString(),
      mar: (b.mar || 0).toString(), apr: (b.apr || 0).toString(),
      may: (b.may || 0).toString(), jun: (b.jun || 0).toString(),
      jul: (b.jul || 0).toString(), aug: (b.aug || 0).toString(),
      sep: (b.sep || 0).toString(), oct: (b.oct || 0).toString(),
      nov: (b.nov || 0).toString(), dec: (b.dec || 0).toString(),
    });
    setEditId(b.id);
    setShowForm(true);
  };

  const fmt = (v: number) => v.toLocaleString('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 });

  // Build chart data from vs-actual
  const chartData = vsActual ? MONTH_LABELS.map((label, idx) => {
    const monthNum = idx + 1;
    const monthItems = vsActual.items.filter((i: any) => i.month === monthNum);
    return {
      month: label,
      budget: monthItems.reduce((s: number, i: any) => s + i.budget, 0),
      actual: monthItems.reduce((s: number, i: any) => s + i.actual, 0),
    };
  }) : [];

  if (loading) {
    return <div className="flex items-center justify-center h-screen"><p className="text-gray-500">Loading budgets...</p></div>;
  }

  return (
    <main className="max-w-7xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Supplier Budgets</h1>
          <p className="text-gray-500 text-sm">{budgets.length} budget(s) for {new Date().getFullYear()}</p>
        </div>
        <Button onClick={() => { setShowForm(!showForm); setEditId(null); }} className="bg-blue-600 hover:bg-blue-700">
          <Plus className="w-4 h-4 mr-2" /> Add Budget
        </Button>
      </div>

      {/* Form */}
      {showForm && (
        <Card className="mb-6 border-blue-200">
          <CardHeader>
            <CardTitle>{editId ? 'Edit Budget' : 'New Supplier Budget'}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Supplier</label>
                <select value={form.supplier_id} onChange={e => setForm({...form, supplier_id: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md">
                  <option value="">Select...</option>
                  {suppliers.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Site</label>
                <select value={form.site_id} onChange={e => setForm({...form, site_id: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md">
                  <option value="1">Nes Ziona</option>
                  <option value="2">Kiryat Gat</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Year</label>
                <input type="number" value={form.year} onChange={e => setForm({...form, year: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Yearly Amount (ILS)</label>
                <div className="flex gap-2">
                  <input type="number" value={form.yearly_amount} onChange={e => setForm({...form, yearly_amount: e.target.value})}
                    className="flex-1 px-3 py-2 border rounded-md" />
                  <Button variant="outline" size="sm" onClick={handleDistributeEvenly} title="Distribute evenly">
                    ÷12
                  </Button>
                </div>
              </div>
            </div>

            <p className="text-sm font-medium text-gray-700 mb-2">Monthly Breakdown</p>
            <div className="grid grid-cols-3 md:grid-cols-6 lg:grid-cols-12 gap-2 mb-4">
              {MONTHS.map((m, i) => (
                <div key={m}>
                  <label className="block text-xs text-gray-500 mb-0.5">{MONTH_LABELS[i]}</label>
                  <input type="number" value={(form as any)[m]}
                    onChange={e => setForm({...form, [m]: e.target.value})}
                    className="w-full px-2 py-1.5 border rounded text-sm" />
                </div>
              ))}
            </div>

            <div className="flex gap-3">
              <Button onClick={handleSave} disabled={saving || !form.supplier_id} className="bg-blue-600 hover:bg-blue-700">
                {saving ? 'Saving...' : editId ? 'Update' : 'Create'}
              </Button>
              <Button variant="outline" onClick={() => { setShowForm(false); setEditId(null); }}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* YTD Chart */}
      {chartData.length > 0 && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Monthly Budget vs Actual ({new Date().getFullYear()})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <XAxis dataKey="month" />
                  <YAxis tickFormatter={(v: number) => `${(v/1000).toFixed(0)}K`} />
                  <Tooltip formatter={(val: number) => fmt(val)} />
                  <Legend />
                  <Bar dataKey="budget" fill="#93c5fd" name="Budget" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="actual" fill="#3b82f6" name="Actual" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Budget List */}
      {budgets.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <DollarSign className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">No budgets configured. Add your first supplier budget above.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {budgets.map((b: any) => {
            const ytdBudget = MONTHS.reduce((s, m) => s + ((b as any)[m] || 0), 0);
            return (
              <Card key={b.id}>
                <CardContent className="py-4">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-1">
                        <h3 className="font-semibold">{b.supplier_name}</h3>
                        <Badge variant="outline">{b.site_name}</Badge>
                        <Badge className="bg-blue-100 text-blue-800">{b.year}</Badge>
                      </div>
                      <p className="text-sm text-gray-600">
                        Yearly: {fmt(b.yearly_amount)} · Monthly avg: {fmt(ytdBudget / 12)}
                      </p>
                      {b.product_budgets?.length > 0 && (
                        <div className="flex gap-2 mt-2">
                          {b.product_budgets.map((pb: any) => (
                            <Badge key={pb.id} variant="outline" className="text-xs">
                              <Package className="w-3 h-3 mr-1" />
                              {pb.product_category}: {pb.monthly_quantity_limit} {pb.unit}/mo
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                    <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); startEdit(b); }}>
                      <Pencil className="w-4 h-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Totals */}
      {vsActual?.totals && (
        <Card className="mt-6 bg-gray-50">
          <CardContent className="py-4">
            <div className="grid grid-cols-4 gap-4 text-center">
              <div>
                <p className="text-xs text-gray-500">Total Budget</p>
                <p className="text-lg font-bold text-gray-900">{fmt(vsActual.totals.budget)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Total Actual</p>
                <p className="text-lg font-bold text-blue-600">{fmt(vsActual.totals.actual)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Variance</p>
                <p className={`text-lg font-bold ${vsActual.totals.variance >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {fmt(vsActual.totals.variance)}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500">% Used</p>
                <p className="text-lg font-bold text-gray-900">{vsActual.totals.percent_used}%</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </main>
  );
}
