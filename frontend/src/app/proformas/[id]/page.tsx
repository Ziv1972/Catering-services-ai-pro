'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft, DollarSign, AlertTriangle, Package,
  Calendar, FileText
} from 'lucide-react';
import { proformasAPI } from '@/lib/api';
import { format } from 'date-fns';

export default function ProformaDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [proforma, setProforma] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (params.id) {
      loadProforma(Number(params.id));
    }
  }, [params.id]);

  const loadProforma = async (id: number) => {
    try {
      const data = await proformasAPI.get(id);
      setProforma(data);
    } catch (error) {
      console.error('Failed to load proforma:', error);
    } finally {
      setLoading(false);
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

  const flaggedItems = (proforma.items || []).filter((i: any) => i.flagged);

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
              {proforma.total_amount.toLocaleString('he-IL', { style: 'currency', currency: proforma.currency })}
            </p>
          </div>
        </div>

        {/* Info Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
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

        {/* Flagged Items Alert */}
        {flaggedItems.length > 0 && (
          <Card className="mb-6 bg-red-50 border-red-200">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-red-900">
                <AlertTriangle className="w-5 h-5" />
                {flaggedItems.length} Flagged Item(s)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {flaggedItems.map((item: any) => (
                  <div key={item.id} className="p-3 bg-white rounded border border-red-200 flex justify-between">
                    <span className="font-medium">{item.product_name}</span>
                    <span className="text-red-700">
                      {item.price_variance != null ? `${item.price_variance > 0 ? '+' : ''}${item.price_variance.toFixed(1)}% variance` : 'Flagged'}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Items Table */}
        <Card>
          <CardHeader>
            <CardTitle>Line Items</CardTitle>
          </CardHeader>
          <CardContent>
            {(proforma.items || []).length === 0 ? (
              <p className="text-gray-500 text-center py-8">No items</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-600">
                      <th className="pb-3 font-medium">Product</th>
                      <th className="pb-3 font-medium text-right">Qty</th>
                      <th className="pb-3 font-medium">Unit</th>
                      <th className="pb-3 font-medium text-right">Unit Price</th>
                      <th className="pb-3 font-medium text-right">Total</th>
                      <th className="pb-3 font-medium text-right">Variance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {proforma.items.map((item: any) => (
                      <tr
                        key={item.id}
                        className={`border-b last:border-b-0 ${item.flagged ? 'bg-red-50' : ''}`}
                      >
                        <td className="py-3 font-medium text-gray-900">
                          {item.product_name}
                          {item.flagged && (
                            <AlertTriangle className="w-4 h-4 text-red-500 inline ml-2" />
                          )}
                        </td>
                        <td className="py-3 text-right">{item.quantity}</td>
                        <td className="py-3">{item.unit || '-'}</td>
                        <td className="py-3 text-right">
                          {item.unit_price.toLocaleString('he-IL', { style: 'currency', currency: proforma.currency })}
                        </td>
                        <td className="py-3 text-right font-medium">
                          {item.total_price.toLocaleString('he-IL', { style: 'currency', currency: proforma.currency })}
                        </td>
                        <td className="py-3 text-right">
                          {item.price_variance != null ? (
                            <span className={item.price_variance > 5 ? 'text-red-600 font-medium' : 'text-gray-600'}>
                              {item.price_variance > 0 ? '+' : ''}{item.price_variance.toFixed(1)}%
                            </span>
                          ) : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2">
                      <td colSpan={4} className="py-3 font-semibold text-gray-900">Total</td>
                      <td className="py-3 text-right font-bold text-lg">
                        {proforma.total_amount.toLocaleString('he-IL', { style: 'currency', currency: proforma.currency })}
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
