'use client';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useRouter } from 'next/navigation';
import { format } from 'date-fns';
import { Clock, MapPin, Sparkles, ArrowRight } from 'lucide-react';
import { meetingsAPI } from '@/lib/api';
import { useState } from 'react';

interface MeetingCardProps {
  meeting: any;
  onRefresh?: () => void;
}

export function MeetingCard({ meeting, onRefresh }: MeetingCardProps) {
  const router = useRouter();
  const [generating, setGenerating] = useState(false);

  const scheduledDate = new Date(meeting.scheduled_at);
  const hasBrief = meeting.ai_brief !== null;

  const handleGenerateBrief = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setGenerating(true);
    try {
      await meetingsAPI.prepareBrief(meeting.id);
      onRefresh?.();
    } catch (error) {
      console.error('Failed to generate brief:', error);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <Card
      className="p-6 hover:shadow-md transition-shadow cursor-pointer"
      onClick={() => router.push(`/meetings/${meeting.id}`)}
    >
      <div className="flex justify-between items-start">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <h3 className="text-lg font-semibold text-gray-900">
              {meeting.title}
            </h3>
            {hasBrief && (
              <Badge className="bg-green-100 text-green-800 border-green-200">
                <Sparkles className="w-3 h-3 mr-1" />
                Brief Ready
              </Badge>
            )}
          </div>

          <div className="flex items-center gap-4 text-sm text-gray-600 mb-3">
            <div className="flex items-center gap-1">
              <Clock className="w-4 h-4" />
              {format(scheduledDate, 'h:mm a')} ({meeting.duration_minutes} min)
            </div>

            {meeting.site_id && (
              <div className="flex items-center gap-1">
                <MapPin className="w-4 h-4" />
                Site {meeting.site_id}
              </div>
            )}
          </div>

          <Badge variant="secondary">
            {meeting.meeting_type.replace('_', ' ')}
          </Badge>
        </div>

        <div className="flex items-center gap-2">
          {!hasBrief ? (
            <Button
              onClick={handleGenerateBrief}
              disabled={generating}
              variant="outline"
            >
              <Sparkles className="w-4 h-4 mr-2" />
              {generating ? 'Generating...' : 'Prepare Brief'}
            </Button>
          ) : (
            <Button variant="ghost">
              View Brief
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
