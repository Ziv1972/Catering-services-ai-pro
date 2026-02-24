"""
API endpoint tests for all routes.
Uses in-memory SQLite + dependency-overridden FastAPI test client.
"""
from datetime import datetime, timedelta, date

from backend.models.meeting import Meeting, MeetingType
from backend.models.complaint import Complaint, ComplaintSource, ComplaintStatus
from backend.models.proforma import Proforma, ProformaItem
from backend.models.supplier import Supplier
from backend.models.operations import Anomaly
from backend.models.historical_data import HistoricalMealData
from backend.models.menu_compliance import MenuCheck, CheckResult


# ===================== HEALTH / ROOT =====================


async def test_root(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "running"


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


# ===================== AUTH =====================


async def test_login_success(unauth_client, seed_data):
    r = await unauth_client.post(
        "/api/auth/login",
        data={"username": "test@hp.com", "password": "testpass123"},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()


async def test_login_wrong_password(unauth_client, seed_data):
    r = await unauth_client.post(
        "/api/auth/login",
        data={"username": "test@hp.com", "password": "wrong"},
    )
    assert r.status_code == 401


async def test_register_new_user(unauth_client, seed_data):
    r = await unauth_client.post(
        "/api/auth/register",
        json={"email": "new@hp.com", "full_name": "New User", "password": "pass123"},
    )
    assert r.status_code == 200
    assert r.json()["email"] == "new@hp.com"


async def test_register_duplicate_email(unauth_client, seed_data):
    r = await unauth_client.post(
        "/api/auth/register",
        json={"email": "test@hp.com", "full_name": "Dup", "password": "pass123"},
    )
    assert r.status_code == 400


async def test_get_me(client):
    r = await client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "test@hp.com"


async def test_protected_route_no_token(unauth_client, seed_data):
    r = await unauth_client.get("/api/auth/me")
    assert r.status_code == 401


# ===================== MEETINGS =====================


async def test_create_meeting(client, seed_data):
    r = await client.post("/api/meetings/", json={
        "title": "Weekly Sync",
        "meeting_type": "site_manager",
        "scheduled_at": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "duration_minutes": 60,
        "site_id": seed_data["nz"].id,
    })
    assert r.status_code == 200
    assert r.json()["title"] == "Weekly Sync"


async def test_list_meetings(client, db_session, seed_data):
    m = Meeting(
        title="Test Meeting",
        meeting_type=MeetingType.OTHER,
        scheduled_at=datetime.utcnow() + timedelta(days=2),
        duration_minutes=30,
    )
    db_session.add(m)
    await db_session.commit()

    r = await client.get("/api/meetings/", params={"upcoming_only": True})
    assert r.status_code == 200
    assert len(r.json()) >= 1


async def test_get_meeting(client, db_session, seed_data):
    m = Meeting(
        title="Detail Test",
        meeting_type=MeetingType.VENDOR,
        scheduled_at=datetime.utcnow() + timedelta(days=3),
    )
    db_session.add(m)
    await db_session.commit()
    await db_session.refresh(m)

    r = await client.get(f"/api/meetings/{m.id}")
    assert r.status_code == 200
    assert r.json()["title"] == "Detail Test"


async def test_get_meeting_not_found(client):
    r = await client.get("/api/meetings/9999")
    assert r.status_code == 404


# ===================== COMPLAINTS =====================


async def test_list_complaints(client, db_session, seed_data):
    c = Complaint(
        complaint_text="Food was cold",
        source=ComplaintSource.MANUAL,
        received_at=datetime.utcnow(),
        status=ComplaintStatus.NEW,
    )
    db_session.add(c)
    await db_session.commit()

    r = await client.get("/api/complaints/", params={"days": 7})
    assert r.status_code == 200
    assert len(r.json()) >= 1


async def test_get_complaint(client, db_session, seed_data):
    c = Complaint(
        complaint_text="Service was slow",
        source=ComplaintSource.EMAIL,
        received_at=datetime.utcnow(),
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)

    r = await client.get(f"/api/complaints/{c.id}")
    assert r.status_code == 200
    assert r.json()["complaint_text"] == "Service was slow"


async def test_acknowledge_complaint(client, db_session, seed_data):
    c = Complaint(
        complaint_text="No vegetarian options",
        source=ComplaintSource.MANUAL,
        received_at=datetime.utcnow(),
        status=ComplaintStatus.NEW,
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)

    r = await client.post(f"/api/complaints/{c.id}/acknowledge")
    assert r.status_code == 200
    assert "acknowledged" in r.json()["message"].lower()


async def test_resolve_complaint(client, db_session, seed_data):
    c = Complaint(
        complaint_text="Cold soup",
        source=ComplaintSource.MANUAL,
        received_at=datetime.utcnow(),
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)

    r = await client.post(
        f"/api/complaints/{c.id}/resolve",
        json={"resolution_notes": "Fixed temperature controls"},
    )
    assert r.status_code == 200


async def test_weekly_summary(client, seed_data):
    r = await client.get("/api/complaints/summary/weekly")
    assert r.status_code == 200
    assert "total_complaints" in r.json()


async def test_active_patterns(client, seed_data):
    r = await client.get("/api/complaints/patterns/active")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ===================== PROFORMAS =====================


async def test_list_proformas(client, db_session, seed_data):
    s = Supplier(name="TestVendor", email="v@test.com")
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)

    p = Proforma(
        supplier_id=s.id,
        invoice_date=date.today(),
        total_amount=5000,
        currency="ILS",
        status="pending",
    )
    db_session.add(p)
    await db_session.commit()

    r = await client.get("/api/proformas/", params={"months": 6})
    assert r.status_code == 200
    assert len(r.json()) >= 1


async def test_get_proforma(client, db_session, seed_data):
    s = Supplier(name="DetailVendor", email="d@test.com")
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)

    p = Proforma(
        supplier_id=s.id,
        invoice_date=date.today(),
        total_amount=3000,
        currency="ILS",
        status="paid",
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)

    item = ProformaItem(
        proforma_id=p.id,
        product_name="Chicken Breast",
        quantity=50,
        unit="kg",
        unit_price=30,
        total_price=1500,
        flagged=False,
    )
    db_session.add(item)
    await db_session.commit()

    r = await client.get(f"/api/proformas/{p.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["total_amount"] == 3000
    assert len(data["items"]) == 1


async def test_vendor_spending(client, db_session, seed_data):
    s = Supplier(name="SpendVendor", email="s@test.com")
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)

    for i in range(3):
        p = Proforma(
            supplier_id=s.id,
            invoice_date=date.today() - timedelta(days=30 * i),
            total_amount=10000 + i * 1000,
            currency="ILS",
            status="paid",
        )
        db_session.add(p)
    await db_session.commit()

    r = await client.get("/api/proformas/vendor-spending/summary", params={"months": 12})
    assert r.status_code == 200
    data = r.json()
    assert "grand_total" in data
    assert data["grand_total"] > 0


# ===================== ANOMALIES =====================


async def test_list_anomalies(client, db_session, seed_data):
    a = Anomaly(
        anomaly_type="price_spike",
        entity_type="product",
        entity_id=1,
        detected_at=date.today(),
        description="Chicken price spiked 25%",
        severity="high",
        expected_value=30.0,
        actual_value=37.5,
        variance_percent=25.0,
    )
    db_session.add(a)
    await db_session.commit()

    r = await client.get("/api/anomalies/")
    assert r.status_code == 200
    assert len(r.json()) >= 1


async def test_acknowledge_anomaly(client, db_session, seed_data):
    a = Anomaly(
        anomaly_type="usage_spike",
        entity_type="site",
        entity_id=1,
        detected_at=date.today(),
        description="Usage spike at Nes Ziona",
        severity="medium",
    )
    db_session.add(a)
    await db_session.commit()
    await db_session.refresh(a)

    r = await client.post(f"/api/anomalies/{a.id}/acknowledge")
    assert r.status_code == 200


async def test_resolve_anomaly(client, db_session, seed_data):
    a = Anomaly(
        anomaly_type="price_spike",
        entity_type="product",
        entity_id=1,
        detected_at=date.today(),
        description="Test anomaly",
        severity="low",
    )
    db_session.add(a)
    await db_session.commit()
    await db_session.refresh(a)

    r = await client.post(
        f"/api/anomalies/{a.id}/resolve",
        json={"resolution_notes": "Seasonal price change, expected"},
    )
    assert r.status_code == 200


# ===================== HISTORICAL =====================


async def test_historical_meals(client, db_session, seed_data):
    for i in range(5):
        meal = HistoricalMealData(
            site_id=seed_data["nz"].id,
            date=date.today() - timedelta(days=i),
            meal_count=200 + i * 10,
            cost=3000 + i * 100,
        )
        db_session.add(meal)
    await db_session.commit()

    r = await client.get("/api/historical/meals")
    assert r.status_code == 200
    assert len(r.json()) >= 5


async def test_historical_analytics(client, db_session, seed_data):
    for i in range(10):
        meal = HistoricalMealData(
            site_id=seed_data["nz"].id,
            date=date.today() - timedelta(days=i * 7),
            meal_count=200,
            cost=3000,
        )
        db_session.add(meal)
    await db_session.commit()

    r = await client.get("/api/historical/analytics")
    assert r.status_code == 200
    data = r.json()
    assert "counts" in data


# ===================== MENU COMPLIANCE =====================


async def test_list_menu_checks(client, db_session, seed_data):
    mc = MenuCheck(
        site_id=seed_data["nz"].id,
        checked_at=date.today(),
        month="2026-02",
        year=2026,
    )
    db_session.add(mc)
    await db_session.commit()

    r = await client.get("/api/menu-compliance/checks")
    assert r.status_code == 200
    assert len(r.json()) >= 1


async def test_get_menu_check(client, db_session, seed_data):
    mc = MenuCheck(
        site_id=seed_data["kg"].id,
        checked_at=date.today(),
        month="2026-01",
        year=2026,
    )
    db_session.add(mc)
    await db_session.commit()
    await db_session.refresh(mc)

    cr = CheckResult(
        menu_check_id=mc.id,
        rule_name="Kosher Separation",
        rule_category="dietary",
        passed=True,
        severity="info",
    )
    db_session.add(cr)
    await db_session.commit()

    r = await client.get(f"/api/menu-compliance/checks/{mc.id}")
    assert r.status_code == 200


async def test_menu_compliance_stats(client, seed_data):
    r = await client.get("/api/menu-compliance/stats")
    assert r.status_code == 200


# ===================== DASHBOARD =====================


async def test_dashboard(client, seed_data):
    r = await client.get("/api/dashboard/")
    assert r.status_code == 200
    data = r.json()
    assert "upcoming_meetings" in data
    assert "total_sites" in data


# ===================== WEBHOOKS =====================


async def test_webhook_test_endpoint(unauth_client, seed_data):
    r = await unauth_client.get("/api/webhooks/test")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_webhook_meeting_non_catering(unauth_client, db_session, seed_data):
    r = await unauth_client.post("/api/webhooks/meetings", json={
        "subject": "Team Standup",
        "start": "2026-03-01T09:00:00Z",
        "end": "2026-03-01T09:30:00Z",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "skipped"


async def test_webhook_meeting_catering(unauth_client, db_session, seed_data):
    r = await unauth_client.post("/api/webhooks/meetings", json={
        "subject": "Weekly Sync - Site Manager Nes Ziona",
        "start": "2026-03-01T10:00:00Z",
        "end": "2026-03-01T11:00:00Z",
        "event_id": "outlook-test-123",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "created"
