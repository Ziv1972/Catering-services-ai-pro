'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { meetingsAPI } from '@/lib/api';
import { UpcomingMeetings } from '@/components/dashboard/UpcomingMeetings';
import { QuickStats } from '@/components/dashboard/QuickStats';
import { Button } from '@/components/ui/button';
import { Plus } from 'lucide-react';

export default function Dashboard() {
  const router = useRouter();
  const [meetings, setMeetings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const data = await meetingsAPI.list(true);
      setMeetings(data);
    } catch (error) {
      console.error('Failed to load:', error);
      router.push('/login');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Catering Services AI Pro
            </h1>
            <p className="text-sm text-gray-500">
              Good morning, Ziv
            </p>
          </div>

          <Button onClick={() => router.push('/meetings/new')}>
            <Plus className="w-4 h-4 mr-2" />
            New Meeting
          </Button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Quick Stats */}
        <QuickStats />

        {/* Upcoming Meetings */}
        <div className="mt-8">
          <UpcomingMeetings meetings={meetings} onRefresh={loadData} />
        </div>
      </main>
    </div>
  );
}
