'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { meetingsAPI } from '@/lib/api';
import { MeetingBrief } from '@/components/meetings/MeetingBrief';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ArrowLeft, Sparkles, Calendar, Clock, MapPin } from 'lucide-react';
import { format } from 'date-fns';

export default function MeetingDetailPage() {
  const router = useRouter();
  const params = useParams();
  const meetingId = parseInt(params.id as string);

  const [meeting, setMeeting] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    loadMeeting();
  }, [meetingId]);

  const loadMeeting = async () => {
    try {
      const data = await meetingsAPI.get(meetingId);
      setMeeting(data);
    } catch (error) {
      console.error('Failed to load meeting:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateBrief = async () => {
    setGenerating(true);
    try {
      const updated = await meetingsAPI.prepareBrief(meetingId);
      setMeeting(updated);
    } catch (error) {
      console.error('Failed to generate brief:', error);
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  if (!meeting) {
    return <div className="flex items-center justify-center h-screen">Meeting not found</div>;
  }

  const hasBrief = meeting.ai_brief !== null;
  const scheduledDate = new Date(meeting.scheduled_at);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b">
        <div className="max-w-5xl mx-auto px-4 py-6">
          <Button
            variant="ghost"
            onClick={() => router.push('/meetings')}
            className="mb-4"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Meetings
          </Button>

          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                {meeting.title}
              </h1>

              <div className="flex items-center gap-4 mt-3 text-sm text-gray-600">
                <div className="flex items-center">
                  <Calendar className="w-4 h-4 mr-1.5" />
                  {format(scheduledDate, 'EEEE, MMMM d, yyyy')}
                </div>
                <div className="flex items-center">
                  <Clock className="w-4 h-4 mr-1.5" />
                  {format(scheduledDate, 'h:mm a')} ({meeting.duration_minutes} min)
                </div>
                {meeting.site_id && (
                  <div className="flex items-center">
                    <MapPin className="w-4 h-4 mr-1.5" />
                    Site {meeting.site_id}
                  </div>
                )}
              </div>

              <div className="mt-3">
                <Badge variant="secondary">
                  {meeting.meeting_type.replace('_', ' ')}
                </Badge>
              </div>
            </div>

            {!hasBrief && (
              <Button
                onClick={handleGenerateBrief}
                disabled={generating}
                size="lg"
              >
                <Sparkles className="w-4 h-4 mr-2" />
                {generating ? 'Generating...' : 'Prepare Brief'}
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8">
        {!hasBrief ? (
          <Card className="p-12 text-center">
            <Sparkles className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              No brief generated yet
            </h3>
            <p className="text-gray-600 mb-6">
              Click &quot;Prepare Brief&quot; to generate an AI-powered meeting brief
              with priority topics, questions, and action items.
            </p>
            <Button onClick={handleGenerateBrief} disabled={generating}>
              <Sparkles className="w-4 h-4 mr-2" />
              {generating ? 'Generating Brief...' : 'Generate Brief Now'}
            </Button>
          </Card>
        ) : (
          <MeetingBrief meeting={meeting} onRefresh={loadMeeting} />
        )}
      </main>
    </div>
  );
}
