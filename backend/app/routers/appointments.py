from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ..db import fetch, fetchrow, transaction
from ..dependencies import AuthBusiness, current_business
from ..errors import AppError
from ..schemas import AppointmentCreate, AppointmentStatus, AppointmentUpdate

router = APIRouter(prefix="/api/appointments", tags=["Appointments"])


@router.get("")
async def list_appointments(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: AppointmentStatus | None = None,
    from_time: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    user: AuthBusiness = Depends(current_business),
) -> dict[str, object]:
    rows = await fetch(
        """SELECT id, customer_id AS "customerId", conversation_id AS "conversationId", status::text,
                  scheduled_start AS "scheduledStart", scheduled_end AS "scheduledEnd",
                  customer_name AS "customerName", customer_phone AS "customerPhone", customer_email AS "customerEmail",
                  count(*) OVER()::int AS "totalCount"
             FROM appointments
            WHERE business_id = $1
              AND ($2::appointment_status IS NULL OR status = $2)
              AND ($3::timestamptz IS NULL OR scheduled_start >= $3)
              AND ($4::timestamptz IS NULL OR scheduled_start < $4)
            ORDER BY scheduled_start DESC
            LIMIT $5 OFFSET $6""",
        user.business_id,
        status.value if status else None,
        from_time,
        to,
        limit,
        (page - 1) * limit,
    )
    total = rows[0]["totalCount"] if rows else 0
    items = []
    for row in rows:
        item = dict(row)
        item.pop("totalCount", None)
        items.append(item)
    return {"appointments": items, "total": total, "page": page}


@router.post("", status_code=201)
async def create_appointment(
    payload: AppointmentCreate, user: AuthBusiness = Depends(current_business)
) -> dict[str, object]:
    if payload.scheduledStart.tzinfo is None:
        raise AppError(400, "Appointment start must include a timezone.", "INVALID_SCHEDULE")
    async with transaction() as connection:
        config = await connection.fetchrow(
            """SELECT appointment_duration_minutes, booking_window_days, maximum_appointments_per_day
                 FROM business_settings WHERE business_id = $1 FOR UPDATE""",
            user.business_id,
        )
        if not config:
            raise AppError(409, "Business booking settings are not configured.", "SETTINGS_MISSING")
        start = payload.scheduledStart
        end = payload.scheduledEnd or start + timedelta(minutes=config["appointment_duration_minutes"])
        now = datetime.now(timezone.utc)
        if start <= now:
            raise AppError(400, "Appointment must be scheduled in the future.", "INVALID_SCHEDULE")
        if start > now + timedelta(days=config["booking_window_days"]):
            raise AppError(400, "Appointment is outside the booking window.", "INVALID_SCHEDULE")
        if config["maximum_appointments_per_day"]:
            count = await connection.fetchval(
                """SELECT count(*)::int FROM appointments a JOIN businesses b ON b.id = a.business_id
                   WHERE a.business_id = $1
                     AND (a.scheduled_start AT TIME ZONE b.timezone)::date = ($2::timestamptz AT TIME ZONE b.timezone)::date
                     AND a.status NOT IN ('CANCELLED', 'NO_SHOW')""",
                user.business_id,
                start,
            )
            if count >= config["maximum_appointments_per_day"]:
                raise AppError(409, "Daily appointment capacity has been reached.", "DAILY_CAPACITY_REACHED")
        customer = await connection.fetchrow(
            """SELECT c.name, c.phone, c.email
                 FROM customers c
                WHERE c.business_id = $1 AND c.id = $2""",
            user.business_id,
            payload.customerId,
        )
        if not customer:
            raise AppError(404, "Customer not found.", "NOT_FOUND")
        row = await connection.fetchrow(
            """INSERT INTO appointments (
                   business_id, customer_id, conversation_id, status,
                   scheduled_start, scheduled_end,
                   customer_name, customer_phone, customer_email
               ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               RETURNING id, customer_id AS "customerId", conversation_id AS "conversationId", status::text,
                         scheduled_start AS "scheduledStart", scheduled_end AS "scheduledEnd",
                         customer_name AS "customerName", customer_phone AS "customerPhone", customer_email AS "customerEmail" """,
            user.business_id,
            payload.customerId,
            payload.conversationId,
            payload.status.value,
            start,
            end,
            payload.customerName if payload.customerName is not None else customer["name"],
            payload.customerPhone if payload.customerPhone is not None else customer["phone"],
            str(payload.customerEmail).lower() if payload.customerEmail is not None else customer["email"],
        )
    return {"appointment": dict(row)}


@router.patch("/{appointment_id}")
async def update_appointment(
    appointment_id: UUID,
    payload: AppointmentUpdate,
    user: AuthBusiness = Depends(current_business),
) -> dict[str, object]:
    if not payload.model_fields_set:
        raise AppError(400, "Provide at least one change.", "VALIDATION_ERROR")
    row = await fetchrow(
        """UPDATE appointments
              SET status = COALESCE($1::appointment_status, status),
                  scheduled_start = COALESCE($2, scheduled_start),
                  scheduled_end = COALESCE($3, scheduled_end),
                  customer_name = CASE WHEN $4 THEN $5 ELSE customer_name END,
                  customer_phone = CASE WHEN $6 THEN $7 ELSE customer_phone END,
                  customer_email = CASE WHEN $8 THEN $9 ELSE customer_email END
            WHERE business_id = $10 AND id = $11
        RETURNING id, customer_id AS "customerId", status::text,
                  scheduled_start AS "scheduledStart", scheduled_end AS "scheduledEnd",
                  customer_name AS "customerName", customer_phone AS "customerPhone", customer_email AS "customerEmail" """,
        payload.status.value if payload.status else None,
        payload.scheduledStart,
        payload.scheduledEnd,
        "customerName" in payload.model_fields_set,
        payload.customerName,
        "customerPhone" in payload.model_fields_set,
        payload.customerPhone,
        "customerEmail" in payload.model_fields_set,
        str(payload.customerEmail).lower() if payload.customerEmail else None,
        user.business_id,
        appointment_id,
    )
    if not row:
        raise AppError(404, "Appointment not found.", "NOT_FOUND")
    return {"appointment": dict(row)}


@router.delete("/{appointment_id}", status_code=204)
async def cancel_appointment(
    appointment_id: UUID, user: AuthBusiness = Depends(current_business)
) -> None:
    row = await fetchrow(
        """UPDATE appointments SET status = 'CANCELLED'::appointment_status
            WHERE business_id = $1 AND id = $2 RETURNING id""",
        user.business_id,
        appointment_id,
    )
    if not row:
        raise AppError(404, "Appointment not found.", "NOT_FOUND")
