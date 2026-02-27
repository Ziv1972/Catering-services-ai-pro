'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft, DollarSign, AlertTriangle, Package,
  Calendar, FileText, RefreshCw, CheckCircle2, XCircle, ArrowUpRight, ArrowDownRight
} from 'lucide-react';
import { proformasAPI } from '@/lib/api';
import { format } from 'date-fns';

const fmtPrice = (v: number | null | undefined, currency = 'ILS') =>
  (v ?? 0).toLocaleString('he-IL', { style: 'currency', currency });

export default function ProformaDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [proforma, setProforma] = useState<any>(null);
  const [comparison, setComparison] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [comparing, setComparing] = useState(false);

  useEffect(() => {
    if (params.id) {
      loadProforma(Number(params.id));
    }
  }, [params.id]);

  const loadProforma = async (id: number) => {
    try {
      const data = await proformasAPI.get(id);
      setProforma(data);
      // Auto-compare prices on load
      runComparison(id);
    } catch (error) {
      // Failed to load
    } finally {
      setLoading(false);
    }
  };

  const runComparison = async (id?: number) => {
    const proformaId = id ?? Number(params.id);
    setComparing(true);
    try {
      const result = await proformasAPI.comparePrices(proformaId);
      setComparison(result);
    } catch {
      // No price list available or comparison failed
    } finally {
      setComparing(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'paid': return 'bg-green-100 text-green-800 border-green-200';
      case 'approved': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'pending': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'rejected': return 'bg-red-100 text-red-800 border-red-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  if (!proforma) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Card className="p-8 text-center max-w-md">
          <AlertTriangle className="w-12 h-12 text-orange-500 mx-auto mb-4" />
          <p className="text-gray-700 font-medium">Proforma not found</p>
          <Button variant="outline" className="mt-4" onClick={() => router.push('/proformas')}>
            Back to Proformas
          </Button>
        </Card>
      </div>
    );
  }

  // Use comparison data if available, otherwise fall back to proforma items
  const displayItems = comparison?.items || (proforma.items || []).map((item: any) => ({
    ...item,
    expected_price: null,
    match_status: 'no_comparison',
  }));

  const summary = comparison?.summary;
  const flaggedItems = displayItems.filter((i: any) => i.flagged);

  return (
    <div>
      <main className="max-w-7xl mx-auto px-4 py-8">
        <Button variant="ghost" className="mb-4" onClick={() => router.push('/proformas')}>
          <ArrowLeft className="w-4 h-4 mr-2" /> Back to Proformas
        </Button>

        {/* Header */}
        <div className="flex justify-between items-start mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">
              {proforma.supplier_name || 'Unknown Supplier'}
            </h2>
            <div className="flex items-center gap-3 mt-2">
              {proforma.proforma_number && (
                <span className="text-gray-500">#{proforma.proforma_number}</span>
              )}
              <Badge className={getStatusColor(proforma.status)}>
                {proforma.status}
              </Badge>
            </div>
          </div>
          <div className="text-right">
            <p className="text-3xl font-bold text-gray-900">
              {fmtPrice(proforma.total_amount, proforma.currency)}
            </p>
          </div>
        </div>

        {/* Info Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <Card className="p-5">
            <div className="flex items-center gap-3">
              <Calendar className="w-5 h-5 text-blue-500" />
              <div>
                <p className="text-sm text-gray-600">Invoice Date</p>
                <p className="font-medium">{format(new Date(proforma.invoice_date), 'MMM d, yyyy')}</p>
              </div>
            </div>
          </Card>
          {proforma.delivery_date && (
            <Card className="p-5">
              <div className="flex items-center gap-3">
                <Package className="w-5 h-5 text-green-500" />
                <div>
                  <p className="text-sm text-gray-600">Delivery Date</p>
                  <p className="font-medium">{format(new Date(proforma.delivery_date), 'MMM d, yyyy')}</p>
                </div>
              </div>
            </Card>
          )}
          {proforma.site_name && (
            <Card className="p-5">
              <div className="flex items-center gap-3">
                <FileText className="w-5 h-5 text-purple-500" />
                <div>
                  <p className="text-sm text-gray-600">Site</p>
                  <p className="font-medium">{proforma.site_name}</p>
                </div>
              </div>
            </Card>
          )}
          <Card className="p-5">
            <div className="flex items-center gap-3">
              <DollarSign className="w-5 h-5 text-orange-500" />
              <div>
                <p className="text-sm text-gray-600">Items</p>
                <p className="font-medium">{(proforma.items || []).length} line items</p>
              </div>
            </div>
          </Card>
        </div>

        {/* Price Comparison Summary */}
        {comparison && (
          <Card className="mb-6 border-l-4 border-l-blue-500">
            <CardContent className="py-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div>
                    <p className="text-sm font-medium text-gray-700">Price List Comparison</p>
                    <p className="text-xs text-gray-500">
                      {comparison.price_list_id
                        ? `vs. price list from ${format(new Date(comparison.price_list_date), 'MMM d, yyyy')}`
                        : 'No price list found for this supplier'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-6 text-sm">
                  {summary && (
                    <>
                      <div className="text-center">
                        <p className="text-lg font-bold text-green-600">{summary.matched}</p>
                        <p className="text-xs text-gray-500">Matched</p>
                      </div>
                      <div className="text-center">
                        <p className="text-lg font-bold text-red-600">{summary.flagged}</p>
                        <p className="text-xs text-gray-500">Flagged</p>
                      </div>
                      <div className="text-center">
                        <p className="text-lg font-bold text-gray-400">{summary.unmatched}</p>
                        <p className="text-xs text-gray-500">Not in list</p>
                      </div>
                    </>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => runComparison()}
                    disabled={comparing}
                  >
                    <RefreshCw className={`w-3.5 h-3.5 mr-1 ${comparing ? 'animate-spin' : ''}`} />
                    Re-check
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Flagged Items Alert */}
        {flaggedItems.length > 0 && (
          <Card className="mb-6 bg-red-50 border-red-200">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-red-900 text-base">
                <AlertTriangle className="w-5 h-5" />
                {flaggedItems.length} Price Difference(s) Detected
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {flaggedItems.map((item: any) => (
                  <div key={item.id} className="p-3 bg-white rounded border border-red-200 flex justify-between items-center">
                    <span className="font-medium text-sm">{item.product_name}</span>
                    <div className="flex items-center gap-3 text-sm">
                      {item.expected_price != null && (
                        <span className="text-gray-500">
                          Expected: {fmtPrice(item.expected_price, proforma.currency)}
                        </span>
                      )}
                      <span className="text-gray-500">→</span>
                      <span className="font-medium">
                        Actual: {fmtPrice(item.unit_price, proforma.currency)}
                      </span>
                      {item.price_variance != null && (
                        <Badge className={item.price_variance > 0
                          ? 'bg-red-100 text-red-700 border-red-200'
                          : 'bg-green-100 text-green-700 border-green-200'
                        }>
                          {item.price_variance > 0 ? '+' : ''}{item.price_variance.toFixed(1)}%
                        </Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Items Table with Price Comparison */}
        <Card>
          <CardHeader>
            <CardTitle>Line Items</CardTitle>
          </CardHeader>
          <CardContent>
            {displayItems.length === 0 ? (
              <p className="text-gray-500 text-center py-8">No items</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-600">
                      <th className="pb-3 font-medium">Product</th>
                      <th className="pb-3 font-medium text-right">Qty</th>
                      <th className="pb-3 font-medium">Unit</th>
                      <th className="pb-3 font-medium text-right">Expected</th>
                      <th className="pb-3 font-medium text-right">Actual Price</th>
                      <th className="pb-3 font-medium text-right">Total</th>
                      <th className="pb-3 font-medium text-right">Variance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayItems.map((item: any) => {
                      const hasExpected = item.expected_price != null;
                      const variance = item.price_variance;
                      const isFlagged = item.flagged;
                      const isHigher = variance != null && variance > 0;
                      const isLower = variance != null && variance < 0;

                      return (
                        <tr
                          key={item.id}
                          className={`border-b last:border-b-0 ${
                            isFlagged ? 'bg-red-50' : hasExpected && !isFlagged ? 'bg-green-50/30' : ''
                          }`}
                        >
                          <td className="py-3 font-medium text-gray-900">
                            <div className="flex items-center gap-1.5">
                              {isFlagged ? (
                                <XCircle className="w-4 h-4 text-red-500 shrink-0" />
                              ) : hasExpected ? (
                                <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />
                              ) : null}
                              {item.product_name}
                            </div>
                          </td>
                          <td className="py-3 text-right tabular-nums">{item.quantity}</td>
                          <td className="py-3 text-gray-600">{item.unit || '-'}</td>
                          <td className="py-3 text-right tabular-nums text-gray-500">
                            {hasExpected ? fmtPrice(item.expected_price, proforma.currency) : (
                              <span className="text-gray-300 text-xs">-</span>
                            )}
                          </td>
                          <td className={`py-3 text-right tabular-nums font-medium ${
                            isFlagged ? 'text-red-700' : ''
                          }`}>
                            {fmtPrice(item.unit_price, proforma.currency)}
                          </td>
                          <td className="py-3 text-right tabular-nums font-medium">
                            {fmtPrice(item.total_price, proforma.currency)}
                          </td>
                          <td className="py-3 text-right">
                            {variance != null ? (
                              <div className="flex items-center justify-end gap-1">
                                {isHigher ? (
                                  <ArrowUpRight className="w-3.5 h-3.5 text-red-500" />
                                ) : isLower ? (
                                  <ArrowDownRight className="w-3.5 h-3.5 text-green-500" />
                                ) : null}
                                <span className={
                                  isFlagged
                                    ? 'text-red-600 font-medium'
                                    : Math.abs(variance) > 0
                                    ? 'text-gray-600'
                                    : 'text-green-600'
                                }>
                                  {variance > 0 ? '+' : ''}{variance.toFixed(1)}%
                                </span>
                              </div>
                            ) : (
                              <span className="text-gray-300 text-xs">-</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2">
                      <td colSpan={5} className="py-3 font-semibold text-gray-900">Total</td>
                      <td className="py-3 text-right font-bold text-lg tabular-nums">
                        {fmtPrice(proforma.total_amount, proforma.currency)}
                      </td>
                      <td />
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Notes */}
        {proforma.notes && (
          <Card className="mt-6">
            <CardHeader>
              <CardTitle>Notes</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-gray-700">{proforma.notes}</p>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
