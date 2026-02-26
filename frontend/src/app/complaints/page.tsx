'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft, AlertTriangle, TrendingUp,
  CheckCircle2, Clock, Plus, X, DollarSign,
  Pencil, Trash2, ListFilter
} from 'lucide-react';
import { complaintsAPI, fineRulesAPI } from '@/lib/api';
import { format } from 'date-fns';

const SOURCES = ['manual', 'email', 'whatsapp', 'slack', 'form'];
const CATEGORIES = [
  'food_quality', 'temperature', 'service', 'variety',
  'dietary', 'cleanliness', 'equipment', 'other',
];
const SEVERITIES = ['low', 'medium', 'high', 'critical'];

export default function ComplaintsPage() {
  const router = useRouter();
  const [complaints, setComplaints] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [patterns, setPatterns] = useState<any[]>([]);
  const [fineRules, setFineRules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Add complaint form state
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    complaint_text: '',
    source: 'manual',
    site_id: '',
    category: '',
    severity: '',
    employee_name: '',
    is_anonymous: false,
    fine_rule_id: '',
    fine_amount: '',
  });

  // Fine catalog management
  const [showFineTab, setShowFineTab] = useState(false);
  const [showFineForm, setShowFineForm] = useState(false);
  const [fineForm, setFineForm] = useState({
    name: '', category: 'food_quality', amount: '', description: '',
  });
  const [editingFineId, setEditingFineId] = useState<number | null>(null);
  const [savingFine, setSavingFine] = useState(false);

  // Filters
  const [filterSeverity, setFilterSeverity] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [complaintsData, summaryData, patternsData, rulesData] = await Promise.allSettled([
        complaintsAPI.list({ days: 90 }),
        complaintsAPI.getWeeklySummary(),
        complaintsAPI.getPatterns(),
        fineRulesAPI.list(),
      ]);

      setComplaints(complaintsData.status === 'fulfilled' ? complaintsData.value : []);
      setSummary(summaryData.status === 'fulfilled' ? summaryData.value : null);
      setPatterns(patternsData.status === 'fulfilled' ? patternsData.value : []);
      setFineRules(rulesData.status === 'fulfilled' ? rulesData.value : []);
    } catch (error) {
      // silently handle
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitComplaint = async () => {
    if (!form.complaint_text.trim()) return;
    setSaving(true);
    try {
      const payload: any = {
        complaint_text: form.complaint_text,
        source: form.source,
        is_anonymous: form.is_anonymous,
      };
      if (form.site_id) payload.site_id = Number(form.site_id);
      if (form.category) payload.category = form.category;
      if (form.severity) payload.severity = form.severity;
      if (form.employee_name) payload.employee_name = form.employee_name;
      if (form.fine_rule_id) payload.fine_rule_id = Number(form.fine_rule_id);
      if (form.fine_amount) payload.fine_amount = Number(form.fine_amount);

      await complaintsAPI.create(payload);
      setShowForm(false);
      setForm({
        complaint_text: '', source: 'manual', site_id: '', category: '',
        severity: '', employee_name: '', is_anonymous: false,
        fine_rule_id: '', fine_amount: '',
      });
      await loadData();
    } catch (error) {
      // silently handle
    } finally {
      setSaving(false);
    }
  };

  const handleSelectFineRule = (ruleId: string) => {
    const updated = { ...form, fine_rule_id: ruleId };
    if (ruleId) {
      const rule = fineRules.find((r: any) => r.id === Number(ruleId));
      if (rule) {
        updated.fine_amount = String(rule.amount);
        if (!form.category) updated.category = rule.category;
      }
    }
    setForm(updated);
  };

  const handleSaveFineRule = async () => {
    if (!fineForm.name || !fineForm.amount) return;
    setSavingFine(true);
    try {
      const payload = {
        name: fineForm.name,
        category: fineForm.category,
        amount: Number(fineForm.amount),
        description: fineForm.description || undefined,
      };
      if (editingFineId) {
        await fineRulesAPI.update(editingFineId, payload);
      } else {
        await fineRulesAPI.create(payload);
      }
      setShowFineForm(false);
      setEditingFineId(null);
      setFineForm({ name: '', category: 'food_quality', amount: '', description: '' });
      await loadData();
    } finally {
      setSavingFine(false);
    }
  };

  const handleDeleteFineRule = async (id: number) => {
    await fineRulesAPI.delete(id);
    await loadData();
  };

  const startEditFineRule = (rule: any) => {
    setEditingFineId(rule.id);
    setFineForm({
      name: rule.name,
      category: rule.category,
      amount: String(rule.amount),
      description: rule.description || '',
    });
    setShowFineForm(true);
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-100 text-red-800 border-red-200';
      case 'high': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'resolved': return <CheckCircle2 className="w-4 h-4 text-green-600" />;
      case 'acknowledged': return <Clock className="w-4 h-4 text-blue-600" />;
      default: return <AlertTriangle className="w-4 h-4 text-orange-600" />;
    }
  };

  const getSourceBadge = (source: string) => {
    const colors: Record<string, string> = {
      whatsapp: 'bg-green-100 text-green-800',
      email: 'bg-blue-100 text-blue-800',
      slack: 'bg-purple-100 text-purple-800',
      manual: 'bg-gray-100 text-gray-700',
      form: 'bg-cyan-100 text-cyan-800',
    };
    return colors[source] || 'bg-gray-100 text-gray-700';
  };

  const filteredComplaints = complaints.filter((c: any) => {
    if (filterSeverity && c.severity !== filterSeverity) return false;
    if (filterStatus && c.status !== filterStatus) return false;
    return true;
  });

  // Calculate fine totals
  const totalFines = complaints.reduce((sum: number, c: any) => sum + (c.fine_amount || 0), 0);

  if (loading) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  return (
    <main className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Complaints & Fines</h2>
          <p className="text-gray-500 text-sm">
            {complaints.length} complaints · {totalFines > 0 ? `${totalFines.toLocaleString()} NIS in fines` : 'No fines'}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={showFineTab ? 'default' : 'outline'}
            size="sm"
            onClick={() => setShowFineTab(!showFineTab)}
          >
            <DollarSign className="w-4 h-4 mr-1" />
            Fine Catalog
          </Button>
          <Button size="sm" className="bg-red-600 hover:bg-red-700" onClick={() => setShowForm(!showForm)}>
            <Plus className="w-4 h-4 mr-1" />
            New Complaint
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <Card className="p-4">
          <p className="text-xs text-gray-500">Total</p>
          <p className="text-2xl font-bold">{complaints.length}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-gray-500">Open</p>
          <p className="text-2xl font-bold text-orange-600">
            {complaints.filter((c: any) => c.status !== 'resolved' && c.status !== 'dismissed').length}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-gray-500">Critical/High</p>
          <p className="text-2xl font-bold text-red-600">
            {complaints.filter((c: any) => c.severity === 'critical' || c.severity === 'high').length}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-gray-500">Total Fines</p>
          <p className="text-2xl font-bold text-purple-600">{totalFines.toLocaleString()} NIS</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-gray-500">Patterns</p>
          <p className="text-2xl font-bold text-blue-600">{patterns.length}</p>
        </Card>
      </div>

      {/* Add Complaint Form */}
      {showForm && (
        <Card className="mb-6 border-red-200">
          <CardHeader className="pb-3">
            <div className="flex justify-between items-center">
              <CardTitle className="text-lg">New Complaint</CardTitle>
              <button onClick={() => setShowForm(false)}><X className="w-5 h-5 text-gray-400" /></button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
              <select
                value={form.source}
                onChange={e => setForm({ ...form, source: e.target.value })}
                className="px-3 py-2 border rounded-md text-sm"
              >
                {SOURCES.map(s => (
                  <option key={s} value={s}>
                    {s === 'whatsapp' ? 'WhatsApp' : s.charAt(0).toUpperCase() + s.slice(1)}
                  </option>
                ))}
              </select>

              <select
                value={form.site_id}
                onChange={e => setForm({ ...form, site_id: e.target.value })}
                className="px-3 py-2 border rounded-md text-sm"
              >
                <option value="">Site (optional)</option>
                <option value="1">Nes Ziona</option>
                <option value="2">Kiryat Gat</option>
              </select>

              <select
                value={form.severity}
                onChange={e => setForm({ ...form, severity: e.target.value })}
                className="px-3 py-2 border rounded-md text-sm"
              >
                <option value="">Severity (optional)</option>
                {SEVERITIES.map(s => (
                  <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                ))}
              </select>

              <select
                value={form.category}
                onChange={e => setForm({ ...form, category: e.target.value })}
                className="px-3 py-2 border rounded-md text-sm"
              >
                <option value="">Category (optional)</option>
                {CATEGORIES.map(c => (
                  <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>
                ))}
              </select>

              <input
                value={form.employee_name}
                onChange={e => setForm({ ...form, employee_name: e.target.value })}
                placeholder="Reported by (optional)"
                className="px-3 py-2 border rounded-md text-sm"
              />

              <label className="flex items-center gap-2 px-3 py-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.is_anonymous}
                  onChange={e => setForm({ ...form, is_anonymous: e.target.checked })}
                  className="rounded"
                />
                Anonymous
              </label>
            </div>

            <textarea
              value={form.complaint_text}
              onChange={e => setForm({ ...form, complaint_text: e.target.value })}
              placeholder="Describe the complaint..."
              className="w-full px-3 py-2 border rounded-md text-sm mb-3"
              rows={3}
            />

            {/* Fine Rule Selector */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3 p-3 bg-gray-50 rounded-lg">
              <div>
                <label className="text-xs font-medium text-gray-600 mb-1 block">Link to Fine Rule</label>
                <select
                  value={form.fine_rule_id}
                  onChange={e => handleSelectFineRule(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md text-sm"
                >
                  <option value="">No fine (optional)</option>
                  {fineRules.map((r: any) => (
                    <option key={r.id} value={r.id}>
                      {r.name} ({r.amount.toLocaleString()} NIS) — {r.category.replace(/_/g, ' ')}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-gray-600 mb-1 block">Fine Amount (NIS)</label>
                <input
                  type="number"
                  value={form.fine_amount}
                  onChange={e => setForm({ ...form, fine_amount: e.target.value })}
                  placeholder="Override amount..."
                  className="w-full px-3 py-2 border rounded-md text-sm"
                />
              </div>
            </div>

            <div className="flex gap-3">
              <Button
                onClick={handleSubmitComplaint}
                disabled={saving || !form.complaint_text.trim()}
                className="bg-red-600 hover:bg-red-700"
              >
                {saving ? 'Submitting...' : 'Submit Complaint'}
              </Button>
              <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Fine Catalog Tab */}
      {showFineTab && (
        <Card className="mb-6 border-purple-200">
          <CardHeader className="pb-3">
            <div className="flex justify-between items-center">
              <CardTitle className="text-lg flex items-center gap-2">
                <DollarSign className="w-5 h-5" />
                Fine Catalog
              </CardTitle>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => {
                  setShowFineForm(!showFineForm);
                  setEditingFineId(null);
                  setFineForm({ name: '', category: 'food_quality', amount: '', description: '' });
                }}>
                  <Plus className="w-4 h-4 mr-1" /> Add Fine Rule
                </Button>
                <button onClick={() => setShowFineTab(false)}><X className="w-5 h-5 text-gray-400" /></button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {showFineForm && (
              <div className="mb-4 p-4 bg-purple-50 rounded-lg">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-3">
                  <input
                    value={fineForm.name}
                    onChange={e => setFineForm({ ...fineForm, name: e.target.value })}
                    placeholder="Fine rule name"
                    className="px-3 py-2 border rounded-md text-sm"
                  />
                  <select
                    value={fineForm.category}
                    onChange={e => setFineForm({ ...fineForm, category: e.target.value })}
                    className="px-3 py-2 border rounded-md text-sm"
                  >
                    {CATEGORIES.map(c => (
                      <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>
                    ))}
                  </select>
                  <input
                    type="number"
                    value={fineForm.amount}
                    onChange={e => setFineForm({ ...fineForm, amount: e.target.value })}
                    placeholder="Amount (NIS)"
                    className="px-3 py-2 border rounded-md text-sm"
                  />
                  <input
                    value={fineForm.description}
                    onChange={e => setFineForm({ ...fineForm, description: e.target.value })}
                    placeholder="Description (optional)"
                    className="px-3 py-2 border rounded-md text-sm"
                  />
                </div>
                <div className="flex gap-2">
                  <Button size="sm" onClick={handleSaveFineRule} disabled={savingFine || !fineForm.name || !fineForm.amount}>
                    {savingFine ? 'Saving...' : editingFineId ? 'Update' : 'Add Rule'}
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => {
                    setShowFineForm(false);
                    setEditingFineId(null);
                  }}>Cancel</Button>
                </div>
              </div>
            )}

            {fineRules.length === 0 ? (
              <p className="text-gray-500 text-center py-4">No fine rules defined yet.</p>
            ) : (
              <div className="space-y-2">
                {fineRules.map((rule: any) => (
                  <div key={rule.id} className="flex items-center justify-between p-3 border rounded-lg hover:bg-gray-50">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{rule.name}</span>
                        <Badge variant="secondary" className="text-xs">{rule.category.replace(/_/g, ' ')}</Badge>
                        <Badge className="bg-purple-100 text-purple-800 text-xs">
                          {rule.amount.toLocaleString()} NIS
                        </Badge>
                      </div>
                      {rule.description && (
                        <p className="text-xs text-gray-500 mt-1">{rule.description}</p>
                      )}
                    </div>
                    <div className="flex gap-1">
                      <button onClick={() => startEditFineRule(rule)} className="p-1 hover:bg-gray-200 rounded">
                        <Pencil className="w-3.5 h-3.5 text-gray-500" />
                      </button>
                      <button onClick={() => handleDeleteFineRule(rule.id)} className="p-1 hover:bg-red-100 rounded">
                        <Trash2 className="w-3.5 h-3.5 text-red-400" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Active Patterns Alert */}
      {patterns.length > 0 && (
        <Card className="mb-6 bg-purple-50 border-purple-200">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-purple-900 text-base">
              <TrendingUp className="w-5 h-5" />
              {patterns.length} Pattern(s) Detected
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {patterns.map((pattern: any) => (
                <div key={pattern.id} className="p-3 bg-white rounded-lg border border-purple-200">
                  <div className="flex justify-between items-start mb-1">
                    <h4 className="font-medium text-sm text-gray-900">{pattern.description}</h4>
                    <Badge className={getSeverityColor(pattern.severity)}>{pattern.severity}</Badge>
                  </div>
                  <p className="text-xs text-gray-600">{pattern.complaint_count} complaints</p>
                  {pattern.recommendation && (
                    <p className="text-xs text-purple-700 mt-1">{pattern.recommendation}</p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <ListFilter className="w-4 h-4 text-gray-500" />
        <select
          value={filterSeverity}
          onChange={e => setFilterSeverity(e.target.value)}
          className="px-3 py-1.5 border rounded-md text-sm"
        >
          <option value="">All Severity</option>
          {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          className="px-3 py-1.5 border rounded-md text-sm"
        >
          <option value="">All Status</option>
          <option value="new">New</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="investigating">Investigating</option>
          <option value="resolved">Resolved</option>
          <option value="dismissed">Dismissed</option>
        </select>
        <span className="text-xs text-gray-500">{filteredComplaints.length} results</span>
      </div>

      {/* Complaints List */}
      <Card>
        <CardHeader>
          <CardTitle>All Complaints</CardTitle>
        </CardHeader>
        <CardContent>
          {filteredComplaints.length === 0 ? (
            <div className="text-center py-12">
              <AlertTriangle className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">No complaints found</p>
              <Button className="mt-4 bg-red-600 hover:bg-red-700" onClick={() => setShowForm(true)}>
                <Plus className="w-4 h-4 mr-1" /> Add First Complaint
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredComplaints.map((complaint: any) => (
                <div
                  key={complaint.id}
                  onClick={() => router.push(`/complaints/${complaint.id}`)}
                  className="p-4 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        {getStatusIcon(complaint.status)}
                        <span className="font-medium text-gray-900 capitalize text-sm">
                          {complaint.status}
                        </span>
                        {complaint.category && (
                          <Badge variant="secondary" className="text-xs">
                            {complaint.category.replace(/_/g, ' ')}
                          </Badge>
                        )}
                        {complaint.severity && (
                          <Badge className={`${getSeverityColor(complaint.severity)} text-xs`}>
                            {complaint.severity}
                          </Badge>
                        )}
                        <Badge className={`${getSourceBadge(complaint.source)} text-xs`}>
                          {complaint.source === 'whatsapp' ? 'WhatsApp' : complaint.source}
                        </Badge>
                        {complaint.fine_amount > 0 && (
                          <Badge className="bg-purple-100 text-purple-800 text-xs">
                            {complaint.fine_amount.toLocaleString()} NIS
                          </Badge>
                        )}
                      </div>

                      <p className="text-sm text-gray-700 mb-2">
                        {complaint.ai_summary || complaint.complaint_text.substring(0, 150)}
                        {!complaint.ai_summary && complaint.complaint_text.length > 150 && '...'}
                      </p>

                      <div className="flex items-center gap-4 text-xs text-gray-500">
                        <span>
                          {format(new Date(complaint.received_at), 'MMM d, h:mm a')}
                        </span>
                        {complaint.site_id && <span>Site {complaint.site_id}</span>}
                        {complaint.employee_name && <span>From: {complaint.employee_name}</span>}
                        {complaint.fine_rule_name && (
                          <span className="text-purple-600">Fine: {complaint.fine_rule_name}</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {complaint.ai_suggested_action && (
                    <div className="mt-2 p-2 bg-blue-50 rounded">
                      <p className="text-xs text-blue-900">
                        Suggested: {complaint.ai_suggested_action}
                      </p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
