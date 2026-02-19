import { useState, useCallback } from 'react';
import { meetingsAPI } from '@/lib/api';

export function useMeetingBrief() {
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generateBrief = useCallback(async (meetingId: number) => {
    setGenerating(true);
    setError(null);
    try {
      const updated = await meetingsAPI.prepareBrief(meetingId);
      return updated;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to generate brief';
      setError(message);
      throw err;
    } finally {
      setGenerating(false);
    }
  }, []);

  return {
    generating,
    error,
    generateBrief,
  };
}
