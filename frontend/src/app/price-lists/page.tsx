'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  FileText, Plus, ChevronRight, ArrowUpDown,
  TrendingUp, TrendingDown, Minus, Search, Filter,
  RefreshCw, Loader2, CheckCircle2,
} from 'lucide-react';
import { priceListsAPI, suppliersAPI } from '@/lib/api';
import { format } from 'date-fns';

export default function PriceListsPage() {
  const router = useRouter();
  const [priceLists, setPriceLists] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [selectedSupplier, setSelectedSupplier] = useState<number | null>(null);
  const [selectedPriceList, setSelectedPriceList] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  // Generate from proformas
  const [generating, setGenerating] = useState(false);
  const [generateResult, setGenerateResult] = useState<any>(null);

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [createData, setCreateData] = useState({
    supplier_id: 0,
    effective_date: new Date().toISOString().split('T')[0],
    notes: '',
  });

  useEffect(() => {
    setSelectedPriceList(null);
    setSearchTerm('');
    setGenerateResult(null);
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
      // handle silently
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
      // handle silently
    } finally {
      setDetailLoading(false);
    }
  };

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
      loadData();
    } catch {
      // handle silently
    }
  };

  const handleGenerateFromProformas = async (supplierId: number) => {
    setGenerating(true);
    setGenerateResult(null);
    try {
      const result = await priceListsAPI.generateFromProformas(supplierId);
      setGenerateResult(result);
      await loadData();
      // Auto-load the newly created price list
      if (result.price_list_id) {
        await loadDetail(result.price_list_id);
      }
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Failed to generate price list';
      setGenerateResult({ error: msg });
    } finally {
      setGenerating(false);
    }
  };

  const handleGenerateAll = async () => {
    setGenerating(true);
    setGenerateResult(null);
    try {
      const results = [];
      for (const s of suppliers) {
        try {
          const result = await priceListsAPI.generateFromProformas(s.id);
          results.push({ supplier: s.name, ...result });
        } catch {
          results.push({ supplier: s.name, error: 'No proforma data' });
        }
      }
      setGenerateResult({
        message: `Generated for ${results.filter((r) => !r.error).length}/${suppliers.length} suppliers`,
        details: results,
      });
      await loadData();
    } catch {
      setGenerateResult({ error: 'Failed to generate price lists' });
    } finally {
      setGenerating(false);
    }
  };

  const filteredItems = selectedPriceList?.items?.filter((item: any) => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      item.product_name?.toLowerCase().includes(term) ||
      item.hebrew_name?.toLowerCase().includes(term) ||
      item.category?.toLowerCase().includes(term)
    );
  }) || [];

  const selectedSupplierName = suppliers.find((s: any) => s.id === selectedSupplier)?.name;

  return (
    <main className="max-w-7xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Price Lists</h1>
          <p className="text-sm text-gray-500">Supplier pricing by product</p>
        </div>
        <div className="flex gap-2">
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
                ? `Generate from Proformas`
                : 'Generate All from Proformas'}
          </Button>
          <Button onClick={() => setShowCreate(true)} className="bg-blue-600 hover:bg-blue-700">
            <Plus className="w-4 h-4 mr-2" /> New Price List
          </Button>
        </div>
      </div>

      {/* Generate result message */}
      {generateResult && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${
          generateResult.error ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-green-50 text-green-700 border border-green-200'
        }`}>
          <div className="flex items-center gap-2">
            {generateResult.error ? (
              <span>⚠️ {generateResult.error}</span>
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4" />
                <span>{generateResult.message}</span>
                {generateResult.items_count && (
                  <Badge variant="outline" className="text-xs text-green-700 border-green-300">
                    {generateResult.items_count} products
                  </Badge>
                )}
              </>
            )}
            <button
              onClick={() => setGenerateResult(null)}
              className="ml-auto text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Create Form Modal */}
      {showCreate && (
        <Card className="mb-6 border-blue-200 bg-blue-50/50">
          <CardContent className="pt-6">
            <h3 className="font-semibold mb-4">Create New Price List</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Supplier</label>
                <select
                  className="w-full px-3 py-2 border rounded-lg text-sm"
                  value={createData.supplier_id}
                  onChange={(e) => setCreateData({ ...createData, supplier_id: Number(e.target.value) })}
                >
                  <option value={0}>Select supplier...</option>
                  {suppliers.map((s: any) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Effective Date</label>
                <input
                  type="date"
                  className="w-full px-3 py-2 border rounded-lg text-sm"
                  value={createData.effective_date}
                  onChange={(e) => setCreateData({ ...createData, effective_date: e.target.value })}
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Notes</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border rounded-lg text-sm"
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

      {/* Supplier Filter */}
      <div className="flex gap-2 mb-4 flex-wrap">
        <button
          onClick={() => setSelectedSupplier(null)}
          className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
            !selectedSupplier ? 'bg-blue-600 text-white' : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
          }`}
        >
          All Suppliers
        </button>
        {suppliers.map((s: any) => (
          <button
            key={s.id}
            onClick={() => setSelectedSupplier(s.id)}
            className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
              selectedSupplier === s.id ? 'bg-blue-600 text-white' : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
            }`}
          >
            {s.name}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Price Lists Column */}
        <div className="lg:col-span-1">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">
                <FileText className="w-4 h-4 inline mr-2" />
                Price Lists ({priceLists.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="text-center py-8 text-gray-400">Loading...</div>
              ) : priceLists.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-gray-400 mb-3">No price lists found</p>
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
              ) : (
                <div className="space-y-2">
                  {priceLists.map((pl: any) => (
                    <div
                      key={pl.id}
                      onClick={() => loadDetail(pl.id)}
                      className={`p-3 rounded-lg cursor-pointer transition-colors ${
                        selectedPriceList?.id === pl.id
                          ? 'bg-blue-50 border border-blue-200'
                          : 'bg-gray-50 hover:bg-gray-100'
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

        {/* Detail Column */}
        <div className="lg:col-span-2">
          {detailLoading ? (
            <Card>
              <CardContent className="py-12 text-center text-gray-400">Loading price list...</CardContent>
            </Card>
          ) : selectedPriceList ? (
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-lg">{selectedPriceList.supplier_name}</CardTitle>
                    <p className="text-sm text-gray-500">
                      Effective: {format(new Date(selectedPriceList.effective_date), 'MMMM d, yyyy')}
                      {' '} &middot; {selectedPriceList.items?.length || 0} products
                    </p>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {/* Search */}
                <div className="relative mb-4">
                  <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search products..."
                    className="w-full pl-10 pr-4 py-2 border rounded-lg text-sm"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>

                {/* Items table */}
                {filteredItems.length === 0 ? (
                  <p className="text-center py-8 text-gray-400">No items in this price list</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-left text-gray-500">
                          <th className="pb-2 font-medium">Product</th>
                          <th className="pb-2 font-medium">Category</th>
                          <th className="pb-2 font-medium text-right">Price</th>
                          <th className="pb-2 font-medium text-right">Unit</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredItems.map((item: any, i: number) => (
                          <tr key={item.id || i} className="border-b last:border-0 hover:bg-gray-50">
                            <td className="py-2.5">
                              <div>
                                <span className="font-medium">{item.product_name}</span>
                                {item.hebrew_name && (
                                  <span className="text-gray-500 mr-2 text-xs block">{item.hebrew_name}</span>
                                )}
                              </div>
                            </td>
                            <td className="py-2.5 text-gray-600">{item.category || '-'}</td>
                            <td className="py-2.5 text-right font-mono font-medium">
                              {item.price.toLocaleString('he-IL', { style: 'currency', currency: 'ILS' })}
                            </td>
                            <td className="py-2.5 text-right text-gray-600">{item.unit || '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="py-12 text-center text-gray-400">
                <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                <p>Select a price list to view details</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </main>
  );
}
