'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft, AlertTriangle, CheckCircle2, Clock,
  MessageSquare, Sparkles, Send
} from 'lucide-react';
import { complaintsAPI } from '@/lib/api';
import { format } from 'date-fns';

export default function ComplaintDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [complaint, setComplaint] = useState<any>(null);
  const [draftResponse, setDraftResponse] = useState<string | null>(null);
  const [resolveNotes, setResolveNotes] = useState('');
  const [loading, setLoading] = useState(true);
  const [drafting, setDrafting] = useState(false);

  useEffect(() => {
    if (params.id) {
      loadComplaint(Number(params.id));
    }
  }, [params.id]);

  const loadComplaint = async (id: number) => {
    try {
      const data = await complaintsAPI.get(id);
      setComplaint(data);
    } catch (error) {
      console.error('Failed to load complaint:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAcknowledge = async () => {
    try {
      await complaintsAPI.acknowledge(complaint.id);
      await loadComplaint(complaint.id);
    } catch (error) {
      console.error('Failed to acknowledge:', error);
    }
  };

  const handleDraftResponse = async () => {
    setDrafting(true);
    try {
      const result = await complaintsAPI.draftResponse(complaint.id);
      setDraftResponse(result.draft);
    } catch (error) {
      console.error('Failed to draft response:', error);
    } finally {
      setDrafting(false);
    }
  };

  const handleResolve = async () => {
    if (!resolveNotes.trim()) return;
    try {
      await complaintsAPI.resolve(complaint.id, resolveNotes);
      await loadComplaint(complaint.id);
      setResolveNotes('');
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

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'resolved': return <CheckCircle2 className="w-5 h-5 text-green-600" />;
      case 'acknowledged': return <Clock className="w-5 h-5 text-blue-600" />;
      default: return <AlertTriangle className="w-5 h-5 text-orange-600" />;
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  if (!complaint) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Card className="p-8 text-center max-w-md">
          <AlertTriangle className="w-12 h-12 text-orange-500 mx-auto mb-4" />
          <p className="text-gray-700 font-medium">Complaint not found</p>
          <Button variant="outline" className="mt-4" onClick={() => router.push('/complaints')}>
            Back to Complaints
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <main className="max-w-7xl mx-auto px-4 py-8">
        <Button variant="ghost" className="mb-4" onClick={() => router.push('/complaints')}>
          <ArrowLeft className="w-4 h-4 mr-2" /> Back to Complaints
        </Button>

        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-3">
            {getStatusIcon(complaint.status)}
            <div>
              <h2 className="text-2xl font-bold text-gray-900 capitalize">{complaint.status}</h2>
              <p className="text-gray-500 text-sm">
                Received {format(new Date(complaint.received_at), 'MMM d, yyyy h:mm a')}
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            {complaint.category && (
              <Badge variant="secondary">{complaint.category.replace('_', ' ')}</Badge>
            )}
            {complaint.severity && (
              <Badge className={getSeverityColor(complaint.severity)}>{complaint.severity}</Badge>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Complaint Text */}
            <Card>
              <CardHeader>
                <CardTitle>Complaint</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-gray-700 whitespace-pre-wrap">{complaint.complaint_text}</p>
                <div className="flex items-center gap-4 mt-4 pt-4 border-t text-sm text-gray-500 flex-wrap">
                  <span className="capitalize">Source: {complaint.source === 'whatsapp' ? 'WhatsApp' : complaint.source}</span>
                  {complaint.site_id && <span>Site ID: {complaint.site_id}</span>}
                  {complaint.employee_name && <span>From: {complaint.employee_name}</span>}
                  {complaint.is_anonymous && <Badge variant="secondary">Anonymous</Badge>}
                  {complaint.fine_amount > 0 && (
                    <Badge className="bg-purple-100 text-purple-800">
                      Fine: {complaint.fine_amount.toLocaleString()} NIS
                    </Badge>
                  )}
                  {complaint.fine_rule_name && (
                    <span className="text-purple-600">Rule: {complaint.fine_rule_name}</span>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* AI Analysis */}
            {(complaint.ai_summary || complaint.ai_root_cause || complaint.ai_suggested_action) && (
              <Card className="bg-blue-50 border-blue-200">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-blue-900">
                    <Sparkles className="w-5 h-5" />
                    AI Analysis
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {complaint.ai_summary && (
                    <div>
                      <p className="text-sm font-medium text-blue-800 mb-1">Summary</p>
                      <p className="text-blue-900">{complaint.ai_summary}</p>
                    </div>
                  )}
                  {complaint.ai_root_cause && (
                    <div>
                      <p className="text-sm font-medium text-blue-800 mb-1">Root Cause</p>
                      <p className="text-blue-900">{complaint.ai_root_cause}</p>
                    </div>
                  )}
                  {complaint.ai_suggested_action && (
                    <div>
                      <p className="text-sm font-medium text-blue-800 mb-1">Suggested Action</p>
                      <p className="text-blue-900">{complaint.ai_suggested_action}</p>
                    </div>
                  )}
                  {complaint.sentiment_score != null && (
                    <div>
                      <p className="text-sm font-medium text-blue-800 mb-1">Sentiment Score</p>
                      <p className="text-blue-900">{complaint.sentiment_score.toFixed(2)}</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* AI Draft Response */}
            {draftResponse && (
              <Card className="bg-green-50 border-green-200">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-green-900">
                    <MessageSquare className="w-5 h-5" />
                    AI Draft Response
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-green-900 whitespace-pre-wrap">{draftResponse}</p>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Sidebar Actions */}
          <div className="space-y-6">
            {/* Actions */}
            <Card>
              <CardHeader>
                <CardTitle>Actions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {complaint.status === 'new' && (
                  <Button className="w-full" onClick={handleAcknowledge}>
                    <CheckCircle2 className="w-4 h-4 mr-2" />
                    Acknowledge
                  </Button>
                )}

                {complaint.status !== 'resolved' && (
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={handleDraftResponse}
                    disabled={drafting}
                  >
                    <Sparkles className="w-4 h-4 mr-2" />
                    {drafting ? 'Generating...' : 'Draft AI Response'}
                  </Button>
                )}

                {complaint.status !== 'resolved' && (
                  <div className="pt-3 border-t">
                    <p className="text-sm font-medium text-gray-700 mb-2">Resolve</p>
                    <textarea
                      className="w-full p-2 border rounded-md text-sm"
                      rows={3}
                      placeholder="Resolution notes..."
                      value={resolveNotes}
                      onChange={(e) => setResolveNotes(e.target.value)}
                    />
                    <Button
                      className="w-full mt-2"
                      variant="outline"
                      onClick={handleResolve}
                      disabled={!resolveNotes.trim()}
                    >
                      <Send className="w-4 h-4 mr-2" />
                      Resolve
                    </Button>
                  </div>
                )}

                {complaint.resolution_notes && (
                  <div className="pt-3 border-t">
                    <p className="text-sm font-medium text-gray-700 mb-1">Resolution Notes</p>
                    <p className="text-sm text-gray-600">{complaint.resolution_notes}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Timeline */}
            <Card>
              <CardHeader>
                <CardTitle>Timeline</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 bg-blue-500 rounded-full" />
                    <div>
                      <p className="text-sm font-medium">Received</p>
                      <p className="text-xs text-gray-500">
                        {format(new Date(complaint.received_at), 'MMM d, h:mm a')}
                      </p>
                    </div>
                  </div>
                  {complaint.acknowledged_at && (
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 bg-yellow-500 rounded-full" />
                      <div>
                        <p className="text-sm font-medium">Acknowledged</p>
                        <p className="text-xs text-gray-500">
                          {format(new Date(complaint.acknowledged_at), 'MMM d, h:mm a')}
                        </p>
                      </div>
                    </div>
                  )}
                  {complaint.resolved_at && (
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 bg-green-500 rounded-full" />
                      <div>
                        <p className="text-sm font-medium">Resolved</p>
                        <p className="text-xs text-gray-500">
                          {format(new Date(complaint.resolved_at), 'MMM d, h:mm a')}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
