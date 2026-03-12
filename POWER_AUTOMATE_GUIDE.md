# Power Automate Setup Guide - Complete Implementation

> **No Azure AD needed! Simple, fast, and works immediately.**

---

## Overview

Set up automatic email and calendar monitoring using Power Automate (included with Office 365).

**What You'll Build:**
1. ✅ Email monitoring → Auto-import violations
2. ✅ Calendar monitoring → Auto-import meetings
3. ✅ AI analysis → Automatic on import

**Time Required:** 30-45 minutes

---

## Part 1: Backend Webhook Endpoints

### Step 1: Create Webhook Handler

**File:** `backend/api/webhooks.py`

```python
"""
Webhook endpoints for Power Automate integration
"""
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Dict, Any
import logging

from backend.database import get_db
from backend.models.violation import Violation, ViolationSource, ViolationStatus
from backend.models.meeting import Meeting, MeetingType
from backend.models.site import Site
from backend.agents.violation_intelligence.agent import ViolationIntelligenceAgent
from sqlalchemy import select

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/violations")
async def receive_violation(request: Request):
    """
    Webhook endpoint for Power Automate email trigger
    Receives violations from monitored emails
    
    Expected JSON body from Power Automate:
    {
        "from": "employee@hp.com",
        "subject": "Food violation",
        "body": "The food was cold today...",
        "received": "2026-02-20T14:30:00Z",
        "message_id": "outlook-message-id"
    }
    """
    try:
        data = await request.json()
        logger.info(f"Received violation webhook: {data.get('subject', 'No subject')}")
        
        # Extract email body (remove HTML if present)
        body_text = data.get('body', '')
        if data.get('bodyPreview'):
            body_text = data['bodyPreview']  # Plain text version
        
        # Parse sender email
        from_email = data.get('from', '')
        if isinstance(from_email, dict):
            from_email = from_email.get('emailAddress', {}).get('address', '')
        
        # Determine site from email or content
        site_id = await _infer_site_from_text(body_text)
        
        async with get_db() as db:
            # Create violation
            violation = Violation(
                violation_text=body_text,
                employee_email=from_email,
                source=ViolationSource.EMAIL,
                source_id=data.get('message_id'),
                received_at=datetime.fromisoformat(data.get('received', datetime.utcnow().isoformat()).replace('Z', '+00:00')),
                status=ViolationStatus.NEW,
                site_id=site_id
            )
            
            db.add(violation)
            await db.flush()
            
            # AI analysis
            agent = ViolationIntelligenceAgent()
            await agent.analyze_violation(db, violation)
            
            await db.commit()
            await db.refresh(violation)
            
            logger.info(f"Violation created: ID={violation.id}, Category={violation.category}, Severity={violation.severity}")
            
            return {
                "status": "success",
                "violation_id": violation.id,
                "category": violation.category.value if violation.category else None,
                "severity": violation.severity.value if violation.severity else None,
                "ai_summary": violation.ai_summary
            }
    
    except Exception as e:
        logger.error(f"Error processing violation webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/meetings")
async def receive_meeting_from_calendar(request: Request):
    """
    Webhook endpoint for Power Automate calendar trigger
    Receives catering-related meetings
    
    Expected JSON body from Power Automate:
    {
        "subject": "Weekly Sync - Nes Ziona",
        "start": "2026-02-24T10:00:00Z",
        "end": "2026-02-24T11:00:00Z",
        "location": "Nes Ziona",
        "event_id": "outlook-event-id"
    }
    """
    try:
        data = await request.json()
        logger.info(f"Received meeting webhook: {data.get('subject', 'No subject')}")
        
        # Extract title
        title = data.get('subject', 'Untitled Meeting')
        
        # Check if catering-related
        if not _is_catering_meeting(title):
            logger.info(f"Skipping non-catering meeting: {title}")
            return {
                "status": "skipped",
                "reason": "Not catering-related"
            }
        
        # Parse times
        start_time = datetime.fromisoformat(data.get('start', '').replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(data.get('end', '').replace('Z', '+00:00'))
        duration_minutes = int((end_time - start_time).total_seconds() / 60)
        
        # Infer meeting type and site
        meeting_type = _infer_meeting_type(title)
        site_id = await _infer_site_from_text(title + ' ' + data.get('location', ''))
        
        async with get_db() as db:
            # Check if meeting already exists (by event_id)
            event_id = data.get('event_id')
            if event_id:
                result = await db.execute(
                    select(Meeting).where(Meeting.outlook_event_id == event_id)
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    # Update existing
                    existing.title = title
                    existing.scheduled_at = start_time
                    existing.duration_minutes = duration_minutes
                    await db.commit()
                    
                    logger.info(f"Updated existing meeting: ID={existing.id}")
                    return {
                        "status": "updated",
                        "meeting_id": existing.id
                    }
            
            # Create new meeting
            meeting = Meeting(
                title=title,
                meeting_type=meeting_type,
                scheduled_at=start_time,
                duration_minutes=duration_minutes,
                site_id=site_id,
                outlook_event_id=event_id
            )
            
            db.add(meeting)
            await db.commit()
            await db.refresh(meeting)
            
            logger.info(f"Meeting created: ID={meeting.id}, Type={meeting.meeting_type}")
            
            return {
                "status": "created",
                "meeting_id": meeting.id,
                "type": meeting.meeting_type.value
            }
    
    except Exception as e:
        logger.error(f"Error processing meeting webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test")
async def test_webhook():
    """Test endpoint to verify webhooks are working"""
    return {
        "status": "ok",
        "message": "Webhooks are operational",
        "timestamp": datetime.utcnow().isoformat()
    }


# Helper functions

async def _infer_site_from_text(text: str) -> int | None:
    """Infer site from text content"""
    text_lower = text.lower()
    
    async with get_db() as db:
        if 'nes ziona' in text_lower or 'nz' in text_lower:
            result = await db.execute(select(Site).where(Site.code == 'NZ'))
            site = result.scalar_one_or_none()
            return site.id if site else None
        
        if 'kiryat gat' in text_lower or 'kg' in text_lower:
            result = await db.execute(select(Site).where(Site.code == 'KG'))
            site = result.scalar_one_or_none()
            return site.id if site else None
    
    return None


def _is_catering_meeting(title: str) -> bool:
    """Check if meeting is catering-related"""
    title_lower = title.lower()
    keywords = [
        'catering', 'food', 'menu', 'dining', 'kitchen',
        'vendor', 'supplier', 'nes ziona', 'kiryat gat',
        'site manager', 'weekly sync', 'foodhouse', 'l.eshel'
    ]
    return any(keyword in title_lower for keyword in keywords)


def _infer_meeting_type(title: str) -> MeetingType:
    """Infer meeting type from title"""
    title_lower = title.lower()
    
    if 'site manager' in title_lower or 'weekly sync' in title_lower:
        return MeetingType.SITE_MANAGER
    elif 'technical' in title_lower or 'equipment' in title_lower:
        return MeetingType.TECHNICAL
    elif 'vendor' in title_lower or 'supplier' in title_lower:
        return MeetingType.VENDOR
    elif 'hp management' in title_lower or 'budget' in title_lower:
        return MeetingType.HP_MANAGEMENT
    else:
        return MeetingType.OTHER
```

### Step 2: Update Main App

**File:** `backend/main.py`

```python
# Add webhooks router
from backend.api import auth, meetings, violations, webhooks  # Add webhooks

app.include_router(auth.router)
app.include_router(meetings.router)
app.include_router(violations.router)
app.include_router(webhooks.router)  # Add this line
```

### Step 3: Update Meeting Model

**File:** `backend/models/meeting.py`

Add this field to the Meeting model:

```python
# Add to Meeting class
outlook_event_id = Column(String, unique=True, nullable=True, index=True)
```

Create migration:
```bash
cd backend
alembic revision -m "add outlook_event_id to meetings"
alembic upgrade head
```

---

## Part 2: Expose Local Backend (ngrok)

### Step 1: Install ngrok

**Windows:**
```bash
# Download from https://ngrok.com/download
# Or use chocolatey:
choco install ngrok
```

**Mac:**
```bash
brew install ngrok
```

**Linux:**
```bash
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | \
  sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null && \
  echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | \
  sudo tee /etc/apt/sources.list.d/ngrok.list && \
  sudo apt update && sudo apt install ngrok
```

### Step 2: Start Backend

```bash
cd backend
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 3: Start ngrok

**In a separate terminal:**

```bash
ngrok http 8000
```

**You'll see output like:**
```
Session Status   online
Account          Your Account
Version          3.x.x
Region           United States (us)
Forwarding       https://abc123.ngrok.io -> http://localhost:8000
```

**Copy the https URL** (e.g., `https://abc123.ngrok.io`)

### Step 4: Test Webhook

```bash
# Test that your webhook is accessible
curl https://abc123.ngrok.io/api/webhooks/test

# Should return: {"status":"ok","message":"Webhooks are operational",...}
```

---

## Part 3: Power Automate Setup

### Step 1: Access Power Automate

1. Go to: **https://make.powerautomate.com**
2. Sign in with: **ziv.reshef-simchoni@hp.com**
3. Should work automatically (Office 365 license)

### Step 2: Create Violation Flow

**Click "Create" → "Automated cloud flow"**

#### **Basic Info:**
- Name: `Catering Violations from Email`
- Trigger: Search for "When a new email arrives (V3)"
- Click "Create"

#### **Configure Trigger:**
1. **Folder:** `Inbox`
2. **Include Attachments:** `No`
3. **Only with Attachments:** `No`
4. **Subject Filter:** (leave empty for now)
5. Click "Show advanced options"
6. **Importance:** `Any`

#### **Add Condition (Optional Filter):**
1. Click "+ New step"
2. Search for "Condition"
3. Configure:
   - **If:** `Subject`
   - **contains:** `violation`
   - **OR**
   - **If:** `Subject`
   - **contains:** `food`
   - **OR**
   - **If:** `Subject`
   - **contains:** `cold`

#### **Add HTTP Action:**
1. Under "If yes" branch
2. Click "Add an action"
3. Search for "HTTP"
4. Select "HTTP" (Premium connector)

Configure HTTP:
```
Method: POST
URI: https://YOUR-NGROK-URL.ngrok.io/api/webhooks/violations

Headers:
Content-Type: application/json

Body:
{
  "from": @{triggerBody()?['from']},
  "subject": @{triggerBody()?['subject']},
  "body": @{triggerBody()?['bodyPreview']},
  "received": @{triggerBody()?['receivedDateTime']},
  "message_id": @{triggerBody()?['id']}
}
```

**To add dynamic content:**
- Click in the field
- Select from "Dynamic content" panel on right
- Use the @ symbol to insert variables

#### **Save the Flow**

Click "Save" (top right)

---

### Step 3: Create Meeting Flow

**Click "Create" → "Automated cloud flow"**

#### **Basic Info:**
- Name: `Catering Meetings to AI System`
- Trigger: Search for "When an event is created or modified (V3)"
- Click "Create"

#### **Configure Trigger:**
1. **Calendar Id:** `Calendar` (your main calendar)
2. Click "Show advanced options"
3. **Time zone:** `(UTC+02:00) Jerusalem`

#### **Add Condition (Filter):**
1. Click "+ New step"
2. Search for "Condition"
3. Configure:
   - **If:** `Subject`
   - **contains:** `catering`
   - **OR**
   - **If:** `Subject`
   - **contains:** `food`
   - **OR**
   - **If:** `Subject`
   - **contains:** `vendor`

#### **Add HTTP Action:**
1. Under "If yes" branch
2. Click "Add an action"
3. Search for "HTTP"
4. Select "HTTP"

Configure HTTP:
```
Method: POST
URI: https://YOUR-NGROK-URL.ngrok.io/api/webhooks/meetings

Headers:
Content-Type: application/json

Body:
{
  "subject": @{triggerBody()?['subject']},
  "start": @{triggerBody()?['start']},
  "end": @{triggerBody()?['end']},
  "location": @{triggerBody()?['location']?['displayName']},
  "event_id": @{triggerBody()?['id']}
}
```

#### **Save the Flow**

Click "Save"

---

## Part 4: Testing

### Test 1: Email → Violation

1. **Send yourself a test email:**
   - To: ziv.reshef-simchoni@hp.com
   - Subject: "Violation - Cold food"
   - Body: "The lunch was cold today at 12:45pm"

2. **Wait ~1-2 minutes**

3. **Check Power Automate:**
   - Go to "My flows"
   - Click on your violation flow
   - Check "28-day run history"
   - Should see "Succeeded"

4. **Check your app:**
   ```bash
   curl http://localhost:8000/api/violations \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```
   Should see new violation with AI analysis!

5. **Check frontend:**
   - Go to http://localhost:3000/violations
   - Should see new violation

### Test 2: Calendar → Meeting

1. **Create a test meeting in Outlook:**
   - Subject: "Weekly Sync - Nes Ziona Catering"
   - Date: Tomorrow at 10:00 AM
   - Duration: 1 hour

2. **Wait ~1-2 minutes**

3. **Check Power Automate:**
   - Go to "My flows"
   - Click on your meeting flow
   - Check "28-day run history"
   - Should see "Succeeded"

4. **Check your app:**
   ```bash
   curl http://localhost:8000/api/meetings \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```
   Should see new meeting!

5. **Check frontend:**
   - Go to http://localhost:3000/meetings
   - Should see imported meeting

---

## Part 5: Troubleshooting

### Flow Failed?

**Check Flow Run History:**
1. Go to "My flows"
2. Click on the flow
3. Click on failed run
4. See error details

**Common Issues:**

**HTTP 401/403:**
- Your webhook endpoint might require authentication
- Remove authentication requirement for webhooks
- OR: Add API key to Power Automate

**HTTP 500:**
- Check backend logs
- Verify data format matches expected

**Timeout:**
- ngrok connection dropped
- Restart ngrok
- Update flow with new URL

### ngrok Issues

**URL Changed:**
- ngrok free tier gives new URL each restart
- Update Power Automate flows with new URL
- OR: Use ngrok paid plan for static URL

**Connection Dropped:**
```bash
# Restart ngrok
ngrok http 8000

# Update flows with new URL
```

### No Violations Showing?

**Check:**
1. Backend running? `curl http://localhost:8000/api/webhooks/test`
2. ngrok running? Check ngrok dashboard: http://127.0.0.1:4040
3. Flow succeeded? Check Power Automate history
4. Database has data? Check backend logs

---

## Part 6: Production Deployment (Future)

### When Ready for Production:

**Option A: Deploy to Azure**
```bash
# Deploy backend to Azure App Service
az webapp up --name catering-ai-backend

# Get public URL: https://catering-ai-backend.azurewebsites.net
# Update Power Automate flows with this URL
```

**Option B: Deploy to AWS**
```bash
# Deploy to Elastic Beanstalk or Lambda
# Get public URL
# Update Power Automate flows
```

**Option C: HP Internal Server**
- Deploy on HP infrastructure
- Get internal URL
- Update Power Automate flows

---

## Summary

### What You Built:

✅ **Webhook Endpoints**
- `/api/webhooks/violations` - Receive emails
- `/api/webhooks/meetings` - Receive calendar events

✅ **Power Automate Flows**
- Email monitoring → Auto-import violations
- Calendar monitoring → Auto-import meetings

✅ **AI Processing**
- Automatic analysis on import
- Categorization, severity, root cause
- Pattern detection

### Next Email/Meeting:
1. Arrives in Outlook
2. Power Automate triggers (~1 min delay)
3. HTTP POST to your webhook
4. AI analysis automatically
5. Appears in your dashboard
6. **Zero manual work!**

---

## Time Saved

**Before:** Manual entry, copy-paste, ~5 min per violation
**After:** Automatic, AI-analyzed, ~0 min

**ROI:** Immediate! Every violation/meeting is now automated.

---

---

## Part 7: Microsoft Forms Integration (Inspector Reports)

Use Microsoft Forms (free with HP M365) for professional inspectors to submit inspection findings directly from their phone or tablet.

### Step 1: Create the Form

1. Go to **https://forms.office.com**
2. Sign in with your HP account
3. Click **"New Form"**
4. Set title: **טופס ביקורת מסעדה** (Restaurant Inspection Form)

### Step 2: Add Form Fields

| # | Field Label (Hebrew) | Type | Required | Options |
|---|---------------------|------|----------|---------|
| 1 | שם הבודק | Text | Yes | — |
| 2 | מסעדה | Choice | Yes | קרית גת - מסעדת בשר, קרית גת - מסעדת חלב, נס ציונה - מסעדת בשר, נס ציונה - מסעדת חלב |
| 3 | קטגוריה | Choice | Yes | ניקיון מטבח וציוד, ניקיון חדר אוכל, לבוש עובדים, חוסר בציוד סועד, משקל מנה לא תואם מפרט, מגוון המנות לא תואם תפריט, מנה עיקרית נגמרה בזמן הארוחה, חוסר עובדים, שירות, נקודות חיוביות |
| 4 | חומרה | Choice | Yes | נמוך, בינוני, גבוה, קריטי |
| 5 | תיאור הממצא | Long Text | Yes | — |
| 6 | תמונה | File Upload | No | Image types only |

**Tips:**
- For field 2 (מסעדה): Use "Choice" type, add all 4 options
- For field 3 (קטגוריה): One category per submission (submit multiple times for multiple findings)
- For field 6 (תמונה): Enable "File upload", limit to image types, max 1 file

### Step 3: Create Power Automate Flow

1. Go to **https://make.powerautomate.com**
2. Click **"Create" → "Automated cloud flow"**
3. Name: **Inspector Form to AI System**
4. Trigger: **"When a new response is submitted"** (Microsoft Forms)
5. Select your form from the dropdown

### Step 4: Configure the Flow

**Action 1: Get response details**
1. Click **"+ New step"**
2. Search for **"Get response details"** (Microsoft Forms)
3. Select your form
4. Response Id: Use dynamic content → **"Response Id"** from the trigger

**Action 2: HTTP POST to webhook**
1. Click **"+ New step"**
2. Search for **"HTTP"**
3. Configure:

```
Method: POST
URI: https://YOUR-URL/api/webhooks/violations

Headers:
Content-Type: application/json

Body:
{
  "source": "form",
  "sender_name": @{outputs('Get_response_details')?['body/r<FIELD_ID_1>']},
  "restaurant": @{outputs('Get_response_details')?['body/r<FIELD_ID_2>']},
  "category": @{outputs('Get_response_details')?['body/r<FIELD_ID_3>']},
  "severity": @{outputs('Get_response_details')?['body/r<FIELD_ID_4>']},
  "body": @{outputs('Get_response_details')?['body/r<FIELD_ID_5>']},
  "received": @{utcNow()}
}
```

**Important:** Replace `<FIELD_ID_N>` with the actual field IDs from your form.
To find field IDs: In "Get response details" action, click "Add dynamic content" and select each field.

### Step 5: Test the Flow

1. Open the form URL on your phone
2. Submit a test inspection finding:
   - שם הבודק: Test Inspector
   - מסעדה: קרית גת - מסעדת בשר
   - קטגוריה: ניקיון מטבח וציוד
   - חומרה: גבוה
   - תיאור הממצא: חלודה על מדפי אחסון במטבח
3. Wait 1-2 minutes
4. Check `/api/violations` — should see new violation with:
   - `source: "form"`
   - `restaurant_type: "meat"`
   - `category: "kitchen_cleanliness"`
   - `severity: "high"`

### How Form Data Is Processed

The webhook automatically:
1. Maps Hebrew restaurant name → `site_id` + `restaurant_type` (meat/dairy)
2. Maps Hebrew category → `ViolationCategory` enum
3. Maps Hebrew severity → `ViolationSeverity` enum
4. Skips AI classification (already provided by inspector)
5. Stores the full finding text for reporting

### Sharing the Form

- Click **"Share"** in Microsoft Forms
- Copy the form URL
- Share with inspectors via email or WhatsApp
- The form works on any device (phone, tablet, desktop)
- No login required for respondents (configure in form settings)

---

Need help with any step? Let me know!
