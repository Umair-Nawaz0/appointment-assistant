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
    profile = business.json()["business"]
    updated_business = await client.put("/api/business", json={
        "name": "FastAPI Test Studio", "address": "123 Test Street", "city": "Lahore",
        "stateProvince": "Punjab", "postalCode": "54000", "countryCode": "pk",
        "industry": "Wellness", "timezone": "Asia/Karachi",
    })
    assert updated_business.status_code == 200, updated_business.text
    assert updated_business.json()["business"]["countryCode"] == "PK"

    settings = await client.put("/api/business/settings", json={
        "appointmentDurationMinutes": 45, "bookingWindowDays": 60, "maximumAppointmentsPerDay": 12,
        "allowCancellation": True, "allowReschedule": True, "collectPhone": False,
        "collectEmail": True, "confirmationRequired": True,
    })
    assert settings.status_code == 200, settings.text
    assert settings.json()["settings"]["appointmentDurationMinutes"] == 45
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
    channels = await client.get("/api/business/channels")
    assert channels.status_code == 200 and len(channels.json()["channels"]) == 6
    website = await client.put("/api/business/channels/WEBSITE", json={
        "enabled": True, "provider": "internal", "externalAccountId": f"fastapi-{time.time_ns()}", "metadata": {"source": "test"},
    })
    assert website.status_code == 200, website.text

    customer = await client.post("/api/customers", json={
        "name": "Ada Customer",
        "identities": [{"channel": "EMAIL", "identifier": "ada@example.com", "isPrimary": True}],
    })
    assert customer.status_code == 201, customer.text
    customer_id = customer.json()["customer"]["id"]
    customer_detail = await client.get(f"/api/customers/{customer_id}")
    assert customer_detail.status_code == 200
    renamed = await client.patch(f"/api/customers/{customer_id}", json={"name": "Ada Updated"})
    assert renamed.status_code == 200, renamed.text
    phone = await client.post(f"/api/customers/{customer_id}/identities", json={
        "channel": "PHONE", "identifier": "+15551234567", "isPrimary": True,
    })
    assert phone.status_code == 201, phone.text
    phone_id = phone.json()["identity"]["id"]
    assert (await client.delete(f"/api/customers/{customer_id}/identities/{phone_id}")).status_code == 204

    appointment = await client.post("/api/appointments", json={
        "customerId": customer_id,
        "scheduledStart": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        "createdChannel": "WEBSITE",
    })
    assert appointment.status_code == 201, appointment.text
    assert appointment.json()["appointment"]["customerEmail"] == "ada@example.com"
    appointment_id = appointment.json()["appointment"]["id"]
    appointment_list = await client.get("/api/appointments?limit=100&status=PENDING")
    assert appointment_list.status_code == 200 and appointment_list.json()["total"] == 1
    confirmed = await client.patch(f"/api/appointments/{appointment_id}", json={"status": "CONFIRMED"})
    assert confirmed.status_code == 200, confirmed.text

    conversation = await client.post("/api/conversations", json={
        "customerId": customer_id, "channel": "WEBSITE", "currentIntent": "BOOK_APPOINTMENT",
    })
    assert conversation.status_code == 201, conversation.text
    conversation_id = conversation.json()["conversation"]["id"]
    message = await client.post(f"/api/conversations/{conversation_id}/messages", json={"content": "Hello from FastAPI"})
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
