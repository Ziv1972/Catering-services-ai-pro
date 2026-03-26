'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  FileText, TrendingUp, Package,
  ArrowRight, AlertTriangle, Plus, X, Check, Trash2, Upload,
} from 'lucide-react';
import { proformasAPI, suppliersAPI } from '@/lib/api';
import { format } from 'date-fns';
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
} from 'recharts';

export default function ProformasPage() {
  const router = useRouter();
  const [proformas, setProformas] = useState<any[]>([]);
  const [spending, setSpending] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [suppliersList, setSuppliersList] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    supplier_id: '',
    site_id: '1',
    proforma_number: '',
    invoice_date: new Date().toISOString().split('T')[0],
    delivery_date: '',
    status: 'pending',
    notes: '',
  });
  const [items, setItems] = useState<Array<{ product_name: string; quantity: string; unit: string; unit_price: string }>>([
    { product_name: '', quantity: '', unit: 'kg', unit_price: '' },
  ]);
  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [uploadForm, setUploadForm] = useState({
    supplier_id: '',
    site_id: '1',
    invoice_date: new Date().toISOString().split('T')[0],
    proforma_number: '',
  });
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [selectedSupplierId, setSelectedSupplierId] = useState<number | null>(null);
  const [vendorAnalysis, setVendorAnalysis] = useState<any>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  // Meal summary updater
  const [showMealUpdate, setShowMealUpdate] = useState(false);
  const [mealSummaryFile, setMealSummaryFile] = useState<File | null>(null);
  const [mealUpdateMonth, setMealUpdateMonth] = useState(new Date().toISOString().slice(0, 7));
  const [mealUpdating, setMealUpdating] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    loadProformas();
    if (selectedSupplierId) {
      loadVendorAnalysis(selectedSupplierId);
    } else {
      setVendorAnalysis(null);
    }
  }, [selectedSupplierId]);

  const loadData = async () => {
    try {
      const [proformaData, spendingData, suppliersData] = await Promise.allSettled([
        proformasAPI.list({ months: 12 }),
        proformasAPI.getVendorSpending(12),
        suppliersAPI.list(true),
      ]);

      setProformas(proformaData.status === 'fulfilled' ? proformaData.value : []);
      setSpending(spendingData.status === 'fulfilled' ? spendingData.value : null);
      setSuppliersList(suppliersData.status === 'fulfilled' ? suppliersData.value : []);
    } catch (error) {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  const loadProformas = async () => {
    try {
      const data = await proformasAPI.list({
        months: 12,
        supplier_id: selectedSupplierId || undefined,
      });
      setProformas(data);
    } catch {
      // keep existing
    }
  };

  const loadVendorAnalysis = async (supplierId: number) => {
    setAnalysisLoading(true);
    try {
      const data = await proformasAPI.getVendorAnalysis(supplierId);
      setVendorAnalysis(data);
    } catch {
      setVendorAnalysis(null);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const selectVendor = (supplierId: number | null) => {
    setSelectedSupplierId(prev => prev === supplierId ? null : supplierId);
  };

  const handleMealSummaryUpdate = async () => {
    if (!mealSummaryFile) {
      alert('Please select the meal summary Excel file (ריכוז מספרי ארוחות)');
      return;
    }
    setMealUpdating(true);
    try {
      const blob = await proformasAPI.updateMealSummary(mealSummaryFile, mealUpdateMonth);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `meal_summary_updated_${mealUpdateMonth}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      setShowMealUpdate(false);
      setMealSummaryFile(null);
    } catch (error: any) {
      const detail = error?.response?.data instanceof Blob
        ? await error.response.data.text().then((t: string) => { try { return JSON.parse(t).detail; } catch { return t; } })
        : error?.response?.data?.detail || 'Failed to update meal summary';
      alert(detail);
    } finally {
      setMealUpdating(false);
    }
  };

  const addItem = () => {
    setItems([...items, { product_name: '', quantity: '', unit: 'kg', unit_price: '' }]);
  };

  const removeItem = (index: number) => {
    setItems(items.filter((_, i) => i !== index));
  };

  const updateItem = (index: number, field: string, value: string) => {
    setItems(items.map((item, i) => i === index ? { ...item, [field]: value } : item));
  };

  const handleCreateProforma = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await proformasAPI.create({
        supplier_id: parseInt(form.supplier_id),
        site_id: parseInt(form.site_id),
        proforma_number: form.proforma_number || null,
        invoice_date: form.invoice_date,
        delivery_date: form.delivery_date || null,
        status: form.status,
        notes: form.notes || null,
        items: items
          .filter(i => i.product_name && i.quantity && i.unit_price)
          .map(i => ({
            product_name: i.product_name,
            quantity: parseFloat(i.quantity),
            unit: i.unit,
            unit_price: parseFloat(i.unit_price),
          })),
      });
      setShowForm(false);
      setForm({ supplier_id: '', site_id: '1', proforma_number: '', invoice_date: new Date().toISOString().split('T')[0], delivery_date: '', status: 'pending', notes: '' });
      setItems([{ product_name: '', quantity: '', unit: 'kg', unit_price: '' }]);
      await loadData();
    } catch (error) {
      console.error('Failed to create proforma:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile || !uploadForm.supplier_id) return;
    setUploading(true);
    setUploadResult(null);
    try {
      const result = await proformasAPI.upload(
        uploadFile,
        parseInt(uploadForm.supplier_id),
        uploadForm.site_id ? parseInt(uploadForm.site_id) : undefined,
        uploadForm.invoice_date || undefined,
        uploadForm.proforma_number || undefined,
      );
      setUploadResult(result);
      setUploadFile(null);
      await loadData();
    } catch (error: any) {
      const detail = error?.response?.data?.detail || 'Upload failed';
      setUploadResult({ error: true, message: detail });
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (proformaId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Delete this proforma and all its items?')) return;
    try {
      await proformasAPI.delete(proformaId);
      await loadData();
    } catch (error: any) {
      alert(error?.response?.data?.detail || 'Delete failed');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'paid': return 'bg-green-100 text-green-800 border-green-200';
      case 'pending': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'overdue': return 'bg-red-100 text-red-800 border-red-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  const totalAmount = proformas.reduce((sum, p) => sum + p.total_amount, 0);
  const suppliers = Array.from(new Set(proformas.map(p => p.supplier_name))).filter(Boolean);

  return (
    <div>
      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Proformas</h2>
            <p className="text-gray-500 text-sm">
              {proformas.length} invoices
              {selectedSupplierId
                ? ` for ${suppliersList.find((s: any) => s.id === selectedSupplierId)?.name || 'vendor'}`
                : ' in last 12 months'}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => { setShowMealUpdate(!showMealUpdate); setShowUpload(false); setShowForm(false); }}
              className="flex items-center gap-2 bg-orange-600 text-white px-4 py-2 rounded-lg hover:bg-orange-700"
            >
              <FileText className="h-4 w-4" /> Update Meals
            </button>
            <button
              onClick={() => { setShowUpload(!showUpload); setShowForm(false); setShowMealUpdate(false); }}
              className="flex items-center gap-2 bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700"
            >
              <Upload className="h-4 w-4" /> Upload Excel
            </button>
            <button
              onClick={() => { setShowForm(!showForm); setShowUpload(false); setShowMealUpdate(false); }}
              className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
            >
              <Plus className="h-4 w-4" /> Add Manual
            </button>
          </div>
        </div>

        {/* Vendor Filter Chips */}
        {suppliersList.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            <button
              onClick={() => setSelectedSupplierId(null)}
              className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                !selectedSupplierId
                  ? 'bg-purple-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              All Vendors
            </button>
            {suppliersList.map((s: any) => (
              <button
                key={s.id}
                onClick={() => selectVendor(s.id)}
                className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                  selectedSupplierId === s.id
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {s.name}
                {selectedSupplierId === s.id && (
                  <X className="inline w-3 h-3 ml-1" />
                )}
              </button>
            ))}
          </div>
        )}

        {/* Vendor Analysis Panel */}
        {selectedSupplierId && vendorAnalysis && !analysisLoading && (
          <Card className="mb-6 border-purple-200 bg-purple-50/30">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-purple-600" />
                {suppliersList.find((s: any) => s.id === selectedSupplierId)?.name} Analysis
                <span className="text-sm font-normal text-gray-500 ml-2">
                  {vendorAnalysis.proforma_count} invoices · ₪{vendorAnalysis.total_spend?.toLocaleString()}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* Spending Timeline */}
              {vendorAnalysis.spending_timeline?.length > 1 && (
                <div className="mb-6">
                  <p className="text-sm font-medium text-gray-700 mb-2">Monthly Spending</p>
                  <div className="h-48">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={vendorAnalysis.spending_timeline}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `₪${(Number(v)/1000).toFixed(0)}k`} />
                        <Tooltip formatter={(v) => [`₪${Number(v).toLocaleString()}`, 'Spend']} />
                        <Bar dataKey="total" fill="#7c3aed" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {/* Top Products Table */}
              {vendorAnalysis.top_products?.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-gray-700 mb-2">Top Products</p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-left text-gray-500">
                          <th className="pb-2">Product</th>
                          <th className="pb-2 text-right">Total Spend</th>
                          <th className="pb-2 text-right">Qty</th>
                          <th className="pb-2 text-right">Avg Price</th>
                          <th className="pb-2 text-right">Invoices</th>
                        </tr>
                      </thead>
                      <tbody>
                        {vendorAnalysis.top_products.slice(0, 15).map((p: any) => (
                          <tr key={p.name} className="border-b last:border-0">
                            <td className="py-1.5 font-medium">{p.name}</td>
                            <td className="py-1.5 text-right">₪{p.total_spend.toLocaleString()}</td>
                            <td className="py-1.5 text-right">{p.total_qty.toLocaleString()}</td>
                            <td className="py-1.5 text-right">₪{p.avg_price.toLocaleString()}</td>
                            <td className="py-1.5 text-right text-gray-500">{p.invoice_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}
        {analysisLoading && selectedSupplierId && (
          <div className="text-center py-4 text-gray-400 mb-4">Loading vendor analysis...</div>
        )}

        {/* Meal Summary Update Dialog */}
        {showMealUpdate && (
          <Card className="mb-6 border-orange-200 bg-orange-50/30">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <FileText className="w-5 h-5 text-orange-600" />
                Update Meal Summary Excel
              </CardTitle>
              <p className="text-sm text-gray-500">
                Uses meal breakdown data auto-extracted from uploaded FoodHouse proformas (NZ + KG).
                Just select the summary file and month.
              </p>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap items-end gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">ריכוז מספרי ארוחות file *</label>
                  <input
                    type="file"
                    accept=".xlsx,.xls"
                    onChange={e => setMealSummaryFile(e.target.files?.[0] || null)}
                    className="text-sm border rounded-md p-2"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Target Month</label>
                  <input
                    type="month"
                    value={mealUpdateMonth}
                    onChange={e => setMealUpdateMonth(e.target.value)}
                    className="px-3 py-2 border rounded-md"
                  />
                </div>
                <button
                  onClick={handleMealSummaryUpdate}
                  disabled={mealUpdating || !mealSummaryFile}
                  className="flex items-center gap-2 bg-orange-600 text-white px-4 py-2 rounded-lg hover:bg-orange-700 disabled:opacity-50"
                >
                  {mealUpdating ? 'Processing...' : 'Update & Download'}
                </button>
                <button
                  onClick={() => setShowMealUpdate(false)}
                  className="px-4 py-2 border rounded-lg text-gray-600 hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </CardContent>
          </Card>
        )}

        {showForm && (
          <Card className="mb-6 border-blue-200">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">New Proforma</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCreateProforma}>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Supplier *</label>
                    <select
                      required
                      value={form.supplier_id}
                      onChange={e => setForm({ ...form, supplier_id: e.target.value })}
                      className="w-full px-3 py-2 border rounded-md"
                    >
                      <option value="">Select supplier...</option>
                      {suppliersList.map((s: any) => (
                        <option key={s.id} value={s.id}>{s.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Site</label>
                    <select
                      value={form.site_id}
                      onChange={e => setForm({ ...form, site_id: e.target.value })}
                      className="w-full px-3 py-2 border rounded-md"
                    >
                      <option value="1">Nes Ziona (NZ)</option>
                      <option value="2">Kiryat Gat (KG)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Proforma #</label>
                    <input
                      value={form.proforma_number}
                      onChange={e => setForm({ ...form, proforma_number: e.target.value })}
                      className="w-full px-3 py-2 border rounded-md"
                      placeholder="PF-2026-001"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Invoice Date *</label>
                    <input
                      type="date"
                      required
                      value={form.invoice_date}
                      onChange={e => setForm({ ...form, invoice_date: e.target.value })}
                      className="w-full px-3 py-2 border rounded-md"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Delivery Date</label>
                    <input
                      type="date"
                      value={form.delivery_date}
                      onChange={e => setForm({ ...form, delivery_date: e.target.value })}
                      className="w-full px-3 py-2 border rounded-md"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
                    <select
                      value={form.status}
                      onChange={e => setForm({ ...form, status: e.target.value })}
                      className="w-full px-3 py-2 border rounded-md"
                    >
                      <option value="pending">Pending</option>
                      <option value="approved">Approved</option>
                      <option value="paid">Paid</option>
                      <option value="rejected">Rejected</option>
                    </select>
                  </div>
                </div>

                <div className="mb-4">
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium text-gray-700">Line Items</label>
                    <button type="button" onClick={addItem} className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1">
                      <Plus className="h-3 w-3" /> Add Item
                    </button>
                  </div>
                  <div className="space-y-2">
                    {items.map((item, idx) => (
                      <div key={idx} className="grid grid-cols-12 gap-2 items-center">
                        <input
                          placeholder="Product name"
                          value={item.product_name}
                          onChange={e => updateItem(idx, 'product_name', e.target.value)}
                          className="col-span-4 px-2 py-1.5 text-sm border rounded-md"
                        />
                        <input
                          type="number"
                          step="0.01"
                          placeholder="Qty"
                          value={item.quantity}
                          onChange={e => updateItem(idx, 'quantity', e.target.value)}
                          className="col-span-2 px-2 py-1.5 text-sm border rounded-md"
                        />
                        <select
                          value={item.unit}
                          onChange={e => updateItem(idx, 'unit', e.target.value)}
                          className="col-span-2 px-2 py-1.5 text-sm border rounded-md"
                        >
                          <option value="kg">kg</option>
                          <option value="unit">unit</option>
                          <option value="liter">liter</option>
                          <option value="box">box</option>
                          <option value="pack">pack</option>
                        </select>
                        <input
                          type="number"
                          step="0.01"
                          placeholder="Unit price"
                          value={item.unit_price}
                          onChange={e => updateItem(idx, 'unit_price', e.target.value)}
                          className="col-span-3 px-2 py-1.5 text-sm border rounded-md"
                        />
                        <button type="button" onClick={() => removeItem(idx)} className="col-span-1 p-1.5 text-gray-400 hover:text-red-500">
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex gap-3">
                  <button type="submit" disabled={saving} className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50">
                    <Check className="h-4 w-4" /> {saving ? 'Saving...' : 'Create Proforma'}
                  </button>
                  <button type="button" onClick={() => setShowForm(false)} className="flex items-center gap-2 bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200">
                    <X className="h-4 w-4" /> Cancel
                  </button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {showUpload && (
          <Card className="mb-6 border-green-200">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <Upload className="h-5 w-5 text-green-600" />
                Upload Proforma
              </CardTitle>
              <p className="text-sm text-gray-500">
                Upload an Excel (.xlsx), CSV, or PDF file with product name, quantity, unit, and price columns.
                Hebrew and English headers are auto-detected. PDF invoices are parsed with AI.
              </p>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleUpload}>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Supplier *</label>
                    <select
                      required
                      value={uploadForm.supplier_id}
                      onChange={e => setUploadForm({ ...uploadForm, supplier_id: e.target.value })}
                      className="w-full px-3 py-2 border rounded-md"
                    >
                      <option value="">Select supplier...</option>
                      {suppliersList.map((s: any) => (
                        <option key={s.id} value={s.id}>{s.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Site</label>
                    <select
                      value={uploadForm.site_id}
                      onChange={e => setUploadForm({ ...uploadForm, site_id: e.target.value })}
                      className="w-full px-3 py-2 border rounded-md"
                    >
                      <option value="1">Nes Ziona (NZ)</option>
                      <option value="2">Kiryat Gat (KG)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Invoice Date</label>
                    <input
                      type="date"
                      value={uploadForm.invoice_date}
                      onChange={e => setUploadForm({ ...uploadForm, invoice_date: e.target.value })}
                      className="w-full px-3 py-2 border rounded-md"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Proforma #</label>
                    <input
                      value={uploadForm.proforma_number}
                      onChange={e => setUploadForm({ ...uploadForm, proforma_number: e.target.value })}
                      className="w-full px-3 py-2 border rounded-md"
                      placeholder="PF-2026-001"
                    />
                  </div>
                </div>

                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Excel / CSV / PDF File *</label>
                  <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-green-400 transition-colors">
                    <input
                      type="file"
                      accept=".xlsx,.xls,.csv,.tsv,.txt,.pdf"
                      onChange={e => setUploadFile(e.target.files?.[0] || null)}
                      className="hidden"
                      id="proforma-file-upload"
                    />
                    <label htmlFor="proforma-file-upload" className="cursor-pointer">
                      <Upload className="h-8 w-8 text-gray-400 mx-auto mb-2" />
                      {uploadFile ? (
                        <p className="text-sm text-green-700 font-medium">{uploadFile.name}</p>
                      ) : (
                        <p className="text-sm text-gray-500">Click to select Excel (.xlsx), CSV, or PDF file</p>
                      )}
                      <p className="text-xs text-gray-400 mt-1">Excel recommended. CSV and PDF also supported. PDF parsed with AI.</p>
                    </label>
                  </div>
                </div>

                {uploadResult && (
                  <div className={`mb-4 p-3 rounded-lg text-sm ${
                    uploadResult.error
                      ? 'bg-red-50 text-red-700 border border-red-200'
                      : 'bg-green-50 text-green-700 border border-green-200'
                  }`}>
                    {uploadResult.error
                      ? uploadResult.message
                      : `Created proforma #${uploadResult.id} with ${uploadResult.items_created} items (₪${uploadResult.total_amount?.toLocaleString()})`
                    }
                  </div>
                )}

                <div className="flex gap-3">
                  <button
                    type="submit"
                    disabled={uploading || !uploadFile || !uploadForm.supplier_id}
                    className="flex items-center gap-2 bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50"
                  >
                    <Upload className="h-4 w-4" /> {uploading ? 'Uploading...' : 'Upload & Create'}
                  </button>
                  <button
                    type="button"
                    onClick={() => { setShowUpload(false); setUploadResult(null); }}
                    className="flex items-center gap-2 bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200"
                  >
                    <X className="h-4 w-4" /> Cancel
                  </button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Invoices</p>
                <p className="text-4xl font-bold text-gray-900 mt-1">{proformas.length}</p>
              </div>
              <FileText className="w-7 h-7 text-blue-500" />
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Amount</p>
                <p className="text-4xl font-bold text-green-600 mt-1">
                  ₪{totalAmount.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                </p>
              </div>
              <span className="text-2xl font-bold text-green-400">₪</span>
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Suppliers</p>
                <p className="text-4xl font-bold text-orange-600 mt-1">{suppliers.length}</p>
              </div>
              <Package className="w-7 h-7 text-orange-500" />
            </div>
          </Card>
        </div>

        {/* Vendor Spending Summary */}
        {spending && spending.vendor_totals?.length > 0 && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-green-600" />
                Vendor Spending Summary
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {spending.vendor_totals.map((vendor: any) => {
                  const pct = spending.grand_total > 0
                    ? ((vendor.total / spending.grand_total) * 100).toFixed(1)
                    : '0';
                  return (
                    <div
                      key={vendor.supplier}
                      className="flex items-center justify-between p-3 border rounded-lg hover:bg-purple-50 cursor-pointer transition-colors"
                      onClick={() => {
                        const match = suppliersList.find((s: any) => s.name === vendor.supplier);
                        if (match) selectVendor(match.id);
                      }}
                    >
                      <div>
                        <p className="font-medium text-purple-700 hover:underline">{vendor.supplier}</p>
                        <p className="text-sm text-gray-500">{pct}% of total spend</p>
                      </div>
                      <p className="text-lg font-bold text-gray-900">
                        ₪{vendor.total.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                      </p>
                    </div>
                  );
                })}
                <div className="flex items-center justify-between p-3 border-t-2 pt-4">
                  <p className="font-semibold text-gray-900">Grand Total</p>
                  <p className="text-xl font-bold text-blue-600">
                    ₪{spending.grand_total.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Proformas List */}
        <Card>
          <CardHeader>
            <CardTitle>All Proformas</CardTitle>
          </CardHeader>
          <CardContent>
            {proformas.length === 0 ? (
              <div className="text-center py-12">
                <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">No proformas found</p>
              </div>
            ) : (
              <div className="space-y-3">
                {proformas.map((proforma: any) => (
                  <div
                    key={proforma.id}
                    onClick={() => router.push(`/proformas/${proforma.id}`)}
                    className="p-4 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors flex items-center justify-between"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <span className="font-medium text-gray-900">
                          {proforma.supplier_name || 'Unknown Supplier'}
                        </span>
                        <Badge className={getStatusColor(proforma.status)}>
                          {proforma.status}
                        </Badge>
                        {proforma.proforma_number && (
                          <span className="text-sm text-gray-500">#{proforma.proforma_number}</span>
                        )}
                        {proforma.flagged_count > 0 && (
                          <Badge className="bg-red-100 text-red-700 border-red-200">
                            <AlertTriangle className="w-3 h-3 mr-1" />
                            {proforma.flagged_count} price {proforma.flagged_count === 1 ? 'flag' : 'flags'}
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-4 text-sm text-gray-600">
                        <span>{format(new Date(proforma.invoice_date), 'MMM d, yyyy')}</span>
                        <span className="font-semibold text-gray-900">
                          {proforma.currency === 'ILS' ? '₪' : '$'}{proforma.total_amount.toLocaleString('en-US', { maximumFractionDigits: 2 })}
                        </span>
                        {proforma.item_count > 0 && (
                          <span className="text-gray-400">{proforma.item_count} items</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => handleDelete(proforma.id, e)}
                        className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                        title="Delete proforma"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                      <ArrowRight className="w-5 h-5 text-gray-400" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
