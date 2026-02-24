'use client';

import { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  AlertTriangle, CheckCircle2, Eye, Send, Shield
} from 'lucide-react';
import { anomaliesAPI } from '@/lib/api';
import { format } from 'date-fns';

export default function AnomaliesPage() {
  const [anomalies, setAnomalies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'active' | 'resolved'>('all');
  const [resolveId, setResolveId] = useState<number | null>(null);
  const [resolveNotes, setResolveNotes] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const data = await anomaliesAPI.list();
      setAnomalies(data);
    } catch (error) {
      console.error('Failed to load anomalies:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAcknowledge = async (id: number) => {
    try {
      await anomaliesAPI.acknowledge(id);
      await loadData();
    } catch (error) {
      console.error('Failed to acknowledge:', error);
    }
  };

  const handleResolve = async (id: number) => {
    if (!resolveNotes.trim()) return;
    try {
      await anomaliesAPI.resolve(id, resolveNotes);
      setResolveId(null);
      setResolveNotes('');
      await loadData();
    } catch (error) {
      console.error('Failed to resolve:', error);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-100 text-red-800 border-red-200';
      case 'high': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  const filtered = anomalies.filter(a => {
    if (filter === 'active') return !a.resolved;
    if (filter === 'resolved') return a.resolved;
    return true;
  });

  const activeCount = anomalies.filter(a => !a.resolved).length;
  const criticalCount = anomalies.filter(a => !a.resolved && a.severity === 'critical').length;
  const acknowledgedCount = anomalies.filter(a => a.acknowledged && !a.resolved).length;

  return (
    <div>
      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-gray-900">Anomalies & Alerts</h2>
          <p className="text-gray-500 text-sm">{anomalies.length} anomalies detected</p>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <Card className="p-6">
            <p className="text-sm text-gray-600">Total</p>
            <p className="text-4xl font-bold text-gray-900 mt-1">{anomalies.length}</p>
          </Card>
          <Card className="p-6">
            <p className="text-sm text-gray-600">Active</p>
            <p className="text-4xl font-bold text-orange-600 mt-1">{activeCount}</p>
          </Card>
          <Card className="p-6">
            <p className="text-sm text-gray-600">Critical</p>
            <p className="text-4xl font-bold text-red-600 mt-1">{criticalCount}</p>
          </Card>
          <Card className="p-6">
            <p className="text-sm text-gray-600">Acknowledged</p>
            <p className="text-4xl font-bold text-blue-600 mt-1">{acknowledgedCount}</p>
          </Card>
        </div>

        {/* Filter Tabs */}
        <div className="flex gap-2 mb-6">
          {(['all', 'active', 'resolved'] as const).map(f => (
            <Button
              key={f}
              variant={filter === f ? 'default' : 'outline'}
              size="sm"
              onClick={() => setFilter(f)}
            >
              {f === 'all' ? `All (${anomalies.length})` : f === 'active' ? `Active (${activeCount})` : `Resolved (${anomalies.length - activeCount})`}
            </Button>
          ))}
        </div>

        {/* Anomalies List */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-orange-600" />
              Anomalies
            </CardTitle>
          </CardHeader>
          <CardContent>
            {filtered.length === 0 ? (
              <div className="text-center py-12">
                <CheckCircle2 className="w-16 h-16 text-green-300 mx-auto mb-4" />
                <p className="text-gray-500">No anomalies found</p>
              </div>
            ) : (
              <div className="space-y-3">
                {filtered.map((anomaly: any) => (
                  <div
                    key={anomaly.id}
                    className={`p-4 border rounded-lg ${anomaly.resolved ? 'bg-gray-50' : 'bg-white'}`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          {anomaly.resolved ? (
                            <CheckCircle2 className="w-4 h-4 text-green-600" />
                          ) : (
                            <AlertTriangle className="w-4 h-4 text-orange-600" />
                          )}
                          <Badge className={getSeverityColor(anomaly.severity)}>
                            {anomaly.severity}
                          </Badge>
                          <Badge variant="secondary">{anomaly.anomaly_type}</Badge>
                          <span className="text-sm text-gray-500">
                            {anomaly.entity_type} #{anomaly.entity_id}
                          </span>
                        </div>
                        <p className="text-gray-700">{anomaly.description}</p>
                        <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                          <span>{format(new Date(anomaly.detected_at), 'MMM d, yyyy')}</span>
                          {anomaly.expected_value != null && anomaly.actual_value != null && (
                            <span>
                              Expected: {anomaly.expected_value.toFixed(1)} | Actual: {anomaly.actual_value.toFixed(1)}
                              {anomaly.variance_percent != null && (
                                <span className="text-red-600 ml-1">
                                  ({anomaly.variance_percent > 0 ? '+' : ''}{anomaly.variance_percent.toFixed(1)}%)
                                </span>
                              )}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Actions */}
                    {!anomaly.resolved && (
                      <div className="flex gap-2 mt-3 pt-3 border-t">
                        {!anomaly.acknowledged && (
                          <Button size="sm" variant="outline" onClick={() => handleAcknowledge(anomaly.id)}>
                            <Eye className="w-3 h-3 mr-1" /> Acknowledge
                          </Button>
                        )}
                        {resolveId === anomaly.id ? (
                          <div className="flex-1 flex gap-2">
                            <input
                              className="flex-1 p-2 border rounded text-sm"
                              placeholder="Resolution notes..."
                              value={resolveNotes}
                              onChange={(e) => setResolveNotes(e.target.value)}
                            />
                            <Button size="sm" onClick={() => handleResolve(anomaly.id)} disabled={!resolveNotes.trim()}>
                              <Send className="w-3 h-3 mr-1" /> Save
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => { setResolveId(null); setResolveNotes(''); }}>
                              Cancel
                            </Button>
                          </div>
                        ) : (
                          <Button size="sm" variant="outline" onClick={() => setResolveId(anomaly.id)}>
                            <CheckCircle2 className="w-3 h-3 mr-1" /> Resolve
                          </Button>
                        )}
                      </div>
                    )}

                    {anomaly.resolution_notes && (
                      <div className="mt-3 pt-3 border-t">
                        <p className="text-sm text-gray-600">
                          <span className="font-medium">Resolution:</span> {anomaly.resolution_notes}
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
    </div>
  );
}
