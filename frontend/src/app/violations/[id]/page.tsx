'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft, AlertTriangle, CheckCircle2, Clock,
  MessageSquare, Sparkles, Send, Upload, FileText,
  Download, Trash2, Loader2, Brain
} from 'lucide-react';
import { violationsAPI, attachmentsAPI } from '@/lib/api';
import { format } from 'date-fns';

export default function ViolationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [violation, setViolation] = useState<any>(null);
  const [draftResponse, setDraftResponse] = useState<string | null>(null);
  const [resolveNotes, setResolveNotes] = useState('');
  const [loading, setLoading] = useState(true);
  const [drafting, setDrafting] = useState(false);
  const [attachments, setAttachments] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const violationId = Number(params.id);

  useEffect(() => {
    if (params.id) {
      loadViolation(violationId);
      loadAttachments(violationId);
    }
  }, [params.id]);

  const loadViolation = async (id: number) => {
    try {
      const data = await violationsAPI.get(id);
      setViolation(data);
    } catch (error) {
      console.error('Failed to load violation:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadAttachments = useCallback(async (id: number) => {
    try {
      const data = await attachmentsAPI.list('violation', id);
      setAttachments(data);
    } catch (error) {
      // Attachments are optional — fail silently
    }
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files?.length) return;
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        await attachmentsAPI.upload('violation', violationId, file);
      }
      await loadAttachments(violationId);
    } catch (error) {
      console.error('Upload failed:', error);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDownload = async (att: any) => {
    try {
      const blob = await attachmentsAPI.download(att.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = att.original_filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Download failed:', error);
    }
  };

  const handleDeleteAttachment = async (attId: number) => {
    try {
      await attachmentsAPI.delete(attId);
      setAttachments((prev) => prev.filter((a) => a.id !== attId));
    } catch (error) {
      console.error('Delete failed:', error);
    }
  };

  const handleProcessAttachment = async (attId: number) => {
    setProcessing(attId);
    try {
      const result = await attachmentsAPI.process(attId, 'both');
      setAttachments((prev) =>
        prev.map((a) => (a.id === attId ? { ...a, ...result } : a))
      );
    } catch (error) {
      console.error('AI processing failed:', error);
    } finally {
      setProcessing(null);
    }
  };

  const handleAcknowledge = async () => {
    try {
      await violationsAPI.acknowledge(violation.id);
      await loadViolation(violation.id);
    } catch (error) {
      console.error('Failed to acknowledge:', error);
    }
  };

  const handleDraftResponse = async () => {
    setDrafting(true);
    try {
      const result = await violationsAPI.draftResponse(violation.id);
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
      await violationsAPI.resolve(violation.id, resolveNotes);
      await loadViolation(violation.id);
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

  if (!violation) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Card className="p-8 text-center max-w-md">
          <AlertTriangle className="w-12 h-12 text-orange-500 mx-auto mb-4" />
          <p className="text-gray-700 font-medium">Violation not found</p>
          <Button variant="outline" className="mt-4" onClick={() => router.push('/violations')}>
            Back to Violations
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <main className="max-w-7xl mx-auto px-4 py-8">
        <Button variant="ghost" className="mb-4" onClick={() => router.push('/violations')}>
          <ArrowLeft className="w-4 h-4 mr-2" /> Back to Violations
        </Button>

        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-3">
            {getStatusIcon(violation.status)}
            <div>
              <h2 className="text-2xl font-bold text-gray-900 capitalize">{violation.status}</h2>
              <p className="text-gray-500 text-sm">
                Received {format(new Date(violation.received_at), 'MMM d, yyyy h:mm a')}
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            {violation.category && (
              <Badge variant="secondary">{violation.category.replace('_', ' ')}</Badge>
            )}
            {violation.severity && (
              <Badge className={getSeverityColor(violation.severity)}>{violation.severity}</Badge>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Violation Text */}
            <Card>
              <CardHeader>
                <CardTitle>Violation</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-gray-700 whitespace-pre-wrap">{violation.violation_text}</p>
                <div className="flex items-center gap-4 mt-4 pt-4 border-t text-sm text-gray-500 flex-wrap">
                  <span className="capitalize">Source: {violation.source === 'whatsapp' ? 'WhatsApp' : violation.source}</span>
                  {violation.site_id && <span>Site ID: {violation.site_id}</span>}
                  {violation.employee_name && <span>From: {violation.employee_name}</span>}
                  {violation.is_anonymous && <Badge variant="secondary">Anonymous</Badge>}
                  {violation.fine_amount > 0 && (
                    <Badge className="bg-purple-100 text-purple-800">
                      Fine: {violation.fine_amount.toLocaleString()} NIS
                    </Badge>
                  )}
                  {violation.fine_rule_name && (
                    <span className="text-purple-600">Rule: {violation.fine_rule_name}</span>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Fine Documents */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="w-5 h-5" />
                    Documents
                  </CardTitle>
                  <div>
                    <input
                      ref={fileInputRef}
                      type="file"
                      className="hidden"
                      multiple
                      accept=".pdf,.jpg,.jpeg,.png,.gif,.xlsx,.xls,.docx,.doc,.csv,.txt"
                      onChange={handleFileUpload}
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={uploading}
                    >
                      {uploading ? (
                        <><Loader2 className="w-4 h-4 mr-1 animate-spin" /> Uploading...</>
                      ) : (
                        <><Upload className="w-4 h-4 mr-1" /> Upload</>
                      )}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {attachments.length === 0 ? (
                  <p className="text-sm text-gray-500 text-center py-4">
                    No documents attached. Upload fine letters, correspondence, or evidence.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {attachments.map((att) => (
                      <div key={att.id} className="flex items-start gap-3 p-3 border rounded-lg hover:bg-gray-50">
                        <FileText className="w-5 h-5 text-gray-400 mt-0.5 shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900 truncate">
                            {att.original_filename}
                          </p>
                          <p className="text-xs text-gray-500">
                            {att.file_size ? `${(att.file_size / 1024).toFixed(0)} KB` : ''}
                            {att.created_at && ` · ${format(new Date(att.created_at), 'MMM d, yyyy')}`}
                          </p>
                          {att.ai_summary && (
                            <div className="mt-2 p-2 bg-blue-50 rounded text-xs text-blue-800">
                              <p className="font-medium mb-1">AI Summary:</p>
                              <p className="whitespace-pre-wrap">{att.ai_summary}</p>
                            </div>
                          )}
                          {att.processing_status === 'processing' && (
                            <p className="text-xs text-blue-600 mt-1 flex items-center gap-1">
                              <Loader2 className="w-3 h-3 animate-spin" /> Processing...
                            </p>
                          )}
                        </div>
                        <div className="flex gap-1 shrink-0">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleProcessAttachment(att.id)}
                            disabled={processing === att.id}
                            title="AI Analyze"
                          >
                            {processing === att.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Brain className="w-4 h-4 text-blue-600" />
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDownload(att)}
                            title="Download"
                          >
                            <Download className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteAttachment(att.id)}
                            title="Delete"
                          >
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* AI Analysis */}
            {(violation.ai_summary || violation.ai_root_cause || violation.ai_suggested_action) && (
              <Card className="bg-blue-50 border-blue-200">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-blue-900">
                    <Sparkles className="w-5 h-5" />
                    AI Analysis
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {violation.ai_summary && (
                    <div>
                      <p className="text-sm font-medium text-blue-800 mb-1">Summary</p>
                      <p className="text-blue-900">{violation.ai_summary}</p>
                    </div>
                  )}
                  {violation.ai_root_cause && (
                    <div>
                      <p className="text-sm font-medium text-blue-800 mb-1">Root Cause</p>
                      <p className="text-blue-900">{violation.ai_root_cause}</p>
                    </div>
                  )}
                  {violation.ai_suggested_action && (
                    <div>
                      <p className="text-sm font-medium text-blue-800 mb-1">Suggested Action</p>
                      <p className="text-blue-900">{violation.ai_suggested_action}</p>
                    </div>
                  )}
                  {violation.sentiment_score != null && (
                    <div>
                      <p className="text-sm font-medium text-blue-800 mb-1">Sentiment Score</p>
                      <p className="text-blue-900">{violation.sentiment_score.toFixed(2)}</p>
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
                {violation.status === 'new' && (
                  <Button className="w-full" onClick={handleAcknowledge}>
                    <CheckCircle2 className="w-4 h-4 mr-2" />
                    Acknowledge
                  </Button>
                )}

                {violation.status !== 'resolved' && (
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

                {violation.status !== 'resolved' && (
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

                {violation.resolution_notes && (
                  <div className="pt-3 border-t">
                    <p className="text-sm font-medium text-gray-700 mb-1">Resolution Notes</p>
                    <p className="text-sm text-gray-600">{violation.resolution_notes}</p>
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
                        {format(new Date(violation.received_at), 'MMM d, h:mm a')}
                      </p>
                    </div>
                  </div>
                  {violation.acknowledged_at && (
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 bg-yellow-500 rounded-full" />
                      <div>
                        <p className="text-sm font-medium">Acknowledged</p>
                        <p className="text-xs text-gray-500">
                          {format(new Date(violation.acknowledged_at), 'MMM d, h:mm a')}
                        </p>
                      </div>
                    </div>
                  )}
                  {violation.resolved_at && (
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 bg-green-500 rounded-full" />
                      <div>
                        <p className="text-sm font-medium">Resolved</p>
                        <p className="text-xs text-gray-500">
                          {format(new Date(violation.resolved_at), 'MMM d, h:mm a')}
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
