from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends

from ..db import execute, fetch, fetchrow, transaction
from ..dependencies import AuthBusiness, current_business
from ..schemas import BusinessUpdate, Channel, ChannelUpdate, HoursUpdate, OverrideUpdate, SettingsUpdate

router = APIRouter(prefix="/api/business", tags=["Business"])


@router.get("")
async def get_business(user: AuthBusiness = Depends(current_business)) -> dict[str, object]:
    row = await fetchrow(
        """SELECT id,name,address,city,state_province AS "stateProvince",postal_code AS "postalCode",
                  country_code AS "countryCode",industry,timezone,status::text,created_at AS "createdAt",updated_at AS "updatedAt"
             FROM businesses WHERE id=$1""", user.business_id,
    )
    return {"business": dict(row)}


@router.put("")
async def update_business(payload: BusinessUpdate, user: AuthBusiness = Depends(current_business)) -> dict[str, object]:
    row = await fetchrow(
        """UPDATE businesses SET name=$1,address=$2,city=$3,state_province=$4,postal_code=$5,
                  country_code=$6,industry=$7,timezone=$8 WHERE id=$9
             RETURNING id,name,address,city,state_province AS "stateProvince",postal_code AS "postalCode",
                  country_code AS "countryCode",industry,timezone,status::text,updated_at AS "updatedAt"
        """,
        payload.name, payload.address, payload.city, payload.stateProvince, payload.postalCode,
        payload.countryCode, payload.industry, payload.timezone, user.business_id,
    )
    return {"business": dict(row)}


@router.get("/settings")
async def get_settings(user: AuthBusiness = Depends(current_business)) -> dict[str, object]:
    row = await fetchrow(
        """SELECT appointment_duration_minutes AS "appointmentDurationMinutes",booking_window_days AS "bookingWindowDays",
                  maximum_appointments_per_day AS "maximumAppointmentsPerDay",allow_cancellation AS "allowCancellation",
                  allow_reschedule AS "allowReschedule",collect_phone AS "collectPhone",collect_email AS "collectEmail",
                  confirmation_required AS "confirmationRequired",updated_at AS "updatedAt"
             FROM business_settings WHERE business_id=$1""", user.business_id,
    )
    return {"settings": dict(row)}


@router.put("/settings")
async def update_settings(payload: SettingsUpdate, user: AuthBusiness = Depends(current_business)) -> dict[str, object]:
    row = await fetchrow(
        """UPDATE business_settings SET appointment_duration_minutes=$1,booking_window_days=$2,
                  maximum_appointments_per_day=$3,allow_cancellation=$4,allow_reschedule=$5,
                  collect_phone=$6,collect_email=$7,confirmation_required=$8 WHERE business_id=$9
             RETURNING appointment_duration_minutes AS "appointmentDurationMinutes",booking_window_days AS "bookingWindowDays",
                  maximum_appointments_per_day AS "maximumAppointmentsPerDay",allow_cancellation AS "allowCancellation",
                  allow_reschedule AS "allowReschedule",collect_phone AS "collectPhone",collect_email AS "collectEmail",
                  confirmation_required AS "confirmationRequired"
        """,
        payload.appointmentDurationMinutes, payload.bookingWindowDays, payload.maximumAppointmentsPerDay,
        payload.allowCancellation, payload.allowReschedule, payload.collectPhone, payload.collectEmail,
        payload.confirmationRequired, user.business_id,
    )
    return {"settings": dict(row)}


@router.get("/hours")
async def get_hours(user: AuthBusiness = Depends(current_business)) -> dict[str, object]:
    rows = await fetch(
        """SELECT day_of_week::text AS "dayOfWeek",opens_at AS "opensAt",closes_at AS "closesAt"
             FROM business_hours WHERE business_id=$1 ORDER BY day_of_week""", user.business_id,
    )
    return {"hours": [dict(row) for row in rows]}


@router.put("/hours")
async def update_hours(payload: HoursUpdate, user: AuthBusiness = Depends(current_business)) -> dict[str, object]:
    async with transaction() as connection:
        await connection.execute("DELETE FROM business_hours WHERE business_id=$1", user.business_id)
        for row in payload.hours:
            await connection.execute(
                "INSERT INTO business_hours (business_id,day_of_week,opens_at,closes_at) VALUES ($1,$2,$3,$4)",
                user.business_id, row.dayOfWeek.value, row.opensAt, row.closesAt,
            )
    return {"hours": [row.model_dump(mode="json") for row in payload.hours]}


@router.get("/overrides")
async def get_overrides(user: AuthBusiness = Depends(current_business)) -> dict[str, object]:
    rows = await fetch(
        """SELECT override_date AS "overrideDate",is_closed AS "isClosed",opens_at AS "opensAt",
                  closes_at AS "closesAt",reason FROM business_schedule_overrides
             WHERE business_id=$1 AND override_date>=CURRENT_DATE ORDER BY override_date LIMIT 100""",
        user.business_id,
    )
    return {"overrides": [dict(row) for row in rows]}


@router.put("/overrides/{override_date}")
async def put_override(override_date: date, payload: OverrideUpdate, user: AuthBusiness = Depends(current_business)) -> dict[str, object]:
    row = await fetchrow(
        """INSERT INTO business_schedule_overrides (business_id,override_date,is_closed,opens_at,closes_at,reason)
             VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT (business_id,override_date) DO UPDATE
             SET is_closed=EXCLUDED.is_closed,opens_at=EXCLUDED.opens_at,closes_at=EXCLUDED.closes_at,reason=EXCLUDED.reason
             RETURNING override_date AS "overrideDate",is_closed AS "isClosed",opens_at AS "opensAt",closes_at AS "closesAt",reason""",
        user.business_id, override_date, payload.isClosed,
        None if payload.isClosed else payload.opensAt, None if payload.isClosed else payload.closesAt, payload.reason,
    )
    return {"override": dict(row)}


@router.delete("/overrides/{override_date}", status_code=204)
async def delete_override(override_date: date, user: AuthBusiness = Depends(current_business)) -> None:
    await execute("DELETE FROM business_schedule_overrides WHERE business_id=$1 AND override_date=$2", user.business_id, override_date)


@router.get("/channels")
async def get_channels(user: AuthBusiness = Depends(current_business)) -> dict[str, object]:
    rows = await fetch(
        """SELECT channel::text,enabled,provider,external_account_id AS "externalAccountId",metadata
             FROM business_channels WHERE business_id=$1 ORDER BY channel""", user.business_id,
    )
    return {"channels": [dict(row) for row in rows]}


@router.put("/channels/{channel}")
async def update_channel(channel: Channel, payload: ChannelUpdate, user: AuthBusiness = Depends(current_business)) -> dict[str, object]:
    row = await fetchrow(
        """UPDATE business_channels SET enabled=$1,provider=$2,external_account_id=$3,metadata=$4
             WHERE business_id=$5 AND channel=$6
             RETURNING channel::text,enabled,provider,external_account_id AS "externalAccountId",metadata""",
        payload.enabled, payload.provider, payload.externalAccountId, payload.metadata, user.business_id, channel.value,
    )
    return {"channel": dict(row)}
