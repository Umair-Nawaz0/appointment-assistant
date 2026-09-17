from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
import httpx
import pytest

from app import db
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    await db.connect()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost:5173") as api:
        yield api
    await db.disconnect()


@pytest.mark.anyio
async def test_authentication_and_tenant_apis(client: httpx.AsyncClient):
    untrusted = await client.post(
        "/api/auth/forgot-password",
        headers={"Origin": "https://evil.example"},
        json={"email": "nobody@example.com"},
    )
    assert untrusted.status_code == 403
    preflight = await client.options(
        "/api/auth/signup",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"

    email = f"fastapi-{time.time_ns()}@example.com"
    signup = await client.post("/api/auth/signup", json={
        "businessName": "FastAPI Test Studio", "email": email,
        "password": "Production123", "timezone": "Asia/Karachi", "industry": "Wellness",
    }, headers={"Origin": "http://127.0.0.1:5173"})
    assert signup.status_code == 201, signup.text
    verification_code = signup.json()["devCode"]
    wrong_code = "999999" if verification_code == "000000" else "000000"
    wrong_verification = await client.post(
        "/api/auth/verify-email", json={"email": email, "code": wrong_code}
    )
    assert wrong_verification.status_code == 400
    verified = await client.post(
        "/api/auth/verify-email", json={"email": email, "code": verification_code}
    )
    assert verified.status_code == 200, verified.text

    login = await client.post("/api/auth/login", json={"email": email, "password": "Production123"})
    assert login.status_code == 200, login.text
    assert "appointment_session" in client.cookies
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["business"]["email"] == email

    business = await client.get("/api/business")
    assert business.status_code == 200
    updated_business = await client.put("/api/business", json={
        "name": "FastAPI Test Studio", "address": "123 Test Street", "city": "Lahore",
        "stateProvince": "Punjab", "postalCode": "54000", "countryCode": "pk",
        "industry": "Wellness", "timezone": "Asia/Karachi",
    })
    assert updated_business.status_code == 200, updated_business.text
    assert updated_business.json()["business"]["countryCode"] == "PK"

    # Test updating business profile with empty optional fields (should convert to None, not fail)
    empty_profile = await client.put("/api/business", json={
        "name": "FastAPI Test Studio", "address": "", "city": "",
        "stateProvince": "", "postalCode": "", "countryCode": "",
        "industry": "", "timezone": "Asia/Karachi",
        "extraForbiddenField": "shouldBeIgnored",
    })
    assert empty_profile.status_code == 200, empty_profile.text
    assert empty_profile.json()["business"]["countryCode"] is None

    settings = await client.put("/api/business/settings", json={
        "appointmentDurationMinutes": 45, "bookingWindowDays": 60, "maximumAppointmentsPerDay": 12,
        "allowCancellation": True, "allowReschedule": True, "collectPhone": False,
        "collectEmail": True, "confirmationRequired": True,
        "updatedAt": "2026-09-18T00:00:00Z", # extra field from get_settings
    })
    assert settings.status_code == 200, settings.text
    assert settings.json()["settings"]["appointmentDurationMinutes"] == 45

    # Test updating settings with empty maximum per day
    settings_empty_cap = await client.put("/api/business/settings", json={
        "appointmentDurationMinutes": 45, "bookingWindowDays": 60, "maximumAppointmentsPerDay": "",
        "allowCancellation": True, "allowReschedule": True, "collectPhone": False,
        "collectEmail": True, "confirmationRequired": True,
    })
    assert settings_empty_cap.status_code == 200, settings_empty_cap.text
    assert settings_empty_cap.json()["settings"]["maximumAppointmentsPerDay"] is None

    hours = await client.put("/api/business/hours", json={"hours": [
        {"dayOfWeek": "MONDAY", "opensAt": "09:00", "closesAt": "17:00"},
        {"dayOfWeek": "TUESDAY", "opensAt": "10:00", "closesAt": "18:00"},
    ]})
    assert hours.status_code == 200, hours.text
    assert len((await client.get("/api/business/hours")).json()["hours"]) == 2
    special_date = (datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat()
    special = await client.put(f"/api/business/overrides/{special_date}", json={
        "isClosed": False, "opensAt": "11:00", "closesAt": "15:00", "reason": "Special hours",
    })
    assert special.status_code == 200, special.text

    # Anonymous conversation without customer
    anon_conv = await client.post("/api/conversations", json={
        "externalConversationId": "visitor-session-123",
        "currentIntent": "GREETING",
    })
    assert anon_conv.status_code == 201, anon_conv.text
    anon_conv_id = anon_conv.json()["conversation"]["id"]
    anon_detail = await client.get(f"/api/conversations/{anon_conv_id}")
    assert anon_detail.status_code == 200
    assert anon_detail.json()["conversation"]["customerId"] is None

    # Customer enters booking flow -> create customer with contact info
    customer = await client.post("/api/customers", json={
        "name": "Ada Customer",
        "phone": "+15551234567",
        "email": "ada@example.com",
    })
    assert customer.status_code == 201, customer.text
    customer_id = customer.json()["customer"]["id"]
    customer_detail = await client.get(f"/api/customers/{customer_id}")
    assert customer_detail.status_code == 200
    assert customer_detail.json()["customer"]["email"] == "ada@example.com"
    renamed = await client.patch(f"/api/customers/{customer_id}", json={"name": "Ada Updated"})
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["customer"]["name"] == "Ada Updated"

    # Associate anonymous conversation with customer and book appointment
    associate = await client.patch(f"/api/conversations/{anon_conv_id}", json={"customerId": customer_id})
    assert associate.status_code == 200, associate.text
    assert associate.json()["conversation"]["customerId"] == customer_id
    conversation_id = anon_conv_id

    # 1. Reject booking on closed day (Sunday)
    now_utc = datetime.now(timezone.utc)
    days_to_sunday = (6 - now_utc.weekday()) % 7
    if days_to_sunday == 0:
        days_to_sunday = 7
    closed_sunday = (now_utc + timedelta(days=days_to_sunday)).replace(hour=6, minute=0, second=0, microsecond=0)
    closed_res = await client.post("/api/appointments", json={
        "customerId": customer_id,
        "conversationId": conversation_id,
        "scheduledStart": closed_sunday.isoformat(),
    })
    assert closed_res.status_code == 400
    assert closed_res.json()["error"]["code"] == "BUSINESS_CLOSED"

    # 2. Reject booking outside business hours (e.g. 2:00 AM PKT = 21:00 UTC previous day)
    days_to_monday = (0 - now_utc.weekday()) % 7
    if days_to_monday == 0:
        days_to_monday = 7
    # 06:00 UTC = 11:00 AM PKT (open: 09:00 - 17:00 PKT)
    valid_monday = (now_utc + timedelta(days=days_to_monday)).replace(hour=6, minute=0, second=0, microsecond=0)
    # 22:00 UTC = 03:00 AM PKT (outside hours)
    invalid_time = valid_monday.replace(hour=22)
    outside_res = await client.post("/api/appointments", json={
        "customerId": customer_id,
        "conversationId": conversation_id,
        "scheduledStart": invalid_time.isoformat(),
    })
    assert outside_res.status_code == 400
    assert outside_res.json()["error"]["code"] == "OUTSIDE_BUSINESS_HOURS"

    # 3. Successful booking during operating hours
    appointment = await client.post("/api/appointments", json={
        "customerId": customer_id,
        "conversationId": conversation_id,
        "scheduledStart": valid_monday.isoformat(),
    })
    assert appointment.status_code == 201, appointment.text
    assert appointment.json()["appointment"]["customerEmail"] == "ada@example.com"
    appointment_id = appointment.json()["appointment"]["id"]

    # 4. Reject conflicting overlapping slot
    conflict_res = await client.post("/api/appointments", json={
        "customerId": customer_id,
        "conversationId": conversation_id,
        "scheduledStart": valid_monday.isoformat(),
    })
    assert conflict_res.status_code == 409
    assert conflict_res.json()["error"]["code"] == "SLOT_CONFLICT"

    appointment_list = await client.get("/api/appointments?limit=100&status=PENDING")
    assert appointment_list.status_code == 200 and appointment_list.json()["total"] == 1
    confirmed = await client.patch(f"/api/appointments/{appointment_id}", json={"status": "CONFIRMED"})
    assert confirmed.status_code == 200, confirmed.text

    message = await client.post(f"/api/conversations/{conversation_id}/messages", json={"content": "Hello from website AI assistant"})
    assert message.status_code == 201, message.text
    detail = await client.get(f"/api/conversations/{conversation_id}")
    assert detail.status_code == 200 and len(detail.json()["messages"]) == 1
    state = await client.patch(f"/api/conversations/{conversation_id}/state", json={
        "currentIntent": "BOOK_APPOINTMENT", "currentStep": "CONFIRM_TIME",
        "collectedData": {"customerId": customer_id}, "contextSummary": "Customer selected a time.",
        "lastAiResponse": "Would you like to confirm?",
    })
    assert state.status_code == 200, state.text
    closed = await client.patch(f"/api/conversations/{conversation_id}/status", json={"status": "CLOSED"})
    assert closed.status_code == 200, closed.text
    reopened = await client.patch(f"/api/conversations/{conversation_id}/status", json={"status": "ACTIVE"})
    assert reopened.status_code == 200, reopened.text
    conversation_list = await client.get("/api/conversations?limit=100")
    assert conversation_list.status_code == 200 and conversation_list.json()["total"] == 1

    summary = await client.get("/api/dashboard/summary")
    assert summary.status_code == 200, summary.text
    assert summary.json()["metrics"]["totalCustomers"] == 1
    assert (await client.delete(f"/api/business/overrides/{special_date}")).status_code == 204
    logout = await client.post("/api/auth/logout")
    assert logout.status_code == 204
    assert (await client.get("/api/auth/me")).status_code == 401

    forgot = await client.post("/api/auth/forgot-password", json={"email": email})
    assert forgot.status_code == 200, forgot.text
    reset_code = forgot.json()["devCode"]
    reset = await client.post("/api/auth/reset-password", json={
        "email": email, "code": reset_code, "password": "Replacement456",
    })
    assert reset.status_code == 200, reset.text
    old_login = await client.post("/api/auth/login", json={"email": email, "password": "Production123"})
    assert old_login.status_code == 401
    new_login = await client.post("/api/auth/login", json={"email": email, "password": "Replacement456"})
    assert new_login.status_code == 200, new_login.text
