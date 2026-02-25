'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DollarSign, FolderKanban, Wrench, CalendarDays,
  ListTodo, ArrowRight, MessageSquare, Send,
  AlertCircle, CheckCircle2, Clock,
  ChevronRight
} from 'lucide-react';
import { dashboardAPI, chatAPI } from '@/lib/api';
import { format } from 'date-fns';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer
} from 'recharts';

export default function Dashboard() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);
  const [chatInput, setChatInput] = useState('');
  const [chatResponse, setChatResponse] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const result = await dashboardAPI.get();
      setData(result);
    } catch (error) {
      // Sections will show empty states
    } finally {
      setLoading(false);
    }
  };

  const handleChat = async () => {
    if (!chatInput.trim()) return;
    setChatLoading(true);
    try {
      const result = await chatAPI.send(chatInput);
      setChatResponse(result.response);
      setChatInput('');
    } catch {
      setChatResponse('Sorry, could not process your request.');
    } finally {
      setChatLoading(false);
    }
  };

  const quickChat = async (prompt: string) => {
    setChatInput(prompt);
    setChatLoading(true);
    try {
      const result = await chatAPI.send(prompt);
      setChatResponse(result.response);
    } catch {
      setChatResponse('Sorry, could not process your request.');
    } finally {
      setChatLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4" />
          <p className="text-gray-500">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  const budgetSummary = data?.budget_summary || [];
  const projects = data?.projects || [];
  const maintenance = data?.maintenance || [];
  const meetings = data?.meetings || [];
  const todos = data?.todos || { mine: [], delegated: [], overdue_count: 0 };

  const chartData = budgetSummary.map((b: any) => ({
    name: `${b.supplier_name} (${b.site_name})`,
    budget: b.monthly_budget,
    actual: b.monthly_actual,
  }));

  const formatCurrency = (val: number) =>
    val.toLocaleString('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 });

  const getPriorityColor = (p: string) => {
    const colors: Record<string, string> = {
      urgent: 'bg-red-100 text-red-800',
      high: 'bg-orange-100 text-orange-800',
      medium: 'bg-blue-100 text-blue-800',
      low: 'bg-gray-100 text-gray-700',
    };
    return colors[p] || colors.medium;
  };

  const getStatusColor = (s: string) => {
    const colors: Record<string, string> = {
      planning: 'bg-purple-100 text-purple-800',
      active: 'bg-green-100 text-green-800',
      on_hold: 'bg-yellow-100 text-yellow-800',
      completed: 'bg-blue-100 text-blue-800',
    };
    return colors[s] || 'bg-gray-100 text-gray-700';
  };

  return (
    <main className="max-w-7xl mx-auto px-4 py-6">
      {/* ═══════ ROW 1: Budget vs Actual ═══════ */}
      <Card
        className="mb-6 hover:shadow-lg transition-shadow cursor-pointer border-l-4 border-l-blue-500"
        onClick={() => router.push('/budget')}
      >
        <CardHeader className="pb-2">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-50 rounded-lg">
                <DollarSign className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <CardTitle className="text-lg">Budget vs Actual</CardTitle>
                <p className="text-sm text-gray-500">Current month supplier spending</p>
              </div>
            </div>
            <Button variant="ghost" size="sm">
              View Details <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {budgetSummary.length === 0 ? (
            <p className="text-gray-400 text-center py-6">
              No budgets configured yet. Click to set up supplier budgets.
            </p>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="space-y-3">
                {budgetSummary.map((b: any, i: number) => (
                  <div key={i} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex-1">
                      <p className="font-medium text-sm">{b.supplier_name}</p>
                      <p className="text-xs text-gray-500">{b.site_name}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-semibold">
                        {formatCurrency(b.monthly_actual)} / {formatCurrency(b.monthly_budget)}
                      </p>
                      <div className="w-32 h-2 bg-gray-200 rounded-full mt-1">
                        <div
                          className={`h-2 rounded-full ${
                            b.monthly_percent > 90 ? 'bg-red-500' :
                            b.monthly_percent > 70 ? 'bg-yellow-500' : 'bg-green-500'
                          }`}
                          style={{ width: `${Math.min(b.monthly_percent, 100)}%` }}
                        />
                      </div>
                      <p className="text-xs text-gray-500 mt-0.5">{b.monthly_percent}%</p>
                    </div>
                  </div>
                ))}
              </div>

              {chartData.length > 0 && (
                <div className="h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData}>
                      <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip formatter={(val: number) => formatCurrency(val)} />
                      <Bar dataKey="budget" fill="#93c5fd" name="Budget" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="actual" fill="#3b82f6" name="Actual" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ═══════ ROW 2: Projects + Maintenance ═══════ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <Card
          className="hover:shadow-lg transition-shadow cursor-pointer border-l-4 border-l-purple-500"
          onClick={() => router.push('/projects')}
        >
          <CardHeader className="pb-2">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-50 rounded-lg">
                  <FolderKanban className="w-5 h-5 text-purple-600" />
                </div>
                <div>
                  <CardTitle className="text-lg">Active Projects</CardTitle>
                  <p className="text-sm text-gray-500">{projects.length} ongoing</p>
                </div>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-400" />
            </div>
          </CardHeader>
          <CardContent>
            {projects.length === 0 ? (
              <p className="text-gray-400 text-center py-6">No active projects. Click to create one.</p>
            ) : (
              <div className="space-y-3">
                {projects.map((p: any) => (
                  <div key={p.id} className="p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium text-sm">{p.name}</span>
                      <Badge className={getStatusColor(p.status)}>{p.status}</Badge>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="flex-1 h-2 bg-gray-200 rounded-full">
                        <div
                          className="h-2 bg-purple-500 rounded-full transition-all"
                          style={{ width: `${p.progress}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500 whitespace-nowrap">
                        {p.done_count}/{p.task_count} tasks
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card
          className="hover:shadow-lg transition-shadow cursor-pointer border-l-4 border-l-amber-500"
          onClick={() => router.push('/maintenance')}
        >
          <CardHeader className="pb-2">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-amber-50 rounded-lg">
                  <Wrench className="w-5 h-5 text-amber-600" />
                </div>
                <div>
                  <CardTitle className="text-lg">Maintenance Budget</CardTitle>
                  <p className="text-sm text-gray-500">Q{data?.current_quarter} {data?.current_year}</p>
                </div>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-400" />
            </div>
          </CardHeader>
          <CardContent>
            {maintenance.length === 0 ? (
              <p className="text-gray-400 text-center py-6">No quarterly budgets set. Click to configure.</p>
            ) : (
              <div className="space-y-3">
                {maintenance.map((m: any, i: number) => (
                  <div key={i} className="p-3 bg-gray-50 rounded-lg">
                    <div className="flex justify-between items-center mb-2">
                      <span className="font-medium text-sm">{m.site_name}</span>
                      <span className="text-sm">{formatCurrency(m.actual)} / {formatCurrency(m.budget)}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="flex-1 h-3 bg-gray-200 rounded-full">
                        <div
                          className={`h-3 rounded-full transition-all ${
                            m.percent_used > 90 ? 'bg-red-500' :
                            m.percent_used > 70 ? 'bg-amber-500' : 'bg-green-500'
                          }`}
                          style={{ width: `${Math.min(m.percent_used, 100)}%` }}
                        />
                      </div>
                      <span className="text-sm font-medium w-12 text-right">{m.percent_used}%</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">Remaining: {formatCurrency(m.remaining)}</p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ═══════ ROW 3: Meetings + Todos ═══════ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <Card
          className="hover:shadow-lg transition-shadow cursor-pointer border-l-4 border-l-sky-500"
          onClick={() => router.push('/meetings')}
        >
          <CardHeader className="pb-2">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-sky-50 rounded-lg">
                  <CalendarDays className="w-5 h-5 text-sky-600" />
                </div>
                <div>
                  <CardTitle className="text-lg">Upcoming Meetings</CardTitle>
                  <p className="text-sm text-gray-500">{meetings.length} scheduled</p>
                </div>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-400" />
            </div>
          </CardHeader>
          <CardContent>
            {meetings.length === 0 ? (
              <p className="text-gray-400 text-center py-6">No upcoming meetings</p>
            ) : (
              <div className="space-y-2">
                {meetings.slice(0, 5).map((m: any) => (
                  <div key={m.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <CalendarDays className="w-4 h-4 text-sky-500" />
                      <div>
                        <p className="font-medium text-sm">{m.title}</p>
                        <p className="text-xs text-gray-500">
                          {m.scheduled_at ? format(new Date(m.scheduled_at), 'EEE, MMM d · h:mm a') : 'TBD'}
                        </p>
                      </div>
                    </div>
                    {m.has_brief ? (
                      <Badge className="bg-green-100 text-green-800">
                        <CheckCircle2 className="w-3 h-3 mr-1" /> Brief
                      </Badge>
                    ) : (
                      <Badge variant="outline"><Clock className="w-3 h-3 mr-1" /> Pending</Badge>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card
          className="hover:shadow-lg transition-shadow cursor-pointer border-l-4 border-l-emerald-500"
          onClick={() => router.push('/todos')}
        >
          <CardHeader className="pb-2">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-emerald-50 rounded-lg">
                  <ListTodo className="w-5 h-5 text-emerald-600" />
                </div>
                <div>
                  <CardTitle className="text-lg">Tasks & Follow-ups</CardTitle>
                  <p className="text-sm text-gray-500">
                    {todos.mine.length + todos.delegated.length} open
                    {todos.overdue_count > 0 && (
                      <span className="text-red-600 ml-2">· {todos.overdue_count} overdue</span>
                    )}
                  </p>
                </div>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-400" />
            </div>
          </CardHeader>
          <CardContent>
            {todos.mine.length === 0 && todos.delegated.length === 0 ? (
              <p className="text-gray-400 text-center py-6">No open tasks. Click to add one.</p>
            ) : (
              <div className="space-y-4">
                {todos.mine.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase mb-2">My Tasks ({todos.mine.length})</p>
                    <div className="space-y-1.5">
                      {todos.mine.slice(0, 3).map((t: any) => (
                        <div key={t.id} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                          <div className="flex items-center gap-2">
                            {t.is_overdue && <AlertCircle className="w-3.5 h-3.5 text-red-500" />}
                            <span className={`text-sm ${t.is_overdue ? 'text-red-700' : ''}`}>{t.title}</span>
                          </div>
                          <Badge className={`text-xs ${getPriorityColor(t.priority)}`}>{t.priority}</Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {todos.delegated.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase mb-2">
                      Delegated ({todos.delegated.length})
                    </p>
                    <div className="space-y-1.5">
                      {todos.delegated.slice(0, 3).map((t: any) => (
                        <div key={t.id} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                          <div className="flex items-center gap-2">
                            {t.is_overdue && <AlertCircle className="w-3.5 h-3.5 text-red-500" />}
                            <span className={`text-sm ${t.is_overdue ? 'text-red-700' : ''}`}>
                              <span className="font-medium">{t.assigned_to}:</span> {t.title}
                            </span>
                          </div>
                          <Badge className={`text-xs ${getPriorityColor(t.priority)}`}>{t.priority}</Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ═══════ ROW 4: AI Chat ═══════ */}
      <Card className="border-l-4 border-l-indigo-500">
        <CardHeader className="pb-2">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-50 rounded-lg">
              <MessageSquare className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <CardTitle className="text-lg">AI Assistant</CardTitle>
              <p className="text-sm text-gray-500">Ask anything about your operations</p>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {chatResponse && (
            <div className="mb-4 p-4 bg-indigo-50 rounded-lg text-sm text-gray-800 whitespace-pre-wrap">
              {chatResponse}
            </div>
          )}

          <div className="flex gap-2">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleChat()}
              placeholder="Ask about budget, complaints, meetings..."
              className="flex-1 px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
              disabled={chatLoading}
            />
            <Button
              onClick={handleChat}
              disabled={chatLoading || !chatInput.trim()}
              className="bg-indigo-600 hover:bg-indigo-700"
            >
              {chatLoading ? (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>

          <div className="flex gap-2 mt-3 flex-wrap">
            {['Budget status this month', 'Upcoming meetings summary', 'Recent complaints'].map((q) => (
              <button
                key={q}
                onClick={() => quickChat(q)}
                className="text-xs px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-full text-gray-600 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
