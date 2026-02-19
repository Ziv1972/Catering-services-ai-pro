import { Badge } from '@/components/ui/badge';
import { CheckSquare, User, Calendar } from 'lucide-react';

interface ActionItem {
  action: string;
  owner: string;
  deadline: string;
  priority: 'high' | 'medium' | 'low';
}

interface ActionItemsProps {
  items: ActionItem[];
}

export function ActionItems({ items }: ActionItemsProps) {
  return (
    <div className="space-y-3">
      {items.map((item, idx) => (
        <div key={idx} className="p-4 border border-gray-200 rounded-lg hover:border-gray-300 transition-colors">
          <div className="flex items-start gap-3">
            <CheckSquare className="w-5 h-5 text-gray-400 mt-0.5" />
            <div className="flex-1">
              <p className="text-gray-900 font-medium mb-2">{item.action}</p>

              <div className="flex items-center gap-4 text-sm text-gray-600">
                <div className="flex items-center gap-1">
                  <User className="w-3.5 h-3.5" />
                  <span>{item.owner}</span>
                </div>

                <div className="flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5" />
                  <span>{item.deadline}</span>
                </div>

                <Badge
                  variant={item.priority === 'high' ? 'destructive' : 'secondary'}
                  className="text-xs"
                >
                  {item.priority}
                </Badge>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
