'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft, AlertTriangle, TrendingUp,
  CheckCircle2, Clock
} from 'lucide-react';
import { complaintsAPI } from '@/lib/api';
import { format } from 'date-fns';

export default function ComplaintsPage() {
  const router = useRouter();
  const [complaints, setComplaints] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [patterns, setPatterns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [complaintsData, summaryData, patternsData] = await Promise.allSettled([
        complaintsAPI.list({ days: 30 }),
        complaintsAPI.getWeeklySummary(),
        complaintsAPI.getPatterns(),
      ]);

      setComplaints(complaintsData.status === 'fulfilled' ? complaintsData.value : []);
      setSummary(summaryData.status === 'fulfilled' ? summaryData.value : null);
      setPatterns(patternsData.status === 'fulfilled' ? patternsData.value : []);
    } catch (error) {
      console.error('Failed to load complaints:', error);
    } finally {
      setLoading(false);
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

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'resolved': return <CheckCircle2 className="w-4 h-4 text-green-600" />;
      case 'acknowledged': return <Clock className="w-4 h-4 text-blue-600" />;
      default: return <AlertTriangle className="w-4 h-4 text-orange-600" />;
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  return (
    <div>
      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Complaints</h2>
            <p className="text-gray-500 text-sm">{complaints.length} complaints in last 30 days</p>
          </div>
          {patterns.length > 0 && (
            <Button variant="outline">
              <TrendingUp className="w-4 h-4 mr-2" />
              Patterns ({patterns.length})
            </Button>
          )}
        </div>
        {/* Summary Cards */}
        {summary && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <Card className="p-6">
              <p className="text-sm text-gray-600">Total This Week</p>
              <p className="text-4xl font-bold text-gray-900 mt-1">
                {summary.total_complaints}
              </p>
            </Card>

            <Card className="p-6">
              <p className="text-sm text-gray-600">Critical/High</p>
              <p className="text-4xl font-bold text-red-600 mt-1">
                {summary.critical_count + summary.high_count}
              </p>
            </Card>

            <Card className="p-6">
              <p className="text-sm text-gray-600">Response Rate</p>
              <p className="text-4xl font-bold text-green-600 mt-1">
                {summary.response_rate}%
              </p>
            </Card>

            <Card className="p-6">
              <p className="text-sm text-gray-600">Active Patterns</p>
              <p className="text-4xl font-bold text-purple-600 mt-1">
                {summary.active_patterns}
              </p>
            </Card>
          </div>
        )}

        {/* Active Patterns Alert */}
        {patterns.length > 0 && (
          <Card className="mb-8 bg-purple-50 border-purple-200">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-purple-900">
                <TrendingUp className="w-5 h-5" />
                {patterns.length} Pattern(s) Detected
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {patterns.map((pattern: any) => (
                  <div
                    key={pattern.id}
                    className="p-4 bg-white rounded-lg border border-purple-200"
                  >
                    <div className="flex justify-between items-start mb-2">
                      <h4 className="font-semibold text-gray-900">
                        {pattern.description}
                      </h4>
                      <Badge className={getSeverityColor(pattern.severity)}>
                        {pattern.severity}
                      </Badge>
                    </div>

                    <p className="text-sm text-gray-600 mb-2">
                      {pattern.complaint_count} complaints share this pattern
                    </p>

                    {pattern.recommendation && (
                      <div className="mt-2 p-2 bg-purple-50 rounded">
                        <p className="text-sm text-purple-900">
                          Recommendation: {pattern.recommendation}
                        </p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Complaints List */}
        <Card>
          <CardHeader>
            <CardTitle>All Complaints</CardTitle>
          </CardHeader>
          <CardContent>
            {complaints.length === 0 ? (
              <div className="text-center py-12">
                <AlertTriangle className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">No complaints in the last 30 days</p>
              </div>
            ) : (
              <div className="space-y-3">
                {complaints.map((complaint: any) => (
                  <div
                    key={complaint.id}
                    onClick={() => router.push(`/complaints/${complaint.id}`)}
                    className="p-4 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          {getStatusIcon(complaint.status)}
                          <span className="font-medium text-gray-900 capitalize">
                            {complaint.status}
                          </span>
                          {complaint.category && (
                            <Badge variant="secondary">
                              {complaint.category.replace('_', ' ')}
                            </Badge>
                          )}
                          {complaint.severity && (
                            <Badge className={getSeverityColor(complaint.severity)}>
                              {complaint.severity}
                            </Badge>
                          )}
                        </div>

                        <p className="text-gray-700 mb-2">
                          {complaint.ai_summary || complaint.complaint_text.substring(0, 150)}
                          {!complaint.ai_summary && complaint.complaint_text.length > 150 && '...'}
                        </p>

                        <div className="flex items-center gap-4 text-sm text-gray-600">
                          <span>
                            {format(new Date(complaint.received_at), 'MMM d, h:mm a')}
                          </span>
                          {complaint.site_id && (
                            <span>Site {complaint.site_id}</span>
                          )}
                          <span className="capitalize">{complaint.source}</span>
                        </div>
                      </div>
                    </div>

                    {complaint.ai_suggested_action && (
                      <div className="mt-3 p-2 bg-blue-50 rounded">
                        <p className="text-sm text-blue-900">
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
    </div>
  );
}
