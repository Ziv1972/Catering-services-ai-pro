'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  Paperclip, Upload, Download, X, FileText, Sparkles,
  File as FileIcon, Image as ImageIcon, Loader2, ChevronDown, ChevronUp,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { attachmentsAPI } from '@/lib/api';

// ─── Types ───

interface AttachmentData {
  id: number;
  entity_type: string;
  entity_id: number;
  filename: string;
  original_filename: string;
  file_size: number | null;
  content_type: string | null;
  ai_summary: string | null;
  ai_extracted_data: string | null;
  processing_status: string | null;
  created_at: string | null;
}

interface AttachmentSectionProps {
  entityType: string;
  entityId: number;
  title?: string;
  compact?: boolean;
}

// ─── Helpers ───

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileIcon(contentType?: string | null) {
  if (contentType?.startsWith('image/')) return <ImageIcon className="w-4 h-4 text-blue-500" />;
  if (contentType?.includes('pdf')) return <FileText className="w-4 h-4 text-red-500" />;
  if (contentType?.includes('spreadsheet') || contentType?.includes('excel'))
    return <FileText className="w-4 h-4 text-green-500" />;
  return <FileIcon className="w-4 h-4 text-gray-500" />;
}

function canProcess(filename: string): boolean {
  const ext = filename.toLowerCase().split('.').pop() || '';
  return ['txt', 'csv', 'json', 'md', 'pdf', 'xlsx', 'xls', 'xml', 'html', 'log'].includes(ext);
}

// ─── Main Component ───

export default function AttachmentSection({
  entityType,
  entityId,
  title = 'Attachments',
  compact = false,
}: AttachmentSectionProps) {
  const [attachments, setAttachments] = useState<AttachmentData[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [processingId, setProcessingId] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const loadAttachments = useCallback(async () => {
    if (!entityId) return;
    try {
      const data = await attachmentsAPI.list(entityType, entityId);
      setAttachments(data);
    } catch {
      // silent — empty list
    } finally {
      setLoading(false);
    }
  }, [entityType, entityId]);

  useEffect(() => {
    loadAttachments();
  }, [loadAttachments]);

  const handleUpload = async (files: File[]) => {
    setUploading(true);
    try {
      for (const file of files) {
        await attachmentsAPI.upload(entityType, entityId, file);
      }
      await loadAttachments();
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('Upload failed:', err);
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) handleUpload(files);
  }, [entityType, entityId]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) handleUpload(files);
    if (inputRef.current) inputRef.current.value = '';
  }, [entityType, entityId]);

  const handleDownload = async (att: AttachmentData) => {
    try {
      const response = await attachmentsAPI.download(att.id);
      const blob = new Blob([response.data]);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = att.original_filename;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      // silent
    }
  };

  const handleDelete = async (attId: number) => {
    try {
      await attachmentsAPI.delete(attId);
      setAttachments((prev) => prev.filter((a) => a.id !== attId));
    } catch {
      // silent
    }
  };

  const handleProcess = async (attId: number, mode: 'summarize' | 'extract' | 'both') => {
    setProcessingId(attId);
    try {
      const updated = await attachmentsAPI.process(attId, mode);
      setAttachments((prev) =>
        prev.map((a) => (a.id === attId ? { ...a, ...updated } : a))
      );
      setExpandedId(attId);
    } catch {
      // silent
    } finally {
      setProcessingId(null);
    }
  };

  // ─── Render ───

  if (loading) return null;

  return (
    <div className="space-y-3">
      {/* Title row */}
      <div className="flex items-center gap-2">
        <Paperclip className="w-4 h-4 text-gray-500" />
        <span className="text-sm font-semibold text-gray-700">{title}</span>
        {attachments.length > 0 && (
          <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded-full">
            {attachments.length}
          </span>
        )}
      </div>

      {/* Attachment list */}
      {attachments.length > 0 && (
        <div className="space-y-2">
          {attachments.map((att) => {
            const isExpanded = expandedId === att.id;
            const isProcessing = processingId === att.id;
            const hasAI = att.ai_summary || att.ai_extracted_data;
            const processable = canProcess(att.original_filename);

            return (
              <div key={att.id} className="border rounded-lg bg-white">
                {/* File row */}
                <div className="flex items-center gap-2 px-3 py-2 group">
                  {getFileIcon(att.content_type)}
                  <span className="text-sm text-gray-700 flex-1 truncate">
                    {att.original_filename}
                  </span>
                  {att.file_size && (
                    <span className="text-xs text-gray-400">{formatFileSize(att.file_size)}</span>
                  )}
                  {hasAI && (
                    <button
                      onClick={() => setExpandedId(isExpanded ? null : att.id)}
                      className="text-purple-500 hover:text-purple-700"
                      title="Show AI results"
                    >
                      {isExpanded ? (
                        <ChevronUp className="w-3.5 h-3.5" />
                      ) : (
                        <ChevronDown className="w-3.5 h-3.5" />
                      )}
                    </button>
                  )}
                  {/* AI process button */}
                  {processable && !hasAI && (
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => handleProcess(att.id, 'summarize')}
                        disabled={isProcessing}
                        className="text-xs px-2 py-0.5 rounded bg-purple-50 text-purple-600 hover:bg-purple-100 disabled:opacity-50"
                        title="AI Summarize"
                      >
                        {isProcessing ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Summarize'}
                      </button>
                      <button
                        onClick={() => handleProcess(att.id, 'extract')}
                        disabled={isProcessing}
                        className="text-xs px-2 py-0.5 rounded bg-blue-50 text-blue-600 hover:bg-blue-100 disabled:opacity-50"
                        title="AI Extract"
                      >
                        Extract
                      </button>
                      <button
                        onClick={() => handleProcess(att.id, 'both')}
                        disabled={isProcessing}
                        className="text-xs px-2 py-0.5 rounded bg-green-50 text-green-600 hover:bg-green-100 disabled:opacity-50"
                        title="Summarize + Extract"
                      >
                        Both
                      </button>
                    </div>
                  )}
                  {/* Processing status */}
                  {isProcessing && (
                    <div className="flex items-center gap-1 text-xs text-purple-500">
                      <Loader2 className="w-3 h-3 animate-spin" />
                      <span>Processing...</span>
                    </div>
                  )}
                  <button
                    onClick={() => handleDownload(att)}
                    className="text-gray-400 hover:text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Download"
                  >
                    <Download className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => handleDelete(att.id)}
                    className="text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Delete"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* AI results (expanded) */}
                {isExpanded && hasAI && (
                  <div className="border-t px-3 py-3 bg-purple-50/50 space-y-3">
                    {att.ai_summary && (
                      <div>
                        <div className="flex items-center gap-1 mb-1">
                          <Sparkles className="w-3 h-3 text-purple-500" />
                          <span className="text-xs font-semibold text-purple-700">AI Summary</span>
                        </div>
                        <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                          {att.ai_summary}
                        </p>
                      </div>
                    )}
                    {att.ai_extracted_data && (
                      <div>
                        <div className="flex items-center gap-1 mb-1">
                          <Sparkles className="w-3 h-3 text-blue-500" />
                          <span className="text-xs font-semibold text-blue-700">Extracted Data</span>
                        </div>
                        <pre className="text-xs text-gray-600 bg-white rounded p-2 overflow-x-auto max-h-48 border">
                          {(() => {
                            try {
                              return JSON.stringify(JSON.parse(att.ai_extracted_data), null, 2);
                            } catch {
                              return att.ai_extracted_data;
                            }
                          })()}
                        </pre>
                      </div>
                    )}
                    {/* Re-process buttons */}
                    <div className="flex gap-2 pt-1">
                      <button
                        onClick={() => handleProcess(att.id, 'summarize')}
                        disabled={isProcessing}
                        className="text-xs px-2 py-1 rounded border text-purple-600 hover:bg-purple-50 disabled:opacity-50"
                      >
                        Re-summarize
                      </button>
                      <button
                        onClick={() => handleProcess(att.id, 'extract')}
                        disabled={isProcessing}
                        className="text-xs px-2 py-1 rounded border text-blue-600 hover:bg-blue-50 disabled:opacity-50"
                      >
                        Re-extract
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Drop zone */}
      <div
        className={`flex ${compact ? 'items-center gap-2 px-3 py-2' : 'flex-col items-center justify-center p-5'}
          border-2 border-dashed rounded-lg cursor-pointer transition-colors
          ${dragOver ? 'border-purple-400 bg-purple-50' : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          onChange={handleFileInput}
        />
        {uploading ? (
          <div className="flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-purple-500" />
            <span className="text-sm text-gray-500">Uploading...</span>
          </div>
        ) : compact ? (
          <>
            <Paperclip className="w-3.5 h-3.5 text-gray-400" />
            <span className="text-xs text-gray-500">Drop files or click to upload</span>
          </>
        ) : (
          <>
            <Upload className="w-6 h-6 text-gray-400 mb-1" />
            <p className="text-sm text-gray-600">Drop files here or click to browse</p>
            <p className="text-xs text-gray-400 mt-0.5">
              AI can summarize & extract data from text, PDF, Excel files
            </p>
          </>
        )}
      </div>
    </div>
  );
}
