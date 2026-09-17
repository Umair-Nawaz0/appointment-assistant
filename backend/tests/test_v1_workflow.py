from __future__ import annotations

from datetime import datetime, timedelta, timezone
import httpx
import pytest

from app import db
from app.config import settings
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    await db.connect()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost:4000") as api:
        yield api
    await db.disconnect()


@pytest.mark.anyio
async def test_v1_workflow_endpoints(client: httpx.AsyncClient):
    headers = {"X-API-Key": settings.backend_api_key}
    business_id = "00000000-0000-4000-8000-000000000001"
    conversation_id = "00000000-0000-4000-8000-000000000099"

    # 1. API key authentication enforcement
    unauth = await client.get(f"/api/v1/businesses/{business_id}/context")
    assert unauth.status_code == 401

    wrong_key = await client.get(f"/api/v1/businesses/{business_id}/context", headers={"X-API-Key": "wrong"})
    assert wrong_key.status_code == 401

    # 2. Get business context
    ctx = await client.get(f"/api/v1/businesses/{business_id}/context", headers=headers)
    assert ctx.status_code == 200
    data = ctx.json()
    assert data["business"]["name"] == "Demo Wellness Studio"
    assert "business_hours" in data
    assert len(data["business_hours"]) > 0

    # 3. Validate chat session
    session = await client.post(
        "/api/v1/chat/sessions/validate",
        headers=headers,
        json={"business_id": business_id, "conversation_id": conversation_id},
    )
    assert session.status_code == 200
    assert session.json()["authorized"] is True

    # 4. Save and Get conversation state
    save_conv = await client.put(
        f"/api/v1/conversations/{conversation_id}",
        headers=headers,
        json={
            "business_id": business_id,
            "current_state": "WAITING_FOR_DATE",
            "status": "ACTIVE",
            "state_json": {
                "waiting_for": "date",
                "last_user_message": "Hello workflow test",
                "last_assistant_message": "How can I help you?",
            },
        },
    )
    assert save_conv.status_code == 200

    get_conv = await client.get(
        f"/api/v1/conversations/{conversation_id}?business_id={business_id}",
        headers=headers,
    )
    assert get_conv.status_code == 200
    assert get_conv.json()["conversation"]["current_state"] == "WAITING_FOR_DATE"

    # 5. Check date validation
    future_date = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")
    val_date = await client.get(
        f"/api/v1/appointments/validate-date?business_id={business_id}&date={future_date}&time=10:00",
        headers=headers,
    )
    assert val_date.status_code == 200

    # Outside operating hours (02:00)
    val_out_hours = await client.get(
        f"/api/v1/appointments/validate-date?business_id={business_id}&date={future_date}&time=02:00",
        headers=headers,
    )
    assert val_out_hours.status_code == 200
    assert val_out_hours.json()["valid"] is False
    assert val_out_hours.json()["reason"] == "OUTSIDE_BUSINESS_HOURS"

    # Past date validation
    past_val = await client.get(
        f"/api/v1/appointments/validate-date?business_id={business_id}&date=2020-01-01",
        headers=headers,
    )
    assert past_val.status_code == 200
    assert past_val.json()["valid"] is False

    # 6. Check availability
    avail = await client.get(
        f"/api/v1/appointments/check-availability?business_id={business_id}&date={future_date}",
        headers=headers,
    )
    assert avail.status_code == 200
    slots = avail.json()["available_slots"]

    # Reject booking on closed day (Saturday)
    now_utc = datetime.now(timezone.utc)
    days_to_sat = (5 - now_utc.weekday()) % 7
    if days_to_sat == 0:
        days_to_sat = 7
    saturday_date = (now_utc + timedelta(days=days_to_sat)).strftime("%Y-%m-%d")
    closed_book = await client.post(
        "/api/v1/appointments/book",
        headers=headers,
        json={
            "business_id": business_id,
            "date": saturday_date,
            "time": "10:00",
            "customer_name": "Test Customer",
            "customer_phone": "+1999888777",
        },
    )
    assert closed_book.status_code == 200
    assert closed_book.json()["success"] is False
    assert closed_book.json()["code"] == "BUSINESS_CLOSED"

    # Reject booking outside business hours (02:00)
    outside_book = await client.post(
        "/api/v1/appointments/book",
        headers=headers,
        json={
            "business_id": business_id,
            "date": future_date,
            "time": "02:00",
            "customer_name": "Test Customer",
            "customer_phone": "+1999888777",
        },
    )
    assert outside_book.status_code == 200
    assert outside_book.json()["success"] is False
    assert outside_book.json()["code"] == "OUTSIDE_BUSINESS_HOURS"

    # 7. Book appointment if slots exist
    if slots:
        target_slot = slots[0]
        book = await client.post(
            "/api/v1/appointments/book",
            headers=headers,
            json={
                "business_id": business_id,
                "date": future_date,
                "time": target_slot,
                "customer_name": "Test Customer",
                "customer_phone": "+1999888777",
                "conversation_id": conversation_id,
            },
        )
        assert book.status_code == 200
        apt_id = book.json()["appointment_id"]
        assert book.json()["success"] is True

        # 8. Cancel appointment
        cancel = await client.post(
            "/api/v1/appointments/cancel",
            headers=headers,
            json={
                "business_id": business_id,
                "appointment_id": apt_id,
                "cancellation_reason": "Automated test cancel",
            },
        )
        assert cancel.status_code == 200
        assert cancel.json()["status"] == "CANCELLED"
