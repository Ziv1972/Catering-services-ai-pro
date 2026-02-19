'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { meetingsAPI } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { ArrowLeft } from 'lucide-react';

const MEETING_TYPES = [
  { value: 'site_manager', label: 'Site Manager' },
  { value: 'technical', label: 'Technical' },
  { value: 'hp_management', label: 'HP Management' },
  { value: 'vendor', label: 'Vendor' },
  { value: 'other', label: 'Other' },
];

export default function CreateMeetingPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    meeting_type: 'site_manager',
    scheduled_at: '',
    duration_minutes: 60,
    site_id: null as number | null,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const created = await meetingsAPI.create(formData);
      router.push(`/meetings/${created.id}`);
    } catch (error) {
      console.error('Failed to create meeting:', error);
    } finally {
      setSubmitting(false);
    }
  };

  const updateField = (field: string, value: string | number | null) => {
    setFormData({ ...formData, [field]: value });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b">
        <div className="max-w-3xl mx-auto px-4 py-6">
          <Button
            variant="ghost"
            onClick={() => router.push('/meetings')}
            className="mb-4"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Meetings
          </Button>
          <h1 className="text-3xl font-bold text-gray-900">Schedule New Meeting</h1>
          <p className="text-gray-500 mt-1">
            Create a meeting and generate an AI-powered brief
          </p>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8">
        <Card>
          <CardHeader>
            <CardTitle>Meeting Details</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Title */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Meeting Title
                </label>
                <input
                  type="text"
                  required
                  value={formData.title}
                  onChange={(e) => updateField('title', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="Weekly Site Review - Nes Ziona"
                />
              </div>

              {/* Type and Duration */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Meeting Type
                  </label>
                  <select
                    value={formData.meeting_type}
                    onChange={(e) => updateField('meeting_type', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    {MEETING_TYPES.map((type) => (
                      <option key={type.value} value={type.value}>
                        {type.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Duration (minutes)
                  </label>
                  <input
                    type="number"
                    min={15}
                    step={15}
                    value={formData.duration_minutes}
                    onChange={(e) => updateField('duration_minutes', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
              </div>

              {/* Date & Time and Site */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Date & Time
                  </label>
                  <input
                    type="datetime-local"
                    required
                    value={formData.scheduled_at}
                    onChange={(e) => updateField('scheduled_at', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Site (optional)
                  </label>
                  <select
                    value={formData.site_id ?? ''}
                    onChange={(e) => updateField('site_id', e.target.value ? parseInt(e.target.value) : null)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="">No specific site</option>
                    <option value="1">Nes Ziona (NZ)</option>
                    <option value="2">Kiryat Gat (KG)</option>
                  </select>
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-3 pt-4">
                <Button type="submit" disabled={submitting}>
                  {submitting ? 'Creating...' : 'Create Meeting'}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => router.push('/meetings')}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
