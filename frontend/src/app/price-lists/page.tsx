'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  FileText, Plus, ChevronRight, Upload,
  Search, RefreshCw, Loader2, CheckCircle2,
  Pencil, Trash2, Save, X, PackagePlus,
  FileSpreadsheet, AlertCircle,
} from 'lucide-react';
import { priceListsAPI, suppliersAPI } from '@/lib/api';
import { format } from 'date-fns';

/* ── Types ────────────────────────────────────────────────────────── */

interface PriceListSummary {
  id: number;
  supplier_id: number;
  supplier_name: string;
  effective_date: string;
  item_count: number;
  notes?: string;
}

interface PriceListItem {
  id: number;
  product_id: number;
  product_name: string;
  hebrew_name?: string;
  category?: string;
  price: number;
  unit?: string;
}

interface PriceListDetail {
  id: number;
  supplier_id: number;
  supplier_name: string;
  effective_date: string;
  items: PriceListItem[];
}

interface Supplier {
  id: number;
  name: string;
}

/* ── Editable row component ───────────────────────────────────────── */

function EditableRow({
  item,
  onSave,
  onDelete,
  saving,
}: {
  item: PriceListItem;
  onSave: (id: number, price: number, unit: string) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
  saving: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [price, setPrice] = useState(item.price.toString());
  const [unit, setUnit] = useState(item.unit || '');

  const handleSave = async () => {
    const parsedPrice = parseFloat(price);
    if (isNaN(parsedPrice) || parsedPrice <= 0) return;
    await onSave(item.id, parsedPrice, unit);
    setEditing(false);
  };

  const handleCancel = () => {
    setPrice(item.price.toString());
    setUnit(item.unit || '');
    setEditing(false);
  };

  if (editing) {
    return (
      <tr className="border-b bg-blue-50/50">
        <td className="py-2 px-2">
          <span className="font-medium text-sm">{item.product_name}</span>
          {item.hebrew_name && (
            <span className="text-gray-500 text-xs block">{item.hebrew_name}</span>
          )}
        </td>
        <td className="py-2 px-2 text-gray-600 text-sm">{item.category || '-'}</td>
        <td className="py-2 px-2">
          <input
            type="number"
            step="0.01"
            min="0"
            className="w-24 px-2 py-1 border rounded text-sm text-right font-mono"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSave()}
            autoFocus
          />
        </td>
        <td className="py-2 px-2">
          <input
            type="text"
            className="w-16 px-2 py-1 border rounded text-sm"
            value={unit}
            onChange={(e) => setUnit(e.target.value)}
            placeholder="kg"
          />
        </td>
        <td className="py-2 px-2 text-right">
          <div className="flex items-center justify-end gap-1">
            <button
              onClick={handleSave}
              disabled={saving}
              className="p-1 rounded hover:bg-green-100 text-green-600 transition-colors"
              title="Save"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            </button>
            <button
              onClick={handleCancel}
              className="p-1 rounded hover:bg-gray-100 text-gray-500 transition-colors"
              title="Cancel"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </td>
      </tr>
    );
  }

  return (
    <tr className="border-b last:border-0 hover:bg-gray-50 group">
      <td className="py-2.5 px-2">
        <span className="font-medium text-sm">{item.product_name}</span>
        {item.hebrew_name && (
          <span className="text-gray-500 text-xs block">{item.hebrew_name}</span>
        )}
      </td>
      <td className="py-2.5 px-2 text-gray-600 text-sm">{item.category || '-'}</td>
      <td className="py-2.5 px-2 text-right font-mono font-medium text-sm">
        {item.price.toLocaleString('he-IL', { style: 'currency', currency: 'ILS' })}
      </td>
      <td className="py-2.5 px-2 text-right text-gray-600 text-sm">{item.unit || '-'}</td>
      <td className="py-2.5 px-2 text-right">
        <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={() => setEditing(true)}
            className="p-1 rounded hover:bg-blue-100 text-blue-600 transition-colors"
            title="Edit"
          >
            <Pencil className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onDelete(item.id)}
            className="p-1 rounded hover:bg-red-100 text-red-500 transition-colors"
            title="Remove"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </td>
    </tr>
  );
}

/* ── Main page ────────────────────────────────────────────────────── */

export default function PriceListsPage() {
  const [priceLists, setPriceLists] = useState<PriceListSummary[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [selectedSupplier, setSelectedSupplier] = useState<number | null>(null);
  const [selectedPriceList, setSelectedPriceList] = useState<PriceListDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [saving, setSaving] = useState(false);

  // Generate from proformas
  const [generating, setGenerating] = useState(false);
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Upload
  const [showUpload, setShowUpload] = useState(false);
  const [uploadSupplier, setUploadSupplier] = useState<number>(0);
  const [uploadDate, setUploadDate] = useState(new Date().toISOString().split('T')[0]);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Add product
  const [showAddProduct, setShowAddProduct] = useState(false);
  const [newProduct, setNewProduct] = useState({
    product_name: '',
    price: '',
    unit: '',
    hebrew_name: '',
    category: '',
  });

  // Create empty list
  const [showCreate, setShowCreate] = useState(false);
  const [createData, setCreateData] = useState({
    supplier_id: 0,
    effective_date: new Date().toISOString().split('T')[0],
    notes: '',
  });

  /* ── Data loading ─────────────────────────────────────────────── */

  useEffect(() => {
    setSelectedPriceList(null);
    setSearchTerm('');
    setToast(null);
    loadData();
  }, [selectedSupplier]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [plData, suppData] = await Promise.all([
        priceListsAPI.list(selectedSupplier ? { supplier_id: selectedSupplier } : {}),
        suppliers.length === 0 ? suppliersAPI.list() : Promise.resolve(suppliers),
      ]);
      setPriceLists(plData);
      if (suppliers.length === 0) setSuppliers(suppData);
    } catch {
      showToast('error', 'Failed to load price lists');
    } finally {
      setLoading(false);
    }
  };

  const loadDetail = async (id: number) => {
    try {
      setDetailLoading(true);
      const data = await priceListsAPI.get(id);
      setSelectedPriceList(data);
    } catch {
      showToast('error', 'Failed to load price list');
    } finally {
      setDetailLoading(false);
    }
  };

  /* ── Toast ────────────────────────────────────────────────────── */

  const showToast = useCallback((type: 'success' | 'error', message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 4000);
  }, []);

  /* ── Handlers ─────────────────────────────────────────────────── */

  const handleCreate = async () => {
    if (!createData.supplier_id) return;
    try {
      await priceListsAPI.create({
        supplier_id: createData.supplier_id,
        effective_date: createData.effective_date,
        notes: createData.notes || undefined,
      });
      setShowCreate(false);
      setCreateData({ supplier_id: 0, effective_date: new Date().toISOString().split('T')[0], notes: '' });
      showToast('success', 'Price list created');
      loadData();
    } catch {
      showToast('error', 'Failed to create price list');
    }
  };

  const handleGenerateFromProformas = async (supplierId: number) => {
    setGenerating(true);
    try {
      const result = await priceListsAPI.generateFromProformas(supplierId);
      showToast('success', result.message);
      await loadData();
      if (result.price_list_id) await loadDetail(result.price_list_id);
    } catch (err: any) {
      showToast('error', err?.response?.data?.detail || 'Failed to generate price list');
    } finally {
      setGenerating(false);
    }
  };

  const handleGenerateAll = async () => {
    setGenerating(true);
    try {
      let success = 0;
      for (const s of suppliers) {
        try {
          await priceListsAPI.generateFromProformas(s.id);
          success++;
        } catch { /* skip */ }
      }
      showToast('success', `Generated for ${success}/${suppliers.length} suppliers`);
      await loadData();
    } catch {
      showToast('error', 'Failed to generate price lists');
    } finally {
      setGenerating(false);
    }
  };

  /* ── File upload ──────────────────────────────────────────────── */

  const handleFileUpload = async (file: File) => {
    if (!uploadSupplier) {
      showToast('error', 'Please select a supplier first');
      return;
    }
    setUploading(true);
    try {
      const result = await priceListsAPI.upload(file, uploadSupplier, uploadDate);
      showToast('success', result.message);
      setShowUpload(false);
      setUploadSupplier(0);
      await loadData();
      if (result.price_list_id) await loadDetail(result.price_list_id);
    } catch (err: any) {
      showToast('error', err?.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileUpload(file);
    e.target.value = '';
  };

  /* ── Inline editing ───────────────────────────────────────────── */

  const handleSaveItem = async (itemId: number, price: number, unit: string) => {
    if (!selectedPriceList) return;
    setSaving(true);
    try {
      await priceListsAPI.updateItem(selectedPriceList.id, itemId, { price, unit: unit || undefined });
      // Update local state immutably
      setSelectedPriceList({
        ...selectedPriceList,
        items: selectedPriceList.items.map((i) =>
          i.id === itemId ? { ...i, price, unit: unit || i.unit } : i
        ),
      });
      showToast('success', 'Price updated');
    } catch {
      showToast('error', 'Failed to update item');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteItem = async (itemId: number) => {
    if (!selectedPriceList) return;
    try {
      await priceListsAPI.deleteItem(selectedPriceList.id, itemId);
      setSelectedPriceList({
        ...selectedPriceList,
        items: selectedPriceList.items.filter((i) => i.id !== itemId),
      });
      showToast('success', 'Item removed');
    } catch {
      showToast('error', 'Failed to remove item');
    }
  };

  const handleAddProduct = async () => {
    if (!selectedPriceList || !newProduct.product_name || !newProduct.price) return;
    const price = parseFloat(newProduct.price);
    if (isNaN(price) || price <= 0) return;

    setSaving(true);
    try {
      const result = await priceListsAPI.addProduct(selectedPriceList.id, {
        product_name: newProduct.product_name,
        price,
        unit: newProduct.unit || undefined,
        hebrew_name: newProduct.hebrew_name || undefined,
        category: newProduct.category || undefined,
      });
      // Re-load detail to get full product data
      await loadDetail(selectedPriceList.id);
      setNewProduct({ product_name: '', price: '', unit: '', hebrew_name: '', category: '' });
      setShowAddProduct(false);
      showToast('success', `Added ${result.product_name}`);
    } catch (err: any) {
      showToast('error', err?.response?.data?.detail || 'Failed to add product');
    } finally {
      setSaving(false);
    }
  };

  /* ── Filtering ────────────────────────────────────────────────── */

  const filteredItems = selectedPriceList?.items?.filter((item) => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      item.product_name?.toLowerCase().includes(term) ||
      item.hebrew_name?.toLowerCase().includes(term) ||
      item.category?.toLowerCase().includes(term)
    );
  }) || [];

  const selectedSupplierName = suppliers.find((s) => s.id === selectedSupplier)?.name;

  /* ── Render ───────────────────────────────────────────────────── */

  return (
    <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Price Lists</h1>
          <p className="text-sm text-muted-foreground">
            Manage supplier pricing — upload from file or edit product-by-product
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={() => setShowUpload(!showUpload)}
            variant="outline"
            className="border-purple-300 text-purple-700 hover:bg-purple-50"
          >
            <Upload className="w-4 h-4 mr-2" />
            Upload CSV
          </Button>
          <Button
            onClick={() => selectedSupplier ? handleGenerateFromProformas(selectedSupplier) : handleGenerateAll()}
            disabled={generating}
            variant="outline"
            className="border-green-300 text-green-700 hover:bg-green-50"
          >
            {generating ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4 mr-2" />
            )}
            {generating
              ? 'Generating...'
              : selectedSupplier
                ? 'Generate from Proformas'
                : 'Generate All'}
          </Button>
          <Button onClick={() => setShowCreate(true)} className="bg-blue-600 hover:bg-blue-700">
            <Plus className="w-4 h-4 mr-2" /> New List
          </Button>
        </div>
      </div>

      {/* ── Toast ───────────────────────────────────────────────── */}
      {toast && (
        <div className={`p-3 rounded-lg text-sm flex items-center gap-2 animate-fade-in-up ${
          toast.type === 'error'
            ? 'bg-red-50 text-red-700 border border-red-200'
            : 'bg-green-50 text-green-700 border border-green-200'
        }`}>
          {toast.type === 'error' ? (
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
          ) : (
            <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          )}
          <span>{toast.message}</span>
          <button onClick={() => setToast(null)} className="ml-auto text-gray-400 hover:text-gray-600">✕</button>
        </div>
      )}

      {/* ── Upload Panel ────────────────────────────────────────── */}
      {showUpload && (
        <Card className="border-purple-200 bg-purple-50/30">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 mb-4">
              <FileSpreadsheet className="w-5 h-5 text-purple-600" />
              <h3 className="font-semibold">Upload Price List from CSV</h3>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Upload a CSV file with columns for product name, price, and optionally unit.
              Column detection is automatic (supports English &amp; Hebrew headers).
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Supplier *</label>
                <select
                  className="w-full px-3 py-2 border rounded-lg text-sm bg-white"
                  value={uploadSupplier}
                  onChange={(e) => setUploadSupplier(Number(e.target.value))}
                >
                  <option value={0}>Select supplier...</option>
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Effective Date</label>
                <input
                  type="date"
                  className="w-full px-3 py-2 border rounded-lg text-sm bg-white"
                  value={uploadDate}
                  onChange={(e) => setUploadDate(e.target.value)}
                />
              </div>
              <div className="flex items-end">
                <Button variant="outline" onClick={() => setShowUpload(false)} className="mr-2">
                  Cancel
                </Button>
              </div>
            </div>
            {/* Drop zone */}
            <div
              onDrop={handleDrop}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onClick={() => uploadSupplier && fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer ${
                dragOver
                  ? 'border-purple-400 bg-purple-100/50'
                  : uploadSupplier
                    ? 'border-gray-300 hover:border-purple-300 hover:bg-purple-50/50'
                    : 'border-gray-200 bg-gray-50 cursor-not-allowed'
              }`}
            >
              {uploading ? (
                <div className="flex items-center justify-center gap-2">
                  <Loader2 className="w-6 h-6 animate-spin text-purple-600" />
                  <span className="text-purple-700 font-medium">Uploading...</span>
                </div>
              ) : (
                <>
                  <Upload className={`w-8 h-8 mx-auto mb-2 ${uploadSupplier ? 'text-purple-400' : 'text-gray-300'}`} />
                  <p className={`text-sm font-medium ${uploadSupplier ? 'text-gray-700' : 'text-gray-400'}`}>
                    {uploadSupplier
                      ? 'Drop CSV file here or click to browse'
                      : 'Select a supplier first'}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    Supports .csv files with product name, price, and unit columns
                  </p>
                </>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.tsv,.txt"
                className="hidden"
                onChange={handleFileInput}
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Create Empty List Panel ─────────────────────────────── */}
      {showCreate && (
        <Card className="border-blue-200 bg-blue-50/30">
          <CardContent className="pt-6">
            <h3 className="font-semibold mb-4">Create Empty Price List</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Supplier</label>
                <select
                  className="w-full px-3 py-2 border rounded-lg text-sm bg-white"
                  value={createData.supplier_id}
                  onChange={(e) => setCreateData({ ...createData, supplier_id: Number(e.target.value) })}
                >
                  <option value={0}>Select supplier...</option>
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Effective Date</label>
                <input
                  type="date"
                  className="w-full px-3 py-2 border rounded-lg text-sm bg-white"
                  value={createData.effective_date}
                  onChange={(e) => setCreateData({ ...createData, effective_date: e.target.value })}
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Notes</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border rounded-lg text-sm bg-white"
                  placeholder="Optional notes..."
                  value={createData.notes}
                  onChange={(e) => setCreateData({ ...createData, notes: e.target.value })}
                />
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              <Button onClick={handleCreate} disabled={!createData.supplier_id} className="bg-blue-600 hover:bg-blue-700">
                Create
              </Button>
              <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Supplier Filter ─────────────────────────────────────── */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setSelectedSupplier(null)}
          className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
            !selectedSupplier ? 'bg-blue-600 text-white shadow-sm' : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
          }`}
        >
          All Suppliers
        </button>
        {suppliers.map((s) => (
          <button
            key={s.id}
            onClick={() => setSelectedSupplier(s.id)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              selectedSupplier === s.id ? 'bg-blue-600 text-white shadow-sm' : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
            }`}
          >
            {s.name}
          </button>
        ))}
      </div>

      {/* ── Main Grid ───────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── Price Lists Column ─────────────────────────────────── */}
        <div className="lg:col-span-1">
          <Card className="overflow-hidden">
            <CardHeader className="pb-2 bg-gray-50/50">
              <CardTitle className="text-base flex items-center gap-2">
                <FileText className="w-4 h-4 text-blue-600" />
                Price Lists ({priceLists.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {loading ? (
                <div className="text-center py-12 text-gray-400">
                  <Loader2 className="w-6 h-6 mx-auto mb-2 animate-spin" />
                  Loading...
                </div>
              ) : priceLists.length === 0 ? (
                <div className="text-center py-12 px-4">
                  <FileText className="w-10 h-10 mx-auto mb-3 text-gray-300" />
                  <p className="text-gray-400 mb-4">No price lists found</p>
                  <div className="flex flex-col gap-2 items-center">
                    <Button
                      size="sm"
                      onClick={() => setShowUpload(true)}
                      className="bg-purple-600 hover:bg-purple-700"
                    >
                      <Upload className="w-3 h-3 mr-1" /> Upload CSV
                    </Button>
                    {selectedSupplier && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleGenerateFromProformas(selectedSupplier)}
                        disabled={generating}
                        className="text-green-700 border-green-300 hover:bg-green-50"
                      >
                        {generating ? (
                          <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                        ) : (
                          <RefreshCw className="w-3 h-3 mr-1" />
                        )}
                        Generate from Proformas
                      </Button>
                    )}
                  </div>
                </div>
              ) : (
                <div className="divide-y">
                  {priceLists.map((pl) => (
                    <div
                      key={pl.id}
                      onClick={() => loadDetail(pl.id)}
                      className={`p-3 cursor-pointer transition-colors ${
                        selectedPriceList?.id === pl.id
                          ? 'bg-blue-50 border-l-2 border-l-blue-500'
                          : 'hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium text-sm">{pl.supplier_name}</p>
                          <p className="text-xs text-gray-500">
                            {format(new Date(pl.effective_date), 'MMM d, yyyy')}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-xs">
                            {pl.item_count} items
                          </Badge>
                          <ChevronRight className="w-4 h-4 text-gray-400" />
                        </div>
                      </div>
                      {pl.notes && (
                        <p className="text-xs text-gray-500 mt-1 truncate">{pl.notes}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* ── Detail Column ──────────────────────────────────────── */}
        <div className="lg:col-span-2">
          {detailLoading ? (
            <Card>
              <CardContent className="py-12 text-center text-gray-400">
                <Loader2 className="w-6 h-6 mx-auto mb-2 animate-spin" />
                Loading price list...
              </CardContent>
            </Card>
          ) : selectedPriceList ? (
            <Card className="overflow-hidden">
              <CardHeader className="pb-3 bg-gray-50/50">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-lg">{selectedPriceList.supplier_name}</CardTitle>
                    <p className="text-sm text-muted-foreground">
                      Effective: {format(new Date(selectedPriceList.effective_date), 'MMMM d, yyyy')}
                      {' '}&middot; {selectedPriceList.items?.length || 0} products
                    </p>
                  </div>
                  <Button
                    size="sm"
                    onClick={() => setShowAddProduct(true)}
                    className="bg-blue-600 hover:bg-blue-700"
                  >
                    <PackagePlus className="w-4 h-4 mr-1" /> Add Product
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="p-4">
                {/* Add product form */}
                {showAddProduct && (
                  <div className="mb-4 p-4 bg-blue-50/50 border border-blue-200 rounded-lg">
                    <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
                      <PackagePlus className="w-4 h-4 text-blue-600" />
                      Add New Product
                    </h4>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                      <div>
                        <label className="text-xs font-medium text-gray-600 block mb-1">Product Name *</label>
                        <input
                          type="text"
                          className="w-full px-2 py-1.5 border rounded text-sm bg-white"
                          placeholder="e.g. Chicken Breast"
                          value={newProduct.product_name}
                          onChange={(e) => setNewProduct({ ...newProduct, product_name: e.target.value })}
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-gray-600 block mb-1">Hebrew Name</label>
                        <input
                          type="text"
                          className="w-full px-2 py-1.5 border rounded text-sm bg-white"
                          placeholder="שם בעברית"
                          value={newProduct.hebrew_name}
                          onChange={(e) => setNewProduct({ ...newProduct, hebrew_name: e.target.value })}
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-gray-600 block mb-1">Price (₪) *</label>
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          className="w-full px-2 py-1.5 border rounded text-sm bg-white"
                          placeholder="0.00"
                          value={newProduct.price}
                          onChange={(e) => setNewProduct({ ...newProduct, price: e.target.value })}
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-gray-600 block mb-1">Unit</label>
                        <input
                          type="text"
                          className="w-full px-2 py-1.5 border rounded text-sm bg-white"
                          placeholder="kg, l, unit"
                          value={newProduct.unit}
                          onChange={(e) => setNewProduct({ ...newProduct, unit: e.target.value })}
                        />
                      </div>
                      <div className="flex items-end gap-2">
                        <Button
                          size="sm"
                          onClick={handleAddProduct}
                          disabled={saving || !newProduct.product_name || !newProduct.price}
                          className="bg-blue-600 hover:bg-blue-700"
                        >
                          {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
                          <span className="ml-1">Add</span>
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => setShowAddProduct(false)}>
                          <X className="w-3 h-3" />
                        </Button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Search */}
                <div className="relative mb-4">
                  <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search products..."
                    className="w-full pl-10 pr-4 py-2 border rounded-lg text-sm bg-white"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>

                {/* Items table */}
                {filteredItems.length === 0 ? (
                  <div className="text-center py-12">
                    <FileText className="w-10 h-10 mx-auto mb-3 text-gray-300" />
                    <p className="text-gray-400 mb-3">No products in this price list</p>
                    <div className="flex gap-2 justify-center">
                      <Button
                        size="sm"
                        onClick={() => setShowAddProduct(true)}
                        className="bg-blue-600 hover:bg-blue-700"
                      >
                        <PackagePlus className="w-3 h-3 mr-1" /> Add Product
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setShowUpload(true)}
                        className="text-purple-700 border-purple-300"
                      >
                        <Upload className="w-3 h-3 mr-1" /> Upload CSV
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-lg border">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-gray-50 text-left text-gray-600">
                          <th className="py-2.5 px-2 font-medium">Product</th>
                          <th className="py-2.5 px-2 font-medium">Category</th>
                          <th className="py-2.5 px-2 font-medium text-right">Price</th>
                          <th className="py-2.5 px-2 font-medium text-right">Unit</th>
                          <th className="py-2.5 px-2 font-medium text-right w-20">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredItems.map((item) => (
                          <EditableRow
                            key={item.id}
                            item={item}
                            onSave={handleSaveItem}
                            onDelete={handleDeleteItem}
                            saving={saving}
                          />
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="py-16 text-center">
                <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                <p className="text-gray-400 text-lg mb-1">Select a price list</p>
                <p className="text-gray-400 text-sm">
                  Or upload a CSV / generate from proformas to get started
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </main>
  );
}
