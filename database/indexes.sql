CREATE INDEX idx_businesses_status
    ON businesses USING btree (status, id);

CREATE INDEX idx_business_auth_codes_active
    ON business_auth_codes USING btree (business_id, code_type, expires_at DESC)
    WHERE consumed_at IS NULL;

CREATE INDEX idx_business_sessions_active
    ON business_sessions USING btree (business_id, expires_at DESC)
    WHERE revoked_at IS NULL;

CREATE UNIQUE INDEX uq_business_channels_external_account
    ON business_channels USING btree (channel, provider, external_account_id)
    WHERE external_account_id IS NOT NULL;

CREATE INDEX idx_business_channels_enabled
    ON business_channels USING btree (business_id, enabled, channel);

CREATE UNIQUE INDEX uq_customer_identities_tenant_channel_identifier
    ON customer_identities USING btree (
        business_id,
        channel,
        (CASE
            WHEN channel = 'EMAIL'::channel_type THEN lower(identifier)
            ELSE identifier
        END)
    );

CREATE UNIQUE INDEX uq_customer_identities_primary_per_channel
    ON customer_identities USING btree (business_id, customer_id, channel)
    WHERE is_primary;

CREATE INDEX idx_customer_identities_lookup
    ON customer_identities USING btree (business_id, channel, identifier);

CREATE INDEX idx_customer_identities_customer_channel
    ON customer_identities USING btree (business_id, customer_id, channel);

CREATE INDEX idx_conversations_customer_channel_last_message
    ON conversations USING btree (business_id, customer_id, channel, last_message_at DESC);

CREATE INDEX idx_conversations_status_last_message
    ON conversations USING btree (business_id, status, last_message_at DESC);

CREATE INDEX idx_conversations_business_channel_last_message
    ON conversations USING btree (business_id, channel, last_message_at DESC);

CREATE UNIQUE INDEX uq_conversations_external_id
    ON conversations USING btree (business_id, channel, external_conversation_id)
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

CREATE INDEX idx_appointments_created_channel
    ON appointments USING btree (business_id, created_channel, scheduled_start);
