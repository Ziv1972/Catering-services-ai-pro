import { useEffect, useState, useCallback } from 'react';
import { meetingsAPI } from '@/lib/api';

interface UseMeetingsOptions {
  upcomingOnly?: boolean;
  autoLoad?: boolean;
}

export function useMeetings(options: UseMeetingsOptions = {}) {
  const { upcomingOnly = true, autoLoad = true } = options;
  const [meetings, setMeetings] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadMeetings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await meetingsAPI.list(upcomingOnly);
      setMeetings(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load meetings';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [upcomingOnly]);

  useEffect(() => {
    if (autoLoad) {
      loadMeetings();
    }
  }, [autoLoad, loadMeetings]);

  const createMeeting = useCallback(async (data: any) => {
    const created = await meetingsAPI.create(data);
    await loadMeetings();
    return created;
  }, [loadMeetings]);

  return {
    meetings,
    loading,
    error,
    refresh: loadMeetings,
    createMeeting,
  };
}
