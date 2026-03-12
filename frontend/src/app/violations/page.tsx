'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft, AlertTriangle, TrendingUp,
  CheckCircle2, Clock, Plus, X, DollarSign,
  Pencil, Trash2, ListFilter, Upload, FileText,
  Download, Loader2, Brain, FileInput, BarChart3,
  Mail, Copy, Calendar
} from 'lucide-react';
import { violationsAPI, fineRulesAPI, attachmentsAPI } from '@/lib/api';
import { format, subMonths, startOfMonth, endOfMonth } from 'date-fns';
import {
  BarChart, Bar, PieChart, Pie, Cell, ComposedChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';

const SOURCES = ['manual', 'email', 'whatsapp', 'slack', 'form'];
const CATEGORIES = [
  'kitchen_cleanliness', 'dining_cleanliness', 'staff_attire',
  'missing_dining_equipment', 'portion_weight', 'menu_variety',
  'main_course_depleted', 'staff_shortage', 'service', 'positive_notes',
];
const SEVERITIES = ['low', 'medium', 'high', 'critical'];

export default function ViolationsPage() {
  const router = useRouter();
  const [violations, setViolations] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [patterns, setPatterns] = useState<any[]>([]);
  const [fineRules, setFineRules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Add violation form state
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    violation_text: '',
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

  // Fine document upload
  const [fineDocuments, setFineDocuments] = useState<any[]>([]);
  const [uploadingFineDoc, setUploadingFineDoc] = useState(false);
  const [processingFineDoc, setProcessingFineDoc] = useState<number | null>(null);
  const fineDocInputRef = useRef<HTMLInputElement>(null);

  // Analytics tab state
  const [showAnalyticsTab, setShowAnalyticsTab] = useState(false);
  const [analyticsData, setAnalyticsData] = useState<any>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsFromDate, setAnalyticsFromDate] = useState(
    format(startOfMonth(subMonths(new Date(), 2)), 'yyyy-MM-dd')
  );
  const [analyticsToDate, setAnalyticsToDate] = useState(
    format(new Date(), 'yyyy-MM-dd')
  );
  const [analyticsSiteId, setAnalyticsSiteId] = useState<string>('');
  const [reportHtml, setReportHtml] = useState<string | null>(null);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [copiedReport, setCopiedReport] = useState(false);

  // Fine rule import from document
  const [importPreview, setImportPreview] = useState<any[] | null>(null);
  const [importSourceName, setImportSourceName] = useState('');
  const [importingFromDoc, setImportingFromDoc] = useState<number | null>(null);
  const [confirmingImport, setConfirmingImport] = useState(false);

  const loadFineDocuments = useCallback(async () => {
    try {
      const docs = await attachmentsAPI.list('fine_catalog', 0);
      setFineDocuments(docs);
    } catch {
      // silently handle
    }
  }, []);

  const handleFineDocUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingFineDoc(true);
    try {
      await attachmentsAPI.upload('fine_catalog', 0, file);
      await loadFineDocuments();
    } catch {
      // silently handle
    } finally {
      setUploadingFineDoc(false);
      if (fineDocInputRef.current) fineDocInputRef.current.value = '';
    }
  };

  const handleFineDocDownload = async (att: any) => {
    try {
      const blob = await attachmentsAPI.download(att.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = att.original_filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // silently handle
    }
  };

  const handleFineDocDelete = async (attId: number) => {
    try {
      await attachmentsAPI.delete(attId);
      setFineDocuments(prev => prev.filter(d => d.id !== attId));
    } catch {
      // silently handle
    }
  };

  const handleFineDocProcess = async (attId: number) => {
    setProcessingFineDoc(attId);
    try {
      await attachmentsAPI.process(attId, 'both');
      await loadFineDocuments();
    } catch {
      // silently handle
    } finally {
      setProcessingFineDoc(null);
    }
  };

  const [importError, setImportError] = useState('');

  const handleImportPreview = async (attId: number) => {
    setImportingFromDoc(attId);
    setImportError('');
    try {
      const result = await fineRulesAPI.importPreview(attId);
      const rulesWithToggle = (result.rules || []).map((r: any) => ({
        ...r,
        include: true,
      }));
      setImportPreview(rulesWithToggle);
      setImportSourceName(result.source_filename || 'document');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Import preview failed';
      setImportError(msg);
    } finally {
      setImportingFromDoc(null);
    }
  };

  const handleToggleImportRule = (idx: number) => {
    setImportPreview(prev =>
      prev ? prev.map((r, i) => (i === idx ? { ...r, include: !r.include } : r)) : null
    );
  };

  const handleConfirmImport = async () => {
    if (!importPreview) return;
    const selected = importPreview.filter((r: any) => r.include);
    if (selected.length === 0) return;
    setConfirmingImport(true);
    try {
      const rulesToSend = selected.map(({ include, ...rest }: any) => rest);
      await fineRulesAPI.importConfirm(rulesToSend, true);
      setImportPreview(null);
      setImportSourceName('');
      await loadData();
    } catch {
      // silently handle
    } finally {
      setConfirmingImport(false);
    }
  };

  const loadAnalytics = useCallback(async () => {
    setAnalyticsLoading(true);
    try {
      const params: any = {};
      if (analyticsFromDate) params.from_date = analyticsFromDate;
      if (analyticsToDate) params.to_date = analyticsToDate;
      if (analyticsSiteId) params.site_id = Number(analyticsSiteId);
      const data = await violationsAPI.getAnalytics(params);
      setAnalyticsData(data);
    } catch {
      // silently handle
    } finally {
      setAnalyticsLoading(false);
    }
  }, [analyticsFromDate, analyticsToDate, analyticsSiteId]);

  const handleGenerateReport = async () => {
    setGeneratingReport(true);
    try {
      const params: any = {};
      if (analyticsFromDate) params.from_date = analyticsFromDate;
      if (analyticsToDate) params.to_date = analyticsToDate;
      if (analyticsSiteId) params.site_id = Number(analyticsSiteId);
      const result = await violationsAPI.generateReport(params);
      setReportHtml(result.html);
    } catch {
      // silently handle
    } finally {
      setGeneratingReport(false);
    }
  };

  const handleCopyReportHtml = async () => {
    if (!reportHtml) return;
    try {
      await navigator.clipboard.writeText(reportHtml);
      setCopiedReport(true);
      setTimeout(() => setCopiedReport(false), 2000);
    } catch {
      // fallback
    }
  };

  const setAnalyticsPreset = (preset: string) => {
    const now = new Date();
    switch (preset) {
      case 'this_month':
        setAnalyticsFromDate(format(startOfMonth(now), 'yyyy-MM-dd'));
        setAnalyticsToDate(format(now, 'yyyy-MM-dd'));
        break;
      case 'last_month': {
        const last = subMonths(now, 1);
        setAnalyticsFromDate(format(startOfMonth(last), 'yyyy-MM-dd'));
        setAnalyticsToDate(format(endOfMonth(last), 'yyyy-MM-dd'));
        break;
      }
      case 'last_3':
        setAnalyticsFromDate(format(startOfMonth(subMonths(now, 2)), 'yyyy-MM-dd'));
        setAnalyticsToDate(format(now, 'yyyy-MM-dd'));
        break;
      case 'last_6':
        setAnalyticsFromDate(format(startOfMonth(subMonths(now, 5)), 'yyyy-MM-dd'));
        setAnalyticsToDate(format(now, 'yyyy-MM-dd'));
        break;
    }
  };

  useEffect(() => {
    if (showAnalyticsTab) {
      loadAnalytics();
    }
  }, [showAnalyticsTab, loadAnalytics]);

  useEffect(() => {
    loadData();
    loadFineDocuments();
  }, [loadFineDocuments]);

  const loadData = async () => {
    try {
      const [violationsData, summaryData, patternsData, rulesData] = await Promise.allSettled([
        violationsAPI.list({ days: 90 }),
        violationsAPI.getWeeklySummary(),
        violationsAPI.getPatterns(),
        fineRulesAPI.list(),
      ]);

      setViolations(violationsData.status === 'fulfilled' ? violationsData.value : []);
      setSummary(summaryData.status === 'fulfilled' ? summaryData.value : null);
      setPatterns(patternsData.status === 'fulfilled' ? patternsData.value : []);
      setFineRules(rulesData.status === 'fulfilled' ? rulesData.value : []);
    } catch (error) {
      // silently handle
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitViolation = async () => {
    if (!form.violation_text.trim()) return;
    setSaving(true);
    try {
      const payload: any = {
        violation_text: form.violation_text,
        source: form.source,
        is_anonymous: form.is_anonymous,
      };
      if (form.site_id) payload.site_id = Number(form.site_id);
      if (form.category) payload.category = form.category;
      if (form.severity) payload.severity = form.severity;
      if (form.employee_name) payload.employee_name = form.employee_name;
      if (form.fine_rule_id) payload.fine_rule_id = Number(form.fine_rule_id);
      if (form.fine_amount) payload.fine_amount = Number(form.fine_amount);

      await violationsAPI.create(payload);
      setShowForm(false);
      setForm({
        violation_text: '', source: 'manual', site_id: '', category: '',
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

  const filteredViolations = violations.filter((c: any) => {
    if (filterSeverity && c.severity !== filterSeverity) return false;
    if (filterStatus && c.status !== filterStatus) return false;
    return true;
  });

  // Calculate fine totals
  const totalFines = violations.reduce((sum: number, c: any) => sum + (c.fine_amount || 0), 0);

  if (loading) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  return (
    <main className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Violations & Fines</h2>
          <p className="text-gray-500 text-sm">
            {violations.length} violations · {totalFines > 0 ? `${totalFines.toLocaleString()} NIS in fines` : 'No fines'}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={showAnalyticsTab ? 'default' : 'outline'}
            size="sm"
            onClick={() => { setShowAnalyticsTab(!showAnalyticsTab); setShowFineTab(false); }}
          >
            <BarChart3 className="w-4 h-4 mr-1" />
            Analytics
          </Button>
          <Button
            variant={showFineTab ? 'default' : 'outline'}
            size="sm"
            onClick={() => { setShowFineTab(!showFineTab); setShowAnalyticsTab(false); }}
          >
            <DollarSign className="w-4 h-4 mr-1" />
            Fine Catalog
          </Button>
          <Button size="sm" className="bg-red-600 hover:bg-red-700" onClick={() => setShowForm(!showForm)}>
            <Plus className="w-4 h-4 mr-1" />
            New Violation
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <Card className="p-4">
          <p className="text-xs text-gray-500">Total</p>
          <p className="text-2xl font-bold">{violations.length}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-gray-500">Open</p>
          <p className="text-2xl font-bold text-orange-600">
            {violations.filter((c: any) => c.status !== 'resolved' && c.status !== 'dismissed').length}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-gray-500">Critical/High</p>
          <p className="text-2xl font-bold text-red-600">
            {violations.filter((c: any) => c.severity === 'critical' || c.severity === 'high').length}
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

      {/* Add Violation Form */}
      {showForm && (
        <Card className="mb-6 border-red-200">
          <CardHeader className="pb-3">
            <div className="flex justify-between items-center">
              <CardTitle className="text-lg">New Violation</CardTitle>
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
              value={form.violation_text}
              onChange={e => setForm({ ...form, violation_text: e.target.value })}
              placeholder="Describe the violation..."
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
                onClick={handleSubmitViolation}
                disabled={saving || !form.violation_text.trim()}
                className="bg-red-600 hover:bg-red-700"
              >
                {saving ? 'Submitting...' : 'Submit Violation'}
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

            {/* Fine Documents Upload Section */}
            <div className="mt-6 pt-5 border-t border-purple-100">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-purple-600" />
                  Fine Documents
                </h4>
                <div>
                  <input
                    ref={fineDocInputRef}
                    type="file"
                    className="hidden"
                    accept=".pdf,.doc,.docx,.xlsx,.xls,.csv,.txt,.jpg,.jpeg,.png"
                    onChange={handleFineDocUpload}
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={uploadingFineDoc}
                    onClick={() => fineDocInputRef.current?.click()}
                    className="border-purple-200 text-purple-700 hover:bg-purple-50"
                  >
                    {uploadingFineDoc ? (
                      <><Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> Uploading...</>
                    ) : (
                      <><Upload className="w-3.5 h-3.5 mr-1" /> Upload Document</>
                    )}
                  </Button>
                </div>
              </div>

              {fineDocuments.length === 0 ? (
                <p className="text-xs text-gray-400 text-center py-3">
                  Upload your fine schedule, contract, or penalty document (PDF, Word, Excel)
                </p>
              ) : (
                <div className="space-y-2">
                  {fineDocuments.map((doc: any) => (
                    <div key={doc.id} className="flex items-center justify-between p-3 bg-purple-50 rounded-lg border border-purple-100">
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <FileText className="w-5 h-5 text-purple-500 shrink-0" />
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-gray-800 truncate">
                            {doc.original_filename}
                          </p>
                          <div className="flex items-center gap-2 text-xs text-gray-500">
                            <span>{doc.file_size ? `${(doc.file_size / 1024).toFixed(0)} KB` : ''}</span>
                            {doc.created_at && (
                              <span>{format(new Date(doc.created_at), 'MMM d, yyyy')}</span>
                            )}
                            {doc.processing_status === 'done' && (
                              <Badge className="bg-green-100 text-green-700 text-[10px] px-1.5 py-0">
                                AI Analyzed
                              </Badge>
                            )}
                          </div>
                          {doc.ai_summary && (
                            <p className="text-xs text-purple-700 mt-1 line-clamp-2">{doc.ai_summary}</p>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-1 ml-2 shrink-0">
                        <button
                          onClick={() => handleFineDocProcess(doc.id)}
                          disabled={processingFineDoc === doc.id}
                          className="p-1.5 hover:bg-purple-100 rounded transition-colors"
                          title="AI Analyze"
                        >
                          {processingFineDoc === doc.id ? (
                            <Loader2 className="w-3.5 h-3.5 text-purple-500 animate-spin" />
                          ) : (
                            <Brain className="w-3.5 h-3.5 text-purple-500" />
                          )}
                        </button>
                        <button
                          onClick={() => handleImportPreview(doc.id)}
                          disabled={importingFromDoc === doc.id}
                          className="p-1.5 hover:bg-green-100 rounded transition-colors"
                          title="Import Fine Rules from Document"
                        >
                          {importingFromDoc === doc.id ? (
                            <Loader2 className="w-3.5 h-3.5 text-green-600 animate-spin" />
                          ) : (
                            <FileInput className="w-3.5 h-3.5 text-green-600" />
                          )}
                        </button>
                        <button
                          onClick={() => handleFineDocDownload(doc)}
                          className="p-1.5 hover:bg-purple-100 rounded transition-colors"
                          title="Download"
                        >
                          <Download className="w-3.5 h-3.5 text-purple-500" />
                        </button>
                        <button
                          onClick={() => handleFineDocDelete(doc.id)}
                          className="p-1.5 hover:bg-red-100 rounded transition-colors"
                          title="Delete"
                        >
                          <Trash2 className="w-3.5 h-3.5 text-red-400" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {importError && (
                <div className="mt-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                  <strong>Import error:</strong> {importError}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Import Preview Modal */}
      {importPreview && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between p-5 border-b">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Import Fine Rules</h3>
                <p className="text-sm text-gray-500 mt-0.5">
                  Extracted from: <span className="font-medium text-purple-700">{importSourceName}</span>
                </p>
              </div>
              <button
                onClick={() => { setImportPreview(null); setImportSourceName(''); }}
                className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>

            <div className="p-4 bg-amber-50 border-b border-amber-200">
              <div className="flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
                <p className="text-sm text-amber-800">
                  This will <strong>deactivate all {fineRules.length} existing rules</strong> and replace
                  them with <strong>{importPreview.filter((r: any) => r.include).length} selected rules</strong> below.
                  Toggle off any rules you don&apos;t want to import.
                </p>
              </div>
            </div>

            <div className="flex-1 overflow-auto p-4">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white">
                  <tr className="border-b text-left">
                    <th className="pb-2 pr-2 w-10">
                      <input
                        type="checkbox"
                        checked={importPreview.every((r: any) => r.include)}
                        onChange={() => {
                          const allSelected = importPreview.every((r: any) => r.include);
                          setImportPreview(prev =>
                            prev ? prev.map(r => ({ ...r, include: !allSelected })) : null
                          );
                        }}
                        className="rounded border-gray-300"
                      />
                    </th>
                    <th className="pb-2 pr-3 font-medium text-gray-600">Rule Name</th>
                    <th className="pb-2 pr-3 font-medium text-gray-600 w-28">Category</th>
                    <th className="pb-2 pr-3 font-medium text-gray-600 w-24 text-right">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {importPreview.map((rule: any, idx: number) => (
                    <tr
                      key={idx}
                      className={`border-b last:border-0 transition-colors ${
                        rule.include ? 'bg-white' : 'bg-gray-50 opacity-60'
                      }`}
                    >
                      <td className="py-2.5 pr-2">
                        <input
                          type="checkbox"
                          checked={rule.include}
                          onChange={() => handleToggleImportRule(idx)}
                          className="rounded border-gray-300"
                        />
                      </td>
                      <td className="py-2.5 pr-3">
                        <p className="font-medium text-gray-800">{rule.name}</p>
                        {rule.description && (
                          <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{rule.description}</p>
                        )}
                      </td>
                      <td className="py-2.5 pr-3">
                        <Badge className="bg-indigo-100 text-indigo-700 text-[10px]">
                          {rule.category}
                        </Badge>
                      </td>
                      <td className="py-2.5 pr-3 text-right font-medium text-gray-700">
                        ₪{Number(rule.amount).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex items-center justify-between p-4 border-t bg-gray-50 rounded-b-xl">
              <p className="text-sm text-gray-500">
                {importPreview.filter((r: any) => r.include).length} of {importPreview.length} rules selected
              </p>
              <div className="flex items-center gap-3">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => { setImportPreview(null); setImportSourceName(''); }}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  onClick={handleConfirmImport}
                  disabled={confirmingImport || importPreview.filter((r: any) => r.include).length === 0}
                  className="bg-green-600 hover:bg-green-700 text-white"
                >
                  {confirmingImport ? (
                    <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Importing...</>
                  ) : (
                    <>Confirm Import ({importPreview.filter((r: any) => r.include).length} rules)</>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Analytics Tab */}
      {showAnalyticsTab && (
        <Card className="mb-6 border-blue-200">
          <CardHeader className="pb-3">
            <div className="flex justify-between items-center">
              <CardTitle className="text-lg flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-blue-600" />
                Violation &amp; Fine Analytics
              </CardTitle>
              <button onClick={() => setShowAnalyticsTab(false)}>
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>
          </CardHeader>
          <CardContent>
            {/* Date & Site Controls */}
            <div className="flex flex-wrap items-center gap-2 mb-5">
              <div className="flex gap-1">
                {[
                  { label: 'This Month', key: 'this_month' },
                  { label: 'Last Month', key: 'last_month' },
                  { label: '3 Months', key: 'last_3' },
                  { label: '6 Months', key: 'last_6' },
                ].map(p => (
                  <button
                    key={p.key}
                    onClick={() => setAnalyticsPreset(p.key)}
                    className="px-3 py-1.5 text-xs border rounded-md hover:bg-blue-50 hover:border-blue-300 transition-colors"
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-1 ml-2">
                <Calendar className="w-3.5 h-3.5 text-gray-400" />
                <input
                  type="date"
                  value={analyticsFromDate}
                  onChange={e => setAnalyticsFromDate(e.target.value)}
                  className="px-2 py-1.5 border rounded-md text-xs"
                />
                <span className="text-xs text-gray-400">to</span>
                <input
                  type="date"
                  value={analyticsToDate}
                  onChange={e => setAnalyticsToDate(e.target.value)}
                  className="px-2 py-1.5 border rounded-md text-xs"
                />
              </div>
              <select
                value={analyticsSiteId}
                onChange={e => setAnalyticsSiteId(e.target.value)}
                className="px-2 py-1.5 border rounded-md text-xs"
              >
                <option value="">All Sites</option>
                <option value="1">Nes Ziona</option>
                <option value="2">Kiryat Gat</option>
              </select>
              <Button size="sm" variant="outline" onClick={loadAnalytics} disabled={analyticsLoading}>
                {analyticsLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Refresh'}
              </Button>
            </div>

            {analyticsLoading && !analyticsData ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
              </div>
            ) : analyticsData ? (
              <>
                {/* KPI Summary Cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
                  <div className="p-4 bg-blue-50 rounded-lg border border-blue-200 text-center">
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Total Violations</p>
                    <p className="text-3xl font-bold text-blue-700 mt-1">{analyticsData.summary.total_violations}</p>
                  </div>
                  <div className="p-4 bg-amber-50 rounded-lg border border-amber-200 text-center">
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Total Fines</p>
                    <p className="text-3xl font-bold text-amber-700 mt-1">{analyticsData.summary.total_fines}</p>
                  </div>
                  <div className="p-4 bg-purple-50 rounded-lg border border-purple-200 text-center">
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Fine Amount</p>
                    <p className="text-3xl font-bold text-purple-700 mt-1">
                      {analyticsData.summary.total_fine_amount.toLocaleString()} <span className="text-sm font-normal">NIS</span>
                    </p>
                  </div>
                  <div className="p-4 bg-green-50 rounded-lg border border-green-200 text-center">
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Avg Resolution</p>
                    <p className="text-3xl font-bold text-green-700 mt-1">
                      {analyticsData.summary.avg_resolution_time_hours}<span className="text-sm font-normal">h</span>
                    </p>
                  </div>
                </div>

                {/* Charts Row */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                  {/* Monthly Trend */}
                  {analyticsData.by_month.length > 0 && (
                    <div className="bg-white p-4 border rounded-lg">
                      <h4 className="text-sm font-semibold text-gray-700 mb-3">Monthly Trend</h4>
                      <ResponsiveContainer width="100%" height={250}>
                        <ComposedChart data={analyticsData.by_month}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                          <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                          <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
                          <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
                          <Tooltip />
                          <Legend wrapperStyle={{ fontSize: 12 }} />
                          <Bar yAxisId="left" dataKey="violations" name="Violations" fill="#3b82f6" radius={[4,4,0,0]} />
                          <Bar yAxisId="left" dataKey="fines" name="Fines" fill="#f59e0b" radius={[4,4,0,0]} />
                          <Line yAxisId="right" dataKey="fine_amount" name="Amount (NIS)" stroke="#7c3aed" strokeWidth={2} dot={{ r: 3 }} />
                        </ComposedChart>
                      </ResponsiveContainer>
                    </div>
                  )}

                  {/* Category Pie */}
                  {analyticsData.by_category.length > 0 && (
                    <div className="bg-white p-4 border rounded-lg">
                      <h4 className="text-sm font-semibold text-gray-700 mb-3">By Category</h4>
                      <ResponsiveContainer width="100%" height={250}>
                        <PieChart>
                          <Pie
                            data={analyticsData.by_category}
                            dataKey="count"
                            nameKey="category"
                            cx="50%"
                            cy="50%"
                            outerRadius={90}
                            label={({ category, count }: any) =>
                              `${(category || '').replace(/_/g, ' ')} (${count})`
                            }
                            labelLine={{ strokeWidth: 1 }}
                          >
                            {analyticsData.by_category.map((_: any, i: number) => (
                              <Cell key={i} fill={['#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6','#ec4899','#06b6d4','#84cc16'][i % 8]} />
                            ))}
                          </Pie>
                          <Tooltip formatter={(v: any, name: any) => [v, (name || '').replace(/_/g, ' ')]} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>

                {/* Site Comparison Chart */}
                {analyticsData.by_site.length > 0 && (
                  <div className="bg-white p-4 border rounded-lg mb-6">
                    <h4 className="text-sm font-semibold text-gray-700 mb-3">By Site</h4>
                    <ResponsiveContainer width="100%" height={200}>
                      <BarChart data={analyticsData.by_site}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis dataKey="site_name" tick={{ fontSize: 12 }} />
                        <YAxis tick={{ fontSize: 11 }} />
                        <Tooltip />
                        <Legend wrapperStyle={{ fontSize: 12 }} />
                        <Bar dataKey="violations" name="Violations" fill="#3b82f6" radius={[4,4,0,0]} />
                        <Bar dataKey="fines" name="Fines" fill="#ef4444" radius={[4,4,0,0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {/* Top Fine Rules Table */}
                {analyticsData.top_fine_rules.length > 0 && (
                  <div className="mb-6">
                    <h4 className="text-sm font-semibold text-gray-700 mb-2">Top Fine Rules Applied</h4>
                    <div className="border rounded-lg overflow-hidden">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="bg-gray-50 text-left">
                            <th className="px-4 py-2.5 font-medium text-gray-600">Rule Name</th>
                            <th className="px-4 py-2.5 font-medium text-gray-600 text-center">Times Applied</th>
                            <th className="px-4 py-2.5 font-medium text-gray-600 text-right">Total Amount</th>
                          </tr>
                        </thead>
                        <tbody>
                          {analyticsData.top_fine_rules.map((rule: any, i: number) => (
                            <tr key={i} className="border-t hover:bg-gray-50">
                              <td className="px-4 py-2.5">{rule.rule_name}</td>
                              <td className="px-4 py-2.5 text-center">{rule.times_applied}</td>
                              <td className="px-4 py-2.5 text-right font-medium text-purple-700">
                                {rule.total_amount.toLocaleString()} NIS
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Detailed Table */}
                {analyticsData.violations_list.length > 0 && (
                  <div className="mb-4">
                    <h4 className="text-sm font-semibold text-gray-700 mb-2">
                      Violation Details ({analyticsData.violations_list.length})
                    </h4>
                    <div className="border rounded-lg overflow-auto max-h-80">
                      <table className="w-full text-xs">
                        <thead className="sticky top-0 bg-gray-50">
                          <tr className="text-left">
                            <th className="px-3 py-2 font-medium text-gray-600">Date</th>
                            <th className="px-3 py-2 font-medium text-gray-600">Site</th>
                            <th className="px-3 py-2 font-medium text-gray-600">Category</th>
                            <th className="px-3 py-2 font-medium text-gray-600">Severity</th>
                            <th className="px-3 py-2 font-medium text-gray-600">Fine Rule</th>
                            <th className="px-3 py-2 font-medium text-gray-600 text-right">Amount</th>
                            <th className="px-3 py-2 font-medium text-gray-600">Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {analyticsData.violations_list.map((c: any) => (
                            <tr
                              key={c.id}
                              className="border-t hover:bg-blue-50 cursor-pointer"
                              onClick={() => router.push(`/violations/${c.id}`)}
                            >
                              <td className="px-3 py-2 whitespace-nowrap">{c.date?.slice(0, 10)}</td>
                              <td className="px-3 py-2">{c.site_name}</td>
                              <td className="px-3 py-2 capitalize">{(c.category || '-').replace(/_/g, ' ')}</td>
                              <td className="px-3 py-2">
                                <Badge className={`${getSeverityColor(c.severity || '')} text-[10px]`}>
                                  {c.severity || '-'}
                                </Badge>
                              </td>
                              <td className="px-3 py-2">{c.fine_rule_name || '-'}</td>
                              <td className="px-3 py-2 text-right font-medium">
                                {c.fine_amount > 0 ? `${c.fine_amount.toLocaleString()} NIS` : '-'}
                              </td>
                              <td className="px-3 py-2 capitalize">{c.status}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Generate Report Button */}
                <div className="flex gap-2 pt-2 border-t">
                  <Button
                    size="sm"
                    onClick={handleGenerateReport}
                    disabled={generatingReport}
                    className="bg-blue-600 hover:bg-blue-700"
                  >
                    {generatingReport ? (
                      <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Generating...</>
                    ) : (
                      <><Mail className="w-3.5 h-3.5 mr-1.5" /> Generate Email Report</>
                    )}
                  </Button>
                </div>
              </>
            ) : (
              <p className="text-gray-500 text-center py-8">No analytics data available</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Report Preview Modal */}
      {reportHtml && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between p-5 border-b">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Email Report Preview</h3>
                <p className="text-sm text-gray-500 mt-0.5">
                  Copy the HTML and ask Claude to send it via Gmail
                </p>
              </div>
              <button
                onClick={() => setReportHtml(null)}
                className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>

            <div className="flex-1 overflow-auto p-4 bg-gray-50">
              <iframe
                srcDoc={reportHtml}
                className="w-full h-full min-h-[500px] border rounded-lg bg-white"
                title="Report Preview"
              />
            </div>

            <div className="flex items-center justify-between p-4 border-t bg-gray-50 rounded-b-xl">
              <p className="text-xs text-gray-500">
                HTML report ready for email delivery
              </p>
              <div className="flex items-center gap-3">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setReportHtml(null)}
                >
                  Close
                </Button>
                <Button
                  size="sm"
                  onClick={handleCopyReportHtml}
                  className="bg-blue-600 hover:bg-blue-700"
                >
                  {copiedReport ? (
                    <><CheckCircle2 className="w-3.5 h-3.5 mr-1.5" /> Copied!</>
                  ) : (
                    <><Copy className="w-3.5 h-3.5 mr-1.5" /> Copy HTML for Email</>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>
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
                  <p className="text-xs text-gray-600">{pattern.violation_count} violations</p>
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
        <span className="text-xs text-gray-500">{filteredViolations.length} results</span>
      </div>

      {/* Violations List */}
      <Card>
        <CardHeader>
          <CardTitle>All Violations</CardTitle>
        </CardHeader>
        <CardContent>
          {filteredViolations.length === 0 ? (
            <div className="text-center py-12">
              <AlertTriangle className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">No violations found</p>
              <Button className="mt-4 bg-red-600 hover:bg-red-700" onClick={() => setShowForm(true)}>
                <Plus className="w-4 h-4 mr-1" /> Add First Violation
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredViolations.map((item: any) => (
                <div
                  key={item.id}
                  onClick={() => router.push(`/violations/${item.id}`)}
                  className="p-4 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        {getStatusIcon(item.status)}
                        <span className="font-medium text-gray-900 capitalize text-sm">
                          {item.status}
                        </span>
                        {item.category && (
                          <Badge variant="secondary" className="text-xs">
                            {item.category.replace(/_/g, ' ')}
                          </Badge>
                        )}
                        {item.severity && (
                          <Badge className={`${getSeverityColor(item.severity)} text-xs`}>
                            {item.severity}
                          </Badge>
                        )}
                        <Badge className={`${getSourceBadge(item.source)} text-xs`}>
                          {item.source === 'whatsapp' ? 'WhatsApp' : item.source}
                        </Badge>
                        {item.fine_amount > 0 && (
                          <Badge className="bg-purple-100 text-purple-800 text-xs">
                            {item.fine_amount.toLocaleString()} NIS
                          </Badge>
                        )}
                      </div>

                      <p className="text-sm text-gray-700 mb-2">
                        {item.ai_summary || item.violation_text.substring(0, 150)}
                        {!item.ai_summary && item.violation_text.length > 150 && '...'}
                      </p>

                      <div className="flex items-center gap-4 text-xs text-gray-500">
                        <span>
                          {format(new Date(item.received_at), 'MMM d, h:mm a')}
                        </span>
                        {item.site_id && <span>Site {item.site_id}</span>}
                        {item.employee_name && <span>From: {item.employee_name}</span>}
                        {item.fine_rule_name && (
                          <span className="text-purple-600">Fine: {item.fine_rule_name}</span>
                        )}
                        {item.fine_match_confidence > 0 && item.fine_match_confidence < 0.7 && !item.fine_rule_id && (
                          <span className="text-amber-600 italic">
                            Possible fine match ({Math.round(item.fine_match_confidence * 100)}%)
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {item.fine_match_confidence >= 0.7 && item.fine_rule_name && (
                    <div className="mt-2 p-2 bg-green-50 rounded border border-green-200">
                      <p className="text-xs text-green-800">
                        <span className="font-medium">AI-matched fine:</span>{' '}
                        {item.fine_rule_name} — ₪{item.fine_amount?.toLocaleString()}{' '}
                        <span className="text-green-600">
                          ({Math.round(item.fine_match_confidence * 100)}% confidence)
                        </span>
                      </p>
                      {item.fine_match_reasoning && (
                        <p className="text-xs text-green-700 mt-0.5">{item.fine_match_reasoning}</p>
                      )}
                    </div>
                  )}

                  {item.ai_suggested_action && (
                    <div className="mt-2 p-2 bg-blue-50 rounded">
                      <p className="text-xs text-blue-900">
                        Suggested: {item.ai_suggested_action}
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
