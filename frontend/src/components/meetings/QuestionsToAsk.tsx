import { MessageCircle } from 'lucide-react';

interface QuestionsToAskProps {
  questions: string[];
}

export function QuestionsToAsk({ questions }: QuestionsToAskProps) {
  return (
    <div className="space-y-3">
      {questions.map((question, idx) => (
        <div key={idx} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
          <MessageCircle className="w-5 h-5 text-blue-500 mt-0.5 flex-shrink-0" />
          <p className="text-gray-700">{question}</p>
        </div>
      ))}
    </div>
  );
}
