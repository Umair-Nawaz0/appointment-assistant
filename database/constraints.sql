ALTER TABLE ONLY businesses
    ADD CONSTRAINT pk_businesses PRIMARY KEY (id),
    ADD CONSTRAINT uq_businesses_email UNIQUE (email),
    ADD CONSTRAINT ck_businesses_name_nonempty CHECK (btrim(name) <> ''::text),
    ADD CONSTRAINT ck_businesses_email CHECK (
        email = lower(btrim(email))
        AND email LIKE '%_@_%._%'
        AND email !~ '[[:space:]]'::text
    ),
    ADD CONSTRAINT ck_businesses_password_hash CHECK (length(password_hash) >= 32),
    ADD CONSTRAINT ck_businesses_address_nonempty CHECK (
        address IS NULL OR btrim(address) <> ''::text
    ),
    ADD CONSTRAINT ck_businesses_city_nonempty CHECK (
        city IS NULL OR btrim(city) <> ''::text
    ),
    ADD CONSTRAINT ck_businesses_state_province_nonempty CHECK (
        state_province IS NULL OR btrim(state_province) <> ''::text
    ),
    ADD CONSTRAINT ck_businesses_postal_code_nonempty CHECK (
        postal_code IS NULL OR btrim(postal_code) <> ''::text
    ),
    ADD CONSTRAINT ck_businesses_country_code CHECK (
        country_code IS NULL OR country_code ~ '^[A-Z]{2}$'::text
    ),
    ADD CONSTRAINT ck_businesses_industry_nonempty CHECK (
        industry IS NULL OR btrim(industry) <> ''::text
    ),
    ADD CONSTRAINT ck_businesses_timezone_nonempty CHECK (btrim(timezone) <> ''::text),
    ADD CONSTRAINT ck_businesses_verified_time CHECK (
        email_verified_at IS NULL OR email_verified_at >= created_at
    ),
    ADD CONSTRAINT ck_businesses_last_login_time CHECK (
        last_login_at IS NULL OR last_login_at >= created_at
    );

ALTER TABLE ONLY business_settings
    ADD CONSTRAINT pk_business_settings PRIMARY KEY (business_id),
    ADD CONSTRAINT ck_business_settings_appointment_duration CHECK (
        appointment_duration_minutes BETWEEN 1 AND 1440
    ),
    ADD CONSTRAINT ck_business_settings_booking_window CHECK (
        booking_window_days BETWEEN 1 AND 3650
    ),
    ADD CONSTRAINT ck_business_settings_daily_capacity CHECK (
        maximum_appointments_per_day IS NULL OR maximum_appointments_per_day > 0
    );

ALTER TABLE ONLY business_hours
    ADD CONSTRAINT pk_business_hours PRIMARY KEY (business_id, day_of_week),
    ADD CONSTRAINT ck_business_hours_valid_interval CHECK (opens_at < closes_at);

ALTER TABLE ONLY business_schedule_overrides
    ADD CONSTRAINT pk_business_schedule_overrides PRIMARY KEY (business_id, override_date),
    ADD CONSTRAINT ck_business_schedule_overrides_hours CHECK (
        (is_closed AND opens_at IS NULL AND closes_at IS NULL)
        OR
        (NOT is_closed AND opens_at IS NOT NULL AND closes_at IS NOT NULL AND opens_at < closes_at)
    ),
    ADD CONSTRAINT ck_business_schedule_overrides_reason CHECK (
        reason IS NULL OR btrim(reason) <> ''::text
    );

ALTER TABLE ONLY business_channels
    ADD CONSTRAINT pk_business_channels PRIMARY KEY (business_id, channel),
    ADD CONSTRAINT ck_business_channels_provider CHECK (
        provider IS NULL OR btrim(provider) <> ''::text
    ),
    ADD CONSTRAINT ck_business_channels_external_account CHECK (
        external_account_id IS NULL OR btrim(external_account_id) <> ''::text
    ),
    ADD CONSTRAINT ck_business_channels_external_provider CHECK (
        external_account_id IS NULL OR provider IS NOT NULL
    ),
    ADD CONSTRAINT ck_business_channels_metadata_object CHECK (
        jsonb_typeof(metadata) = 'object'::text
    );

ALTER TABLE ONLY customers
    ADD CONSTRAINT pk_customers PRIMARY KEY (id),
    ADD CONSTRAINT uq_customers_business_id_id UNIQUE (business_id, id),
    ADD CONSTRAINT ck_customers_name_nonempty CHECK (
        name IS NULL OR btrim(name) <> ''::text
    );

ALTER TABLE ONLY business_auth_codes
    ADD CONSTRAINT pk_business_auth_codes PRIMARY KEY (id),
    ADD CONSTRAINT uq_business_auth_codes_hash UNIQUE (code_hash),
    ADD CONSTRAINT ck_business_auth_codes_hash CHECK (
        code_hash ~ '^[0-9a-f]{64}$'::text
    ),
    ADD CONSTRAINT ck_business_auth_codes_expiry CHECK (expires_at > created_at),
    ADD CONSTRAINT ck_business_auth_codes_consumed_time CHECK (
        consumed_at IS NULL OR consumed_at >= created_at
    ),
    ADD CONSTRAINT ck_business_auth_codes_attempts CHECK (attempt_count BETWEEN 0 AND 5);

ALTER TABLE ONLY business_sessions
    ADD CONSTRAINT pk_business_sessions PRIMARY KEY (id),
    ADD CONSTRAINT uq_business_sessions_hash UNIQUE (token_hash),
    ADD CONSTRAINT ck_business_sessions_hash CHECK (
        token_hash ~ '^[0-9a-f]{64}$'::text
    ),
    ADD CONSTRAINT ck_business_sessions_expiry CHECK (expires_at > created_at),
    ADD CONSTRAINT ck_business_sessions_last_seen CHECK (last_seen_at >= created_at),
    ADD CONSTRAINT ck_business_sessions_revoked_time CHECK (
        revoked_at IS NULL OR revoked_at >= created_at
    );

ALTER TABLE ONLY customer_identities
    ADD CONSTRAINT pk_customer_identities PRIMARY KEY (id),
    ADD CONSTRAINT ck_customer_identities_identifier CHECK (
        identifier = btrim(identifier) AND identifier <> ''::text
    ),
    ADD CONSTRAINT ck_customer_identities_display_name CHECK (
        display_name IS NULL OR btrim(display_name) <> ''::text
    );

ALTER TABLE ONLY conversations
    ADD CONSTRAINT pk_conversations PRIMARY KEY (id),
    ADD CONSTRAINT uq_conversations_business_id_id UNIQUE (business_id, id),
    ADD CONSTRAINT uq_conversations_business_customer_id UNIQUE (business_id, customer_id, id),
    ADD CONSTRAINT ck_conversations_external_id CHECK (
        external_conversation_id IS NULL OR btrim(external_conversation_id) <> ''::text
    ),
    ADD CONSTRAINT ck_conversations_last_message_time CHECK (
        last_message_at IS NULL OR last_message_at >= started_at
    ),
    ADD CONSTRAINT ck_conversations_closed_state CHECK (
        (status = 'CLOSED'::conversation_status) = (closed_at IS NOT NULL)
    ),
    ADD CONSTRAINT ck_conversations_closed_time CHECK (
        closed_at IS NULL OR closed_at >= started_at
    );

ALTER TABLE ONLY conversation_messages
    ADD CONSTRAINT pk_conversation_messages PRIMARY KEY (id),
    ADD CONSTRAINT ck_conversation_messages_content CHECK (
        CASE
            WHEN message_type = ANY (
                ARRAY['TEXT'::message_type, 'EMAIL'::message_type, 'CALL_TRANSCRIPT'::message_type]
            ) THEN content IS NOT NULL AND btrim(content) <> ''::text
            ELSE
                (content IS NOT NULL AND btrim(content) <> ''::text)
                OR (media_url IS NOT NULL AND btrim(media_url) <> ''::text)
        END
    ),
    ADD CONSTRAINT ck_conversation_messages_media_url CHECK (
        media_url IS NULL OR btrim(media_url) <> ''::text
    ),
    ADD CONSTRAINT ck_conversation_messages_external_id CHECK (
        external_message_id IS NULL OR btrim(external_message_id) <> ''::text
    ),
    ADD CONSTRAINT ck_conversation_messages_metadata_object CHECK (
        jsonb_typeof(metadata) = 'object'::text
    );

ALTER TABLE ONLY conversation_state
    ADD CONSTRAINT pk_conversation_state PRIMARY KEY (conversation_id),
    ADD CONSTRAINT ck_conversation_state_current_intent CHECK (
        current_intent IS NULL OR btrim(current_intent) <> ''::text
    ),
    ADD CONSTRAINT ck_conversation_state_current_step CHECK (
        current_step IS NULL OR btrim(current_step) <> ''::text
    ),
    ADD CONSTRAINT ck_conversation_state_collected_data_object CHECK (
        jsonb_typeof(collected_data) = 'object'::text
    );

ALTER TABLE ONLY appointments
    ADD CONSTRAINT pk_appointments PRIMARY KEY (id),
    ADD CONSTRAINT ck_appointments_schedule CHECK (scheduled_end > scheduled_start),
    ADD CONSTRAINT ck_appointments_customer_name CHECK (
        customer_name IS NULL OR btrim(customer_name) <> ''::text
    ),
    ADD CONSTRAINT ck_appointments_customer_phone CHECK (
        customer_phone IS NULL OR btrim(customer_phone) <> ''::text
    ),
    ADD CONSTRAINT ck_appointments_customer_email CHECK (
        customer_email IS NULL OR btrim(customer_email) <> ''::text
    );

ALTER TABLE ONLY business_settings
    ADD CONSTRAINT fk_business_settings_business FOREIGN KEY (business_id)
        REFERENCES businesses(id) ON UPDATE NO ACTION ON DELETE CASCADE;

ALTER TABLE ONLY business_hours
    ADD CONSTRAINT fk_business_hours_business FOREIGN KEY (business_id)
        REFERENCES businesses(id) ON UPDATE NO ACTION ON DELETE CASCADE;

ALTER TABLE ONLY business_schedule_overrides
    ADD CONSTRAINT fk_business_schedule_overrides_business FOREIGN KEY (business_id)
        REFERENCES businesses(id) ON UPDATE NO ACTION ON DELETE CASCADE;

ALTER TABLE ONLY business_channels
    ADD CONSTRAINT fk_business_channels_business FOREIGN KEY (business_id)
        REFERENCES businesses(id) ON UPDATE NO ACTION ON DELETE CASCADE;

ALTER TABLE ONLY customers
    ADD CONSTRAINT fk_customers_business FOREIGN KEY (business_id)
        REFERENCES businesses(id) ON UPDATE NO ACTION ON DELETE CASCADE;

ALTER TABLE ONLY business_auth_codes
    ADD CONSTRAINT fk_business_auth_codes_business FOREIGN KEY (business_id)
        REFERENCES businesses(id) ON UPDATE NO ACTION ON DELETE CASCADE;

ALTER TABLE ONLY business_sessions
    ADD CONSTRAINT fk_business_sessions_business FOREIGN KEY (business_id)
        REFERENCES businesses(id) ON UPDATE NO ACTION ON DELETE CASCADE;

ALTER TABLE ONLY customer_identities
    ADD CONSTRAINT fk_customer_identities_customer FOREIGN KEY (business_id, customer_id)
        REFERENCES customers(business_id, id) ON UPDATE NO ACTION ON DELETE CASCADE;

ALTER TABLE ONLY conversations
    ADD CONSTRAINT fk_conversations_business FOREIGN KEY (business_id)
        REFERENCES businesses(id) ON UPDATE NO ACTION ON DELETE CASCADE,
    ADD CONSTRAINT fk_conversations_customer FOREIGN KEY (business_id, customer_id)
        REFERENCES customers(business_id, id) ON UPDATE NO ACTION ON DELETE CASCADE,
    ADD CONSTRAINT fk_conversations_business_channel FOREIGN KEY (business_id, channel)
        REFERENCES business_channels(business_id, channel)
        ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE ONLY conversation_messages
    ADD CONSTRAINT fk_conversation_messages_conversation FOREIGN KEY (business_id, conversation_id)
        REFERENCES conversations(business_id, id) ON UPDATE NO ACTION ON DELETE CASCADE;

ALTER TABLE ONLY conversation_state
    ADD CONSTRAINT fk_conversation_state_conversation FOREIGN KEY (business_id, conversation_id)
        REFERENCES conversations(business_id, id) ON UPDATE NO ACTION ON DELETE CASCADE;

ALTER TABLE ONLY appointments
    ADD CONSTRAINT fk_appointments_business FOREIGN KEY (business_id)
        REFERENCES businesses(id) ON UPDATE NO ACTION ON DELETE CASCADE,
    ADD CONSTRAINT fk_appointments_customer FOREIGN KEY (business_id, customer_id)
        REFERENCES customers(business_id, id)
        ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    ADD CONSTRAINT fk_appointments_conversation FOREIGN KEY (business_id, customer_id, conversation_id)
        REFERENCES conversations(business_id, customer_id, id)
        ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;
