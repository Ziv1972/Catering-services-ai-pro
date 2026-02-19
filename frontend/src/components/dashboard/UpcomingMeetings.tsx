'use client';

import { useRouter } from 'next/navigation';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { MeetingCard } from '@/components/meetings/MeetingCard';
import { Calendar, ArrowRight } from 'lucide-react';

interface UpcomingMeetingsProps {
  meetings: any[];
  onRefresh?: () => void;
}

export function UpcomingMeetings({ meetings, onRefresh }: UpcomingMeetingsProps) {
  const router = useRouter();

  if (meetings.length === 0) {
    return (
      <Card className="p-12 text-center">
        <Calendar className="w-16 h-16 text-gray-300 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          No upcoming meetings
        </h3>
        <p className="text-gray-500 mb-6">
          Create your first meeting to get an AI-powered brief
        </p>
        <Button onClick={() => router.push('/meetings/new')}>
          Create Meeting
        </Button>
      </Card>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-semibold text-gray-900">
          Upcoming Meetings
        </h2>
        <Button
          variant="ghost"
          onClick={() => router.push('/meetings')}
        >
          View All
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </div>

      <div className="space-y-4">
        {meetings.slice(0, 5).map((meeting: any) => (
          <MeetingCard
            key={meeting.id}
            meeting={meeting}
            onRefresh={onRefresh}
          />
        ))}
      </div>
    </div>
  );
}
