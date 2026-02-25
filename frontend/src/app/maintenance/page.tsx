'use client';

import { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Wrench, Plus, Pencil, Trash2 } from 'lucide-react';
import { maintenanceAPI } from '@/lib/api';
import { format } from 'date-fns';

const CATEGORIES = ['equipment_repair', 'kitchen_upgrade', 'plumbing', 'electrical', 'hvac', 'general'];
const QUARTERS = [1, 2, 3, 4];

export default function MaintenancePage() {
  const [budgets, setBudgets] = useState<any[]>([]);
  const [expenses, setExpenses] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showBudgetForm, setShowBudgetForm] = useState(false);
  const [showExpenseForm, setShowExpenseForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [budgetForm, setBudgetForm] = useState({ site_id: '1', year: new Date().getFullYear().toString(), quarter: '1', budget_amount: '', notes: '' });
  const [expenseForm, setExpenseForm] = useState({ site_id: '1', date: '', description: '', amount: '', category: 'general', vendor: '', notes: '' });

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    try {
      const [b, e] = await Promise.allSettled([
        maintenanceAPI.listBudgets({ year: new Date().getFullYear() }),
        maintenanceAPI.listExpenses({ year: new Date().getFullYear() }),
      ]);
      if (b.status === 'fulfilled') setBudgets(b.value);
      if (e.status === 'fulfilled') setExpenses(e.value);
    } finally { setLoading(false); }
  };

  const handleCreateBudget = async () => {
    setSaving(true);
    try {
      await maintenanceAPI.createBudget({
        site_id: parseInt(budgetForm.site_id),
        year: parseInt(budgetForm.year),
        quarter: parseInt(budgetForm.quarter),
        budget_amount: parseFloat(budgetForm.budget_amount) || 0,
        notes: budgetForm.notes || undefined,
      });
      setShowBudgetForm(false);
      setBudgetForm({ site_id: '1', year: new Date().getFullYear().toString(), quarter: '1', budget_amount: '', notes: '' });
      await loadData();
    } finally { setSaving(false); }
  };

  const handleCreateExpense = async () => {
    setSaving(true);
    try {
      // Find matching budget
      const expDate = new Date(expenseForm.date);
      const quarter = Math.floor(expDate.getMonth() / 3) + 1;
      const matchBudget = budgets.find((b: any) =>
        b.site_id === parseInt(expenseForm.site_id) &&
        b.year === expDate.getFullYear() &&
        b.quarter === quarter
      );

      await maintenanceAPI.createExpense({
        site_id: parseInt(expenseForm.site_id),
        maintenance_budget_id: matchBudget?.id || undefined,
        date: expenseForm.date,
        description: expenseForm.description,
        amount: parseFloat(expenseForm.amount) || 0,
        category: expenseForm.category,
        vendor: expenseForm.vendor || undefined,
        notes: expenseForm.notes || undefined,
      });
      setShowExpenseForm(false);
      setExpenseForm({ site_id: '1', date: '', description: '', amount: '', category: 'general', vendor: '', notes: '' });
      await loadData();
    } finally { setSaving(false); }
  };

  const handleDeleteExpense = async (id: number) => {
    await maintenanceAPI.deleteExpense(id);
    await loadData();
  };

  const fmt = (v: number) => v.toLocaleString('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 });

  if (loading) {
    return <div className="flex items-center justify-center h-screen"><p className="text-gray-500">Loading maintenance data...</p></div>;
  }

  return (
    <main className="max-w-7xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Maintenance Budget</h1>
          <p className="text-gray-500 text-sm">Quarterly budgets and expense tracking</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => setShowBudgetForm(!showBudgetForm)} variant="outline">
            <Plus className="w-4 h-4 mr-2" /> Add Quarter Budget
          </Button>
          <Button onClick={() => setShowExpenseForm(!showExpenseForm)} className="bg-amber-600 hover:bg-amber-700">
            <Plus className="w-4 h-4 mr-2" /> Add Expense
          </Button>
        </div>
      </div>

      {/* Budget Form */}
      {showBudgetForm && (
        <Card className="mb-6 border-amber-200">
          <CardHeader><CardTitle>New Quarterly Budget</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Site</label>
                <select value={budgetForm.site_id} onChange={e => setBudgetForm({...budgetForm, site_id: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md">
                  <option value="1">Nes Ziona</option>
                  <option value="2">Kiryat Gat</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Year</label>
                <input type="number" value={budgetForm.year} onChange={e => setBudgetForm({...budgetForm, year: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Quarter</label>
                <select value={budgetForm.quarter} onChange={e => setBudgetForm({...budgetForm, quarter: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md">
                  {QUARTERS.map(q => <option key={q} value={q}>Q{q}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Budget Amount (ILS)</label>
                <input type="number" value={budgetForm.budget_amount} onChange={e => setBudgetForm({...budgetForm, budget_amount: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md" />
              </div>
            </div>
            <div className="flex gap-3">
              <Button onClick={handleCreateBudget} disabled={saving || !budgetForm.budget_amount} className="bg-amber-600 hover:bg-amber-700">
                {saving ? 'Saving...' : 'Create Budget'}
              </Button>
              <Button variant="outline" onClick={() => setShowBudgetForm(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Expense Form */}
      {showExpenseForm && (
        <Card className="mb-6 border-amber-200">
          <CardHeader><CardTitle>Add Expense</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Site</label>
                <select value={expenseForm.site_id} onChange={e => setExpenseForm({...expenseForm, site_id: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md">
                  <option value="1">Nes Ziona</option>
                  <option value="2">Kiryat Gat</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Date</label>
                <input type="date" value={expenseForm.date} onChange={e => setExpenseForm({...expenseForm, date: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Amount (ILS)</label>
                <input type="number" value={expenseForm.amount} onChange={e => setExpenseForm({...expenseForm, amount: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <input value={expenseForm.description} onChange={e => setExpenseForm({...expenseForm, description: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md" placeholder="e.g. AC unit repair" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                <select value={expenseForm.category} onChange={e => setExpenseForm({...expenseForm, category: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md">
                  {CATEGORIES.map(c => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Vendor</label>
                <input value={expenseForm.vendor} onChange={e => setExpenseForm({...expenseForm, vendor: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md" placeholder="Optional" />
              </div>
            </div>
            <div className="flex gap-3">
              <Button onClick={handleCreateExpense} disabled={saving || !expenseForm.description || !expenseForm.date}
                className="bg-amber-600 hover:bg-amber-700">
                {saving ? 'Saving...' : 'Add Expense'}
              </Button>
              <Button variant="outline" onClick={() => setShowExpenseForm(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Quarterly Budget Summary */}
      <h2 className="text-lg font-semibold mb-3">Quarterly Budgets</h2>
      {budgets.length === 0 ? (
        <Card className="mb-6">
          <CardContent className="py-8 text-center">
            <Wrench className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">No quarterly budgets set up yet.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          {budgets.map((b: any) => (
            <Card key={b.id}>
              <CardContent className="py-4">
                <div className="flex justify-between items-center mb-3">
                  <div className="flex items-center gap-2">
                    <Badge className="bg-amber-100 text-amber-800">Q{b.quarter}</Badge>
                    <span className="font-medium">{b.site_name}</span>
                  </div>
                  <span className="text-sm font-medium">
                    {fmt(b.actual_amount)} / {fmt(b.budget_amount)}
                  </span>
                </div>
                <div className="h-3 bg-gray-200 rounded-full mb-2">
                  <div
                    className={`h-3 rounded-full transition-all ${
                      b.budget_amount > 0 && b.actual_amount / b.budget_amount > 0.9 ? 'bg-red-500' :
                      b.budget_amount > 0 && b.actual_amount / b.budget_amount > 0.7 ? 'bg-amber-500' : 'bg-green-500'
                    }`}
                    style={{ width: `${Math.min(b.budget_amount > 0 ? b.actual_amount / b.budget_amount * 100 : 0, 100)}%` }}
                  />
                </div>
                <p className="text-xs text-gray-500">
                  Remaining: {fmt(b.budget_amount - b.actual_amount)}
                  {' · '}
                  {b.budget_amount > 0 ? Math.round(b.actual_amount / b.budget_amount * 100) : 0}% used
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Expense Log */}
      <h2 className="text-lg font-semibold mb-3">Expense Log</h2>
      {expenses.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-gray-500">No expenses recorded yet.</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="py-2">
            <div className="divide-y">
              {expenses.map((e: any) => (
                <div key={e.id} className="flex items-center justify-between py-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{e.description}</span>
                      <Badge variant="outline" className="text-xs">{e.category.replace('_', ' ')}</Badge>
                      {e.vendor && <span className="text-xs text-gray-500">· {e.vendor}</span>}
                    </div>
                    <p className="text-xs text-gray-500">
                      {e.site_name} · {format(new Date(e.date), 'MMM d, yyyy')}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-semibold text-sm">{fmt(e.amount)}</span>
                    <button onClick={() => handleDeleteExpense(e.id)}
                      className="text-gray-400 hover:text-red-500 transition-colors">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </main>
  );
}
