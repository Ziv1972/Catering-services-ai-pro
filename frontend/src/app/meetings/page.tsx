'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { meetingsAPI } from '@/lib/api';
import { MeetingCard } from '@/components/meetings/MeetingCard';
import { Button } from '@/components/ui/button';
import { Plus, Calendar } from 'lucide-react';
import { format } from 'date-fns';

export default function MeetingsPage() {
  const router = useRouter();
  const [meetings, setMeetings] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadMeetings();
  }, []);

  const loadMeetings = async () => {
    try {
      const data = await meetingsAPI.list(true);
      setMeetings(data);
    } catch (error) {
      console.error('Failed to load meetings:', error);
    } finally {
      setLoading(false);
    }
  };

  // Group meetings by date
  const groupedMeetings = meetings.reduce((groups: Record<string, any[]>, meeting: any) => {
    const date = format(new Date(meeting.scheduled_at), 'yyyy-MM-dd');
    if (!groups[date]) groups[date] = [];
    groups[date].push(meeting);
    return groups;
  }, {});

  return (
    <div>
      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Meetings</h2>
            <p className="text-gray-500 text-sm">
              {meetings.length} upcoming meetings
            </p>
          </div>
          <Button onClick={() => router.push('/meetings/new')}>
            <Plus className="w-4 h-4 mr-2" />
            New Meeting
          </Button>
        </div>
        {loading ? (
          <div className="text-center py-12">Loading meetings...</div>
        ) : meetings.length === 0 ? (
          <div className="text-center py-12">
            <Calendar className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              No upcoming meetings
            </h3>
            <p className="text-gray-500 mb-6">
              Create your first meeting to get started
            </p>
            <Button onClick={() => router.push('/meetings/new')}>
              <Plus className="w-4 h-4 mr-2" />
              Create Meeting
            </Button>
          </div>
        ) : (
          <div className="space-y-8">
            {Object.entries(groupedMeetings).map(([date, dateMeetings]) => (
              <div key={date}>
                <h2 className="text-lg font-semibold text-gray-900 mb-4">
                  {format(new Date(date), 'EEEE, MMMM d, yyyy')}
                </h2>
                <div className="space-y-4">
                  {(dateMeetings as any[]).map((meeting: any) => (
                    <MeetingCard
                      key={meeting.id}
                      meeting={meeting}
                      onRefresh={loadMeetings}
                    />
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

