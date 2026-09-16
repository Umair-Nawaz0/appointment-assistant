--
-- PostgreSQL database dump
--

\restrict aUoxsmhF5jEPIIhqX3DoWlF4CQQrffsONpsQbRozgMdKhugzDJYkYEVkvIvtrah

-- Dumped from database version 18.6 (Ubuntu 18.6-0ubuntu0.26.04.1)
-- Dumped by pg_dump version 18.6 (Ubuntu 18.6-0ubuntu0.26.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA public;


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS 'AI appointment assistant application schema.';


--
-- Name: appointment_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.appointment_status AS ENUM (
    'PENDING',
    'CONFIRMED',
    'CANCELLED',
    'COMPLETED',
    'NO_SHOW'
);


--
-- Name: business_auth_code_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.business_auth_code_type AS ENUM (
    'EMAIL_VERIFICATION',
    'PASSWORD_RESET'
);


--
-- Name: business_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.business_status AS ENUM (
    'ACTIVE',
    'INACTIVE',
    'SUSPENDED'
);


--
-- Name: conversation_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.conversation_status AS ENUM (
    'ACTIVE',
    'WAITING_CUSTOMER',
    'WAITING_BUSINESS',
    'CLOSED'
);


--
-- Name: day_of_week; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.day_of_week AS ENUM (
    'MONDAY',
    'TUESDAY',
    'WEDNESDAY',
    'THURSDAY',
    'FRIDAY',
    'SATURDAY',
    'SUNDAY'
);


--
-- Name: message_sender; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.message_sender AS ENUM (
    'CUSTOMER',
    'AI',
    'BUSINESS',
    'SYSTEM'
);


--
-- Name: message_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.message_type AS ENUM (
    'TEXT',
    'IMAGE',
    'AUDIO',
    'VIDEO',
    'DOCUMENT'
);


--
-- Name: advance_conversation_last_message_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.advance_conversation_last_message_at() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
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
$$;


--
-- Name: enforce_conversation_state_cardinality(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.enforce_conversation_state_cardinality() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
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
$$;


--
-- Name: enforce_open_conversation_state(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.enforce_open_conversation_state() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
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
$$;


--
-- Name: remove_state_when_conversation_closes(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.remove_state_when_conversation_closes() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
BEGIN
    IF NEW.status = 'CLOSED'::conversation_status
       AND OLD.status IS DISTINCT FROM NEW.status THEN
        DELETE FROM public.conversation_state
        WHERE conversation_id = NEW.id;
    END IF;

    RETURN NEW;
END;
$$;


--
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


--
-- Name: validate_business_timezone(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.validate_business_timezone() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
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
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: appointments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.appointments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    business_id uuid NOT NULL,
    customer_id uuid NOT NULL,
    conversation_id uuid,
    status public.appointment_status DEFAULT 'PENDING'::public.appointment_status NOT NULL,
    scheduled_start timestamp with time zone NOT NULL,
    scheduled_end timestamp with time zone NOT NULL,
    customer_name text,
    customer_phone text,
    customer_email text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_appointments_customer_email CHECK (((customer_email IS NULL) OR ((customer_email = lower(btrim(customer_email))) AND (customer_email ~~ '%_@_%._%'::text) AND (customer_email !~ '[[:space:]]'::text)))),
    CONSTRAINT ck_appointments_customer_name CHECK (((customer_name IS NULL) OR (btrim(customer_name) <> ''::text))),
    CONSTRAINT ck_appointments_customer_phone CHECK (((customer_phone IS NULL) OR (btrim(customer_phone) <> ''::text))),
    CONSTRAINT ck_appointments_schedule CHECK ((scheduled_end > scheduled_start))
);


--
-- Name: TABLE appointments; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.appointments IS 'Appointments with immutable contact snapshots captured at booking confirmation time.';


--
-- Name: COLUMN appointments.conversation_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.appointments.conversation_id IS 'Optional source conversation; when present it must belong to the same tenant and customer.';


--
-- Name: COLUMN appointments.customer_phone; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.appointments.customer_phone IS 'Historical booking-time snapshot; does not change if customer profile is later updated.';


--
-- Name: COLUMN appointments.customer_email; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.appointments.customer_email IS 'Historical booking-time snapshot; does not change if customer profile is later updated.';


--
-- Name: business_auth_codes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.business_auth_codes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    business_id uuid NOT NULL,
    code_type public.business_auth_code_type NOT NULL,
    code_hash character(64) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    consumed_at timestamp with time zone,
    attempt_count smallint DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_business_auth_codes_attempts CHECK (((attempt_count >= 0) AND (attempt_count <= 5))),
    CONSTRAINT ck_business_auth_codes_consumed_time CHECK (((consumed_at IS NULL) OR (consumed_at >= created_at))),
    CONSTRAINT ck_business_auth_codes_expiry CHECK ((expires_at > created_at)),
    CONSTRAINT ck_business_auth_codes_hash CHECK ((code_hash ~ '^[0-9a-f]{64}$'::text))
);


--
-- Name: TABLE business_auth_codes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.business_auth_codes IS 'Short-lived hashed codes for business email verification and password reset.';


--
-- Name: business_hours; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.business_hours (
    business_id uuid NOT NULL,
    day_of_week public.day_of_week NOT NULL,
    opens_at time without time zone NOT NULL,
    closes_at time without time zone NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_business_hours_valid_interval CHECK ((opens_at < closes_at))
);


--
-- Name: TABLE business_hours; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.business_hours IS 'Weekly opening hours keyed by named weekday. An absent weekday is closed.';


--
-- Name: business_schedule_overrides; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.business_schedule_overrides (
    business_id uuid NOT NULL,
    override_date date NOT NULL,
    is_closed boolean NOT NULL,
    opens_at time without time zone,
    closes_at time without time zone,
    reason text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_business_schedule_overrides_hours CHECK (((is_closed AND (opens_at IS NULL) AND (closes_at IS NULL)) OR ((NOT is_closed) AND (opens_at IS NOT NULL) AND (closes_at IS NOT NULL) AND (opens_at < closes_at)))),
    CONSTRAINT ck_business_schedule_overrides_reason CHECK (((reason IS NULL) OR (btrim(reason) <> ''::text)))
);


--
-- Name: TABLE business_schedule_overrides; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.business_schedule_overrides IS 'A date-specific replacement for weekly hours; closed dates have no opening interval.';


--
-- Name: business_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.business_sessions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    business_id uuid NOT NULL,
    token_hash character(64) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    last_seen_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    revoked_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_business_sessions_expiry CHECK ((expires_at > created_at)),
    CONSTRAINT ck_business_sessions_hash CHECK ((token_hash ~ '^[0-9a-f]{64}$'::text)),
    CONSTRAINT ck_business_sessions_last_seen CHECK ((last_seen_at >= created_at)),
    CONSTRAINT ck_business_sessions_revoked_time CHECK (((revoked_at IS NULL) OR (revoked_at >= created_at)))
);


--
-- Name: TABLE business_sessions; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.business_sessions IS 'Revocable sessions for authenticated businesses, identified by hashed cookie tokens.';


--
-- Name: business_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.business_settings (
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
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_business_settings_appointment_duration CHECK (((appointment_duration_minutes >= 1) AND (appointment_duration_minutes <= 1440))),
    CONSTRAINT ck_business_settings_booking_window CHECK (((booking_window_days >= 1) AND (booking_window_days <= 3650))),
    CONSTRAINT ck_business_settings_daily_capacity CHECK (((maximum_appointments_per_day IS NULL) OR (maximum_appointments_per_day > 0)))
);


--
-- Name: TABLE business_settings; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.business_settings IS 'One row per business containing appointment workflow settings.';


--
-- Name: COLUMN business_settings.maximum_appointments_per_day; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.business_settings.maximum_appointments_per_day IS 'Optional tenant-wide daily booking cap; NULL means unlimited.';


--
-- Name: businesses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.businesses (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    address text,
    city text,
    state_province text,
    postal_code text,
    country_code character(2),
    industry text,
    timezone text DEFAULT 'UTC'::text NOT NULL,
    status public.business_status DEFAULT 'ACTIVE'::public.business_status NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    email text NOT NULL,
    password_hash text NOT NULL,
    email_verified_at timestamp with time zone,
    last_login_at timestamp with time zone,
    CONSTRAINT ck_businesses_address_nonempty CHECK (((address IS NULL) OR (btrim(address) <> ''::text))),
    CONSTRAINT ck_businesses_city_nonempty CHECK (((city IS NULL) OR (btrim(city) <> ''::text))),
    CONSTRAINT ck_businesses_country_code CHECK (((country_code IS NULL) OR (country_code ~ '^[A-Z]{2}$'::text))),
    CONSTRAINT ck_businesses_email CHECK (((email = lower(btrim(email))) AND (email ~~ '%_@_%._%'::text) AND (email !~ '[[:space:]]'::text))),
    CONSTRAINT ck_businesses_industry_nonempty CHECK (((industry IS NULL) OR (btrim(industry) <> ''::text))),
    CONSTRAINT ck_businesses_last_login_time CHECK (((last_login_at IS NULL) OR (last_login_at >= created_at))),
    CONSTRAINT ck_businesses_name_nonempty CHECK ((btrim(name) <> ''::text)),
    CONSTRAINT ck_businesses_password_hash CHECK ((length(password_hash) >= 32)),
    CONSTRAINT ck_businesses_postal_code_nonempty CHECK (((postal_code IS NULL) OR (btrim(postal_code) <> ''::text))),
    CONSTRAINT ck_businesses_state_province_nonempty CHECK (((state_province IS NULL) OR (btrim(state_province) <> ''::text))),
    CONSTRAINT ck_businesses_timezone_nonempty CHECK ((btrim(timezone) <> ''::text)),
    CONSTRAINT ck_businesses_verified_time CHECK (((email_verified_at IS NULL) OR (email_verified_at >= created_at)))
);


--
-- Name: TABLE businesses; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.businesses IS 'Tenant root for each business that owns an AI receptionist.';


--
-- Name: COLUMN businesses.country_code; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.businesses.country_code IS 'Optional ISO 3166-1 alpha-2 country code in uppercase.';


--
-- Name: COLUMN businesses.timezone; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.businesses.timezone IS 'PostgreSQL/IANA time zone used to interpret local business dates and hours.';


--
-- Name: COLUMN businesses.email; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.businesses.email IS 'Unique dashboard login and verification email for the business itself.';


--
-- Name: COLUMN businesses.password_hash; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.businesses.password_hash IS 'Strong one-way password hash for direct business authentication.';


--
-- Name: conversation_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversation_messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    business_id uuid NOT NULL,
    conversation_id uuid NOT NULL,
    sender public.message_sender NOT NULL,
    message_type public.message_type NOT NULL,
    content text,
    media_url text,
    external_message_id text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    sent_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_conversation_messages_content CHECK (
CASE
    WHEN (message_type = 'TEXT'::public.message_type) THEN ((content IS NOT NULL) AND (btrim(content) <> ''::text))
    ELSE (((content IS NOT NULL) AND (btrim(content) <> ''::text)) OR ((media_url IS NOT NULL) AND (btrim(media_url) <> ''::text)))
END),
    CONSTRAINT ck_conversation_messages_external_id CHECK (((external_message_id IS NULL) OR (btrim(external_message_id) <> ''::text))),
    CONSTRAINT ck_conversation_messages_media_url CHECK (((media_url IS NULL) OR (btrim(media_url) <> ''::text))),
    CONSTRAINT ck_conversation_messages_metadata_object CHECK ((jsonb_typeof(metadata) = 'object'::text))
);


--
-- Name: TABLE conversation_messages; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.conversation_messages IS 'Unified immutable message stream for web chat conversations.';


--
-- Name: conversation_state; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversation_state (
    conversation_id uuid NOT NULL,
    business_id uuid NOT NULL,
    current_intent text,
    current_step text,
    collected_data jsonb DEFAULT '{}'::jsonb NOT NULL,
    context_summary text,
    last_ai_response text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_conversation_state_collected_data_object CHECK ((jsonb_typeof(collected_data) = 'object'::text)),
    CONSTRAINT ck_conversation_state_current_intent CHECK (((current_intent IS NULL) OR (btrim(current_intent) <> ''::text))),
    CONSTRAINT ck_conversation_state_current_step CHECK (((current_step IS NULL) OR (btrim(current_step) <> ''::text)))
);


--
-- Name: TABLE conversation_state; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.conversation_state IS 'Exactly one mutable AI workflow state row for each non-closed conversation.';


--
-- Name: conversations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    business_id uuid NOT NULL,
    customer_id uuid,
    external_conversation_id text,
    status public.conversation_status DEFAULT 'ACTIVE'::public.conversation_status NOT NULL,
    started_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_message_at timestamp with time zone,
    closed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_conversations_closed_state CHECK (((status = 'CLOSED'::public.conversation_status) = (closed_at IS NOT NULL))),
    CONSTRAINT ck_conversations_closed_time CHECK (((closed_at IS NULL) OR (closed_at >= started_at))),
    CONSTRAINT ck_conversations_external_id CHECK (((external_conversation_id IS NULL) OR (btrim(external_conversation_id) <> ''::text))),
    CONSTRAINT ck_conversations_last_message_time CHECK (((last_message_at IS NULL) OR (last_message_at >= started_at)))
);


--
-- Name: TABLE conversations; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.conversations IS 'Natural conversation stream between an anonymous visitor or customer and the AI assistant.';


--
-- Name: COLUMN conversations.customer_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.conversations.customer_id IS 'Optional customer association; NULL for anonymous chat until booking flow starts.';


--
-- Name: COLUMN conversations.external_conversation_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.conversations.external_conversation_id IS 'Optional website session or widget client conversation identifier.';


--
-- Name: customers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.customers (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    business_id uuid NOT NULL,
    name text,
    phone text,
    email text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_customers_contact_info CHECK (((name IS NOT NULL) OR (phone IS NOT NULL) OR (email IS NOT NULL))),
    CONSTRAINT ck_customers_email CHECK (((email IS NULL) OR ((email = lower(btrim(email))) AND (email ~~ '%_@_%._%'::text) AND (email !~ '[[:space:]]'::text)))),
    CONSTRAINT ck_customers_name_nonempty CHECK (((name IS NULL) OR (btrim(name) <> ''::text))),
    CONSTRAINT ck_customers_phone_nonempty CHECK (((phone IS NULL) OR (btrim(phone) <> ''::text)))
);


--
-- Name: TABLE customers; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.customers IS 'Tenant-owned customer profile created when entering the booking flow.';


--
-- Name: COLUMN customers.phone; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.customers.phone IS 'Customer phone number collected for appointment booking.';


--
-- Name: COLUMN customers.email; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.customers.email IS 'Customer email address collected for appointment booking.';


--
-- Name: appointments pk_appointments; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT pk_appointments PRIMARY KEY (id);


--
-- Name: business_auth_codes pk_business_auth_codes; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_auth_codes
    ADD CONSTRAINT pk_business_auth_codes PRIMARY KEY (id);


--
-- Name: business_hours pk_business_hours; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_hours
    ADD CONSTRAINT pk_business_hours PRIMARY KEY (business_id, day_of_week);


--
-- Name: business_schedule_overrides pk_business_schedule_overrides; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_schedule_overrides
    ADD CONSTRAINT pk_business_schedule_overrides PRIMARY KEY (business_id, override_date);


--
-- Name: business_sessions pk_business_sessions; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_sessions
    ADD CONSTRAINT pk_business_sessions PRIMARY KEY (id);


--
-- Name: business_settings pk_business_settings; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_settings
    ADD CONSTRAINT pk_business_settings PRIMARY KEY (business_id);


--
-- Name: businesses pk_businesses; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.businesses
    ADD CONSTRAINT pk_businesses PRIMARY KEY (id);


--
-- Name: conversation_messages pk_conversation_messages; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_messages
    ADD CONSTRAINT pk_conversation_messages PRIMARY KEY (id);


--
-- Name: conversation_state pk_conversation_state; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_state
    ADD CONSTRAINT pk_conversation_state PRIMARY KEY (conversation_id);


--
-- Name: conversations pk_conversations; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT pk_conversations PRIMARY KEY (id);


--
-- Name: customers pk_customers; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT pk_customers PRIMARY KEY (id);


--
-- Name: business_auth_codes uq_business_auth_codes_hash; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_auth_codes
    ADD CONSTRAINT uq_business_auth_codes_hash UNIQUE (code_hash);


--
-- Name: business_sessions uq_business_sessions_hash; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_sessions
    ADD CONSTRAINT uq_business_sessions_hash UNIQUE (token_hash);


--
-- Name: businesses uq_businesses_email; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.businesses
    ADD CONSTRAINT uq_businesses_email UNIQUE (email);


--
-- Name: conversations uq_conversations_business_customer_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT uq_conversations_business_customer_id UNIQUE (business_id, customer_id, id);


--
-- Name: conversations uq_conversations_business_id_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT uq_conversations_business_id_id UNIQUE (business_id, id);


--
-- Name: customers uq_customers_business_id_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT uq_customers_business_id_id UNIQUE (business_id, id);


--
-- Name: idx_appointments_business_schedule; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_appointments_business_schedule ON public.appointments USING btree (business_id, scheduled_start);


--
-- Name: idx_appointments_conversation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_appointments_conversation ON public.appointments USING btree (business_id, conversation_id) WHERE (conversation_id IS NOT NULL);


--
-- Name: idx_appointments_customer_schedule; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_appointments_customer_schedule ON public.appointments USING btree (business_id, customer_id, scheduled_start DESC);


--
-- Name: idx_appointments_status_schedule; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_appointments_status_schedule ON public.appointments USING btree (business_id, status, scheduled_start);


--
-- Name: idx_business_auth_codes_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_business_auth_codes_active ON public.business_auth_codes USING btree (business_id, code_type, expires_at DESC) WHERE (consumed_at IS NULL);


--
-- Name: idx_business_sessions_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_business_sessions_active ON public.business_sessions USING btree (business_id, expires_at DESC) WHERE (revoked_at IS NULL);


--
-- Name: idx_businesses_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_businesses_status ON public.businesses USING btree (status, id);


--
-- Name: idx_conversation_messages_timeline; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conversation_messages_timeline ON public.conversation_messages USING btree (business_id, conversation_id, sent_at, id);


--
-- Name: idx_conversation_state_business_updated; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conversation_state_business_updated ON public.conversation_state USING btree (business_id, updated_at DESC);


--
-- Name: idx_conversations_anonymous_last_message; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conversations_anonymous_last_message ON public.conversations USING btree (business_id, last_message_at DESC NULLS LAST) WHERE (customer_id IS NULL);


--
-- Name: idx_conversations_customer_last_message; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conversations_customer_last_message ON public.conversations USING btree (business_id, customer_id, last_message_at DESC NULLS LAST) WHERE (customer_id IS NOT NULL);


--
-- Name: idx_conversations_status_last_message; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conversations_status_last_message ON public.conversations USING btree (business_id, status, last_message_at DESC NULLS LAST);


--
-- Name: idx_customers_business_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_customers_business_created ON public.customers USING btree (business_id, created_at DESC);


--
-- Name: idx_customers_business_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_customers_business_email ON public.customers USING btree (business_id, lower(email)) WHERE (email IS NOT NULL);


--
-- Name: idx_customers_business_phone; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_customers_business_phone ON public.customers USING btree (business_id, phone) WHERE (phone IS NOT NULL);


--
-- Name: uq_conversation_messages_external_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_conversation_messages_external_id ON public.conversation_messages USING btree (business_id, conversation_id, external_message_id) WHERE (external_message_id IS NOT NULL);


--
-- Name: uq_conversations_external_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_conversations_external_id ON public.conversations USING btree (business_id, external_conversation_id) WHERE (external_conversation_id IS NOT NULL);


--
-- Name: appointments trg_appointments_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_appointments_set_updated_at BEFORE UPDATE ON public.appointments FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: business_hours trg_business_hours_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_business_hours_set_updated_at BEFORE UPDATE ON public.business_hours FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: business_schedule_overrides trg_business_schedule_overrides_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_business_schedule_overrides_set_updated_at BEFORE UPDATE ON public.business_schedule_overrides FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: business_settings trg_business_settings_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_business_settings_set_updated_at BEFORE UPDATE ON public.business_settings FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: businesses trg_businesses_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_businesses_set_updated_at BEFORE UPDATE ON public.businesses FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: businesses trg_businesses_validate_timezone; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_businesses_validate_timezone BEFORE INSERT OR UPDATE OF timezone ON public.businesses FOR EACH ROW EXECUTE FUNCTION public.validate_business_timezone();


--
-- Name: conversation_messages trg_conversation_messages_advance_last_message; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_conversation_messages_advance_last_message AFTER INSERT ON public.conversation_messages FOR EACH ROW EXECUTE FUNCTION public.advance_conversation_last_message_at();


--
-- Name: conversation_state trg_conversation_state_cardinality; Type: TRIGGER; Schema: public; Owner: -
--

CREATE CONSTRAINT TRIGGER trg_conversation_state_cardinality AFTER INSERT OR DELETE OR UPDATE ON public.conversation_state DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.enforce_conversation_state_cardinality();


--
-- Name: conversation_state trg_conversation_state_require_open; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_conversation_state_require_open BEFORE INSERT OR DELETE OR UPDATE ON public.conversation_state FOR EACH ROW EXECUTE FUNCTION public.enforce_open_conversation_state();


--
-- Name: conversation_state trg_conversation_state_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_conversation_state_set_updated_at BEFORE UPDATE ON public.conversation_state FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: conversations trg_conversations_remove_state_on_close; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_conversations_remove_state_on_close AFTER UPDATE OF status ON public.conversations FOR EACH ROW EXECUTE FUNCTION public.remove_state_when_conversation_closes();


--
-- Name: conversations trg_conversations_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_conversations_set_updated_at BEFORE UPDATE ON public.conversations FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: conversations trg_conversations_state_cardinality; Type: TRIGGER; Schema: public; Owner: -
--

CREATE CONSTRAINT TRIGGER trg_conversations_state_cardinality AFTER INSERT OR DELETE OR UPDATE ON public.conversations DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.enforce_conversation_state_cardinality();


--
-- Name: customers trg_customers_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_customers_set_updated_at BEFORE UPDATE ON public.customers FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: appointments fk_appointments_business; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT fk_appointments_business FOREIGN KEY (business_id) REFERENCES public.businesses(id) ON DELETE CASCADE;


--
-- Name: appointments fk_appointments_conversation; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT fk_appointments_conversation FOREIGN KEY (business_id, customer_id, conversation_id) REFERENCES public.conversations(business_id, customer_id, id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: appointments fk_appointments_customer; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT fk_appointments_customer FOREIGN KEY (business_id, customer_id) REFERENCES public.customers(business_id, id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: business_auth_codes fk_business_auth_codes_business; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_auth_codes
    ADD CONSTRAINT fk_business_auth_codes_business FOREIGN KEY (business_id) REFERENCES public.businesses(id) ON DELETE CASCADE;


--
-- Name: business_hours fk_business_hours_business; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_hours
    ADD CONSTRAINT fk_business_hours_business FOREIGN KEY (business_id) REFERENCES public.businesses(id) ON DELETE CASCADE;


--
-- Name: business_schedule_overrides fk_business_schedule_overrides_business; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_schedule_overrides
    ADD CONSTRAINT fk_business_schedule_overrides_business FOREIGN KEY (business_id) REFERENCES public.businesses(id) ON DELETE CASCADE;


--
-- Name: business_sessions fk_business_sessions_business; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_sessions
    ADD CONSTRAINT fk_business_sessions_business FOREIGN KEY (business_id) REFERENCES public.businesses(id) ON DELETE CASCADE;


--
-- Name: business_settings fk_business_settings_business; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_settings
    ADD CONSTRAINT fk_business_settings_business FOREIGN KEY (business_id) REFERENCES public.businesses(id) ON DELETE CASCADE;


--
-- Name: conversation_messages fk_conversation_messages_conversation; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_messages
    ADD CONSTRAINT fk_conversation_messages_conversation FOREIGN KEY (business_id, conversation_id) REFERENCES public.conversations(business_id, id) ON DELETE CASCADE;


--
-- Name: conversation_state fk_conversation_state_conversation; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_state
    ADD CONSTRAINT fk_conversation_state_conversation FOREIGN KEY (business_id, conversation_id) REFERENCES public.conversations(business_id, id) ON DELETE CASCADE;


--
-- Name: conversations fk_conversations_business; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT fk_conversations_business FOREIGN KEY (business_id) REFERENCES public.businesses(id) ON DELETE CASCADE;


--
-- Name: conversations fk_conversations_customer; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT fk_conversations_customer FOREIGN KEY (business_id, customer_id) REFERENCES public.customers(business_id, id) ON DELETE SET NULL (customer_id);


--
-- Name: customers fk_customers_business; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT fk_customers_business FOREIGN KEY (business_id) REFERENCES public.businesses(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict aUoxsmhF5jEPIIhqX3DoWlF4CQQrffsONpsQbRozgMdKhugzDJYkYEVkvIvtrah

