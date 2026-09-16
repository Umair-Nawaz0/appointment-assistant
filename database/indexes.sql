CREATE INDEX idx_businesses_status
    ON businesses USING btree (status, id);

CREATE INDEX idx_business_auth_codes_active
    ON business_auth_codes USING btree (business_id, code_type, expires_at DESC)
    WHERE consumed_at IS NULL;

CREATE INDEX idx_business_sessions_active
    ON business_sessions USING btree (business_id, expires_at DESC)
    WHERE revoked_at IS NULL;

CREATE INDEX idx_customers_business_created
    ON customers USING btree (business_id, created_at DESC);

CREATE INDEX idx_customers_business_email
    ON customers USING btree (business_id, lower(email))
    WHERE email IS NOT NULL;

CREATE INDEX idx_customers_business_phone
    ON customers USING btree (business_id, phone)
    WHERE phone IS NOT NULL;

CREATE INDEX idx_conversations_status_last_message
    ON conversations USING btree (business_id, status, last_message_at DESC NULLS LAST);

CREATE INDEX idx_conversations_customer_last_message
    ON conversations USING btree (business_id, customer_id, last_message_at DESC NULLS LAST)
    WHERE customer_id IS NOT NULL;

CREATE INDEX idx_conversations_anonymous_last_message
    ON conversations USING btree (business_id, last_message_at DESC NULLS LAST)
    WHERE customer_id IS NULL;

CREATE UNIQUE INDEX uq_conversations_external_id
    ON conversations USING btree (business_id, external_conversation_id)
    WHERE external_conversation_id IS NOT NULL;

CREATE INDEX idx_conversation_messages_timeline
    ON conversation_messages USING btree (business_id, conversation_id, sent_at, id);

CREATE UNIQUE INDEX uq_conversation_messages_external_id
    ON conversation_messages USING btree (business_id, conversation_id, external_message_id)
    WHERE external_message_id IS NOT NULL;

CREATE INDEX idx_conversation_state_business_updated
    ON conversation_state USING btree (business_id, updated_at DESC);

CREATE INDEX idx_appointments_business_schedule
    ON appointments USING btree (business_id, scheduled_start);

CREATE INDEX idx_appointments_status_schedule
    ON appointments USING btree (business_id, status, scheduled_start);

CREATE INDEX idx_appointments_customer_schedule
    ON appointments USING btree (business_id, customer_id, scheduled_start DESC);

CREATE INDEX idx_appointments_conversation
    ON appointments USING btree (business_id, conversation_id)
    WHERE conversation_id IS NOT NULL;
