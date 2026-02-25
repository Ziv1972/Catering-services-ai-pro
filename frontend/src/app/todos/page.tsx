'use client';

import { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ListTodo, Plus, CheckCircle2, Circle, AlertCircle,
  Trash2, Clock, Link2
} from 'lucide-react';
import { todosAPI } from '@/lib/api';
import { format } from 'date-fns';

const PRIORITIES = ['low', 'medium', 'high', 'urgent'];
const ENTITY_TYPES = ['menu_check', 'proforma', 'supplier', 'contract', 'compliance_rule', 'project'];

export default function TodosPage() {
  const [todos, setTodos] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState('all');
  const [form, setForm] = useState({
    title: '', description: '', assigned_to: '', priority: 'medium',
    due_date: '', linked_entity_type: '', linked_entity_label: '',
  });

  useEffect(() => { loadTodos(); }, [filter]);

  const loadTodos = async () => {
    try {
      const params: any = {};
      if (filter !== 'all') params.filter = filter;
      const data = await todosAPI.list(params);
      setTodos(data);
    } finally { setLoading(false); }
  };

  const handleCreate = async () => {
    setSaving(true);
    try {
      const payload: any = {
        title: form.title,
        priority: form.priority,
      };
      if (form.description) payload.description = form.description;
      if (form.assigned_to) payload.assigned_to = form.assigned_to;
      if (form.due_date) payload.due_date = form.due_date;
      if (form.linked_entity_type) {
        payload.linked_entity_type = form.linked_entity_type;
        payload.linked_entity_label = form.linked_entity_label;
      }

      await todosAPI.create(payload);
      setShowForm(false);
      setForm({ title: '', description: '', assigned_to: '', priority: 'medium', due_date: '', linked_entity_type: '', linked_entity_label: '' });
      await loadTodos();
    } finally { setSaving(false); }
  };

  const handleComplete = async (id: number) => {
    await todosAPI.complete(id);
    await loadTodos();
  };

  const handleReopen = async (id: number) => {
    await todosAPI.update(id, { status: 'pending' });
    await loadTodos();
  };

  const handleDelete = async (id: number) => {
    await todosAPI.delete(id);
    await loadTodos();
  };

  const getPriorityColor = (p: string) => {
    const colors: Record<string, string> = {
      urgent: 'bg-red-100 text-red-800',
      high: 'bg-orange-100 text-orange-800',
      medium: 'bg-blue-100 text-blue-800',
      low: 'bg-gray-100 text-gray-700',
    };
    return colors[p] || colors.medium;
  };

  const myTodos = todos.filter(t => !t.assigned_to && t.status !== 'done');
  const delegated = todos.filter(t => t.assigned_to && t.status !== 'done');
  const done = todos.filter(t => t.status === 'done');
  const overdueCount = todos.filter(t => t.is_overdue).length;

  if (loading) {
    return <div className="flex items-center justify-center h-screen"><p className="text-gray-500">Loading tasks...</p></div>;
  }

  return (
    <main className="max-w-5xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Tasks & Follow-ups</h1>
          <p className="text-gray-500 text-sm">
            {myTodos.length + delegated.length} open · {done.length} completed
            {overdueCount > 0 && <span className="text-red-600"> · {overdueCount} overdue</span>}
          </p>
        </div>
        <Button onClick={() => setShowForm(!showForm)} className="bg-emerald-600 hover:bg-emerald-700">
          <Plus className="w-4 h-4 mr-2" /> New Task
        </Button>
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-6">
        {[
          { key: 'all', label: 'All' },
          { key: 'mine', label: 'My Tasks' },
          { key: 'delegated', label: 'Delegated' },
        ].map(f => (
          <button key={f.key} onClick={() => setFilter(f.key)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              filter === f.key ? 'bg-emerald-100 text-emerald-800' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}>
            {f.label}
          </button>
        ))}
      </div>

      {/* Form */}
      {showForm && (
        <Card className="mb-6 border-emerald-200">
          <CardHeader><CardTitle>New Task</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
                <input value={form.title} onChange={e => setForm({...form, title: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md" placeholder="e.g. Review FoodHouse contract" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Assigned To <span className="text-gray-400">(empty = my task)</span>
                </label>
                <input value={form.assigned_to} onChange={e => setForm({...form, assigned_to: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md" placeholder="e.g. David" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
                <select value={form.priority} onChange={e => setForm({...form, priority: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md">
                  {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Due Date</label>
                <input type="date" value={form.due_date} onChange={e => setForm({...form, due_date: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md" />
              </div>
              <div className="md:col-span-2 flex gap-2">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Link to (optional)</label>
                  <select value={form.linked_entity_type} onChange={e => setForm({...form, linked_entity_type: e.target.value})}
                    className="w-full px-3 py-2 border rounded-md">
                    <option value="">No link</option>
                    {ENTITY_TYPES.map(t => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
                  </select>
                </div>
                {form.linked_entity_type && (
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-700 mb-1">Link label</label>
                    <input value={form.linked_entity_label} onChange={e => setForm({...form, linked_entity_label: e.target.value})}
                      className="w-full px-3 py-2 border rounded-md" placeholder="e.g. FoodHouse Contract 2026" />
                  </div>
                )}
              </div>
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Description (optional)</label>
              <textarea value={form.description} onChange={e => setForm({...form, description: e.target.value})}
                className="w-full px-3 py-2 border rounded-md" rows={2} />
            </div>
            <div className="flex gap-3">
              <Button onClick={handleCreate} disabled={saving || !form.title} className="bg-emerald-600 hover:bg-emerald-700">
                {saving ? 'Creating...' : 'Create Task'}
              </Button>
              <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* My Tasks */}
      {(filter === 'all' || filter === 'mine') && myTodos.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-semibold text-gray-500 uppercase mb-3">My Tasks ({myTodos.length})</h2>
          <div className="space-y-2">
            {myTodos.map((t: any) => (
              <Card key={t.id} className={t.is_overdue ? 'border-red-200' : ''}>
                <CardContent className="py-3">
                  <div className="flex items-center gap-3">
                    <button onClick={() => handleComplete(t.id)}>
                      <Circle className="w-5 h-5 text-gray-300 hover:text-green-500 transition-colors" />
                    </button>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        {t.is_overdue && <AlertCircle className="w-4 h-4 text-red-500" />}
                        <span className={`font-medium text-sm ${t.is_overdue ? 'text-red-700' : ''}`}>{t.title}</span>
                        <Badge className={`text-xs ${getPriorityColor(t.priority)}`}>{t.priority}</Badge>
                        {t.linked_entity_type && (
                          <Badge variant="outline" className="text-xs">
                            <Link2 className="w-3 h-3 mr-1" />{t.linked_entity_label || t.linked_entity_type}
                          </Badge>
                        )}
                      </div>
                      {t.due_date && (
                        <p className={`text-xs mt-0.5 ${t.is_overdue ? 'text-red-500' : 'text-gray-500'}`}>
                          <Clock className="w-3 h-3 inline mr-1" />
                          {format(new Date(t.due_date), 'MMM d, yyyy')}
                          {t.is_overdue && ' (overdue)'}
                        </p>
                      )}
                    </div>
                    <button onClick={() => handleDelete(t.id)} className="text-gray-400 hover:text-red-500">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Delegated */}
      {(filter === 'all' || filter === 'delegated') && delegated.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-semibold text-gray-500 uppercase mb-3">Delegated ({delegated.length})</h2>
          <div className="space-y-2">
            {delegated.map((t: any) => (
              <Card key={t.id} className={t.is_overdue ? 'border-red-200' : ''}>
                <CardContent className="py-3">
                  <div className="flex items-center gap-3">
                    <button onClick={() => handleComplete(t.id)}>
                      <Circle className="w-5 h-5 text-gray-300 hover:text-green-500 transition-colors" />
                    </button>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        {t.is_overdue && <AlertCircle className="w-4 h-4 text-red-500" />}
                        <Badge variant="outline" className="text-xs font-semibold">→ {t.assigned_to}</Badge>
                        <span className={`font-medium text-sm ${t.is_overdue ? 'text-red-700' : ''}`}>{t.title}</span>
                        <Badge className={`text-xs ${getPriorityColor(t.priority)}`}>{t.priority}</Badge>
                      </div>
                      {t.due_date && (
                        <p className={`text-xs mt-0.5 ${t.is_overdue ? 'text-red-500' : 'text-gray-500'}`}>
                          <Clock className="w-3 h-3 inline mr-1" />
                          {format(new Date(t.due_date), 'MMM d, yyyy')}
                        </p>
                      )}
                    </div>
                    <button onClick={() => handleDelete(t.id)} className="text-gray-400 hover:text-red-500">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Completed */}
      {done.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-500 uppercase mb-3">Completed ({done.length})</h2>
          <div className="space-y-2">
            {done.slice(0, 5).map((t: any) => (
              <Card key={t.id} className="opacity-60">
                <CardContent className="py-3">
                  <div className="flex items-center gap-3">
                    <button onClick={() => handleReopen(t.id)}>
                      <CheckCircle2 className="w-5 h-5 text-green-500 hover:text-gray-400 transition-colors" />
                    </button>
                    <span className="text-sm line-through text-gray-400">{t.title}</span>
                    {t.assigned_to && <Badge variant="outline" className="text-xs opacity-60">→ {t.assigned_to}</Badge>}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {todos.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <ListTodo className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">No tasks yet. Create your first task above.</p>
          </CardContent>
        </Card>
      )}
    </main>
  );
}
