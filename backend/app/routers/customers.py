from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ..db import execute, fetch, fetchrow, transaction
from ..dependencies import AuthBusiness, current_business
from ..errors import AppError
from ..schemas import CustomerCreate, CustomerUpdate, IdentityInput

router = APIRouter(prefix="/api/customers", tags=["Customers"])


@router.get("")
async def list_customers(
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), search: str = Query("", max_length=200),
    user: AuthBusiness = Depends(current_business),
) -> dict[str, object]:
    pattern = f"%{search.strip()}%" if search.strip() else ""
    rows = await fetch(
        """SELECT c.id,c.name,c.created_at AS "createdAt",c.updated_at AS "updatedAt",
          COALESCE(jsonb_agg(jsonb_build_object('id',i.id,'channel',i.channel,'identifier',i.identifier,
            'displayName',i.display_name,'verified',i.verified,'isPrimary',i.is_primary)
            ORDER BY i.is_primary DESC,i.channel) FILTER (WHERE i.id IS NOT NULL),'[]'::jsonb) AS identities,
          count(*) OVER()::int AS "totalCount"
        FROM customers c LEFT JOIN customer_identities i ON i.business_id=c.business_id AND i.customer_id=c.id
        WHERE c.business_id=$1 AND ($2::text='' OR COALESCE(c.name,'') ILIKE $2 OR EXISTS (
          SELECT 1 FROM customer_identities search_i WHERE search_i.business_id=c.business_id
            AND search_i.customer_id=c.id AND search_i.identifier ILIKE $2))
        GROUP BY c.id ORDER BY c.updated_at DESC LIMIT $3 OFFSET $4""",
        user.business_id, pattern, limit, (page - 1) * limit,
    )
    total = rows[0]["totalCount"] if rows else 0
    customers = []
    for row in rows:
        item = dict(row)
        item.pop("totalCount", None)
        customers.append(item)
    return {"customers": customers, "total": total, "page": page}


@router.get("/{customer_id}")
async def get_customer(customer_id: UUID, user: AuthBusiness = Depends(current_business)) -> dict[str, object]:
    row = await fetchrow(
        """SELECT c.id,c.name,c.created_at AS "createdAt",c.updated_at AS "updatedAt",
          COALESCE(jsonb_agg(jsonb_build_object('id',i.id,'channel',i.channel,'identifier',i.identifier,
            'displayName',i.display_name,'verified',i.verified,'isPrimary',i.is_primary)
            ORDER BY i.is_primary DESC,i.channel) FILTER (WHERE i.id IS NOT NULL),'[]'::jsonb) AS identities
        FROM customers c LEFT JOIN customer_identities i ON i.business_id=c.business_id AND i.customer_id=c.id
        WHERE c.business_id=$1 AND c.id=$2 GROUP BY c.id""", user.business_id, customer_id,
    )
    if not row:
        raise AppError(404, "Customer not found.", "NOT_FOUND")
    return {"customer": dict(row)}


@router.post("", status_code=201)
async def create_customer(payload: CustomerCreate, user: AuthBusiness = Depends(current_business)) -> dict[str, object]:
    async with transaction() as connection:
        customer = await connection.fetchrow(
            "INSERT INTO customers (business_id,name) VALUES ($1,$2) RETURNING id,name",
            user.business_id, payload.name,
        )
        for identity in payload.identities:
            identifier = identity.identifier.lower() if identity.channel.value == "EMAIL" else identity.identifier
            await connection.execute(
                """INSERT INTO customer_identities (business_id,customer_id,channel,identifier,display_name,verified,is_primary)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                user.business_id, customer["id"], identity.channel.value, identifier,
                identity.displayName, identity.verified, identity.isPrimary,
            )
    return {"customer": dict(customer)}


@router.patch("/{customer_id}")
async def update_customer(customer_id: UUID, payload: CustomerUpdate, user: AuthBusiness = Depends(current_business)) -> dict[str, object]:
    row = await fetchrow(
        "UPDATE customers SET name=$1 WHERE business_id=$2 AND id=$3 RETURNING id,name,updated_at AS " + '"updatedAt"',
        payload.name, user.business_id, customer_id,
    )
    if not row:
        raise AppError(404, "Customer not found.", "NOT_FOUND")
    return {"customer": dict(row)}


@router.delete("/{customer_id}", status_code=204)
async def delete_customer(customer_id: UUID, user: AuthBusiness = Depends(current_business)) -> None:
    row = await fetchrow("DELETE FROM customers WHERE business_id=$1 AND id=$2 RETURNING id", user.business_id, customer_id)
    if not row:
        raise AppError(404, "Customer not found.", "NOT_FOUND")


@router.post("/{customer_id}/identities", status_code=201)
async def add_identity(customer_id: UUID, payload: IdentityInput, user: AuthBusiness = Depends(current_business)) -> dict[str, object]:
    async with transaction() as connection:
        if payload.isPrimary:
            await connection.execute(
                "UPDATE customer_identities SET is_primary=false WHERE business_id=$1 AND customer_id=$2 AND channel=$3 AND is_primary",
                user.business_id, customer_id, payload.channel.value,
            )
        identifier = payload.identifier.lower() if payload.channel.value == "EMAIL" else payload.identifier
        row = await connection.fetchrow(
            """INSERT INTO customer_identities (business_id,customer_id,channel,identifier,display_name,verified,is_primary)
               VALUES ($1,$2,$3,$4,$5,$6,$7)
               RETURNING id,channel::text,identifier,display_name AS "displayName",verified,is_primary AS "isPrimary"
            """,
            user.business_id, customer_id, payload.channel.value, identifier,
            payload.displayName, payload.verified, payload.isPrimary,
        )
    return {"identity": dict(row)}


@router.delete("/{customer_id}/identities/{identity_id}", status_code=204)
async def delete_identity(customer_id: UUID, identity_id: UUID, user: AuthBusiness = Depends(current_business)) -> None:
    row = await fetchrow(
        "DELETE FROM customer_identities WHERE business_id=$1 AND customer_id=$2 AND id=$3 RETURNING id",
        user.business_id, customer_id, identity_id,
    )
    if not row:
        raise AppError(404, "Identity not found.", "NOT_FOUND")
