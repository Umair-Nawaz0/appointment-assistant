BEGIN;

SET LOCAL client_min_messages = warning;
SET LOCAL search_path = public, pg_catalog;

CREATE TYPE business_status AS ENUM (
    'ACTIVE',
    'INACTIVE',
    'SUSPENDED'
);

CREATE TYPE day_of_week AS ENUM (
    'MONDAY',
    'TUESDAY',
    'WEDNESDAY',
    'THURSDAY',
    'FRIDAY',
    'SATURDAY',
    'SUNDAY'
);

CREATE TYPE business_auth_code_type AS ENUM (
    'EMAIL_VERIFICATION',
    'PASSWORD_RESET'
);

CREATE TYPE conversation_status AS ENUM (
    'ACTIVE',
    'WAITING_CUSTOMER',
    'WAITING_BUSINESS',
    'CLOSED'
);

CREATE TYPE appointment_status AS ENUM (
    'PENDING',
    'CONFIRMED',
    'CANCELLED',
    'COMPLETED',
    'NO_SHOW'
);

CREATE TYPE message_sender AS ENUM (
    'CUSTOMER',
    'AI',
    'BUSINESS',
    'SYSTEM'
);

CREATE TYPE message_type AS ENUM (
    'TEXT',
    'IMAGE',
    'AUDIO',
    'VIDEO',
    'DOCUMENT'
);

CREATE FUNCTION set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $function$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$function$;

CREATE FUNCTION validate_business_timezone()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $function$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_timezone_names
        WHERE name = NEW.timezone
    ) THEN
        RAISE EXCEPTION 'Unknown PostgreSQL time zone: %', NEW.timezone
            USING ERRCODE = '22023';
    END IF;

    RETURN NEW;
END;
$function$;

CREATE FUNCTION enforce_open_conversation_state()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $function$
DECLARE
    target_business_id uuid;
    target_conversation_id uuid;
    current_status conversation_status;
BEGIN
    IF TG_OP = 'UPDATE'
       AND (
           NEW.business_id IS DISTINCT FROM OLD.business_id
           OR NEW.conversation_id IS DISTINCT FROM OLD.conversation_id
       ) THEN
        RAISE EXCEPTION 'Conversation state ownership keys are immutable'
            USING ERRCODE = '23514';
    END IF;

    IF TG_OP = 'DELETE' THEN
        target_business_id := OLD.business_id;
        target_conversation_id := OLD.conversation_id;
    ELSE
        target_business_id := NEW.business_id;
        target_conversation_id := NEW.conversation_id;
    END IF;

    SELECT status
    INTO current_status
    FROM public.conversations
    WHERE id = target_conversation_id
      AND business_id = target_business_id
    FOR UPDATE;

    IF TG_OP <> 'DELETE'
       AND current_status = 'CLOSED'::conversation_status THEN
        RAISE EXCEPTION 'Conversation state cannot exist for closed conversation %',
            target_conversation_id
            USING ERRCODE = '23514';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;

    RETURN NEW;
END;
$function$;

CREATE FUNCTION enforce_conversation_state_cardinality()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $function$
DECLARE
    target_conversation_id uuid;
    current_status conversation_status;
    state_exists boolean;
BEGIN
    IF TG_TABLE_NAME = 'conversations' THEN
        IF TG_OP = 'DELETE' THEN
            target_conversation_id := OLD.id;
        ELSE
            target_conversation_id := NEW.id;
        END IF;
    ELSIF TG_OP = 'DELETE' THEN
        target_conversation_id := OLD.conversation_id;
    ELSE
        target_conversation_id := NEW.conversation_id;
    END IF;

    SELECT status
    INTO current_status
    FROM public.conversations
    WHERE id = target_conversation_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM public.conversation_state
        WHERE conversation_id = target_conversation_id
    )
    INTO state_exists;

    IF (current_status <> 'CLOSED'::conversation_status) <> state_exists THEN
        RAISE EXCEPTION
            'Conversation % must have exactly one state row while open and none while closed',
            target_conversation_id
            USING ERRCODE = '23514';
    END IF;

    RETURN NULL;
END;
$function$;

CREATE FUNCTION remove_state_when_conversation_closes()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $function$
BEGIN
    IF NEW.status = 'CLOSED'::conversation_status
       AND OLD.status IS DISTINCT FROM NEW.status THEN
        DELETE FROM public.conversation_state
        WHERE conversation_id = NEW.id;
    END IF;

    RETURN NEW;
END;
$function$;

CREATE FUNCTION advance_conversation_last_message_at()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $function$
BEGIN
    UPDATE public.conversations
    SET last_message_at = CASE
        WHEN last_message_at IS NULL OR last_message_at < NEW.sent_at
            THEN NEW.sent_at
        ELSE last_message_at
    END
    WHERE id = NEW.conversation_id
      AND business_id = NEW.business_id;

    RETURN NEW;
END;
$function$;

CREATE TABLE businesses (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    address text,
    city text,
    state_province text,
    postal_code text,
    country_code character(2),
    industry text,
    timezone text DEFAULT 'UTC'::text NOT NULL,
    status business_status DEFAULT 'ACTIVE'::business_status NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    email text NOT NULL,
    password_hash text NOT NULL,
    email_verified_at timestamp with time zone,
    last_login_at timestamp with time zone
);

CREATE TABLE business_settings (
    business_id uuid NOT NULL,
    appointment_duration_minutes integer DEFAULT 30 NOT NULL,
    booking_window_days integer DEFAULT 30 NOT NULL,
    maximum_appointments_per_day integer,
    allow_cancellation boolean DEFAULT true NOT NULL,
    allow_reschedule boolean DEFAULT true NOT NULL,
    collect_phone boolean DEFAULT false NOT NULL,
    collect_email boolean DEFAULT false NOT NULL,
    confirmation_required boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE business_hours (
    business_id uuid NOT NULL,
    day_of_week day_of_week NOT NULL,
    opens_at time without time zone NOT NULL,
    closes_at time without time zone NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE business_schedule_overrides (
    business_id uuid NOT NULL,
    override_date date NOT NULL,
    is_closed boolean NOT NULL,
    opens_at time without time zone,
    closes_at time without time zone,
    reason text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE customers (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    business_id uuid NOT NULL,
    name text,
    phone text,
    email text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE business_auth_codes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    business_id uuid NOT NULL,
    code_type business_auth_code_type NOT NULL,
    code_hash character(64) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    consumed_at timestamp with time zone,
    attempt_count smallint DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE business_sessions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    business_id uuid NOT NULL,
    token_hash character(64) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    last_seen_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    revoked_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE conversations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    business_id uuid NOT NULL,
    customer_id uuid,
    external_conversation_id text,
    status conversation_status DEFAULT 'ACTIVE'::conversation_status NOT NULL,
    started_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_message_at timestamp with time zone,
    closed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE conversation_messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    business_id uuid NOT NULL,
    conversation_id uuid NOT NULL,
    sender message_sender NOT NULL,
    message_type message_type NOT NULL,
    content text,
    media_url text,
    external_message_id text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    sent_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE conversation_state (
    conversation_id uuid NOT NULL,
    business_id uuid NOT NULL,
    current_intent text,
    current_step text,
    collected_data jsonb DEFAULT '{}'::jsonb NOT NULL,
    context_summary text,
    last_ai_response text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE appointments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    business_id uuid NOT NULL,
    customer_id uuid NOT NULL,
    conversation_id uuid,
    status appointment_status DEFAULT 'PENDING'::appointment_status NOT NULL,
    scheduled_start timestamp with time zone NOT NULL,
    scheduled_end timestamp with time zone NOT NULL,
    customer_name text,
    customer_phone text,
    customer_email text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

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

ALTER TABLE ONLY customers
    ADD CONSTRAINT pk_customers PRIMARY KEY (id),
    ADD CONSTRAINT uq_customers_business_id_id UNIQUE (business_id, id),
    ADD CONSTRAINT ck_customers_name_nonempty CHECK (
        name IS NULL OR btrim(name) <> ''::text
    ),
    ADD CONSTRAINT ck_customers_email CHECK (
        email IS NULL OR (
            email = lower(btrim(email))
            AND email LIKE '%_@_%._%'
            AND email !~ '[[:space:]]'::text
        )
    ),
    ADD CONSTRAINT ck_customers_phone_nonempty CHECK (
        phone IS NULL OR btrim(phone) <> ''::text
    ),
    ADD CONSTRAINT ck_customers_contact_info CHECK (
        name IS NOT NULL OR phone IS NOT NULL OR email IS NOT NULL
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
            WHEN message_type = 'TEXT'::message_type THEN content IS NOT NULL AND btrim(content) <> ''::text
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
        customer_email IS NULL OR (
            customer_email = lower(btrim(customer_email))
            AND customer_email LIKE '%_@_%._%'
            AND customer_email !~ '[[:space:]]'::text
        )
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

ALTER TABLE ONLY customers
    ADD CONSTRAINT fk_customers_business FOREIGN KEY (business_id)
        REFERENCES businesses(id) ON UPDATE NO ACTION ON DELETE CASCADE;

ALTER TABLE ONLY business_auth_codes
    ADD CONSTRAINT fk_business_auth_codes_business FOREIGN KEY (business_id)
        REFERENCES businesses(id) ON UPDATE NO ACTION ON DELETE CASCADE;

ALTER TABLE ONLY business_sessions
    ADD CONSTRAINT fk_business_sessions_business FOREIGN KEY (business_id)
        REFERENCES businesses(id) ON UPDATE NO ACTION ON DELETE CASCADE;

ALTER TABLE ONLY conversations
    ADD CONSTRAINT fk_conversations_business FOREIGN KEY (business_id)
        REFERENCES businesses(id) ON UPDATE NO ACTION ON DELETE CASCADE,
    ADD CONSTRAINT fk_conversations_customer FOREIGN KEY (business_id, customer_id)
        REFERENCES customers(business_id, id) ON UPDATE NO ACTION ON DELETE SET NULL (customer_id);

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

CREATE TRIGGER trg_businesses_validate_timezone
    BEFORE INSERT OR UPDATE OF timezone ON businesses
    FOR EACH ROW EXECUTE FUNCTION validate_business_timezone();

CREATE TRIGGER trg_businesses_set_updated_at
    BEFORE UPDATE ON businesses
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_business_settings_set_updated_at
    BEFORE UPDATE ON business_settings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_business_hours_set_updated_at
    BEFORE UPDATE ON business_hours
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_business_schedule_overrides_set_updated_at
    BEFORE UPDATE ON business_schedule_overrides
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_customers_set_updated_at
    BEFORE UPDATE ON customers
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_conversations_set_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_conversations_remove_state_on_close
    AFTER UPDATE OF status ON conversations
    FOR EACH ROW EXECUTE FUNCTION remove_state_when_conversation_closes();

CREATE TRIGGER trg_conversation_messages_advance_last_message
    AFTER INSERT ON conversation_messages
    FOR EACH ROW EXECUTE FUNCTION advance_conversation_last_message_at();

CREATE TRIGGER trg_conversation_state_require_open
    BEFORE INSERT OR UPDATE OR DELETE ON conversation_state
    FOR EACH ROW EXECUTE FUNCTION enforce_open_conversation_state();

CREATE CONSTRAINT TRIGGER trg_conversations_state_cardinality
    AFTER INSERT OR UPDATE OR DELETE ON conversations
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION enforce_conversation_state_cardinality();

CREATE CONSTRAINT TRIGGER trg_conversation_state_cardinality
    AFTER INSERT OR UPDATE OR DELETE ON conversation_state
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION enforce_conversation_state_cardinality();

CREATE TRIGGER trg_conversation_state_set_updated_at
    BEFORE UPDATE ON conversation_state
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_appointments_set_updated_at
    BEFORE UPDATE ON appointments
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON SCHEMA public IS
    'AI appointment assistant application schema.';

COMMENT ON TABLE businesses IS
    'Tenant root for each business that owns an AI receptionist.';
COMMENT ON COLUMN businesses.country_code IS
    'Optional ISO 3166-1 alpha-2 country code in uppercase.';
COMMENT ON COLUMN businesses.timezone IS
    'PostgreSQL/IANA time zone used to interpret local business dates and hours.';

COMMENT ON TABLE business_settings IS
    'One row per business containing appointment workflow settings.';
COMMENT ON COLUMN business_settings.maximum_appointments_per_day IS
    'Optional tenant-wide daily booking cap; NULL means unlimited.';
COMMENT ON TABLE business_hours IS
    'Weekly opening hours keyed by named weekday. An absent weekday is closed.';
COMMENT ON TABLE business_schedule_overrides IS
    'A date-specific replacement for weekly hours; closed dates have no opening interval.';

COMMENT ON TABLE customers IS
    'Tenant-owned customer profile created when entering the booking flow.';
COMMENT ON COLUMN customers.phone IS
    'Customer phone number collected for appointment booking.';
COMMENT ON COLUMN customers.email IS
    'Customer email address collected for appointment booking.';

COMMENT ON COLUMN businesses.email IS
    'Unique dashboard login and verification email for the business itself.';
COMMENT ON COLUMN businesses.password_hash IS
    'Strong one-way password hash for direct business authentication.';
COMMENT ON TABLE business_auth_codes IS
    'Short-lived hashed codes for business email verification and password reset.';
COMMENT ON TABLE business_sessions IS
    'Revocable sessions for authenticated businesses, identified by hashed cookie tokens.';

COMMENT ON TABLE conversations IS
    'Natural conversation stream between an anonymous visitor or customer and the AI assistant.';
COMMENT ON COLUMN conversations.customer_id IS
    'Optional customer association; NULL for anonymous chat until booking flow starts.';
COMMENT ON COLUMN conversations.external_conversation_id IS
    'Optional website session or widget client conversation identifier.';
COMMENT ON TABLE conversation_messages IS
    'Unified immutable message stream for web chat conversations.';
COMMENT ON TABLE conversation_state IS
    'Exactly one mutable AI workflow state row for each non-closed conversation.';

COMMENT ON TABLE appointments IS
    'Appointments with immutable contact snapshots captured at booking confirmation time.';
COMMENT ON COLUMN appointments.conversation_id IS
    'Optional source conversation; when present it must belong to the same tenant and customer.';
COMMENT ON COLUMN appointments.customer_phone IS
    'Historical booking-time snapshot; does not change if customer profile is later updated.';
COMMENT ON COLUMN appointments.customer_email IS
    'Historical booking-time snapshot; does not change if customer profile is later updated.';

COMMIT;
