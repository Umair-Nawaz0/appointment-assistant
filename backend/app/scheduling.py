from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from .errors import AppError


async def validate_appointment_slot(
    connection: Any,
    business_id: UUID,
    scheduled_start: datetime,
    scheduled_end: datetime | None = None,
    exclude_appointment_id: UUID | None = None,
) -> tuple[datetime, datetime, ZoneInfo]:
    """
    Validates that an appointment:
    1. Has valid timezone awareness.
    2. Falls in the future and within the business booking window.
    3. Falls on an open day (not closed by schedule override or closed weekday).
    4. Start and end times are strictly within operating hours on that day.
    5. Does not conflict with another existing active appointment.
    6. Does not exceed daily maximum appointment capacity.

    Returns (start_dt_utc, end_dt_utc, tz).
    """
    # 1. Fetch business timezone and settings
    business = await connection.fetchrow(
        "SELECT timezone FROM businesses WHERE id = $1",
        business_id,
    )
    if not business:
        raise AppError(404, "Business not found.", "NOT_FOUND")

    tz_name = business["timezone"] or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")

    config = await connection.fetchrow(
        """SELECT appointment_duration_minutes, booking_window_days, maximum_appointments_per_day
             FROM business_settings WHERE business_id = $1""",
        business_id,
    )
    duration_minutes = config["appointment_duration_minutes"] if config else 30
    booking_window_days = config["booking_window_days"] if config else 30
    max_per_day = config["maximum_appointments_per_day"] if config else None

    # 2. Normalize start and end
    if scheduled_start.tzinfo is None:
        raise AppError(400, "Appointment start time must include a timezone.", "INVALID_SCHEDULE")

    start_dt = scheduled_start.astimezone(timezone.utc)
    now_utc = datetime.now(timezone.utc)

    if start_dt <= now_utc:
        raise AppError(400, "Appointment must be scheduled in the future.", "INVALID_SCHEDULE")

    if start_dt > now_utc + timedelta(days=booking_window_days):
        raise AppError(
            400,
            f"Appointment is outside the booking window (bookings accepted up to {booking_window_days} days in advance).",
            "INVALID_SCHEDULE",
        )

    if scheduled_end is not None:
        if scheduled_end.tzinfo is None:
            raise AppError(400, "Appointment end time must include a timezone.", "INVALID_SCHEDULE")
        end_dt = scheduled_end.astimezone(timezone.utc)
        if end_dt <= start_dt:
            raise AppError(400, "Appointment end time must be after start time.", "INVALID_SCHEDULE")
    else:
        end_dt = start_dt + timedelta(minutes=duration_minutes)

    # 3. Convert to business local time to check calendar date and operating hours
    local_start = start_dt.astimezone(tz)
    local_end = end_dt.astimezone(tz)
    target_date = local_start.date()

    if local_end.date() != target_date:
        raise AppError(400, "Appointments cannot span across multiple calendar days.", "INVALID_SCHEDULE")

    # 4. Check schedule overrides for this specific date
    override = await connection.fetchrow(
        """SELECT is_closed, opens_at, closes_at, reason
             FROM business_schedule_overrides
            WHERE business_id = $1 AND override_date = $2""",
        business_id,
        target_date,
    )
    if override and override["is_closed"]:
        reason = f": {override['reason']}" if override["reason"] else "."
        raise AppError(400, f"The business is closed on {target_date.strftime('%A, %b %d, %Y')}{reason}", "BUSINESS_CLOSED")

    # 5. Determine operating hours
    day_opens_at: time | None = None
    day_closes_at: time | None = None

    if override and override["opens_at"] and override["closes_at"]:
        day_opens_at = override["opens_at"]
        day_closes_at = override["closes_at"]
    else:
        weekday = target_date.strftime("%A").upper()
        bh = await connection.fetchrow(
            """SELECT opens_at, closes_at
                 FROM business_hours
                WHERE business_id = $1 AND day_of_week = $2::day_of_week""",
            business_id,
            weekday,
        )
        if not bh:
            raise AppError(400, f"The business is closed on {weekday.title()}s.", "BUSINESS_CLOSED")
        day_opens_at = bh["opens_at"]
        day_closes_at = bh["closes_at"]

    # 6. Compare operating hours
    start_time = local_start.time()
    end_time = local_end.time()

    if start_time < day_opens_at or end_time > day_closes_at:
        raise AppError(
            400,
            f"The business operates between {day_opens_at.strftime('%H:%M')} and {day_closes_at.strftime('%H:%M')} on {target_date.strftime('%A, %b %d, %Y')}. Requested time {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')} is outside operating hours.",
            "OUTSIDE_BUSINESS_HOURS",
        )

    # 7. Slot collision check against active appointments
    collision = await connection.fetchrow(
        """SELECT id, scheduled_start, scheduled_end
             FROM appointments
            WHERE business_id = $1
              AND status NOT IN ('CANCELLED', 'NO_SHOW')
              AND ($2::uuid IS NULL OR id <> $2)
              AND scheduled_start < $4 AND scheduled_end > $3
            LIMIT 1""",
        business_id,
        exclude_appointment_id,
        start_dt,
        end_dt,
    )
    if collision:
        col_start_local = collision["scheduled_start"].astimezone(tz).strftime("%H:%M")
        col_end_local = collision["scheduled_end"].astimezone(tz).strftime("%H:%M")
        raise AppError(
            409,
            f"This time slot conflicts with an existing booking ({col_start_local} - {col_end_local}). Please select another available time.",
            "SLOT_CONFLICT",
        )

    # 8. Daily capacity check
    if max_per_day:
        count = await connection.fetchval(
            """SELECT count(*)::int
                 FROM appointments a
                 JOIN businesses b ON b.id = a.business_id
                WHERE a.business_id = $1
                  AND (a.scheduled_start AT TIME ZONE b.timezone)::date = ($2::timestamptz AT TIME ZONE b.timezone)::date
                  AND a.status NOT IN ('CANCELLED', 'NO_SHOW')
                  AND ($3::uuid IS NULL OR a.id <> $3)""",
            business_id,
            start_dt,
            exclude_appointment_id,
        )
        if count >= max_per_day:
            raise AppError(409, "Daily appointment capacity has been reached for this date.", "DAILY_CAPACITY_REACHED")

    return start_dt, end_dt, tz
