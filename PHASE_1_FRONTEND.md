# Phase 1 Frontend - Meeting Prep Agent UI

> **Upload this file to Cursor and ask it to implement the Meeting Prep Agent frontend**

---

## Overview

Build a beautiful, production-ready frontend for the Meeting Prep Agent. Users can:
- View upcoming meetings in a calendar/list view
- Create new meetings with one click
- Generate AI briefs with one click
- View formatted meeting briefs with priority topics, questions, and action items
- Add meeting notes after the meeting
- Track action items

---

## Design Philosophy

**AI-Native, Not CRUD:**
- Emphasize the AI-generated brief (not forms)
- One-click actions ("Prepare Brief" button)
- Visual hierarchy (urgent items stand out)
- Progressive disclosure (show summary, expand for details)
- Conversational tone (like talking to an assistant)

**Reference Design:** Linear, Notion, Height (modern, clean, fast)

---

## Tech Stack

- **Framework:** Next.js 14 (App Router)
- **Styling:** Tailwind CSS
- **Components:** shadcn/ui
- **Icons:** Lucide React
- **Date handling:** date-fns
- **API Client:** Axios (already setup in `src/lib/api.ts`)

---

## File Structure

```
frontend/src/
├── app/
│   ├── layout.tsx                    # Root layout (already exists)
│   ├── page.tsx                      # Dashboard (update)
│   ├── meetings/
│   │   ├── page.tsx                  # Meetings list view
│   │   ├── [id]/
│   │   │   └── page.tsx              # Single meeting detail + brief
│   │   └── new/
│   │       └── page.tsx              # Create new meeting
│   └── login/
│       └── page.tsx                  # Login (already exists)
│
├── components/
│   ├── ui/                           # shadcn/ui components (to be added)
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── badge.tsx
│   │   ├── dialog.tsx
│   │   ├── select.tsx
│   │   ├── calendar.tsx
│   │   └── ...
│   │
│   ├── meetings/
│   │   ├── MeetingCard.tsx          # Meeting summary card
│   │   ├── MeetingBrief.tsx         # AI-generated brief display
│   │   ├── CreateMeetingDialog.tsx  # Quick create dialog
│   │   ├── PriorityTopics.tsx       # Priority topics section
│   │   ├── QuestionsToAsk.tsx       # Questions section
│   │   ├── ActionItems.tsx          # Action items checklist
│   │   └── MeetingNotes.tsx         # Post-meeting notes
│   │
│   └── dashboard/
│       ├── UpcomingMeetings.tsx     # Dashboard widget
│       └── QuickStats.tsx           # Stats cards
│
├── lib/
│   ├── api.ts                       # API client (already exists)
│   └── utils.ts                     # Utilities
│
└── hooks/
    ├── useMeetings.ts               # Meeting data hook
    └── useMeetingBrief.ts           # Brief generation hook
```

---

## Component Specifications

### 1. Dashboard Page (`app/page.tsx`)

**Purpose:** Quick overview of upcoming meetings and system status

```typescript
'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { meetingsAPI } from '@/lib/api';
import { UpcomingMeetings } from '@/components/dashboard/UpcomingMeetings';
import { QuickStats } from '@/components/dashboard/QuickStats';
import { Button } from '@/components/ui/button';
import { Plus } from 'lucide-react';

export default function Dashboard() {
  const router = useRouter();
  const [meetings, setMeetings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const data = await meetingsAPI.list(true);
      setMeetings(data);
    } catch (error) {
      console.error('Failed to load:', error);
      router.push('/login');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              🍽️ Catering Services AI Pro
            </h1>
            <p className="text-sm text-gray-500">
              Good morning, Ziv
            </p>
          </div>
          
          <Button onClick={() => router.push('/meetings/new')}>
            <Plus className="w-4 h-4 mr-2" />
            New Meeting
          </Button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Quick Stats */}
        <QuickStats />

        {/* Upcoming Meetings */}
        <div className="mt-8">
          <UpcomingMeetings meetings={meetings} />
        </div>
      </main>
    </div>
  );
}
```

---

### 2. Meetings List (`app/meetings/page.tsx`)

**Purpose:** View all upcoming meetings, create new ones, quick actions

```typescript
'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { meetingsAPI } from '@/lib/api';
import { MeetingCard } from '@/components/meetings/MeetingCard';
import { Button } from '@/components/ui/button';
import { Plus, Calendar } from 'lucide-react';
import { format } from 'date-fns';

export default function MeetingsPage() {
  const router = useRouter();
  const [meetings, setMeetings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadMeetings();
  }, []);

  const loadMeetings = async () => {
    try {
      const data = await meetingsAPI.list(true);
      setMeetings(data);
    } catch (error) {
      console.error('Failed to load meetings:', error);
    } finally {
      setLoading(false);
    }
  };

  // Group meetings by date
  const groupedMeetings = meetings.reduce((groups, meeting) => {
    const date = format(new Date(meeting.scheduled_at), 'yyyy-MM-dd');
    if (!groups[date]) groups[date] = [];
    groups[date].push(meeting);
    return groups;
  }, {});

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Meetings</h1>
              <p className="text-gray-500 mt-1">
                {meetings.length} upcoming meetings
              </p>
            </div>
            
            <Button onClick={() => router.push('/meetings/new')}>
              <Plus className="w-4 h-4 mr-2" />
              New Meeting
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {loading ? (
          <div className="text-center py-12">Loading meetings...</div>
        ) : meetings.length === 0 ? (
          <div className="text-center py-12">
            <Calendar className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              No upcoming meetings
            </h3>
            <p className="text-gray-500 mb-6">
              Create your first meeting to get started
            </p>
            <Button onClick={() => router.push('/meetings/new')}>
              <Plus className="w-4 h-4 mr-2" />
              Create Meeting
            </Button>
          </div>
        ) : (
          <div className="space-y-8">
            {Object.entries(groupedMeetings).map(([date, dateMeetings]) => (
              <div key={date}>
                <h2 className="text-lg font-semibold text-gray-900 mb-4">
                  {format(new Date(date), 'EEEE, MMMM d, yyyy')}
                </h2>
                <div className="space-y-4">
                  {dateMeetings.map((meeting) => (
                    <MeetingCard 
                      key={meeting.id} 
                      meeting={meeting}
                      onRefresh={loadMeetings}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
```

---

### 3. Meeting Detail Page (`app/meetings/[id]/page.tsx`)

**Purpose:** View meeting details and AI-generated brief

```typescript
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
  
  const [meeting, setMeeting] = useState(null);
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
      alert('Failed to generate brief. Check your API key.');
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
              Click "Prepare Brief" to generate an AI-powered meeting brief
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
```

---

### 4. Meeting Brief Component (`components/meetings/MeetingBrief.tsx`)

**Purpose:** Display AI-generated brief in a beautiful, scannable format

```typescript
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
              {brief.follow_ups.map((followUp, idx) => (
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
                  <h4 className="font-semibold text-green-700 mb-2">✅ Successes</h4>
                  <ul className="space-y-1 ml-4">
                    {brief.talking_points.successes.map((item, idx) => (
                      <li key={idx} className="text-gray-700">• {item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {brief.talking_points.concerns && brief.talking_points.concerns.length > 0 && (
                <div>
                  <h4 className="font-semibold text-orange-700 mb-2">⚠️ Concerns</h4>
                  <ul className="space-y-1 ml-4">
                    {brief.talking_points.concerns.map((item, idx) => (
                      <li key={idx} className="text-gray-700">• {item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {brief.talking_points.data_highlights && brief.talking_points.data_highlights.length > 0 && (
                <div>
                  <h4 className="font-semibold text-blue-700 mb-2">📊 Data Highlights</h4>
                  <ul className="space-y-1 ml-4">
                    {brief.talking_points.data_highlights.map((item, idx) => (
                      <li key={idx} className="text-gray-700">• {item}</li>
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
```

---

### 5. Priority Topics Component (`components/meetings/PriorityTopics.tsx`)

```typescript
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
                      <li key={i}>• {point}</li>
                    ))}
                  </ul>
                </div>
              )}
              
              {topic.suggested_approach && (
                <div className="mt-2 p-2 bg-white rounded border border-gray-200">
                  <p className="text-sm font-medium text-gray-700">
                    💡 Suggested approach: {topic.suggested_approach}
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
```

---

### 6. Questions Component (`components/meetings/QuestionsToAsk.tsx`)

```typescript
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
```

---

### 7. Action Items Component (`components/meetings/ActionItems.tsx`)

```typescript
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
```

---

### 8. Meeting Card Component (`components/meetings/MeetingCard.tsx`)

```typescript
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
      alert('Failed to generate brief');
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
```

---

## Installation Steps for Cursor

**Step 1: Install shadcn/ui components**

```bash
cd frontend

# Initialize shadcn/ui (if not done)
npx shadcn-ui@latest init

# Install required components
npx shadcn-ui@latest add button
npx shadcn-ui@latest add card
npx shadcn-ui@latest add badge
npx shadcn-ui@latest add dialog
npx shadcn-ui@latest add select
npx shadcn-ui@latest add calendar
npx shadcn-ui@latest add input
npx shadcn-ui@latest add label
```

**Step 2: Install additional dependencies**

```bash
npm install date-fns lucide-react
```

---

## Instructions for Cursor

1. **Read this entire file** to understand the component structure
2. **Create all components** in the specified file locations
3. **Use shadcn/ui components** for consistency
4. **Follow the design system**:
   - Colors: Red for high priority, Orange for medium, Blue for low
   - Spacing: Consistent padding/margins
   - Hover states: Subtle shadows and color transitions
   - Icons: Lucide React
5. **Ensure responsiveness** - works on mobile and desktop
6. **Add loading states** for all async operations
7. **Handle errors gracefully** with user-friendly messages

---

## Expected User Flow

1. **Login** → Dashboard
2. **Dashboard** → See upcoming meetings + quick stats
3. **Click "New Meeting"** → Create meeting dialog
4. **Fill form** → Meeting created
5. **Click meeting** → Meeting detail page
6. **Click "Prepare Brief"** → Loading... → Brief generated
7. **View brief** → Priority topics, questions, action items beautifully formatted
8. **Use brief** → During actual meeting

---

## Success Criteria

After implementation, user should be able to:
- ✅ Create a meeting in <30 seconds
- ✅ Generate AI brief with one click
- ✅ View brief in scannable, hierarchical format
- ✅ Identify urgent topics immediately (red badges)
- ✅ See questions and action items clearly
- ✅ Navigate smoothly between views

---

## Design Reference

**Visual Hierarchy:**
```
🔴 HIGH PRIORITY    → Red border, red icon, prominent
🟡 MEDIUM PRIORITY  → Orange border, orange icon
🔵 LOW PRIORITY     → Blue border, blue icon, subtle
```

**Spacing:**
```
Section gaps:     24px (6 Tailwind units)
Card padding:     24px
Inner spacing:    12-16px
Text line height: 1.5-1.75
```

**Typography:**
```
Page title:       text-3xl font-bold
Section title:    text-xl font-semibold
Card title:       text-lg font-semibold
Body text:        text-base
Small text:       text-sm text-gray-600
```

---

## Post-Implementation Testing

After Cursor builds this, test:

1. **Create meeting** → Should work smoothly
2. **Generate brief** → Should take ~20 seconds, show loading state
3. **View brief** → Should be beautiful, scannable, hierarchical
4. **Responsive** → Check on mobile (optional but nice)
5. **Error handling** → What happens if API fails?

---

This completes the Phase 1 Frontend implementation guide. Upload this to Cursor and ask it to build all components following this specification.
