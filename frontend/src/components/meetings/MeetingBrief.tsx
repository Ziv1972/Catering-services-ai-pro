import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { PriorityTopics } from './PriorityTopics';
import { QuestionsToAsk } from './QuestionsToAsk';
import { ActionItems } from './ActionItems';
import { Sparkles, CheckCircle2, AlertCircle } from 'lucide-react';

interface MeetingBriefProps {
  meeting: any;
  onRefresh?: () => void;
}

export function MeetingBrief({ meeting, onRefresh }: MeetingBriefProps) {
  const brief = meeting.ai_brief;

  if (!brief) return null;

  return (
    <div className="space-y-6">
      {/* AI Badge */}
      <div className="flex items-center gap-2 text-sm text-gray-600">
        <Sparkles className="w-4 h-4 text-purple-500" />
        <span>AI-generated meeting brief</span>
        <Badge variant="secondary" className="ml-2">
          {brief.priority_topics?.length || 0} topics
        </Badge>
      </div>

      {/* Priority Topics */}
      {brief.priority_topics && brief.priority_topics.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-red-500" />
              Priority Topics
            </CardTitle>
          </CardHeader>
          <CardContent>
            <PriorityTopics topics={brief.priority_topics} />
          </CardContent>
        </Card>
      )}

      {/* Follow-ups */}
      {brief.follow_ups && brief.follow_ups.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Follow-ups from Last Meeting</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {brief.follow_ups.map((followUp: any, idx: number) => (
                <div key={idx} className="flex items-start gap-3">
                  {followUp.status === 'completed' ? (
                    <CheckCircle2 className="w-5 h-5 text-green-500 mt-0.5" />
                  ) : (
                    <div className="w-5 h-5 rounded-full border-2 border-gray-300 mt-0.5" />
                  )}
                  <div className="flex-1">
                    <p className={followUp.status === 'completed' ? 'line-through text-gray-500' : ''}>
                      {followUp.item}
                    </p>
                    {followUp.notes && (
                      <p className="text-sm text-gray-600 mt-1">{followUp.notes}</p>
                    )}
                  </div>
                  <Badge variant={followUp.status === 'completed' ? 'success' : 'secondary'}>
                    {followUp.status}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Questions to Ask */}
      {brief.questions_to_ask && brief.questions_to_ask.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Questions to Ask</CardTitle>
          </CardHeader>
          <CardContent>
            <QuestionsToAsk questions={brief.questions_to_ask} />
          </CardContent>
        </Card>
      )}

      {/* Talking Points */}
      {brief.talking_points && (
        <Card>
          <CardHeader>
            <CardTitle>Talking Points</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {brief.talking_points.successes && brief.talking_points.successes.length > 0 && (
                <div>
                  <h4 className="font-semibold text-green-700 mb-2">Successes</h4>
                  <ul className="space-y-1 ml-4">
                    {brief.talking_points.successes.map((item: string, idx: number) => (
                      <li key={idx} className="text-gray-700">&bull; {item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {brief.talking_points.concerns && brief.talking_points.concerns.length > 0 && (
                <div>
                  <h4 className="font-semibold text-orange-700 mb-2">Concerns</h4>
                  <ul className="space-y-1 ml-4">
                    {brief.talking_points.concerns.map((item: string, idx: number) => (
                      <li key={idx} className="text-gray-700">&bull; {item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {brief.talking_points.data_highlights && brief.talking_points.data_highlights.length > 0 && (
                <div>
                  <h4 className="font-semibold text-blue-700 mb-2">Data Highlights</h4>
                  <ul className="space-y-1 ml-4">
                    {brief.talking_points.data_highlights.map((item: string, idx: number) => (
                      <li key={idx} className="text-gray-700">&bull; {item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Action Items */}
      {brief.suggested_action_items && brief.suggested_action_items.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Suggested Action Items</CardTitle>
          </CardHeader>
          <CardContent>
            <ActionItems items={brief.suggested_action_items} />
          </CardContent>
        </Card>
      )}

      {/* Formatted Agenda */}
      {meeting.ai_agenda && (
        <Card>
          <CardHeader>
            <CardTitle>Formatted Agenda</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans">
              {meeting.ai_agenda}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
