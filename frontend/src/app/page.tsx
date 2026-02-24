'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  CalendarDays, AlertTriangle, FileText, TrendingUp,
  CheckCircle2, Clock, ArrowRight
} from 'lucide-react';
import { meetingsAPI, complaintsAPI } from '@/lib/api';
import { format } from 'date-fns';

interface DashboardData {
  meetings: any[];
  complaintSummary: any;
  stats: {
    pendingMeetings: number;
    activeComplaints: number;
    criticalFindings: number;
    pendingProformas: number;
  };
}

export default function Dashboard() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<DashboardData>({
    meetings: [],
    complaintSummary: null,
    stats: {
      pendingMeetings: 0,
      activeComplaints: 0,
      criticalFindings: 0,
      pendingProformas: 0,
    },
  });

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      const [meetings, complaintSummary] = await Promise.allSettled([
        meetingsAPI.list(true),
        complaintsAPI.getWeeklySummary(),
      ]);

      const meetingsData = meetings.status === 'fulfilled' ? meetings.value : [];
      const summaryData = complaintSummary.status === 'fulfilled' ? complaintSummary.value : null;

      setData({
        meetings: meetingsData.slice(0, 5),
        complaintSummary: summaryData,
        stats: {
          pendingMeetings: meetingsData.length,
          activeComplaints: summaryData?.total_complaints ?? 0,
          criticalFindings: 0,
          pendingProformas: 0,
        },
      });
    } catch (error) {
      console.error('Failed to load dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  const greeting = new Date().getHours() < 12 ? 'morning' : 'afternoon';

  return (
    <div>
      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <Card
            className="hover:shadow-md transition-shadow cursor-pointer"
            onClick={() => router.push('/meetings')}
          >
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Upcoming Meetings</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {data.stats.pendingMeetings}
                  </p>
                </div>
                <CalendarDays className="w-8 h-8 text-blue-500" />
              </div>
            </CardContent>
          </Card>

          <Card
            className="hover:shadow-md transition-shadow cursor-pointer"
            onClick={() => router.push('/complaints')}
          >
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Active Complaints</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {data.stats.activeComplaints}
                  </p>
                  {data.complaintSummary?.critical_count > 0 && (
                    <p className="text-xs text-red-600 mt-1">
                      {data.complaintSummary.critical_count} critical
                    </p>
                  )}
                </div>
                <AlertTriangle className="w-8 h-8 text-orange-500" />
              </div>
            </CardContent>
          </Card>

          <Card
            className="hover:shadow-md transition-shadow cursor-pointer"
            onClick={() => router.push('/menu-compliance')}
          >
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Menu Findings</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {data.stats.criticalFindings}
                  </p>
                  <p className="text-xs text-gray-600 mt-1">Last 3 checks</p>
                </div>
                <FileText className="w-8 h-8 text-purple-500" />
              </div>
            </CardContent>
          </Card>

          <Card
            className="hover:shadow-md transition-shadow cursor-pointer"
            onClick={() => router.push('/analytics')}
          >
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Data Records</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">1,132</p>
                  <p className="text-xs text-green-600 mt-1">All migrated</p>
                </div>
                <TrendingUp className="w-8 h-8 text-green-500" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Upcoming Meetings */}
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Upcoming Meetings</CardTitle>
                <Button variant="ghost" size="sm" onClick={() => router.push('/meetings')}>
                  View All
                  <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {data.meetings.length === 0 ? (
                <p className="text-gray-500 text-center py-8">No upcoming meetings</p>
              ) : (
                <div className="space-y-3">
                  {data.meetings.map((meeting: any) => (
                    <div
                      key={meeting.id}
                      className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 cursor-pointer transition-colors"
                      onClick={() => router.push(`/meetings/${meeting.id}`)}
                    >
                      <div className="flex-1">
                        <p className="font-medium text-gray-900">{meeting.title}</p>
                        <p className="text-sm text-gray-600">
                          {format(new Date(meeting.scheduled_at), 'MMM d, h:mm a')}
                        </p>
                      </div>
                      {meeting.ai_brief ? (
                        <Badge className="bg-green-100 text-green-800">
                          <CheckCircle2 className="w-3 h-3 mr-1" />
                          Brief Ready
                        </Badge>
                      ) : (
                        <Badge variant="outline">
                          <Clock className="w-3 h-3 mr-1" />
                          Pending
                        </Badge>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Complaint Summary */}
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Complaints This Week</CardTitle>
                <Button variant="ghost" size="sm" onClick={() => router.push('/complaints')}>
                  View All
                  <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {data.complaintSummary ? (
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Total</span>
                    <span className="text-2xl font-bold">
                      {data.complaintSummary.total_complaints}
                    </span>
                  </div>

                  <div className="space-y-2">
                    <h4 className="font-medium text-sm text-gray-700">By Category</h4>
                    {Object.entries(data.complaintSummary.by_category || {}).map(
                      ([cat, count]: [string, any]) => (
                        <div key={cat} className="flex justify-between items-center text-sm">
                          <span className="text-gray-600 capitalize">
                            {cat.replace('_', ' ')}
                          </span>
                          <Badge variant="secondary">{count}</Badge>
                        </div>
                      )
                    )}
                  </div>

                  <div className="pt-4 border-t">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Response Rate</span>
                      <span className="font-medium">{data.complaintSummary.response_rate}%</span>
                    </div>
                    {data.complaintSummary.active_patterns > 0 && (
                      <div className="mt-2 p-2 bg-red-50 rounded">
                        <p className="text-sm text-red-800">
                          {data.complaintSummary.active_patterns} pattern(s) detected
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <p className="text-gray-500 text-center py-8">No complaint data available</p>
              )}
            </CardContent>
          </Card>

          {/* Recent Menu Checks */}
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Recent Menu Checks</CardTitle>
                <Button variant="ghost" size="sm" onClick={() => router.push('/menu-compliance')}>
                  View All
                  <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-gray-500 text-center py-8">
                Connect menu compliance API to view checks
              </p>
            </CardContent>
          </Card>

          {/* Quick Actions */}
          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-3">
                <Button
                  variant="outline"
                  className="h-20 flex flex-col items-center justify-center"
                  onClick={() => router.push('/meetings/new')}
                >
                  <CalendarDays className="w-6 h-6 mb-2" />
                  <span className="text-sm">New Meeting</span>
                </Button>

                <Button
                  variant="outline"
                  className="h-20 flex flex-col items-center justify-center"
                  onClick={() => router.push('/complaints')}
                >
                  <AlertTriangle className="w-6 h-6 mb-2" />
                  <span className="text-sm">Log Complaint</span>
                </Button>

                <Button
                  variant="outline"
                  className="h-20 flex flex-col items-center justify-center"
                  onClick={() => router.push('/menu-compliance')}
                >
                  <FileText className="w-6 h-6 mb-2" />
                  <span className="text-sm">View Checks</span>
                </Button>

                <Button
                  variant="outline"
                  className="h-20 flex flex-col items-center justify-center"
                  onClick={() => router.push('/analytics')}
                >
                  <TrendingUp className="w-6 h-6 mb-2" />
                  <span className="text-sm">Analytics</span>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}

// Remove unused imports after header removal

