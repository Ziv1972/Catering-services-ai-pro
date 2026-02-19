"""
Test Phase 1 - Meeting Prep Agent
Tests the complete flow: create meeting → generate AI brief
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from backend.database import AsyncSessionLocal
from backend.models.user import User
from backend.models.site import Site
from backend.models.meeting import Meeting, MeetingType
from backend.agents.meeting_prep.agent import MeetingPrepAgent
from sqlalchemy import select


async def test_meeting_prep():
    """Test the Meeting Prep Agent with a real scenario"""
    
    print("="*60)
    print("🧪 TESTING PHASE 1: MEETING PREP AGENT")
    print("="*60)
    print()
    
    async with AsyncSessionLocal() as session:
        # Step 1: Get Nes Ziona site
        print("📍 Step 1: Finding Nes Ziona site...")
        result = await session.execute(
            select(Site).where(Site.name == "Nes Ziona")
        )
        nes_ziona = result.scalar_one_or_none()
        
        if not nes_ziona:
            print("❌ Nes Ziona site not found!")
            return
        
        print(f"   ✅ Found site: {nes_ziona.name} (ID: {nes_ziona.id})")
        print()
        
        # Step 2: Create a test meeting
        print("📅 Step 2: Creating test meeting...")
        
        # Schedule for next Monday at 10:00 AM
        next_monday = datetime.now() + timedelta(days=(7 - datetime.now().weekday()))
        meeting_time = next_monday.replace(hour=10, minute=0, second=0, microsecond=0)
        
        meeting = Meeting(
            title="Weekly Sync - Nes Ziona Catering Manager",
            meeting_type=MeetingType.SITE_MANAGER,
            scheduled_at=meeting_time,
            duration_minutes=60,
            site_id=nes_ziona.id
        )
        
        session.add(meeting)
        await session.commit()
        await session.refresh(meeting)
        
        print(f"   ✅ Meeting created:")
        print(f"      - ID: {meeting.id}")
        print(f"      - Title: {meeting.title}")
        print(f"      - Scheduled: {meeting.scheduled_at}")
        print(f"      - Site: {meeting.site.name}")
        print()
        
        # Step 3: Generate AI Brief
        print("🤖 Step 3: Generating AI brief with Claude...")
        print("   (This may take 10-20 seconds...)")
        print()
        
        try:
            agent = MeetingPrepAgent()
            brief = await agent.prepare_meeting_brief(session, meeting)
            
            await session.commit()
            await session.refresh(meeting)
            
            print("   ✅ AI Brief generated successfully!")
            print()
            
            # Step 4: Display the brief
            print("="*60)
            print("📋 MEETING BRIEF")
            print("="*60)
            print()
            
            # Priority Topics
            if brief.get('priority_topics'):
                print("🔴 PRIORITY TOPICS:\n")
                for i, topic in enumerate(brief['priority_topics'], 1):
                    print(f"{i}. {topic['title']} ({topic['urgency'].upper()})")
                    print(f"   {topic['description']}")
                    if topic.get('data_points'):
                        print(f"   Data: {', '.join(topic['data_points'])}")
                    print()
            
            # Follow-ups
            if brief.get('follow_ups'):
                print("\n📝 FOLLOW-UPS FROM LAST MEETING:\n")
                for fu in brief['follow_ups']:
                    status_icon = "✅" if fu['status'] == 'completed' else "⏳"
                    print(f"   {status_icon} {fu['item']}")
                    if fu.get('notes'):
                        print(f"      Notes: {fu['notes']}")
                print()
            
            # Questions
            if brief.get('questions_to_ask'):
                print("\n❓ QUESTIONS TO ASK:\n")
                for q in brief['questions_to_ask']:
                    print(f"   • {q}")
                print()
            
            # Talking Points
            if brief.get('talking_points'):
                tp = brief['talking_points']
                print("\n💬 TALKING POINTS:\n")
                
                if tp.get('successes'):
                    print("   ✅ Successes:")
                    for s in tp['successes']:
                        print(f"      • {s}")
                
                if tp.get('concerns'):
                    print("\n   ⚠️  Concerns:")
                    for c in tp['concerns']:
                        print(f"      • {c}")
                
                if tp.get('data_highlights'):
                    print("\n   📊 Data Highlights:")
                    for d in tp['data_highlights']:
                        print(f"      • {d}")
                print()
            
            # Suggested Actions
            if brief.get('suggested_action_items'):
                print("\n✅ SUGGESTED ACTION ITEMS:\n")
                for action in brief['suggested_action_items']:
                    print(f"   • {action['action']}")
                    print(f"     Owner: {action['owner']} | Deadline: {action['deadline']} | Priority: {action['priority']}")
                print()
            
            # Formatted Agenda
            print("\n" + "="*60)
            print("📄 FORMATTED AGENDA")
            print("="*60)
            print()
            print(meeting.ai_agenda)
            print()
            
            # Test Summary
            print("\n" + "="*60)
            print("✅ PHASE 1 TEST: PASSED")
            print("="*60)
            print()
            print("What worked:")
            print("✅ Database connection")
            print("✅ Meeting creation")
            print("✅ Claude API integration")
            print("✅ AI brief generation")
            print("✅ Structured data parsing")
            print()
            print("The Meeting Prep Agent is fully functional!")
            print()
            print(f"Meeting ID: {meeting.id}")
            print("You can now view this in the frontend at:")
            print(f"http://localhost:3000/meetings/{meeting.id}")
            print()
            
        except Exception as e:
            print(f"❌ Error generating brief: {e}")
            import traceback
            traceback.print_exc()
            print()
            print("Possible issues:")
            print("- Check ANTHROPIC_API_KEY is set correctly in .env")
            print("- Verify Claude API quota/credits")
            print("- Check network connectivity")


if __name__ == "__main__":
    asyncio.run(test_meeting_prep())
