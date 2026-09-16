from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ..db import fetch, fetchrow, transaction
from ..dependencies import AuthBusiness, current_business
from ..errors import AppError
from ..schemas import ConversationCreate, ConversationStatus, ConversationUpdate, MessageCreate, StateUpdate, StatusUpdate

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])


@router.get("")
async def list_conversations(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: ConversationStatus | None = None,
    user: AuthBusiness = Depends(current_business),
) -> dict[str, object]:
    rows = await fetch(
        """SELECT c.id, c.customer_id AS "customerId", cu.name AS "customerName",
                  c.status::text, c.started_at AS "startedAt",
                  c.last_message_at AS "lastMessageAt", c.closed_at AS "closedAt",
                  (SELECT content FROM conversation_messages m
                    WHERE m.business_id = c.business_id AND m.conversation_id = c.id
                    ORDER BY m.sent_at DESC, m.id DESC LIMIT 1) AS "lastMessage",
                  count(*) OVER()::int AS "totalCount"
             FROM conversations c
        LEFT JOIN customers cu ON cu.business_id = c.business_id AND cu.id = c.customer_id
            WHERE c.business_id = $1
              AND ($2::conversation_status IS NULL OR c.status = $2)
            ORDER BY c.last_message_at DESC NULLS LAST, c.started_at DESC
            LIMIT $3 OFFSET $4""",
        user.business_id,
        status.value if status else None,
        limit,
        (page - 1) * limit,
    )
    total = rows[0]["totalCount"] if rows else 0
    items = []
    for row in rows:
        item = dict(row)
        item.pop("totalCount", None)
        items.append(item)
    return {"conversations": items, "total": total, "page": page}


@router.post("", status_code=201)
async def create_conversation(
    payload: ConversationCreate, user: AuthBusiness = Depends(current_business)
) -> dict[str, object]:
    async with transaction() as connection:
        conversation_id = await connection.fetchval(
            """INSERT INTO conversations (business_id, customer_id, external_conversation_id)
               VALUES ($1, $2, $3)
               RETURNING id""",
            user.business_id,
            payload.customerId,
            payload.externalConversationId,
        )
        await connection.execute(
            "INSERT INTO conversation_state (conversation_id, business_id, current_intent) VALUES ($1, $2, $3)",
            conversation_id,
            user.business_id,
            payload.currentIntent,
        )
    return {"conversation": {"id": str(conversation_id)}}


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: UUID, user: AuthBusiness = Depends(current_business)
) -> dict[str, object]:
    conversation = await fetchrow(
        """SELECT c.id, c.customer_id AS "customerId", cu.name AS "customerName",
                  c.status::text, c.external_conversation_id AS "externalConversationId",
                  c.started_at AS "startedAt", c.last_message_at AS "lastMessageAt", c.closed_at AS "closedAt",
                  CASE WHEN s.conversation_id IS NULL THEN NULL
                       ELSE jsonb_build_object(
                           'currentIntent', s.current_intent,
                           'currentStep', s.current_step,
                           'collectedData', s.collected_data,
                           'contextSummary', s.context_summary,
                           'lastAiResponse', s.last_ai_response
                       ) END AS state
             FROM conversations c
        LEFT JOIN customers cu ON cu.business_id = c.business_id AND cu.id = c.customer_id
        LEFT JOIN conversation_state s ON s.business_id = c.business_id AND s.conversation_id = c.id
            WHERE c.business_id = $1 AND c.id = $2""",
        user.business_id,
        conversation_id,
    )
    if not conversation:
        raise AppError(404, "Conversation not found.", "NOT_FOUND")
    messages = await fetch(
        """SELECT id, sender::text, message_type::text AS "messageType", content,
                  media_url AS "mediaUrl", metadata, sent_at AS "sentAt"
             FROM conversation_messages
            WHERE business_id = $1 AND conversation_id = $2
            ORDER BY sent_at, id
            LIMIT 500""",
        user.business_id,
        conversation_id,
    )
    return {"conversation": dict(conversation), "messages": [dict(row) for row in messages]}


@router.patch("/{conversation_id}")
async def update_conversation(
    conversation_id: UUID, payload: ConversationUpdate, user: AuthBusiness = Depends(current_business)
) -> dict[str, object]:
    async with transaction() as connection:
        if payload.customerId is not None:
            customer = await connection.fetchval(
                "SELECT 1 FROM customers WHERE business_id = $1 AND id = $2",
                user.business_id,
                payload.customerId,
            )
            if not customer:
                raise AppError(404, "Customer not found.", "CUSTOMER_NOT_FOUND")
        row = await connection.fetchrow(
            """UPDATE conversations
                  SET customer_id = $1
                WHERE business_id = $2 AND id = $3
            RETURNING id, customer_id AS "customerId", status::text""",
            payload.customerId,
            user.business_id,
            conversation_id,
        )
        if not row:
            raise AppError(404, "Conversation not found.", "NOT_FOUND")
    return {"conversation": dict(row)}


@router.patch("/{conversation_id}/status")
async def update_status(
    conversation_id: UUID, payload: StatusUpdate, user: AuthBusiness = Depends(current_business)
) -> dict[str, object]:
    async with transaction() as connection:
        current = await connection.fetchrow(
            "SELECT status::text FROM conversations WHERE business_id = $1 AND id = $2 FOR UPDATE",
            user.business_id,
            conversation_id,
        )
        if not current:
            raise AppError(404, "Conversation not found.", "NOT_FOUND")
        reopening = current["status"] == "CLOSED" and payload.status != ConversationStatus.CLOSED
        row = await connection.fetchrow(
            """UPDATE conversations
                  SET status = $1::conversation_status,
                      closed_at = CASE WHEN $1::conversation_status = 'CLOSED'::conversation_status
                                       THEN CURRENT_TIMESTAMP ELSE NULL END
                WHERE business_id = $2 AND id = $3
            RETURNING id, status::text, closed_at AS "closedAt" """,
            payload.status.value,
            user.business_id,
            conversation_id,
        )
        if reopening:
            await connection.execute(
                "INSERT INTO conversation_state (conversation_id, business_id) VALUES ($1, $2)",
                conversation_id,
                user.business_id,
            )
    return {"conversation": dict(row)}


@router.patch("/{conversation_id}/state")
async def update_state(
    conversation_id: UUID, payload: StateUpdate, user: AuthBusiness = Depends(current_business)
) -> dict[str, object]:
    row = await fetchrow(
        """UPDATE conversation_state
              SET current_intent = $1, current_step = $2, collected_data = $3,
                  context_summary = $4, last_ai_response = $5
            WHERE business_id = $6 AND conversation_id = $7
        RETURNING current_intent AS "currentIntent", current_step AS "currentStep",
                  collected_data AS "collectedData", context_summary AS "contextSummary",
                  last_ai_response AS "lastAiResponse" """,
        payload.currentIntent,
        payload.currentStep,
        payload.collectedData,
        payload.contextSummary,
        payload.lastAiResponse,
        user.business_id,
        conversation_id,
    )
    if not row:
        raise AppError(409, "Only open conversations have workflow state.", "CONVERSATION_CLOSED")
    return {"state": dict(row)}


@router.post("/{conversation_id}/messages", status_code=201)
async def send_message(
    conversation_id: UUID, payload: MessageCreate, user: AuthBusiness = Depends(current_business)
) -> dict[str, object]:
    row = await fetchrow(
        """INSERT INTO conversation_messages (business_id, conversation_id, sender, message_type, content, metadata)
           SELECT $1, $2, 'BUSINESS', 'TEXT', $3, $4
            WHERE EXISTS (
              SELECT 1 FROM conversations WHERE business_id = $1 AND id = $2 AND status <> 'CLOSED'
            )
        RETURNING id, sender::text, message_type::text AS "messageType", content, metadata, sent_at AS "sentAt" """,
        user.business_id,
        conversation_id,
        payload.content,
        payload.metadata,
    )
    if not row:
        raise AppError(409, "Cannot send a message to a closed conversation.", "CONVERSATION_CLOSED")
    return {"message": dict(row)}
