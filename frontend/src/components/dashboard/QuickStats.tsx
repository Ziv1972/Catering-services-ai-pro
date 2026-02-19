'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { api } from '@/lib/api';
import { CalendarDays, MapPin, Sparkles, AlertCircle } from 'lucide-react';

interface DashboardData {
  upcoming_meetings: number;
  total_sites: number;
  meetings_with_briefs: number;
  meetings_without_briefs: number;
}

export function QuickStats() {
  const [stats, setStats] = useState<DashboardData | null>(null);

  useEffect(() => {
    const loadStats = async () => {
      try {
        const response = await api.get('/api/dashboard/');
        setStats(response.data);
      } catch (error) {
        console.error('Failed to load stats:', error);
      }
    };
    loadStats();
  }, []);

  if (!stats) return null;

  const statCards = [
    {
      label: 'Upcoming Meetings',
      value: stats.upcoming_meetings,
      icon: CalendarDays,
      color: 'text-blue-600',
      bg: 'bg-blue-50',
    },
    {
      label: 'Active Sites',
      value: stats.total_sites,
      icon: MapPin,
      color: 'text-green-600',
      bg: 'bg-green-50',
    },
    {
      label: 'Briefs Ready',
      value: stats.meetings_with_briefs,
      icon: Sparkles,
      color: 'text-purple-600',
      bg: 'bg-purple-50',
    },
    {
      label: 'Need Preparation',
      value: stats.meetings_without_briefs,
      icon: AlertCircle,
      color: 'text-orange-600',
      bg: 'bg-orange-50',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      {statCards.map((stat) => (
        <Card key={stat.label} className="p-6">
          <div className="flex items-center gap-4">
            <div className={`p-3 rounded-lg ${stat.bg}`}>
              <stat.icon className={`w-5 h-5 ${stat.color}`} />
            </div>
            <div>
              <p className="text-sm text-gray-500">{stat.label}</p>
              <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}
