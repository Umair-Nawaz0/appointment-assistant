from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ..db import execute, fetch, fetchrow
from ..dependencies import AuthBusiness, current_business
from ..errors import AppError
from ..schemas import CustomerCreate, CustomerUpdate

router = APIRouter(prefix="/api/customers", tags=["Customers"])


@router.get("")
async def list_customers(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=200),
    user: AuthBusiness = Depends(current_business),
) -> dict[str, object]:
    pattern = f"%{search.strip()}%" if search.strip() else ""
    rows = await fetch(
        """SELECT c.id, c.name, c.phone, c.email,
                  c.created_at AS "createdAt", c.updated_at AS "updatedAt",
                  count(*) OVER()::int AS "totalCount"
             FROM customers c
            WHERE c.business_id = $1
              AND ($2::text = ''
                   OR COALESCE(c.name, '') ILIKE $2
                   OR COALESCE(c.phone, '') ILIKE $2
                   OR COALESCE(c.email, '') ILIKE $2)
            ORDER BY c.updated_at DESC
            LIMIT $3 OFFSET $4""",
        user.business_id,
        pattern,
        limit,
        (page - 1) * limit,
    )
    total = rows[0]["totalCount"] if rows else 0
    customers = []
    for row in rows:
        item = dict(row)
        item.pop("totalCount", None)
        customers.append(item)
    return {"customers": customers, "total": total, "page": page}


@router.get("/{customer_id}")
async def get_customer(
    customer_id: UUID, user: AuthBusiness = Depends(current_business)
) -> dict[str, object]:
    row = await fetchrow(
        """SELECT c.id, c.name, c.phone, c.email,
                  c.created_at AS "createdAt", c.updated_at AS "updatedAt"
             FROM customers c
            WHERE c.business_id = $1 AND c.id = $2""",
        user.business_id,
        customer_id,
    )
    if not row:
        raise AppError(404, "Customer not found.", "NOT_FOUND")
    return {"customer": dict(row)}


@router.post("", status_code=201)
async def create_customer(
    payload: CustomerCreate, user: AuthBusiness = Depends(current_business)
) -> dict[str, object]:
    email = str(payload.email).lower() if payload.email else None
    customer = await fetchrow(
        """INSERT INTO customers (business_id, name, phone, email)
           VALUES ($1, $2, $3, $4)
           RETURNING id, name, phone, email, created_at AS "createdAt", updated_at AS "updatedAt" """,
        user.business_id,
        payload.name,
        payload.phone,
        email,
    )
    return {"customer": dict(customer)}


@router.patch("/{customer_id}")
async def update_customer(
    customer_id: UUID,
    payload: CustomerUpdate,
    user: AuthBusiness = Depends(current_business),
) -> dict[str, object]:
    if not payload.model_fields_set:
        raise AppError(400, "Provide at least one change.", "VALIDATION_ERROR")

    email = str(payload.email).lower() if payload.email else None
    row = await fetchrow(
        """UPDATE customers
              SET name = CASE WHEN $1 THEN $2 ELSE name END,
                  phone = CASE WHEN $3 THEN $4 ELSE phone END,
                  email = CASE WHEN $5 THEN $6 ELSE email END
            WHERE business_id = $7 AND id = $8
        RETURNING id, name, phone, email, created_at AS "createdAt", updated_at AS "updatedAt" """,
        "name" in payload.model_fields_set,
        payload.name,
        "phone" in payload.model_fields_set,
        payload.phone,
        "email" in payload.model_fields_set,
        email,
        user.business_id,
        customer_id,
    )
    if not row:
        raise AppError(404, "Customer not found.", "NOT_FOUND")
    return {"customer": dict(row)}


@router.delete("/{customer_id}", status_code=204)
async def delete_customer(
    customer_id: UUID, user: AuthBusiness = Depends(current_business)
) -> None:
    row = await fetchrow(
        "DELETE FROM customers WHERE business_id = $1 AND id = $2 RETURNING id",
        user.business_id,
        customer_id,
    )
    if not row:
        raise AppError(404, "Customer not found.", "NOT_FOUND")
