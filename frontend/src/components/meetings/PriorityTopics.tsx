import { Badge } from '@/components/ui/badge';
import { AlertCircle, AlertTriangle, Info } from 'lucide-react';

interface Topic {
  title: string;
  urgency: 'high' | 'medium' | 'low';
  description: string;
  data_points?: string[];
  suggested_approach?: string;
}

interface PriorityTopicsProps {
  topics: Topic[];
}

export function PriorityTopics({ topics }: PriorityTopicsProps) {
  const getUrgencyIcon = (urgency: string) => {
    switch (urgency) {
      case 'high':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      case 'medium':
        return <AlertTriangle className="w-5 h-5 text-orange-500" />;
      default:
        return <Info className="w-5 h-5 text-blue-500" />;
    }
  };

  const getUrgencyColor = (urgency: string) => {
    switch (urgency) {
      case 'high':
        return 'border-red-200 bg-red-50';
      case 'medium':
        return 'border-orange-200 bg-orange-50';
      default:
        return 'border-blue-200 bg-blue-50';
    }
  };

  return (
    <div className="space-y-4">
      {topics.map((topic, idx) => (
        <div
          key={idx}
          className={`p-4 border-l-4 rounded-r ${getUrgencyColor(topic.urgency)}`}
        >
          <div className="flex items-start gap-3">
            {getUrgencyIcon(topic.urgency)}
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <h4 className="font-semibold text-gray-900">{topic.title}</h4>
                <Badge variant={topic.urgency === 'high' ? 'destructive' : 'secondary'}>
                  {topic.urgency}
                </Badge>
              </div>

              <p className="text-gray-700 mb-2">{topic.description}</p>

              {topic.data_points && topic.data_points.length > 0 && (
                <div className="mb-2">
                  <p className="text-sm font-medium text-gray-600 mb-1">Data:</p>
                  <ul className="text-sm text-gray-600 space-y-0.5 ml-4">
                    {topic.data_points.map((point, i) => (
                      <li key={i}>&bull; {point}</li>
                    ))}
                  </ul>
                </div>
              )}

              {topic.suggested_approach && (
                <div className="mt-2 p-2 bg-white rounded border border-gray-200">
                  <p className="text-sm font-medium text-gray-700">
                    Suggested approach: {topic.suggested_approach}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
