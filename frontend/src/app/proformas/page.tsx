'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  FileText, TrendingUp, Package,
  ArrowRight, AlertTriangle, Plus, X, Check, Trash2, Receipt
} from 'lucide-react';
import { proformasAPI, suppliersAPI } from '@/lib/api';
import { format } from 'date-fns';

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

  useEffect(() => {
    loadData();
  }, []);

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
      console.error('Failed to load proformas:', error);
    } finally {
      setLoading(false);
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
  const paidCount = proformas.filter(p => p.status === 'paid').length;
  const suppliers = Array.from(new Set(proformas.map(p => p.supplier_name))).filter(Boolean);

  return (
    <div>
      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Proformas</h2>
            <p className="text-gray-500 text-sm">{proformas.length} invoices in last 12 months</p>
          </div>
          <button
            onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
          >
            <Plus className="h-4 w-4" /> Add Proforma
          </button>
        </div>

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

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
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
              <Receipt className="w-7 h-7 text-green-500" />
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Paid</p>
                <p className="text-4xl font-bold text-purple-600 mt-1">{paidCount}</p>
              </div>
              <TrendingUp className="w-7 h-7 text-purple-500" />
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
                    <div key={vendor.supplier} className="flex items-center justify-between p-3 border rounded-lg">
                      <div>
                        <p className="font-medium text-gray-900">{vendor.supplier}</p>
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
                      </div>
                      <div className="flex items-center gap-4 text-sm text-gray-600">
                        <span>{format(new Date(proforma.invoice_date), 'MMM d, yyyy')}</span>
                        <span className="font-semibold text-gray-900">
                          {proforma.currency === 'ILS' ? '₪' : '$'}{proforma.total_amount.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                        </span>
                      </div>
                    </div>
                    <ArrowRight className="w-5 h-5 text-gray-400" />
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
