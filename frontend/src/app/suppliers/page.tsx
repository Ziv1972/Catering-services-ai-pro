'use client';

import { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Building2, Plus, Pencil, Phone, Mail, X, Check } from 'lucide-react';
import { suppliersAPI } from '@/lib/api';

interface Supplier {
  id: number;
  name: string;
  contact_name: string | null;
  email: string | null;
  phone: string | null;
  contract_start_date: string | null;
  contract_end_date: string | null;
  payment_terms: string | null;
  notes: string | null;
  is_active: boolean;
}

const emptyForm = {
  name: '',
  contact_name: '',
  email: '',
  phone: '',
  contract_start_date: '',
  contract_end_date: '',
  payment_terms: '',
  notes: '',
};

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const data = await suppliersAPI.list();
      setSuppliers(data);
    } catch (error) {
      console.error('Failed to load suppliers:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        ...form,
        contract_start_date: form.contract_start_date || null,
        contract_end_date: form.contract_end_date || null,
      };

      if (editingId) {
        await suppliersAPI.update(editingId, payload);
      } else {
        await suppliersAPI.create(payload);
      }
      setShowForm(false);
      setEditingId(null);
      setForm(emptyForm);
      await loadData();
    } catch (error) {
      console.error('Failed to save supplier:', error);
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (s: Supplier) => {
    setEditingId(s.id);
    setForm({
      name: s.name,
      contact_name: s.contact_name || '',
      email: s.email || '',
      phone: s.phone || '',
      contract_start_date: s.contract_start_date || '',
      contract_end_date: s.contract_end_date || '',
      payment_terms: s.payment_terms || '',
      notes: s.notes || '',
    });
    setShowForm(true);
  };

  const handleDeactivate = async (id: number) => {
    try {
      await suppliersAPI.delete(id);
      await loadData();
    } catch (error) {
      console.error('Failed to deactivate supplier:', error);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  const activeCount = suppliers.filter(s => s.is_active).length;

  return (
    <div>
      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Suppliers</h1>
            <p className="text-gray-500 mt-1">{activeCount} active suppliers</p>
          </div>
          <button
            onClick={() => { setShowForm(true); setEditingId(null); setForm(emptyForm); }}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
          >
            <Plus className="h-4 w-4" /> Add Supplier
          </button>
        </div>

        {showForm && (
          <Card className="mb-6 border-blue-200">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">
                {editingId ? 'Edit Supplier' : 'New Supplier'}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                  <input
                    required
                    value={form.name}
                    onChange={e => setForm({ ...form, name: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Contact Name</label>
                  <input
                    value={form.contact_name}
                    onChange={e => setForm({ ...form, contact_name: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                  <input
                    type="email"
                    value={form.email}
                    onChange={e => setForm({ ...form, email: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                  <input
                    value={form.phone}
                    onChange={e => setForm({ ...form, phone: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Contract Start</label>
                  <input
                    type="date"
                    value={form.contract_start_date}
                    onChange={e => setForm({ ...form, contract_start_date: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Contract End</label>
                  <input
                    type="date"
                    value={form.contract_end_date}
                    onChange={e => setForm({ ...form, contract_end_date: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Payment Terms</label>
                  <input
                    value={form.payment_terms}
                    onChange={e => setForm({ ...form, payment_terms: e.target.value })}
                    placeholder="e.g. Net 30"
                    className="w-full px-3 py-2 border rounded-md focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
                  <input
                    value={form.notes}
                    onChange={e => setForm({ ...form, notes: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <div className="md:col-span-2 flex gap-3">
                  <button
                    type="submit"
                    disabled={saving}
                    className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    <Check className="h-4 w-4" /> {saving ? 'Saving...' : 'Save'}
                  </button>
                  <button
                    type="button"
                    onClick={() => { setShowForm(false); setEditingId(null); }}
                    className="flex items-center gap-2 bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200"
                  >
                    <X className="h-4 w-4" /> Cancel
                  </button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {suppliers.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <Building2 className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">No suppliers yet. Add your first supplier.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4">
            {suppliers.map(s => (
              <Card key={s.id} className={!s.is_active ? 'opacity-50' : ''}>
                <CardContent className="py-4">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <Building2 className="h-5 w-5 text-blue-600" />
                        <h3 className="font-semibold text-gray-900">{s.name}</h3>
                        <Badge className={s.is_active
                          ? 'bg-green-100 text-green-800 border-green-200'
                          : 'bg-gray-100 text-gray-600 border-gray-200'
                        }>
                          {s.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                        {s.payment_terms && (
                          <Badge className="bg-blue-50 text-blue-700 border-blue-200">
                            {s.payment_terms}
                          </Badge>
                        )}
                      </div>
                      <div className="flex gap-6 text-sm text-gray-500">
                        {s.contact_name && <span>{s.contact_name}</span>}
                        {s.email && (
                          <span className="flex items-center gap-1">
                            <Mail className="h-3 w-3" /> {s.email}
                          </span>
                        )}
                        {s.phone && (
                          <span className="flex items-center gap-1">
                            <Phone className="h-3 w-3" /> {s.phone}
                          </span>
                        )}
                        {s.contract_end_date && (
                          <span>Contract ends: {s.contract_end_date}</span>
                        )}
                      </div>
                      {s.notes && (
                        <p className="text-sm text-gray-400 mt-1">{s.notes}</p>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => startEdit(s)}
                        className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      {s.is_active && (
                        <button
                          onClick={() => handleDeactivate(s.id)}
                          className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
