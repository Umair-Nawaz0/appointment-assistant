from __future__ import annotations

from datetime import date as dt_date, datetime, time as dt_time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..config import settings
from ..db import execute, fetch, fetchrow, transaction
from ..errors import AppError
from ..scheduling import validate_appointment_slot

router = APIRouter(prefix="/api/v1", tags=["Workflow v1 API"])


def _verify_api_key(x_api_key: str | None = Header(None)) -> None:
    if not x_api_key or x_api_key.strip() != settings.backend_api_key.strip():
        raise AppError(401, "Invalid or missing X-API-Key header.", "UNAUTHORIZED")


# ==============================================================================
# Pydantic Schemas for v1 API
# ==============================================================================

class ChatSessionValidateRequest(BaseModel):
    business_id: UUID
    customer_id: UUID | None = None
    conversation_id: UUID
    customer_token: str | None = None


class ConversationUpdatePayload(BaseModel):
    business_id: UUID
    current_state: str = "START"
    status: str = "ACTIVE"
    state_json: dict[str, Any] = Field(default_factory=dict)


class BookAppointmentPayload(BaseModel):
    business_id: UUID
    date: str
    time: str
    customer_name: str
    customer_phone: str
    customer_email: str | None = None
    whatsapp_number: str | None = None
    notes: str | None = None
    conversation_id: UUID | None = None


class CancelAppointmentPayload(BaseModel):
    business_id: UUID
    appointment_id: UUID | None = None
    customer_phone: str | None = None
    date: str | None = None
    time: str | None = None
    cancellation_reason: str | None = None


# ==============================================================================
# 1. Validate Chat Session
# ==============================================================================

@router.post("/chat/sessions/validate")
async def validate_chat_session(
    payload: ChatSessionValidateRequest,
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)

    business = await fetchrow(
        "SELECT id, name, status::text FROM businesses WHERE id = $1",
        payload.business_id,
    )
    if not business:
        raise AppError(404, "Business not found.", "NOT_FOUND")
    if business["status"] != "ACTIVE":
        raise AppError(403, "Business is not currently active.", "FORBIDDEN")

    async with transaction() as connection:
        # Ensure conversation exists; if not found, create as active
        await connection.execute(
            """INSERT INTO conversations (id, business_id, customer_id, status)
               VALUES ($1, $2, $3, 'ACTIVE'::conversation_status)
               ON CONFLICT (id) DO UPDATE
                   SET customer_id = COALESCE(conversations.customer_id, EXCLUDED.customer_id)""",
            payload.conversation_id,
            payload.business_id,
            payload.customer_id,
        )
        await connection.execute(
            """INSERT INTO conversation_state (conversation_id, business_id)
               VALUES ($1, $2)
               ON CONFLICT (conversation_id) DO NOTHING""",
            payload.conversation_id,
            payload.business_id,
        )

        # Look up customer if associated
        customer_row = await connection.fetchrow(
            """SELECT cu.id, cu.name, cu.phone, cu.email
                 FROM conversations c
                 LEFT JOIN customers cu ON cu.business_id = c.business_id AND cu.id = c.customer_id
                WHERE c.business_id = $1 AND c.id = $2""",
            payload.business_id,
            payload.conversation_id,
        )

    customer_name = customer_row["name"] if customer_row and customer_row["name"] else None
    customer_phone = customer_row["phone"] if customer_row and customer_row["phone"] else None
    resolved_customer_id = customer_row["id"] if customer_row and customer_row["id"] else None

    return {
        "authorized": True,
        "business_id": str(payload.business_id),
        "conversation_id": str(payload.conversation_id),
        "customer_id": str(resolved_customer_id) if resolved_customer_id else None,
        "customer_name": customer_name,
        "customer_phone": customer_phone,
    }


# ==============================================================================
# 2. Get Business Context
# ==============================================================================

@router.get("/businesses/{business_id}/context")
async def get_business_context(
    business_id: UUID,
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)

    b = await fetchrow(
        """SELECT id, name, email, address, city, state_province, postal_code, country_code, timezone, industry
             FROM businesses
            WHERE id = $1 AND status = 'ACTIVE'""",
        business_id,
    )
    if not b:
        raise AppError(404, "Business not found.", "NOT_FOUND")

    s = await fetchrow(
        """SELECT appointment_duration_minutes, booking_window_days, maximum_appointments_per_day,
                  allow_cancellation, allow_reschedule, collect_phone, collect_email, confirmation_required
             FROM business_settings
            WHERE business_id = $1""",
        business_id,
    )

    hours = await fetch(
        """SELECT day_of_week::text, opens_at::text, closes_at::text
             FROM business_hours
            WHERE business_id = $1
            ORDER BY CASE day_of_week
              WHEN 'MONDAY' THEN 1 WHEN 'TUESDAY' THEN 2 WHEN 'WEDNESDAY' THEN 3
              WHEN 'THURSDAY' THEN 4 WHEN 'FRIDAY' THEN 5 WHEN 'SATURDAY' THEN 6
              WHEN 'SUNDAY' THEN 7 END""",
        business_id,
    )

    overrides = await fetch(
        """SELECT override_date::text, is_closed, opens_at::text, closes_at::text, reason
             FROM business_schedule_overrides
            WHERE business_id = $1 AND override_date >= CURRENT_DATE - interval '1 day'
            ORDER BY override_date""",
        business_id,
    )

    address_parts = [part for part in [b["address"], b["city"], b["state_province"], b["postal_code"], b["country_code"]] if part]
    full_address = ", ".join(address_parts) if address_parts else ""

    settings_dict = {
        "appointment_duration_minutes": s["appointment_duration_minutes"] if s else 30,
        "booking_window_days": s["booking_window_days"] if s else 30,
        "minimum_notice_minutes": 60,
        "allow_same_day_booking": True,
        "maximum_appointments_per_day": s["maximum_appointments_per_day"] if s and s["maximum_appointments_per_day"] else 10,
        "allow_cancellation": s["allow_cancellation"] if s else True,
        "allow_reschedule": s["allow_reschedule"] if s else True,
        "collect_phone": s["collect_phone"] if s else True,
        "collect_email": s["collect_email"] if s else False,
        "confirmation_required": s["confirmation_required"] if s else False,
    }

    return {
        "business": {
            "id": str(b["id"]),
            "name": b["name"],
            "email": b["email"],
            "phone": "",
            "address": full_address,
            "description": b["industry"] or "",
            "timezone": b["timezone"] or "UTC",
        },
        "settings": settings_dict,
        "business_hours": [
            {
                "weekday": h["day_of_week"],
                "day_of_week": h["day_of_week"],
                "start_time": h["opens_at"][:5] if h["opens_at"] else "09:00",
                "opens_at": h["opens_at"][:5] if h["opens_at"] else "09:00",
                "end_time": h["closes_at"][:5] if h["closes_at"] else "17:00",
                "closes_at": h["closes_at"][:5] if h["closes_at"] else "17:00",
            }
            for h in hours
        ],
        "schedule_overrides": [
            {
                "override_date": o["override_date"],
                "is_closed": o["is_closed"],
                "opens_at": o["opens_at"][:5] if o["opens_at"] else None,
                "closes_at": o["closes_at"][:5] if o["closes_at"] else None,
                "reason": o["reason"],
            }
            for o in overrides
        ],
        "closures": [
            {"date": o["override_date"], "reason": o["reason"]}
            for o in overrides if o["is_closed"]
        ],
    }


# ==============================================================================
# 3. Get Conversation State
# ==============================================================================

@router.get("/conversations/{conversation_id}")
async def get_conversation_v1(
    conversation_id: UUID,
    business_id: UUID = Query(...),
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)

    row = await fetchrow(
        """SELECT c.id, c.business_id, c.customer_id, c.status::text,
                  cu.name AS customer_name, cu.phone AS customer_phone,
                  s.current_intent, s.current_step, s.collected_data, s.last_ai_response
             FROM conversations c
             LEFT JOIN customers cu ON cu.business_id = c.business_id AND cu.id = c.customer_id
             LEFT JOIN conversation_state s ON s.business_id = c.business_id AND s.conversation_id = c.id
            WHERE c.business_id = $1 AND c.id = $2""",
        business_id,
        conversation_id,
    )
    if not row:
        raise AppError(404, "Conversation not found.", "NOT_FOUND")

    return {
        "conversation": {
            "id": str(row["id"]),
            "conversation_id": str(row["id"]),
            "business_id": str(row["business_id"]),
            "customer_id": str(row["customer_id"]) if row["customer_id"] else None,
            "customer_name": row["customer_name"] or "",
            "customer_phone": row["customer_phone"] or "",
            "status": row["status"],
            "current_state": row["current_step"] or row["current_intent"] or "START",
            "state_json": row["collected_data"] or {},
            "last_ai_response": row["last_ai_response"] or "",
        }
    }


# ==============================================================================
# 4. Save Conversation State
# ==============================================================================

@router.put("/conversations/{conversation_id}")
async def save_conversation_v1(
    conversation_id: UUID,
    payload: ConversationUpdatePayload,
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)

    async with transaction() as connection:
        # Check if customer id is present in state_json to link anonymous conversation
        customer_id_str = payload.state_json.get("customer_id")
        if customer_id_str:
            try:
                cid = UUID(str(customer_id_str))
                await connection.execute(
                    """UPDATE conversations
                          SET customer_id = $1
                        WHERE business_id = $2 AND id = $3 AND customer_id IS NULL""",
                    cid,
                    payload.business_id,
                    conversation_id,
                )
            except (ValueError, TypeError):
                pass

        target_status = "CLOSED" if payload.status in {"COMPLETED", "CLOSED"} else "ACTIVE"
        await connection.execute(
            """UPDATE conversations
                  SET status = $1::conversation_status,
                      last_message_at = CURRENT_TIMESTAMP,
                      closed_at = CASE WHEN $1 = 'CLOSED' THEN CURRENT_TIMESTAMP ELSE NULL END
                WHERE business_id = $2 AND id = $3""",
            target_status,
            payload.business_id,
            conversation_id,
        )

        intent = payload.state_json.get("intent") or payload.current_state
        step = payload.current_state
        last_response = payload.state_json.get("last_assistant_message")

        if target_status != "CLOSED":
            await connection.execute(
                """INSERT INTO conversation_state (
                       conversation_id, business_id, current_intent, current_step,
                       collected_data, last_ai_response, updated_at
                   ) VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)
                   ON CONFLICT (conversation_id) DO UPDATE SET
                       current_intent = EXCLUDED.current_intent,
                       current_step = EXCLUDED.current_step,
                       collected_data = EXCLUDED.collected_data,
                       last_ai_response = EXCLUDED.last_ai_response,
                       updated_at = CURRENT_TIMESTAMP""",
                conversation_id,
                payload.business_id,
                intent,
                step,
                payload.state_json,
                last_response,
            )

        # Log conversation messages if provided
        user_msg = payload.state_json.get("last_user_message")
        if user_msg and str(user_msg).strip():
            recent_user = await connection.fetchval(
                """SELECT 1 FROM conversation_messages
                    WHERE business_id = $1 AND conversation_id = $2 AND sender = 'CUSTOMER'
                      AND content = $3 AND sent_at >= CURRENT_TIMESTAMP - interval '30 seconds'""",
                payload.business_id,
                conversation_id,
                str(user_msg).strip(),
            )
            if not recent_user:
                await connection.execute(
                    """INSERT INTO conversation_messages (business_id, conversation_id, sender, message_type, content)
                       VALUES ($1, $2, 'CUSTOMER', 'TEXT', $3)""",
                    payload.business_id,
                    conversation_id,
                    str(user_msg).strip(),
                )

        if last_response and str(last_response).strip():
            recent_bot = await connection.fetchval(
                """SELECT 1 FROM conversation_messages
                    WHERE business_id = $1 AND conversation_id = $2 AND sender = 'AI'
                      AND content = $3 AND sent_at >= CURRENT_TIMESTAMP - interval '30 seconds'""",
                payload.business_id,
                conversation_id,
                str(last_response).strip(),
            )
            if not recent_bot:
                await connection.execute(
                    """INSERT INTO conversation_messages (business_id, conversation_id, sender, message_type, content)
                       VALUES ($1, $2, 'AI', 'TEXT', $3)""",
                    payload.business_id,
                    conversation_id,
                    str(last_response).strip(),
                )

    return {"status": "ok", "conversation_id": str(conversation_id)}


# ==============================================================================
# 5. Validate Appointment Date & Time
# ==============================================================================

@router.get("/appointments/validate-date")
async def validate_appointment_date_v1(
    business_id: UUID = Query(...),
    date: str = Query(...),
    time: str | None = Query(None),
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)

    business = await fetchrow("SELECT timezone FROM businesses WHERE id = $1", business_id)
    if not business:
        raise AppError(404, "Business not found.", "NOT_FOUND")

    tz_name = business["timezone"] or "UTC"
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)

    s = await fetchrow(
        "SELECT booking_window_days FROM business_settings WHERE business_id = $1",
        business_id,
    )
    window_days = s["booking_window_days"] if s else 30
    allow_same_day = True
    notice_minutes = 60

    try:
        req_date = datetime.strptime(date.strip(), "%Y-%m-%d").date()
    except ValueError:
        return {
            "valid": False,
            "reason": "INVALID_DATE_FORMAT",
            "message": "Date must be in YYYY-MM-DD format.",
            "business_timezone": tz_name,
            "earliest_allowed_date": now.date().isoformat(),
            "latest_allowed_date": (now.date() + timedelta(days=window_days)).isoformat(),
        }

    earliest_date = now.date() if allow_same_day else (now.date() + timedelta(days=1))
    latest_date = now.date() + timedelta(days=window_days)

    if req_date < now.date():
        return {
            "valid": False,
            "reason": "DATE_IN_PAST",
            "message": f"The date {date} is in the past. Please select a future date.",
            "business_timezone": tz_name,
            "earliest_allowed_date": earliest_date.isoformat(),
            "latest_allowed_date": latest_date.isoformat(),
        }

    if req_date > latest_date:
        return {
            "valid": False,
            "reason": "OUTSIDE_BOOKING_WINDOW",
            "message": f"Bookings are only accepted up to {window_days} days in advance (until {latest_date}).",
            "business_timezone": tz_name,
            "earliest_allowed_date": earliest_date.isoformat(),
            "latest_allowed_date": latest_date.isoformat(),
        }

    # Check schedule override
    override = await fetchrow(
        "SELECT is_closed, opens_at, closes_at, reason FROM business_schedule_overrides WHERE business_id = $1 AND override_date = $2",
        business_id,
        req_date,
    )
    if override and override["is_closed"]:
        return {
            "valid": False,
            "reason": "BUSINESS_CLOSED",
            "message": f"The business is closed on {date}" + (f" due to {override['reason']}." if override["reason"] else "."),
            "business_timezone": tz_name,
            "earliest_allowed_date": earliest_date.isoformat(),
            "latest_allowed_date": latest_date.isoformat(),
        }

    # Check regular hours for weekday
    weekday = req_date.strftime("%A").upper()
    hours = await fetchrow(
        "SELECT opens_at, closes_at FROM business_hours WHERE business_id = $1 AND day_of_week = $2::day_of_week",
        business_id,
        weekday,
    )
    if not override and not hours:
        return {
            "valid": False,
            "reason": "BUSINESS_CLOSED",
            "message": f"The business is closed on {weekday.title()}s.",
            "business_timezone": tz_name,
            "earliest_allowed_date": earliest_date.isoformat(),
            "latest_allowed_date": latest_date.isoformat(),
        }

    # Validate time if provided
    if time and time.strip():
        try:
            req_time = datetime.strptime(time.strip(), "%H:%M").time()
            slot_dt = datetime.combine(req_date, req_time, tzinfo=tz)
            if slot_dt < now + timedelta(minutes=notice_minutes):
                return {
                    "valid": False,
                    "reason": "INSUFFICIENT_NOTICE",
                    "message": f"A minimum notice of {notice_minutes} minutes is required. This time is too soon.",
                    "business_timezone": tz_name,
                    "earliest_allowed_date": earliest_date.isoformat(),
                    "latest_allowed_date": latest_date.isoformat(),
                }
            day_opens = override["opens_at"] if override and override["opens_at"] else (hours["opens_at"] if hours else None)
            day_closes = override["closes_at"] if override and override["closes_at"] else (hours["closes_at"] if hours else None)
            if day_opens and day_closes:
                if req_time < day_opens or req_time >= day_closes:
                    return {
                        "valid": False,
                        "reason": "OUTSIDE_BUSINESS_HOURS",
                        "message": f"The business operates between {day_opens.strftime('%H:%M')} and {day_closes.strftime('%H:%M')} on this day.",
                        "business_timezone": tz_name,
                        "earliest_allowed_date": earliest_date.isoformat(),
                        "latest_allowed_date": latest_date.isoformat(),
                    }
        except ValueError:
            return {
                "valid": False,
                "reason": "INVALID_TIME_FORMAT",
                "message": "Time must be in HH:MM format (24-hour).",
                "business_timezone": tz_name,
                "earliest_allowed_date": earliest_date.isoformat(),
                "latest_allowed_date": latest_date.isoformat(),
            }

    return {
        "valid": True,
        "reason": "OK",
        "message": f"Date {date} is available for booking.",
        "business_timezone": tz_name,
        "earliest_allowed_date": earliest_date.isoformat(),
        "latest_allowed_date": latest_date.isoformat(),
    }


# ==============================================================================
# 6. Check Availability
# ==============================================================================

@router.get("/appointments/check-availability")
async def check_availability_v1(
    business_id: UUID = Query(...),
    date: str | None = Query(None),
    time: str | None = Query(None),
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)

    business = await fetchrow("SELECT timezone FROM businesses WHERE id = $1", business_id)
    if not business:
        raise AppError(404, "Business not found.", "NOT_FOUND")

    tz_name = business["timezone"] or "UTC"
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)

    s = await fetchrow(
        "SELECT appointment_duration_minutes, booking_window_days FROM business_settings WHERE business_id = $1",
        business_id,
    )
    duration = s["appointment_duration_minutes"] if s else 30
    window_days = s["booking_window_days"] if s else 30
    notice_minutes = 60

    async def get_slots_for_date(target_date: dt_date) -> list[str]:
        ov = await fetchrow(
            "SELECT is_closed, opens_at, closes_at FROM business_schedule_overrides WHERE business_id = $1 AND override_date = $2",
            business_id,
            target_date,
        )
        if ov and ov["is_closed"]:
            return []

        opens_at: dt_time | None = None
        closes_at: dt_time | None = None

        if ov and ov["opens_at"] and ov["closes_at"]:
            opens_at = ov["opens_at"]
            closes_at = ov["closes_at"]
        else:
            weekday = target_date.strftime("%A").upper()
            bh = await fetchrow(
                "SELECT opens_at, closes_at FROM business_hours WHERE business_id = $1 AND day_of_week = $2::day_of_week",
                business_id,
                weekday,
            )
            if bh:
                opens_at = bh["opens_at"]
                closes_at = bh["closes_at"]

        if not opens_at or not closes_at:
            return []

        candidates: list[str] = []
        current_dt = datetime.combine(target_date, opens_at, tzinfo=tz)
        closing_dt = datetime.combine(target_date, closes_at, tzinfo=tz)
        step = timedelta(minutes=duration)

        day_start = datetime.combine(target_date, dt_time.min, tzinfo=tz)
        day_end = datetime.combine(target_date, dt_time.max, tzinfo=tz)
        existing = await fetch(
            """SELECT scheduled_start, scheduled_end
                 FROM appointments
                WHERE business_id = $1 AND status <> 'CANCELLED'
                  AND scheduled_start >= $2 AND scheduled_start <= $3""",
            business_id,
            day_start,
            day_end,
        )

        min_notice_dt = now + timedelta(minutes=notice_minutes)

        while current_dt + step <= closing_dt:
            slot_end = current_dt + step
            if current_dt >= min_notice_dt:
                conflict = any(
                    apt["scheduled_start"] < slot_end and apt["scheduled_end"] > current_dt
                    for apt in existing
                )
                if not conflict:
                    candidates.append(current_dt.strftime("%H:%M"))
            current_dt += step

        return candidates

    resolved_date: dt_date
    if date and date.strip():
        try:
            resolved_date = datetime.strptime(date.strip(), "%Y-%m-%d").date()
        except ValueError:
            raise AppError(400, "Date must be YYYY-MM-DD.", "INVALID_DATE")
    else:
        start_day = now.date()
        resolved_date = start_day
        found_date = None
        for i in range(window_days):
            candidate_day = start_day + timedelta(days=i)
            slots = await get_slots_for_date(candidate_day)
            if slots:
                found_date = candidate_day
                break
        if found_date:
            resolved_date = found_date

    slots = await get_slots_for_date(resolved_date)

    target_time = time.strip() if time and time.strip() else None
    is_avail = (target_time in slots) if target_time else (len(slots) > 0)

    return {
        "business_id": str(business_id),
        "date": resolved_date.isoformat(),
        "timezone": tz_name,
        "available_slots": slots,
        "is_available": is_avail,
        "duration_minutes": duration,
    }


# ==============================================================================
# 7. Book Appointment
# ==============================================================================

@router.post("/appointments/book")
async def book_appointment_v1(
    payload: BookAppointmentPayload,
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)

    business = await fetchrow("SELECT timezone FROM businesses WHERE id = $1", payload.business_id)
    if not business:
        raise AppError(404, "Business not found.", "NOT_FOUND")

    tz_name = business["timezone"] or "UTC"
    tz = ZoneInfo(tz_name)

    s = await fetchrow(
        "SELECT appointment_duration_minutes FROM business_settings WHERE business_id = $1",
        payload.business_id,
    )
    duration = s["appointment_duration_minutes"] if s else 30

    try:
        book_date = datetime.strptime(payload.date.strip(), "%Y-%m-%d").date()
        book_time = datetime.strptime(payload.time.strip(), "%H:%M").time()
    except ValueError:
        raise AppError(400, "Date must be YYYY-MM-DD and time must be HH:MM.", "INVALID_DATETIME")

    start_dt = datetime.combine(book_date, book_time, tzinfo=tz)
    end_dt = start_dt + timedelta(minutes=duration)

    clean_name = payload.customer_name.strip()
    clean_phone = payload.customer_phone.strip()
    clean_email = payload.customer_email.strip() if payload.customer_email else None

    async with transaction() as connection:
        try:
            start_dt, end_dt, tz = await validate_appointment_slot(
                connection,
                payload.business_id,
                start_dt,
                end_dt,
            )
        except AppError as e:
            return {
                "success": False,
                "error": e.message,
                "code": e.code,
            }

        customer = await connection.fetchrow(
            """SELECT id, name, phone, email FROM customers
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
        if not customer:
            customer_id = await connection.fetchval(
                """INSERT INTO customers (business_id, name, phone, email)
                   VALUES ($1, $2, $3, $4)
                   RETURNING id""",
                payload.business_id,
                clean_name,
                clean_phone,
                clean_email,
            )
        else:
            customer_id = customer["id"]
            await connection.execute(
                """UPDATE customers
                      SET name = COALESCE($1, name),
                          email = COALESCE($2, email),
                          phone = COALESCE($3, phone)
                    WHERE business_id = $4 AND id = $5""",
                clean_name,
                clean_email,
                clean_phone,
                payload.business_id,
                customer_id,
            )

        # Link conversation to customer if provided
        if payload.conversation_id:
            await connection.execute(
                """UPDATE conversations
                      SET customer_id = $1
                    WHERE business_id = $2 AND id = $3""",
                customer_id,
                payload.business_id,
                payload.conversation_id,
            )

        # Create appointment
        apt = await connection.fetchrow(
            """INSERT INTO appointments (
                   business_id, customer_id, conversation_id, status,
                   scheduled_start, scheduled_end,
                   customer_name, customer_phone, customer_email
               ) VALUES ($1, $2, $3, 'CONFIRMED'::appointment_status, $4, $5, $6, $7, $8)
               RETURNING id, scheduled_start, scheduled_end, status::text""",
            payload.business_id,
            customer_id,
            payload.conversation_id,
            start_dt,
            end_dt,
            clean_name,
            clean_phone,
            clean_email,
        )

    return {
        "success": True,
        "appointment_id": str(apt["id"]),
        "start_datetime": apt["scheduled_start"].isoformat(),
        "end_datetime": apt["scheduled_end"].isoformat(),
        "timezone": tz_name,
        "status": apt["status"],
        "customer_name": clean_name,
        "customer_phone": clean_phone,
    }


# ==============================================================================
# 8. Cancel Appointment
# ==============================================================================

@router.post("/appointments/cancel")
async def cancel_appointment_v1(
    payload: CancelAppointmentPayload,
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)

    async with transaction() as connection:
        apt = None
        if payload.appointment_id:
            apt = await connection.fetchrow(
                "SELECT id, status::text FROM appointments WHERE business_id = $1 AND id = $2",
                payload.business_id,
                payload.appointment_id,
            )
        elif payload.customer_phone:
            apt = await connection.fetchrow(
                """SELECT id, status::text FROM appointments
                    WHERE business_id = $1 AND customer_phone = $2 AND status <> 'CANCELLED'
                    ORDER BY scheduled_start DESC LIMIT 1""",
                payload.business_id,
                payload.customer_phone.strip(),
            )

        if not apt:
            return {
                "success": False,
                "error": "Appointment not found.",
            }

        await connection.execute(
            "UPDATE appointments SET status = 'CANCELLED'::appointment_status WHERE business_id = $1 AND id = $2",
            payload.business_id,
            apt["id"],
        )

    return {
        "success": True,
        "appointment_id": str(apt["id"]),
        "status": "CANCELLED",
        "cancellation_reason": payload.cancellation_reason or "Customer requested cancellation.",
    }
