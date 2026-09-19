from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from ..config import settings
from ..db import execute, fetch, fetchrow, transaction
from ..errors import AppError
from ..scheduling import validate_appointment_slot

logger = logging.getLogger("appointment_assistant.public")
router = APIRouter(prefix="/api/public", tags=["Public Patient Portal"])


class PublicChatRequest(BaseModel):
    business_id: UUID | None = None
    conversation_id: UUID | None = None
    customer_id: UUID | None = None
    message: str = Field(min_length=1, max_length=2000)
    customer_name: str | None = None
    customer_phone: str | None = None
    customer_email: str | None = None


class PublicCustomerRegisterRequest(BaseModel):
    business_id: UUID
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=3, max_length=50)
    email: str | None = None


# ==============================================================================
# Helper: Resolve Default Active Business
# ==============================================================================

async def get_default_business_id() -> UUID:
    row = await fetchrow(
        "SELECT id FROM businesses WHERE status = 'ACTIVE' ORDER BY created_at ASC LIMIT 1"
    )
    if not row:
        raise AppError(404, "No active business found in system.", "BUSINESS_NOT_FOUND")
    return row["id"]


# ==============================================================================
# 0. Public Businesses List (For Customer Selection)
# ==============================================================================

@router.get("/businesses")
async def list_public_businesses() -> dict[str, Any]:
    rows = await fetch(
        """SELECT id, name, email, address, city, state_province, postal_code,
                  country_code, timezone, industry
             FROM businesses
            WHERE status = 'ACTIVE'
            ORDER BY name ASC"""
    )
    items = []
    for r in rows:
        address_parts = [
            part
            for part in [
                r["address"],
                r["city"],
                r["state_province"],
                r["postal_code"],
                r["country_code"],
            ]
            if part
        ]
        formatted_address = ", ".join(address_parts) if address_parts else "Address not specified"
        items.append({
            "id": str(r["id"]),
            "name": r["name"],
            "email": r["email"],
            "industry": r["industry"] or "Healthcare & Services",
            "address": formatted_address,
            "city": r["city"] or "",
            "timezone": r["timezone"] or "UTC",
        })
    return {"businesses": items}


# ==============================================================================
# 0b. Register Customer for a Selected Business (Stores in PostgreSQL)
# ==============================================================================

@router.post("/customers/register")
async def register_public_customer(payload: PublicCustomerRegisterRequest) -> dict[str, Any]:
    business = await fetchrow(
        "SELECT id, name, industry, city FROM businesses WHERE id = $1 AND status = 'ACTIVE'",
        payload.business_id,
    )
    if not business:
        raise AppError(404, "Business not found or inactive.", "BUSINESS_NOT_FOUND")

    clean_name = payload.name.strip()
    clean_phone = payload.phone.strip()
    clean_email = payload.email.strip() if payload.email and payload.email.strip() else None

    async with transaction() as conn:
        existing = await conn.fetchrow(
            """SELECT id, name, phone, email, created_at
                 FROM customers
                WHERE business_id = $1
                  AND (
                    (phone IS NOT NULL AND phone = $2) OR
                    ($3::text IS NOT NULL AND email IS NOT NULL AND email = $3)
                  )
                LIMIT 1""",
            payload.business_id,
            clean_phone,
            clean_email,
        )
        if existing:
            customer_id = existing["id"]
            await conn.execute(
                """UPDATE customers
                      SET name = COALESCE($1, name),
                          phone = COALESCE($2, phone),
                          email = COALESCE($3, email),
                          updated_at = CURRENT_TIMESTAMP
                    WHERE business_id = $4 AND id = $5""",
                clean_name,
                clean_phone,
                clean_email,
                payload.business_id,
                customer_id,
            )
            created = False
        else:
            customer_id = await conn.fetchval(
                """INSERT INTO customers (business_id, name, phone, email)
                   VALUES ($1, $2, $3, $4)
                   RETURNING id""",
                payload.business_id,
                clean_name,
                clean_phone,
                clean_email,
            )
            created = True

    return {
        "success": True,
        "created": created,
        "customer": {
            "id": str(customer_id),
            "business_id": str(payload.business_id),
            "business_name": business["name"],
            "name": clean_name,
            "phone": clean_phone,
            "email": clean_email,
        },
        "message": f"Customer successfully {'registered' if created else 'updated'} with {business['name']} in database."
    }


# ==============================================================================
# 1. Public Clinic / Business Info (For Patient Chat Header & Modal)
# ==============================================================================

@router.get("/clinic-info")
async def get_public_clinic_info(business_id: UUID | None = Query(None)) -> dict[str, Any]:
    resolved_id = business_id or await get_default_business_id()

    business = await fetchrow(
        """SELECT id, name, email, address, city, state_province, postal_code,
                  country_code, timezone, industry
             FROM businesses
            WHERE id = $1 AND status = 'ACTIVE'""",
        resolved_id,
    )
    if not business:
        raise AppError(404, "Business not found or inactive.", "NOT_FOUND")

    b_settings = await fetchrow(
        """SELECT appointment_duration_minutes, booking_window_days, maximum_appointments_per_day,
                  allow_cancellation, allow_reschedule, collect_phone, collect_email, confirmation_required
             FROM business_settings
            WHERE business_id = $1""",
        resolved_id,
    )

    hours = await fetch(
        """SELECT day_of_week::text, opens_at::text, closes_at::text
             FROM business_hours
            WHERE business_id = $1
            ORDER BY CASE day_of_week
              WHEN 'MONDAY' THEN 1 WHEN 'TUESDAY' THEN 2 WHEN 'WEDNESDAY' THEN 3
              WHEN 'THURSDAY' THEN 4 WHEN 'FRIDAY' THEN 5 WHEN 'SATURDAY' THEN 6
              WHEN 'SUNDAY' THEN 7 END""",
        resolved_id,
    )

    overrides = await fetch(
        """SELECT override_date::text, is_closed, opens_at::text, closes_at::text, reason
             FROM business_schedule_overrides
            WHERE business_id = $1 AND override_date >= CURRENT_DATE
            ORDER BY override_date LIMIT 10""",
        resolved_id,
    )

    address_parts = [
        part
        for part in [
            business["address"],
            business["city"],
            business["state_province"],
            business["postal_code"],
            business["country_code"],
        ]
        if part
    ]
    formatted_address = ", ".join(address_parts) if address_parts else "Clinic address not specified"

    return {
        "business": {
            "id": str(business["id"]),
            "name": business["name"],
            "email": business["email"],
            "industry": business["industry"] or "Healthcare & Wellness",
            "address": formatted_address,
            "timezone": business["timezone"] or "UTC",
        },
        "settings": {
            "appointment_duration_minutes": b_settings["appointment_duration_minutes"] if b_settings else 30,
            "booking_window_days": b_settings["booking_window_days"] if b_settings else 30,
            "allow_cancellation": b_settings["allow_cancellation"] if b_settings else True,
            "allow_reschedule": b_settings["allow_reschedule"] if b_settings else True,
        },
        "business_hours": [
            {
                "day_of_week": h["day_of_week"],
                "opens_at": h["opens_at"][:5] if h["opens_at"] else "09:00",
                "closes_at": h["closes_at"][:5] if h["closes_at"] else "17:00",
            }
            for h in hours
        ],
        "schedule_overrides": [
            {
                "override_date": o["override_date"],
                "is_closed": o["is_closed"],
                "reason": o["reason"],
            }
            for o in overrides
        ],
    }


# ==============================================================================
# 2. Public Patient Chat Endpoint
# ==============================================================================

@router.post("/chat")
async def public_chat(payload: PublicChatRequest, request: Request) -> dict[str, Any]:
    # 1. Resolve business
    business_id = payload.business_id or await get_default_business_id()
    business = await fetchrow(
        "SELECT id, name, timezone, industry, address, city FROM businesses WHERE id = $1 AND status = 'ACTIVE'",
        business_id,
    )
    if not business:
        raise AppError(404, "Clinic is currently inactive or not found.", "NOT_FOUND")

    # 2. Resolve customer and conversation
    conversation_id = payload.conversation_id or uuid4()
    clean_msg = payload.message.strip()

    resolved_customer_id = payload.customer_id
    clean_name = payload.customer_name.strip() if payload.customer_name and payload.customer_name.strip() else None
    clean_phone = payload.customer_phone.strip() if payload.customer_phone and payload.customer_phone.strip() else None
    clean_email = payload.customer_email.strip() if payload.customer_email and payload.customer_email.strip() else None

    async with transaction() as connection:
        if not resolved_customer_id and (clean_phone or clean_email):
            cust_row = await connection.fetchrow(
                """SELECT id, name, phone, email FROM customers
                    WHERE business_id = $1
                      AND (
                        ($2::text IS NOT NULL AND phone = $2) OR
                        ($3::text IS NOT NULL AND email IS NOT NULL AND email = $3)
                      )
                    LIMIT 1""",
                business_id,
                clean_phone,
                clean_email,
            )
            if cust_row:
                resolved_customer_id = cust_row["id"]
                if clean_name and clean_name != cust_row["name"]:
                    await connection.execute(
                        "UPDATE customers SET name = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
                        clean_name,
                        resolved_customer_id,
                    )
            elif clean_phone:
                resolved_customer_id = await connection.fetchval(
                    """INSERT INTO customers (business_id, name, phone, email)
                       VALUES ($1, $2, $3, $4)
                       RETURNING id""",
                    business_id,
                    clean_name or "Valued Customer",
                    clean_phone,
                    clean_email,
                )

        await connection.execute(
            """INSERT INTO conversations (id, business_id, customer_id, status)
               VALUES ($1, $2, $3, 'ACTIVE'::conversation_status)
               ON CONFLICT (id) DO UPDATE SET
                   last_message_at = CURRENT_TIMESTAMP,
                   customer_id = COALESCE(conversations.customer_id, EXCLUDED.customer_id)""",
            conversation_id,
            business_id,
            resolved_customer_id,
        )
        await connection.execute(
            """INSERT INTO conversation_state (conversation_id, business_id)
               VALUES ($1, $2)
               ON CONFLICT (conversation_id) DO NOTHING""",
            conversation_id,
            business_id,
        )
        recent_user = await connection.fetchval(
            """SELECT 1 FROM conversation_messages
                WHERE business_id = $1 AND conversation_id = $2 AND sender = 'CUSTOMER'
                  AND content = $3 AND sent_at >= CURRENT_TIMESTAMP - interval '10 seconds'""",
            business_id,
            conversation_id,
            clean_msg,
        )
        if not recent_user:
            await connection.execute(
                """INSERT INTO conversation_messages (business_id, conversation_id, sender, message_type, content)
                   VALUES ($1, $2, 'CUSTOMER', 'TEXT', $3)""",
                business_id,
                conversation_id,
                clean_msg,
            )

    # 3. Attempt n8n Webhook forward (try workflow-specific path first, then generic)
    n8n_urls = [
        "http://127.0.0.1:5678/webhook/ApptAssistant01/webhook/chat",
        "http://127.0.0.1:5678/webhook/chat",
    ]
    n8n_response_data: dict[str, Any] | None = None

    webhook_body = {
        "business_id": str(business_id),
        "conversation_id": str(conversation_id),
        "customer_id": str(resolved_customer_id) if resolved_customer_id else None,
        "message": clean_msg,
        "customer_name": clean_name,
        "customer_phone": clean_phone,
        "customer_email": clean_email,
    }

    try:
        async with httpx.AsyncClient(timeout=25.0) as http_client:
            for n8n_url in n8n_urls:
                try:
                    resp = await http_client.post(n8n_url, json=webhook_body)
                    if resp.status_code == 200:
                        n8n_response_data = resp.json()
                        break
                except Exception:
                    continue
    except Exception as e:
        logger.warning("n8n webhook call failed, falling back to direct assistant engine: %s", e)

    # 4. If n8n answered successfully and didn't fail with an LLM error
    if n8n_response_data and "reply" in n8n_response_data:
        ai_reply = str(n8n_response_data.get("reply", "")).strip()
        is_llm_error = "trouble processing that with the ai assistant" in ai_reply.lower()

        if not is_llm_error:
            recent_bot = await fetchrow(
                """SELECT 1 FROM conversation_messages
                    WHERE business_id = $1 AND conversation_id = $2 AND sender = 'AI'
                      AND content = $3 AND sent_at >= CURRENT_TIMESTAMP - interval '15 seconds'""",
                business_id,
                conversation_id,
                ai_reply,
            )
            if not recent_bot and ai_reply:
                await execute(
                    """INSERT INTO conversation_messages (business_id, conversation_id, sender, message_type, content)
                       VALUES ($1, $2, 'AI', 'TEXT', $3)""",
                    business_id,
                    conversation_id,
                    ai_reply,
                )
            return {
                "conversation_id": str(conversation_id),
                "business_id": str(business_id),
                "clinic_name": business["name"],
                "action": n8n_response_data.get("action", "RESPOND"),
                "reply": ai_reply,
                "workflow": n8n_response_data.get("workflow", "NO_CHANGE"),
                "data": n8n_response_data.get("data", {}),
            }

    # 5. Smart Direct Fallback & Recovery Engine
    # Check if conversation is in a progressive booking step in PostgreSQL
    state_row = await fetchrow(
        """SELECT current_step, collected_data FROM conversation_state
            WHERE business_id = $1 AND conversation_id = $2""",
        business_id,
        conversation_id,
    )
    col_data = (state_row["collected_data"] or {}) if state_row else {}
    step = (state_row["current_step"] if state_row and state_row["current_step"] else col_data.get("waiting_for", "none")).upper()

    normalized = clean_msg.lower().strip()

    # Case A: Waiting for phone number -> Complete the booking!
    if "PHONE" in step or col_data.get("waiting_for") == "phone":
        book_date_str = col_data.get("date") or col_data.get("requested_date")
        book_time_str = col_data.get("time") or col_data.get("selected_slot") or col_data.get("requested_time")
        cust_name = col_data.get("customer_name") or payload.customer_name or "Valued Patient"
        cust_phone = clean_msg

        if book_date_str and book_time_str:
            try:
                from zoneinfo import ZoneInfo
                from datetime import timedelta
                tz = ZoneInfo(business["timezone"] or "UTC")
                b_date = datetime.strptime(book_date_str.strip(), "%Y-%m-%d").date()
                b_time = datetime.strptime(book_time_str.strip()[:5], "%H:%M").time()
                start_dt = datetime.combine(b_date, b_time, tzinfo=tz)
                end_dt = start_dt + timedelta(minutes=30)

                async with transaction() as conn:
                    # Upsert customer
                    cid = resolved_customer_id
                    if not cid:
                        cid = await conn.fetchval(
                            """INSERT INTO customers (business_id, name, phone, email)
                               VALUES ($1, $2, $3, $4)
                               ON CONFLICT DO NOTHING RETURNING id""",
                            business_id,
                            cust_name,
                            cust_phone,
                            clean_email,
                        )
                        if not cid:
                            cid = await conn.fetchval(
                                """SELECT id FROM customers
                                    WHERE business_id = $1
                                      AND (phone = $2 OR ($3::text IS NOT NULL AND email = $3))
                                    LIMIT 1""",
                                business_id,
                                cust_phone,
                                clean_email,
                            )
                    else:
                        await conn.execute(
                            """UPDATE customers
                                  SET name = COALESCE(NULLIF($1, 'Valued Patient'), name),
                                      phone = COALESCE($2, phone),
                                      email = COALESCE($3, email),
                                      updated_at = CURRENT_TIMESTAMP
                                WHERE business_id = $4 AND id = $5""",
                            cust_name,
                            cust_phone,
                            clean_email,
                            business_id,
                            cid,
                        )

                    # Lookup customer email for confirmation if not explicitly provided in message
                    cust_email_to_notify = clean_email
                    if not cust_email_to_notify and cid:
                        c_info = await conn.fetchrow("SELECT email, name FROM customers WHERE id = $1", cid)
                        if c_info and c_info["email"]:
                            cust_email_to_notify = c_info["email"]
                            if not cust_name or cust_name == "Valued Patient":
                                cust_name = c_info["name"] or cust_name

                    # Insert appointment
                    apt_row = await conn.fetchrow(
                        """INSERT INTO appointments (
                               business_id, customer_id, conversation_id, status,
                               scheduled_start, scheduled_end, customer_name, customer_phone
                           ) VALUES ($1, $2, $3, 'CONFIRMED'::appointment_status, $4, $5, $6, $7)
                           RETURNING id, scheduled_start, scheduled_end""",
                        business_id,
                        cid,
                        conversation_id,
                        start_dt,
                        end_dt,
                        cust_name,
                        cust_phone,
                    )
                    # Update conversation status
                    await conn.execute(
                        """UPDATE conversations SET status = 'CLOSED'::conversation_status,
                                                    customer_id = $1, closed_at = CURRENT_TIMESTAMP
                            WHERE business_id = $2 AND id = $3""",
                        cid,
                        business_id,
                        conversation_id,
                    )
                    col_data["appointment_id"] = str(apt_row["id"])
                    col_data["start_datetime"] = apt_row["scheduled_start"].isoformat()
                    col_data["end_datetime"] = apt_row["scheduled_end"].isoformat()
                    col_data["customer_phone"] = cust_phone
                    col_data["waiting_for"] = "none"

                    await conn.execute(
                        """UPDATE conversation_state
                              SET current_step = 'BOOKED', current_intent = 'BOOKED',
                                  collected_data = $1, updated_at = CURRENT_TIMESTAMP
                            WHERE business_id = $2 AND conversation_id = $3""",
                        col_data,
                        business_id,
                        conversation_id,
                    )

                conf_reply = (
                    f"Your appointment with {business['name']} is confirmed for "
                    f"{b_date.strftime('%A, %B %d, %Y')} at {b_time.strftime('%I:%M %p')}. "
                    f"We look forward to seeing you, {cust_name}!"
                )
                await execute(
                    """INSERT INTO conversation_messages (business_id, conversation_id, sender, message_type, content)
                       VALUES ($1, $2, 'AI', 'TEXT', $3)""",
                    business_id,
                    conversation_id,
                    conf_reply,
                )

                if cust_email_to_notify:
                    try:
                        from ..mail import deliver_appointment_email
                        email_html = f"""
                        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; color: #1e293b; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px;">
                          <h2 style="margin-top: 0; color: #0f172a; font-size: 20px; font-weight: 600; border-bottom: 2px solid #0284c7; padding-bottom: 8px;">Appointment Confirmation</h2>
                          <p style="font-size: 15px; line-height: 1.6; color: #334155;">Dear {cust_name},</p>
                          <p style="font-size: 15px; line-height: 1.6; color: #334155;">Your appointment with <strong>{business['name']}</strong> has been confirmed. Below are your appointment details:</p>
                          <table style="width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px;">
                            <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 10px 0; font-weight: 600; color: #475569; width: 35%;">Booking Reference</td><td style="padding: 10px 0; color: #0f172a; font-family: monospace;">{str(apt_row['id'])[:8].upper()}</td></tr>
                            <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 10px 0; font-weight: 600; color: #475569;">Date</td><td style="padding: 10px 0; color: #0f172a;">{b_date.strftime('%A, %B %d, %Y')}</td></tr>
                            <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 10px 0; font-weight: 600; color: #475569;">Time</td><td style="padding: 10px 0; color: #0f172a;">{b_time.strftime('%I:%M %p')}</td></tr>
                            <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 10px 0; font-weight: 600; color: #475569;">Location</td><td style="padding: 10px 0; color: #0f172a;">{business['address'] or 'Clinic Reception'}</td></tr>
                          </table>
                          <p style="font-size: 14px; line-height: 1.6; color: #334155;">If you need to make any changes or reschedule, please reach out to our office.</p>
                          <div style="margin-top: 28px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 13px; color: #64748b; line-height: 1.5;">
                            <strong style="color: #334155;">{business['name']}</strong><br />
                            {business['address'] or 'Islamabad'}
                          </div>
                        </div>
                        """
                        await deliver_appointment_email(
                            to=cust_email_to_notify,
                            subject=f"Appointment Confirmation — {business['name']}",
                            html_body=email_html,
                            sender_name=business["name"],
                        )
                        logger.info("Sent appointment confirmation email to %s", cust_email_to_notify)
                    except Exception as mail_err:
                        logger.warning("Could not dispatch confirmation email: %s", mail_err)
                return {
                    "conversation_id": str(conversation_id),
                    "business_id": str(business_id),
                    "clinic_name": business["name"],
                    "action": "BOOKING_CONFIRMED",
                    "reply": conf_reply,
                    "workflow": "BOOKED",
                    "data": {
                        "appointment_id": str(apt_row["id"]),
                        "start_datetime": apt_row["scheduled_start"].isoformat(),
                        "end_datetime": apt_row["scheduled_end"].isoformat(),
                        "customer_name": cust_name,
                        "customer_phone": cust_phone,
                        "date": book_date_str,
                        "time": book_time_str,
                    },
                }
            except Exception as book_err:
                logger.error("Direct booking fallback error: %s", book_err)

    # Case B: Waiting for name
    elif "NAME" in step or col_data.get("waiting_for") == "name":
        col_data["customer_name"] = clean_msg
        col_data["waiting_for"] = "phone"
        await execute(
            """UPDATE conversation_state
                  SET current_step = 'WAITING_FOR_PHONE', collected_data = $1, updated_at = CURRENT_TIMESTAMP
                WHERE business_id = $2 AND conversation_id = $3""",
            col_data,
            business_id,
            conversation_id,
        )
        reply = f"Thank you, {clean_msg}. Please provide your phone number to complete your booking."
        await execute(
            """INSERT INTO conversation_messages (business_id, conversation_id, sender, message_type, content)
               VALUES ($1, $2, 'AI', 'TEXT', $3)""",
            business_id,
            conversation_id,
            reply,
        )
        return {
            "conversation_id": str(conversation_id),
            "business_id": str(business_id),
            "clinic_name": business["name"],
            "action": "RESPOND",
            "reply": reply,
            "workflow": "WAITING_FOR_PHONE",
            "data": col_data,
        }

    # Greetings
    if any(greeting in normalized for greeting in ["hi", "hello", "hey", "salam", "morning", "afternoon", "evening"]):
        reply = (
            f"Hello! Welcome to {business['name']}. I'm your AI Medical Receptionist. "
            "How can I assist you today? You can book an appointment, check available slots, "
            "or ask for clinic hours and location."
        )
        action = "RESPOND"
        workflow = "NO_CHANGE"
        data: dict[str, Any] = {}

    # Address / Location
    elif any(kw in normalized for kw in ["address", "location", "where are you", "where is the clinic", "directions"]):
        addr = f"{business['address']}, {business['city']}" if business['address'] else "our clinic"
        reply = f"{business['name']} is located at {addr}."
        action = "INFO"
        workflow = "BUSINESS_INFORMATION"
        data = {"address": addr}

    # Business Hours
    elif any(kw in normalized for kw in ["hours", "timings", "timing", "open", "close", "operating"]):
        hours_rows = await fetch(
            "SELECT day_of_week::text, opens_at::text, closes_at::text FROM business_hours WHERE business_id = $1 ORDER BY day_of_week",
            business_id,
        )
        if hours_rows:
            formatted = "; ".join(f"{h['day_of_week'].title()}: {h['opens_at'][:5]} - {h['closes_at'][:5]}" for h in hours_rows)
            reply = f"Our standard clinic hours are: {formatted}."
        else:
            reply = f"{business['name']} operates Monday to Friday, 09:00 to 17:00."
        action = "INFO"
        workflow = "BUSINESS_INFORMATION"
        data = {"hours": [dict(h) for h in hours_rows]}

    # Default friendly medical booking prompt
    else:
        reply = (
            f"I'm here to help you schedule with {business['name']}. "
            "Could you please tell me which date you would like to book your visit for? "
            "(For example: tomorrow, next Monday, or a specific date like 2026-09-22)."
        )
        action = "RESPOND"
        workflow = "WAITING_FOR_DATE"
        data = {}

    # Log fallback reply
    await execute(
        """INSERT INTO conversation_messages (business_id, conversation_id, sender, message_type, content)
           VALUES ($1, $2, 'AI', 'TEXT', $3)""",
        business_id,
        conversation_id,
        reply,
    )

    return {
        "conversation_id": str(conversation_id),
        "business_id": str(business_id),
        "clinic_name": business["name"],
        "action": action,
        "reply": reply,
        "workflow": workflow,
        "data": data,
    }


# ==============================================================================
# 3. Direct Public Patient Booking Endpoint
# ==============================================================================

class PublicBookingRequest(BaseModel):
    business_id: UUID | None = None
    customer_name: str = Field(min_length=1, max_length=120)
    customer_phone: str = Field(min_length=3, max_length=50)
    customer_email: str | None = None
    service_name: str = "General Consultation"
    date: str  # YYYY-MM-DD
    time_slot: str  # HH:MM
    notes: str | None = None


@router.post("/book")
async def public_book_appointment(payload: PublicBookingRequest) -> dict[str, Any]:
    resolved_id = payload.business_id or await get_default_business_id()
    business = await fetchrow(
        "SELECT id, name, timezone, address, city FROM businesses WHERE id = $1 AND status = 'ACTIVE'",
        resolved_id,
    )
    if not business:
        raise AppError(404, "Clinic is inactive or not found.", "NOT_FOUND")

    try:
        from zoneinfo import ZoneInfo
        from datetime import timedelta
        tz = ZoneInfo(business["timezone"] or "UTC")
        b_date = datetime.strptime(payload.date.strip(), "%Y-%m-%d").date()
        b_time = datetime.strptime(payload.time_slot.strip()[:5], "%H:%M").time()
        start_dt = datetime.combine(b_date, b_time, tzinfo=tz)
        end_dt = start_dt + timedelta(minutes=30)
    except Exception as e:
        raise AppError(400, f"Invalid date or time slot format: {e}", "INVALID_DATETIME")

    async with transaction() as conn:
        conflict = await conn.fetchval(
            """SELECT 1 FROM appointments
                WHERE business_id = $1
                  AND status = 'CONFIRMED'::appointment_status
                  AND scheduled_start < $3 AND scheduled_end > $2""",
            resolved_id,
            start_dt,
            end_dt,
        )
        if conflict:
            raise AppError(409, "This time slot is already reserved. Please select another slot.", "SLOT_CONFLICT")

        cid = await conn.fetchval(
            """INSERT INTO customers (business_id, name, phone, email)
               VALUES ($1, $2, $3, $4)
               RETURNING id""",
            resolved_id,
            payload.customer_name.strip(),
            payload.customer_phone.strip(),
            payload.customer_email.strip() if payload.customer_email else None,
        )

        apt_row = await conn.fetchrow(
            """INSERT INTO appointments (
                   business_id, customer_id, status,
                   scheduled_start, scheduled_end, customer_name, customer_phone, customer_email
               ) VALUES ($1, $2, 'CONFIRMED'::appointment_status, $3, $4, $5, $6, $7)
               RETURNING id, scheduled_start, scheduled_end""",
            resolved_id,
            cid,
            start_dt,
            end_dt,
            payload.customer_name.strip(),
            payload.customer_phone.strip(),
            payload.customer_email.strip() if payload.customer_email else None,
        )

    addr = f"{business['address']}, {business['city']}" if business['address'] else "Clinic Main Reception"

    return {
        "success": True,
        "appointment_id": str(apt_row["id"]),
        "business_id": str(resolved_id),
        "clinic_name": business["name"],
        "customer_name": payload.customer_name.strip(),
        "customer_phone": payload.customer_phone.strip(),
        "service_name": payload.service_name,
        "start_datetime": apt_row["scheduled_start"].isoformat(),
        "end_datetime": apt_row["scheduled_end"].isoformat(),
        "address": addr,
    }

