from __future__ import annotations

from fastapi import APIRouter, Depends

from ..db import fetch, fetchrow
from ..dependencies import AuthBusiness, current_business

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/summary")
async def summary(user: AuthBusiness = Depends(current_business)) -> dict[str, object]:
    metrics = await fetchrow(
        """SELECT
          (SELECT count(*)::int FROM appointments a JOIN businesses b ON b.id=a.business_id WHERE a.business_id=$1
            AND (a.scheduled_start AT TIME ZONE b.timezone)::date=(CURRENT_TIMESTAMP AT TIME ZONE b.timezone)::date
            AND a.status NOT IN ('CANCELLED','NO_SHOW')) AS "appointmentsToday",
          (SELECT count(*)::int FROM appointments WHERE business_id=$1 AND scheduled_start>=CURRENT_TIMESTAMP
            AND scheduled_start<CURRENT_TIMESTAMP+interval '7 days' AND status IN ('PENDING','CONFIRMED')) AS "upcomingAppointments",
          (SELECT count(*)::int FROM conversations WHERE business_id=$1 AND status<>'CLOSED') AS "openConversations",
          (SELECT count(*)::int FROM customers WHERE business_id=$1) AS "totalCustomers",
          (SELECT count(*)::int FROM business_channels WHERE business_id=$1 AND enabled) AS "enabledChannels"
        """,
        user.business_id,
    )
    upcoming = await fetch(
        """SELECT id,scheduled_start AS "scheduledStart",scheduled_end AS "scheduledEnd",status::text,
                  customer_name AS "customerName",created_channel::text AS "createdChannel"
             FROM appointments WHERE business_id=$1 AND scheduled_start>=CURRENT_TIMESTAMP
              AND status IN ('PENDING','CONFIRMED') ORDER BY scheduled_start LIMIT 6""", user.business_id,
    )
    return {"metrics": dict(metrics), "upcoming": [dict(row) for row in upcoming]}
