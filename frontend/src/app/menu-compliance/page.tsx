'use client';

import { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  FileText, AlertTriangle, CheckCircle2, Upload, X, Plus, Pencil, BookOpen, Check
} from 'lucide-react';
import { menuComplianceAPI } from '@/lib/api';
import { format } from 'date-fns';

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

export default function MenuCompliancePage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [checks, setChecks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [rules, setRules] = useState<any[]>([]);
  const [showRules, setShowRules] = useState(false);
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [editingRuleId, setEditingRuleId] = useState<number | null>(null);
  const [ruleForm, setRuleForm] = useState({ name: '', rule_type: 'mandatory', description: '', category: '', priority: 1 });
  const [savingRule, setSavingRule] = useState(false);
  const [uploadForm, setUploadForm] = useState({
    siteId: 1,
    month: MONTHS[new Date().getMonth()],
    year: new Date().getFullYear(),
    file: null as File | null,
  });

  useEffect(() => {
    loadChecks();
    loadRules();
  }, []);

  const loadChecks = async () => {
    try {
      const data = await menuComplianceAPI.listChecks();
      setChecks(data);
    } catch (error) {
      console.error('Failed to load checks:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async () => {
    if (!uploadForm.file) return;
    setUploading(true);
    try {
      await menuComplianceAPI.uploadMenu(
        uploadForm.file,
        uploadForm.siteId,
        uploadForm.month,
        uploadForm.year
      );
      setShowUpload(false);
      setUploadForm({ ...uploadForm, file: null });
      await loadChecks();
    } catch (error) {
      console.error('Failed to upload menu:', error);
    } finally {
      setUploading(false);
    }
  };

  const loadRules = async () => {
    try {
      const data = await menuComplianceAPI.listRules();
      setRules(data);
    } catch (error) {
      console.error('Failed to load rules:', error);
    }
  };

  const handleRuleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingRule(true);
    try {
      if (editingRuleId) {
        await menuComplianceAPI.updateRule(editingRuleId, ruleForm);
      } else {
        await menuComplianceAPI.createRule(ruleForm);
      }
      setShowRuleForm(false);
      setEditingRuleId(null);
      setRuleForm({ name: '', rule_type: 'mandatory', description: '', category: '', priority: 1 });
      await loadRules();
    } catch (error) {
      console.error('Failed to save rule:', error);
    } finally {
      setSavingRule(false);
    }
  };

  const startEditRule = (r: any) => {
    setEditingRuleId(r.id);
    setRuleForm({
      name: r.name,
      rule_type: r.rule_type,
      description: r.description || '',
      category: r.category || '',
      priority: r.priority,
    });
    setShowRuleForm(true);
  };

  const handleDeleteRule = async (id: number) => {
    try {
      await menuComplianceAPI.deleteRule(id);
      await loadRules();
    } catch (error) {
      console.error('Failed to delete rule:', error);
    }
  };

  const groupedChecks: Record<string, any[]> = checks.reduce((acc: Record<string, any[]>, check: any) => {
    const key = `${check.year}-${check.month}`;
    if (!acc[key]) acc[key] = [];
    acc[key].push(check);
    return acc;
  }, {});

  const totalCritical = checks.reduce((sum: number, c: any) => sum + (c.critical_findings || 0), 0);
  const totalFindings = checks.reduce((sum: number, c: any) => sum + (c.total_findings || 0), 0);
  const totalPassed = checks.reduce((sum: number, c: any) => sum + (c.passed_rules || 0), 0);

  return (
    <div>
      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Menu Compliance</h2>
            <p className="text-gray-500 text-sm">
              {checks.length} checks across {Object.keys(groupedChecks).length} months
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowRules(!showRules)}>
              <BookOpen className="w-4 h-4 mr-2" />
              Rules ({rules.length})
            </Button>
            <Button onClick={() => setShowUpload(!showUpload)}>
              <Upload className="w-4 h-4 mr-2" />
              Upload Menu
            </Button>
          </div>
        </div>

        {/* Upload Menu Panel */}
        {showUpload && (
          <Card className="mb-6 border-blue-200 bg-blue-50">
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle className="text-blue-900">Upload Menu for Compliance Check</CardTitle>
                <Button variant="ghost" size="sm" onClick={() => setShowUpload(false)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Site</label>
                  <select
                    value={uploadForm.siteId}
                    onChange={(e) => setUploadForm({ ...uploadForm, siteId: parseInt(e.target.value) })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value={1}>Nes Ziona (NZ)</option>
                    <option value={2}>Kiryat Gat (KG)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Month</label>
                  <select
                    value={uploadForm.month}
                    onChange={(e) => setUploadForm({ ...uploadForm, month: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {MONTHS.map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Year</label>
                  <input
                    type="number"
                    value={uploadForm.year}
                    onChange={(e) => setUploadForm({ ...uploadForm, year: parseInt(e.target.value) })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Menu File</label>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.xlsx,.xls,.csv,.doc,.docx"
                    onChange={(e) => {
                      const file = e.target.files?.[0] || null;
                      setUploadForm({ ...uploadForm, file });
                    }}
                    className="w-full text-sm text-gray-600 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-blue-100 file:text-blue-700 hover:file:bg-blue-200"
                  />
                </div>
              </div>

              <div className="flex items-center gap-3">
                <Button
                  onClick={handleUpload}
                  disabled={!uploadForm.file || uploading}
                >
                  {uploading ? 'Uploading...' : 'Upload & Check'}
                </Button>
                {uploadForm.file && (
                  <span className="text-sm text-gray-600">
                    Selected: {uploadForm.file.name}
                  </span>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Compliance Rules Panel */}
        {showRules && (
          <Card className="mb-6">
            <CardHeader className="pb-3">
              <div className="flex justify-between items-center">
                <CardTitle className="text-lg">Compliance Rules</CardTitle>
                <div className="flex gap-2">
                  <button
                    onClick={() => { setShowRuleForm(true); setEditingRuleId(null); setRuleForm({ name: '', rule_type: 'mandatory', description: '', category: '', priority: 1 }); }}
                    className="flex items-center gap-1 text-sm bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700"
                  >
                    <Plus className="h-3 w-3" /> Add Rule
                  </button>
                  <button onClick={() => setShowRules(false)} className="p-1 text-gray-400 hover:text-gray-600">
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {showRuleForm && (
                <form onSubmit={handleRuleSubmit} className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4 p-3 bg-gray-50 rounded-lg">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Rule Name *</label>
                    <input
                      required
                      value={ruleForm.name}
                      onChange={e => setRuleForm({ ...ruleForm, name: e.target.value })}
                      className="w-full px-2 py-1.5 text-sm border rounded-md"
                      placeholder="e.g. Daily Vegan Option"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Type</label>
                    <select
                      value={ruleForm.rule_type}
                      onChange={e => setRuleForm({ ...ruleForm, rule_type: e.target.value })}
                      className="w-full px-2 py-1.5 text-sm border rounded-md"
                    >
                      <option value="mandatory">Mandatory</option>
                      <option value="frequency">Frequency</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Category</label>
                    <input
                      value={ruleForm.category}
                      onChange={e => setRuleForm({ ...ruleForm, category: e.target.value })}
                      className="w-full px-2 py-1.5 text-sm border rounded-md"
                      placeholder="e.g. Dietary, Menu Variety"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-xs font-medium text-gray-600 mb-1">Description</label>
                    <input
                      value={ruleForm.description}
                      onChange={e => setRuleForm({ ...ruleForm, description: e.target.value })}
                      className="w-full px-2 py-1.5 text-sm border rounded-md"
                      placeholder="Describe the rule..."
                    />
                  </div>
                  <div className="flex items-end gap-2">
                    <button type="submit" disabled={savingRule} className="flex items-center gap-1 text-sm bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 disabled:opacity-50">
                      <Check className="h-3 w-3" /> {savingRule ? 'Saving...' : 'Save'}
                    </button>
                    <button type="button" onClick={() => { setShowRuleForm(false); setEditingRuleId(null); }} className="text-sm text-gray-500 px-3 py-1.5 hover:text-gray-700">
                      Cancel
                    </button>
                  </div>
                </form>
              )}

              {rules.length === 0 ? (
                <p className="text-gray-500 text-sm py-4 text-center">No compliance rules defined yet. Add your first rule.</p>
              ) : (
                <div className="space-y-2">
                  {rules.map((r: any) => (
                    <div key={r.id} className={`flex items-center justify-between p-3 rounded-lg border ${r.is_active ? 'bg-white' : 'bg-gray-50 opacity-60'}`}>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm">{r.name}</span>
                          <Badge className="text-xs bg-blue-50 text-blue-700 border-blue-200">{r.rule_type}</Badge>
                          {r.category && <Badge className="text-xs bg-gray-100 text-gray-600">{r.category}</Badge>}
                        </div>
                        {r.description && <p className="text-xs text-gray-500 mt-0.5">{r.description}</p>}
                      </div>
                      <div className="flex gap-1">
                        <button onClick={() => startEditRule(r)} className="p-1.5 text-gray-400 hover:text-blue-600 rounded">
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        {r.is_active && (
                          <button onClick={() => handleDeleteRule(r.id)} className="p-1.5 text-gray-400 hover:text-red-600 rounded">
                            <X className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Summary Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Checks</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">{checks.length}</p>
              </div>
              <FileText className="w-8 h-8 text-blue-500" />
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Critical Findings</p>
                <p className="text-3xl font-bold text-red-600 mt-1">{totalCritical}</p>
              </div>
              <AlertTriangle className="w-8 h-8 text-red-500" />
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Findings</p>
                <p className="text-3xl font-bold text-orange-600 mt-1">{totalFindings}</p>
              </div>
              <AlertTriangle className="w-8 h-8 text-orange-500" />
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Passed Rules</p>
                <p className="text-3xl font-bold text-green-600 mt-1">{totalPassed}</p>
              </div>
              <CheckCircle2 className="w-8 h-8 text-green-500" />
            </div>
          </Card>
        </div>

        {/* Checks List */}
        {loading ? (
          <div className="text-center py-12">Loading checks...</div>
        ) : checks.length === 0 ? (
          <Card className="p-12 text-center">
            <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">No menu checks available yet.</p>
            <p className="text-sm text-gray-400 mt-1">
              Upload a menu file above to run a compliance check.
            </p>
          </Card>
        ) : (
          <div className="space-y-8">
            {Object.entries(groupedChecks).map(([period, periodChecks]) => (
              <div key={period}>
                <h3 className="text-xl font-semibold text-gray-900 mb-4">{period}</h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {periodChecks.map((check: any) => (
                    <Card
                      key={check.id}
                      className="p-6 hover:shadow-lg transition-shadow cursor-pointer"
                      onClick={() => router.push(`/menu-compliance/${check.id}`)}
                    >
                      <div className="flex justify-between items-start mb-4">
                        <div>
                          <h4 className="font-semibold text-lg text-gray-900">
                            {check.site_name || 'Unknown Site'}
                          </h4>
                          <p className="text-sm text-gray-600">
                            {check.month} {check.year}
                          </p>
                          {check.checked_at && (
                            <p className="text-xs text-gray-500 mt-1">
                              Checked: {format(new Date(check.checked_at), 'MMM d, yyyy')}
                            </p>
                          )}
                        </div>

                        {check.critical_findings > 0 ? (
                          <Badge variant="destructive">
                            {check.critical_findings} Critical
                          </Badge>
                        ) : check.total_findings > 0 ? (
                          <Badge className="bg-orange-100 text-orange-800">
                            {check.total_findings} Findings
                          </Badge>
                        ) : (
                          <Badge className="bg-green-100 text-green-800">
                            <CheckCircle2 className="w-3 h-3 mr-1" />
                            All Clear
                          </Badge>
                        )}
                      </div>

                      <div className="grid grid-cols-3 gap-4 text-center pt-4 border-t">
                        <div>
                          <p className="text-2xl font-bold text-red-600">
                            {check.critical_findings || 0}
                          </p>
                          <p className="text-xs text-gray-600">Critical</p>
                        </div>
                        <div>
                          <p className="text-2xl font-bold text-orange-600">
                            {check.warnings || 0}
                          </p>
                          <p className="text-xs text-gray-600">Warnings</p>
                        </div>
                        <div>
                          <p className="text-2xl font-bold text-green-600">
                            {check.passed_rules || 0}
                          </p>
                          <p className="text-xs text-gray-600">Passed</p>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
